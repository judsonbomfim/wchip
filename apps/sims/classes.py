import base64
from datetime import datetime
import hashlib
import http.client
import io
import json
import logging
import time
from urllib.parse import urlparse
from urllib.request import urlopen
from venv import logger
from django.conf import settings
from django.core.cache import cache
from django.core.files.base import ContentFile
import cv2
import numpy as np
import pytz
import qrcode
import requests

from apps.sims.models import Sims

HTTP_TIMEOUT = 10

def _cm_subscription_key(data_dict):
    """Child order (subscriptionKey) do pacote ativo na resposta CMI."""
    bundles = data_dict.get("userDataBundles") or []
    if isinstance(bundles, dict):
        bundles = [bundles]
    if not isinstance(bundles, list):
        return None

    activated = []
    others = []
    for bundle in bundles:
        if not isinstance(bundle, dict):
            continue
        key = bundle.get("subscriptionKey")
        if not key:
            continue
        if str(bundle.get("status")) == "3":
            activated.append(key)
        else:
            others.append(key)
    return (activated or others or [None])[0]


def _cm_quota_node(data_dict):
    if not isinstance(data_dict, dict):
        return {}
    if data_dict.get("subscriberQuota") or data_dict.get("historyQuota"):
        return data_dict
    quota_list = data_dict.get("quotaList")
    if isinstance(quota_list, list) and quota_list:
        first = quota_list[0]
        return first if isinstance(first, dict) else {}
    if isinstance(quota_list, dict):
        return quota_list
    return data_dict


def _cm_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _cm_daily_quota(data_dict, date_today):
    quota = _cm_quota_node(data_dict)
    subscriber = quota.get("subscriberQuota") or {}
    if not isinstance(subscriber, dict):
        subscriber = {}

    used_today = _cm_float(subscriber.get("qtaconsumption"))
    if used_today is not None:
        return used_today

    history_quota = quota.get("historyQuota") or []
    if isinstance(history_quota, dict):
        history_quota = [history_quota]
    today_total = [
        entry for entry in history_quota
        if isinstance(entry, dict)
        and str(entry.get("time")) == date_today
        and not entry.get("appName")
    ]
    if today_total:
        try:
            return sum(float(entry["qtaconsumption"]) for entry in today_total)
        except (TypeError, ValueError, KeyError):
            pass
    return 0


def _cm_quota_payload(api_token, iccid, date_today, child_order_id=None):
    body = {
        "accessToken": api_token,
        "iccid": iccid,
        "beginTime": date_today,
        "endTime": date_today,
        "ext": {"todayFlow": "2"},
    }
    if child_order_id:
        body["childOrderId"] = child_order_id
    return json.dumps(body)



class RateLimitExceeded(Exception):
    """BICS/Telcon retornou HTTP 429 ou mensagem de rate limit."""


class OperatorSelect():
    @staticmethod
    def opSelSim():
        # Plano / Operadora
        operSelSim = {
            '4769': 'AR',
            '4768': 'AR',
            '4763': 'AR',
            '4752': 'TC',
            '4740': 'AR',
            '4735': 'AR',
            '4718': 'AR',
            '3734': 'TC',
            '3564': 'TC',
            '981': 'TC',
            '980': 'CM',
            '976': 'AR',
            '977': 'TM', #
            '975': 'CM', 
            '974': 'TC', #
            '971': 'TC', 
            '001': 'TM', 
        } 
        return operSelSim

    def opSelESim():
        # Plano / Operadora
        operSelESim = {
            '4769': 'AR',
            '4768': 'AR',
            '4763': 'AR',
            '4752': 'TC',
            '4740': 'AR',
            '4735': 'AR',
            '4718': 'AR',
            '3734': 'AR', #
            '3564': 'TC', 
            '981': 'AR', #
            '980': 'CM',
            '976': 'AR',
            '977': 'VR', #
            '975': 'CM', 
            '4816': 'AR', #
            '971': 'TC', 
            '001': 'TM', 
        } 
        return operSelESim

class ApiTC:
    # Default BICS = 2 TPS por conta; 1 req/s deixa margem para outras tasks
    RATE_MIN_INTERVAL = 1.0
    RATE_RETRY_WAIT = 2.0

    @staticmethod
    def is_rate_limit_message(value):
        return 'rate limit' in str(value or '').lower()

    @staticmethod
    def throttle(min_interval=None):
        """Espaça chamadas à API TC no nível da conta (cache compartilhado)."""
        interval = ApiTC.RATE_MIN_INTERVAL if min_interval is None else min_interval
        last_key = 'api_tc_last_request'
        lock_key = 'api_tc_throttle_lock'

        for _ in range(100):
            now = time.time()
            last = cache.get(last_key)
            if last is not None:
                wait = interval - (now - float(last))
                if wait > 0:
                    time.sleep(wait)
                    continue

            if cache.add(lock_key, '1', timeout=5):
                try:
                    now = time.time()
                    last = cache.get(last_key)
                    if last is not None:
                        wait = interval - (now - float(last))
                        if wait > 0:
                            time.sleep(wait)
                            now = time.time()
                    cache.set(last_key, str(now), timeout=120)
                finally:
                    cache.delete(lock_key)
                return

            time.sleep(0.05)

        time.sleep(interval)

    @staticmethod
    def _raise_if_rate_limited(status, body, context=''):
        text = body.decode('utf-8', errors='replace') if isinstance(body, (bytes, bytearray)) else str(body or '')
        if status == 429 or ApiTC.is_rate_limit_message(text):
            raise RateLimitExceeded(
                f'API rate limit exceeded{f" em {context}" if context else ""}'
            )

    # Get tokem de acesso a API
    @staticmethod
    def get_token():
        # Verificar token
        token_api = cache.get('api_tc_token')
        if token_api:
            return token_api

        payload_token = json.dumps({
            "username": settings.APITC_USERNAME,
            "password": settings.APITC_PASSWORD
        })
        
        headers_token = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }
        host = settings.APITC_HTTPCONN
        if not host or host == 'None':
            raise ValueError('APITC_HTTPCONN não configurado')

        ApiTC.throttle()
        conn = http.client.HTTPSConnection(host, timeout=30)
        try:
            conn.request("POST", "/api/login", payload_token, headers_token)
            res_token = conn.getresponse()
            body = res_token.read()
            status = res_token.status
        finally:
            conn.close()

        ApiTC._raise_if_rate_limited(status, body, context='login')

        if not body:
            raise ValueError(
                f'Login TC retornou corpo vazio (HTTP {status}) em {host}/api/login'
            )

        try:
            data_token = json.loads(body)
        except json.JSONDecodeError as e:
            preview = body[:300].decode('utf-8', errors='replace')
            raise ValueError(
                f'Login TC não retornou JSON (HTTP {status}): {preview}'
            ) from e

        token_api = data_token.get("AccessToken")
        if not token_api:
            raise ValueError(
                f'Login TC sem AccessToken (HTTP {status}): {data_token}'
            )

        cache.set('api_tc_token', token_api, timeout=540)
        return token_api


    # Set headers
    @staticmethod    
    def get_headers(token_api, cookie=None):
        headers = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
            'X-Authorization': f'Bearer {token_api}'
        }
        if cookie is None:
            headers['Cookie'] = 'Encrypt_cookies=rd20o00000000000000000000ffff0af30e15o12021'
        print(">>>>>>>>>>>>>>>>>>> get_headers finalizado")
        return headers


    # Get EndPointID / Status
    @staticmethod
    def get_iccid(iccid, headers):
        payload_endpointId = ''
        ApiTC.throttle()
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        try:
            conn.request(
                "GET", f"/api/fetchSIM?iccid={iccid}", payload_endpointId, headers)
            res_endpointId = conn.getresponse()
            status = res_endpointId.status
            body = res_endpointId.read()
        finally:
            conn.close()

        ApiTC._raise_if_rate_limited(status, body, context=f'fetchSIM/{iccid}')

        try:
            data_endpointId = json.loads(body)
        except json.JSONDecodeError as e:
            preview = body[:300].decode('utf-8', errors='replace')
            raise ValueError(
                f'fetchSIM não retornou JSON (HTTP {status}): {preview}'
            ) from e

        response = data_endpointId.get("Response") or {}
        result_code = str(response.get("resultCode", "1"))
        result_param = response.get("resultParam") or {}
        result_description = result_param.get(
            "resultDescription", data_endpointId
        )

        if ApiTC.is_rate_limit_message(result_description):
            raise RateLimitExceeded(
                f'API rate limit exceeded em fetchSIM/{iccid}'
            )

        # responseParam é opcional na API BICS; só existe em sucesso
        if result_code != "0":
            raise ValueError(
                f'fetchSIM falhou para ICCID {iccid}: {result_description}'
            )

        rows = (response.get("responseParam") or {}).get("rows") or []
        if not rows:
            raise ValueError(
                f'fetchSIM sem SIM para ICCID {iccid}: {result_description}'
            )

        simStatus = rows[0]['simStatus']
        endpointId = rows[0]['endPointId']
        return endpointId, simStatus

    @staticmethod
    def endpoint_lifecycle_change(endpoint_id, headers, life_cycle='S', reason='1'):
        payload = json.dumps({
            "Request": {
                "endPointId": f"{endpoint_id}",
                "requestParam": {
                    "lifeCycle": life_cycle,
                    "reason": reason,
                }
            }
        })
        ApiTC.throttle()
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        try:
            conn.request("POST", "/api/EndPointLifeCycleChange", payload, headers)
            res = conn.getresponse()
            status = res.status
            body = res.read()
        finally:
            conn.close()

        ApiTC._raise_if_rate_limited(
            status, body, context=f'EndPointLifeCycleChange/{endpoint_id}'
        )

        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            preview = body[:300].decode('utf-8', errors='replace')
            raise ValueError(
                f'EndPointLifeCycleChange não retornou JSON (HTTP {status}): {preview}'
            ) from e

        response = data.get("Response") or {}
        result_param = response.get("resultParam") or {}
        result_description = result_param.get("resultDescription", data)
        if ApiTC.is_rate_limit_message(result_description):
            raise RateLimitExceeded(
                f'API rate limit exceeded em EndPointLifeCycleChange/{endpoint_id}'
            )

        return data


    # Pl0an Change
    @staticmethod
    def planChange(endpointId,headers,day,dataDay,product):
        time.sleep(0.5)        
        planList = {}

        planList = {
            # Europa Controle
            "971": [
                ["5", "500mb-dia", "870497"],
                ["5", "1gb-dia", "876051"],
                ["5", "2gb-dia", "922296"],
                ["6", "500mb-dia", "922478"],
                ["6", "1gb-dia", "922480"],
                ["6", "2gb-dia", "922484"],
                ["7", "500mb-dia", "872120"],
                ["7", "1gb-dia", "872386"],
                ["7", "2gb-dia", "880077"],
                ["8", "500mb-dia", "875083"],
                ["8", "1gb-dia", "922302"],
                ["8", "2gb-dia", "890275"],
                ["9", "500mb-dia", "922643"],
                ["9", "1gb-dia", "922645"],
                ["9", "2gb-dia", "922647"],
                ["10", "500mb-dia", "872389"],
                ["10", "1gb-dia", "875085"],
                ["10", "2gb-dia", "922661"],
                ["11", "500mb-dia", "922666"],
                ["11", "1gb-dia", "922696"],
                ["11", "2gb-dia", "922697"],
                ["12", "500mb-dia", "873326"],
                ["12", "1gb-dia", "871951"],
                ["12", "2gb-dia", "922727"],
                ["13", "500mb-dia", "878385"],
                ["13", "1gb-dia", "882368"],
                ["13", "2gb-dia", "878387"],
                ["14", "500mb-dia", "922730"],
                ["14", "1gb-dia", "922732"],
                ["14", "2gb-dia", "922733"],
                ["15", "500mb-dia", "871110"],
                ["15", "1gb-dia", "872724"],
                ["15", "2gb-dia", "878388"],
                ["16", "500mb-dia", "922735"],
                ["16", "1gb-dia", "889666"],
                ["16", "2gb-dia", "922736"],
                ["17", "500mb-dia", "922739"],
                ["17", "1gb-dia", "922743"],
                ["17", "2gb-dia", "923572"],
                ["18", "500mb-dia", "871671"],
                ["18", "1gb-dia", "922935"],
                ["18", "2gb-dia", "923574"],
                ["19", "500mb-dia", "922939"],
                ["19", "1gb-dia", "923577"],
                ["19", "2gb-dia", "923579"],
                ["20", "500mb-dia", "871947"],
                ["20", "1gb-dia", "878389"],
                ["20", "2gb-dia", "871948"],
                ["21", "500mb-dia", "877341"],
                ["21", "1gb-dia", "876594"],
                ["21", "2gb-dia", "923583"],
                ["22", "500mb-dia", "872932"],
                ["22", "1gb-dia", "923584"],
                ["22", "2gb-dia", "923587"],
                ["23", "500mb-dia", "923588"],
                ["23", "1gb-dia", "923590"],
                ["23", "2gb-dia", "923591"],
                ["24", "500mb-dia", "923592"],
                ["24", "1gb-dia", "923593"],
                ["24", "2gb-dia", "923594"],
                ["25", "500mb-dia", "923610"],
                ["25", "1gb-dia", "923612"],
                ["25", "2gb-dia", "923613"],
                ["26", "500mb-dia", "923615"],
                ["26", "1gb-dia", "923618"],
                ["26", "2gb-dia", "923620"],
                ["27", "500mb-dia", "923775"],
                ["27", "1gb-dia", "923776"],
                ["27", "2gb-dia", "923778"],
                ["28", "500mb-dia", "923779"],
                ["28", "1gb-dia", "923782"],
                ["28", "2gb-dia", "923787"],
                ["29", "500mb-dia", "923788"],
                ["29", "1gb-dia", "923791"],
                ["29", "2gb-dia", "923793"],
                ["30", "500mb-dia", "876593"],
                ["30", "1gb-dia", "923597"],
                ["30", "2gb-dia", "923599"],
            ],
            # Europa Flex (F)
            "974": [
                ["7", "1gb-periodo", "870915"],
                ["15", "2gb-periodo", "870918"],
                ["30", "3gb-periodo", "941348"],
                ["30", "5gb-periodo", "870710"],
                ["30", "10gb-periodo", "941349"],
                ["30", "20gb-periodo", "871952"],
            ],
            # A. Norte Flex
            "981": [
                ["7", "1gb-periodo", "925965"],
                ["15", "2gb-periodo", "925970"],
                ["30", "3gb-periodo", "925972"],
                ["30", "5gb-periodo", "925973"],
                ["30", "10gb-periodo", "925974"],
            ],
            # A. Sul Controle
            "3564": [
                ["5", "500mb-dia", "872723"],
                ["5", "1gb-dia", "870905"],
                ["5", "2gb-dia", "922750"],
                ["6", "500mb-dia", "872388"],
                ["6", "1gb-dia", "876050"],
                ["6", "2gb-dia", "923808"],
                ["7", "500mb-dia", "871593"],
                ["7", "1gb-dia", "870913"],
                ["7", "2gb-dia", "923813"],
                ["8", "500mb-dia", "871665"],
                ["8", "1gb-dia", "871664"],
                ["8", "2gb-dia", "871667"],
                ["9", "500mb-dia", "871670"],
                ["9", "1gb-dia", "878383"],
                ["9", "2gb-dia", "923816"],
                ["10", "500mb-dia", "870914"],
                ["10", "1gb-dia", "876550"],
                ["10", "2gb-dia", "923818"],
                ["11", "500mb-dia", "924554"],
                ["11", "1gb-dia", "924556"],
                ["11", "2gb-dia", "924558"],
                ["12", "500mb-dia", "924564"],
                ["12", "1gb-dia", "878376"],
                ["12", "2gb-dia", "924566"],
                ["13", "500mb-dia", "924569"],
                ["13", "1gb-dia", "924568"],
                ["13", "2gb-dia", "878382"],
                ["14", "500mb-dia", "871380"],
                ["14", "1gb-dia", "925165"],
                ["14", "2gb-dia", "925166"],
                ["15", "500mb-dia", "892468"],
                ["15", "1gb-dia", "922340"],
                ["15", "2gb-dia", "925352"],
                ["16", "500mb-dia", "925353"],
                ["16", "1gb-dia", "925354"],
                ["16", "2gb-dia", "925357"],
                ["17", "500mb-dia", "925358"],
                ["17", "1gb-dia", "925361"],
                ["17", "2gb-dia", "925373"],
                ["18", "500mb-dia", "889665"],
                ["18", "1gb-dia", "925375"],
                ["18", "2gb-dia", "925377"],
                ["19", "500mb-dia", "925378"],
                ["19", "1gb-dia", "925379"],
                ["19", "2gb-dia", "925381"],
                ["20", "500mb-dia", "892469"],
                ["20", "1gb-dia", "925403"],
                ["20", "2gb-dia", "925405"],
                ["21", "500mb-dia", "925406"],
                ["21", "1gb-dia", "925407"],
                ["21", "2gb-dia", "925413"],
                ["22", "500mb-dia", "925603"],
                ["22", "1gb-dia", "925605"],
                ["22", "2gb-dia", "925606"],
                ["23", "500mb-dia", "925610"],
                ["23", "1gb-dia", "925612"],
                ["23", "2gb-dia", "925617"],
                ["24", "500mb-dia", "925631"],
                ["24", "1gb-dia", "925633"],
                ["24", "2gb-dia", "925639"],
                ["25", "500mb-dia", "925640"],
                ["25", "1gb-dia", "925641"],
                ["25", "2gb-dia", "925648"],
                ["26", "500mb-dia", "925652"],
                ["26", "1gb-dia", "925654"],
                ["26", "2gb-dia", "925656"],
                ["27", "500mb-dia", "925658"],
                ["27", "1gb-dia", "925663"],
                ["27", "2gb-dia", "925665"],
                ["28", "500mb-dia", "925678"],
                ["28", "1gb-dia", "925680"],
                ["28", "2gb-dia", "925681"],
                ["29", "500mb-dia", "925685"],
                ["29", "1gb-dia", "925686"],
                ["29", "2gb-dia", "925687"],
                ["30", "500mb-dia", "890220"],
                ["30", "1gb-dia", "925693"],
                ["30", "2gb-dia", "925694"],
            ],
            # A. Sul Flex (F)
            "3734": [
                ["7", "1gb-periodo", "870910"],
                ["15", "2gb-periodo", "870705"],
                ["30", "3gb-periodo", "871388"],
                ["30", "10gb-periodo", "870908"],
                ["30", "20gb-periodo", "941347"],
            ],
            # Cuba Flex
            "4752": [
                ["7", "1gb-periodo", "927214"],
                ["15", "2gb-periodo", "927215"],
                ["30", "3gb-periodo", "927216"],
                ["30", "5gb-periodo", "927217"],
            ],          
        }
          
        # Verificar Planos    
        try:
            day = str(day)
            dataDay = str(dataDay).strip().lower()
            product = str(product).strip()
            end_point_id = str(endpointId).strip() if endpointId is not None else ''

            plan_list = next((item[2] for item in planList.get(product, []) if item[0] == day and item[1] == dataDay), None)

            if not end_point_id or not plan_list:
                logger.error(
                    f">>>>>>>>>>>>>>>>>>> Parâmetros obrigatórios ausentes para SubscribeAddon: endPointId='{end_point_id}', planId='{plan_list}', day='{day}', dataDay='{dataDay}', product='{product}'"
                )
                return 0

            payload = json.dumps({
                "Request": {
                    "requestParam": {
                        "endPointId": end_point_id,
                        "planId": str(plan_list)
                    }
                }
            })
            conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
            conn.request("POST", "/api/SubscribeAddon", payload, headers)
            res_plan = conn.getresponse()
            data_plan = res_plan.read()
            conn.close()
        except KeyError:
            data_plan = 0
            logger.error(f">>>>>>>>>>>>>>>>>>> Plano não encontrado para os parâmetros: day={day}, dataDay={dataDay}, product={product}")
        return data_plan
    
    @staticmethod
    def mobileData(iccid):
        # Gerar token de acesso a API
        token_api = ApiTC.get_token()
        payload = ''
        headers = ApiTC.get_headers(token_api)
        tz = pytz.timezone(settings.TIME_ZONE)
        dateToday = datetime.now(tz).strftime("%Y%m%d")
        # Obter EndPointID
        endPointId = ApiTC.get_iccid(iccid, headers)
        # Obter dados de uso
        time.sleep(0.5)
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)    
        conn.request("GET", f"/api/GetStatistics?endPointId={endPointId[0]}&from_date={dateToday}&to_date={dateToday}", payload, headers)
        res = conn.getresponse()
        data_endpointId = json.loads(res.read())
        try:
            if data_endpointId["Response"]["responseParam"]["dataUsage"][0]['totalVolume'] is None:
                mobile_data = 0
            else:
                mobile_data = data_endpointId["Response"]["responseParam"]["dataUsage"][0]['totalVolume']
        except IndexError:
            # Caso não haja dados de uso, retornar 0
            mobile_data = 0
        except KeyError:
            # Caso a chave não exista, retornar 0
            mobile_data = 0
        
        conn.close()
        return mobile_data


class ApiCM:
        
    app_key = settings.APICM_KEY
    app_secret = settings.APICM_SECRET

    @staticmethod
    def generate_password_digest(app_secret):
        nonce = str(int(time.time() * 1000))
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        digest = base64.b64encode(hashlib.sha256((nonce + created + app_secret).encode('utf-8')).digest()).decode('utf-8')
        return nonce, created, digest
    
    @staticmethod
    def get_token():
        
        api_token = cache.get('api_cm_token')
        if api_token:
            return api_token
        
        print(">>>>>>>>>>>>>>>>>>> Obtendo token de acesso para API CM...")
        # URL do endpoint
        url_api = f'{settings.APICM_URL}/aep/APP_getAccessToken_SBO/v1'
        parsed_url = urlparse(url_api)

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCM.generate_password_digest(ApiCM.app_secret)

        # Corpo da requisição
        payload = json.dumps({
            "id": ApiCM.app_key,
            "type": "106",
        })

        # Cabeçalhos da requisição
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCM.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"',
        }

        conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
        conn.request("POST", parsed_url.path, payload, headers)
        res = conn.getresponse()
        data = res.read()
                
        # Verificar status da requisição        
        if res.status != 200:
            result_token = 'error'
        else:
            try:
                if data:
                    data_dict = json.loads(data)
                    result_token = data_dict.get('accessToken')
                    if result_token:
                        cache.set('api_cm_token', result_token, timeout=540)
                else:
                    result_token = 'error: resposta vazia'
            except json.JSONDecodeError:
                result_token = 'error: JSON malformado'

        conn.close()
            
        return result_token
    

    @staticmethod
    def childOrderId(iccid):

        print(f">>>>>>>>>>>>>>>>>>> Acessando childOrderId {iccid}")

        url_api = f'{settings.APICM_URL}/aep/APP_getSubedUserDataBundle_SBO/v1'
        parsed_url = urlparse(url_api)
        api_token = ApiCM.get_token()
        
        # Verificar se token foi obtido com sucesso
        if api_token == 'error' or not api_token:
            print(f">>>>>>>>>>>>>>>>>>> Erro ao obter token de acesso para API CM")
            return 0

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCM.generate_password_digest(ApiCM.app_secret)

        # Cabeçalhos da requisição
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCM.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"'
        }

        # Corpo da requisição
        payload = json.dumps({
            "accessToken": api_token,
            "iccid": iccid,
            "language": 2,
        })

        # Fazer a requisição POST com tempo limite
        try:
            conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=100)
            conn.request("POST", parsed_url.path, payload, headers)
            res = conn.getresponse()

            # Verificar o status da resposta               
            try:
                data = res.read()
                data_dict = json.loads(data)
                orderId = data_dict["userDataBundles"][0]["subscriptionKey"]
                return orderId
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                return 0
                
        except Exception as e:
            return 0
        finally:
            if 'conn' in locals():
                conn.close()
    
    def selPlan(day, dataDay, product):
        
        planList = {
            # Mundo Controle
            "975": [
                ["5", "500mb-dia", "D181030042539_227624"],
                ["5", "1gb-dia", "D2205171902194598628"],
                ["5", "2gb-dia", "D2206301059342263262"],
                ["6", "500mb-dia", "D181030043319_227719"],
                ["6", "1gb-dia", "D2205171902519779100"],
                ["6", "2gb-dia", "D2206301100122278918"],
                ["7", "500mb-dia", "D181030043319_227719"],
                ["7", "1gb-dia", "D2205171902519779100"],
                ["7", "2gb-dia", "D2206301100122278918"],
                ["8", "500mb-dia", "D181030044052_227812"],
                ["8", "1gb-dia", "D2205171903285254520"],
                ["8", "2gb-dia", "D2206301100537072952"],
                ["9", "500mb-dia", "D181030044052_227812"],
                ["9", "1gb-dia", "D2205171903285254520"],
                ["9", "2gb-dia", "D2206301100537072952"],
                ["10", "500mb-dia", "D181030044052_227812"],
                ["10", "1gb-dia", "D2205171903285254520"],
                ["10", "2gb-dia", "D2206301100537072952"],
                ["11", "500mb-dia", "D181030060952_227953"],
                ["11", "1gb-dia", "D2205171904079201878"],
                ["11", "2gb-dia", "D2206301101255910272"],
                ["12", "500mb-dia", "D181030060952_227953"],
                ["12", "1gb-dia", "D2205171904079201878"],
                ["12", "2gb-dia", "D2206301101255910272"],
                ["13", "500mb-dia", "D181030060952_227953"],
                ["13", "1gb-dia", "D2205171904079201878"],
                ["13", "2gb-dia", "D2206301101255910272"],
                ["14", "500mb-dia", "D181030060952_227953"],
                ["14", "1gb-dia", "D2205171904079201878"],
                ["14", "2gb-dia", "D2206301101255910272"],
                ["15", "500mb-dia", "D181030060952_227953"],
                ["15", "1gb-dia", "D2205171904079201878"],
                ["15", "2gb-dia", "D2206301101255910272"],
                ["16", "500mb-dia", "D210520111201_567505"],
                ["16", "1gb-dia", "D2205171904426262385"],
                ["16", "2gb-dia", "D2206301102116254489"],
                ["17", "500mb-dia", "D210520111201_567505"],
                ["17", "1gb-dia", "D2205171904426262385"],
                ["17", "2gb-dia", "D2206301102116254489"],
                ["18", "500mb-dia", "D210520111201_567505"],
                ["18", "1gb-dia", "D2205171904426262385"],
                ["18", "2gb-dia", "D2206301102116254489"],
                ["19", "500mb-dia", "D210520111201_567505"],
                ["19", "1gb-dia", "D2205171904426262385"],
                ["19", "2gb-dia", "D2206301102116254489"],
                ["20", "500mb-dia", "D210520111201_567505"],
                ["20", "1gb-dia", "D2205171904426262385"],
                ["20", "2gb-dia", "D2206301102116254489"],
                ["21", "500mb-dia", "D210521020847_567890"],
                ["21", "1gb-dia", "D2205171905123822954"],
                ["21", "2gb-dia", "D2206301102507299017"],
                ["22", "500mb-dia", "D210521020847_567890"],
                ["22", "1gb-dia", "D2205171905123822954"],
                ["22", "2gb-dia", "D2206301102507299017"],
                ["23", "500mb-dia", "D210521020847_567890"],
                ["23", "1gb-dia", "D2205171905123822954"],
                ["23", "2gb-dia", "D2206301102507299017"],
                ["24", "500mb-dia", "D210521020847_567890"],
                ["24", "1gb-dia", "D2205171905123822954"],
                ["24", "2gb-dia", "D2206301102507299017"],
                ["25", "500mb-dia", "D210521020847_567890"],
                ["25", "1gb-dia", "D2205171905123822954"],
                ["25", "2gb-dia", "D2206301102507299017"],
                ["26", "500mb-dia", "D181030062003_228049"],
                ["26", "1gb-dia", "D2205171905428070570"],
                ["26", "2gb-dia", "D2206301103268430586"],
                ["27", "500mb-dia", "D181030062003_228049"],
                ["27", "1gb-dia", "D2205171905428070570"],
                ["27", "2gb-dia", "D2206301103268430586"],
                ["28", "500mb-dia", "D181030062003_228049"],
                ["28", "1gb-dia", "D2205171905428070570"],
                ["28", "2gb-dia", "D2206301103268430586"],
                ["29", "500mb-dia", "D181030062003_228049"],
                ["29", "1gb-dia", "D2205171905428070570"],
                ["29", "2gb-dia", "D2206301103268430586"],
                ["30", "500mb-dia", "D181030062003_228049"],
                ["30", "1gb-dia", "D2205171905428070570"],
                ["30", "2gb-dia", "D2206301103268430586"],
            ],
            # Norte Controle
            "980": [
                ["5", "500mb-dia", "D181029074947_215300"],
                ["5", "1gb-dia", "D2206091118158677818"],
                ["5", "2gb-dia", "D2206291909256195940"],
                ["6", "500mb-dia", "D181029074947_215300"],
                ["6", "1gb-dia", "D2206091118158677818"],
                ["6", "2gb-dia", "D2206291909256195940"],
                ["7", "500mb-dia", "D181029074947_215300"],
                ["7", "1gb-dia", "D2206091118158677818"],
                ["7", "2gb-dia", "D2206291909256195940"],
                ["8", "500mb-dia", "D181029075127_215305"],
                ["8", "1gb-dia", "D2206091118433144508"],
                ["8", "2gb-dia", "D2206291910012200492"],
                ["9", "500mb-dia", "D181029075127_215305"],
                ["9", "1gb-dia", "D2206091118433144508"],
                ["9", "2gb-dia", "D2206291910012200492"],
                ["10", "500mb-dia", "D181029075127_215305"],
                ["10", "1gb-dia", "D2206091118433144508"],
                ["10", "2gb-dia", "D2206291910012200492"],
                ["11", "500mb-dia", "D181029075231_215312"],
                ["11", "1gb-dia", "D2206291906432072367"],
                ["11", "2gb-dia", "D2206291910234719163"],
                ["12", "500mb-dia", "D181029075231_215312"],
                ["12", "1gb-dia", "D2206291906432072367"],
                ["12", "2gb-dia", "D2206291910234719163"],
                ["13", "500mb-dia", "D181029075347_215318"],
                ["13", "1gb-dia", "D2206091119091070123"],
                ["13", "2gb-dia", "D2206291910482445815"],
                ["14", "500mb-dia", "D181029075347_215318"],
                ["14", "1gb-dia", "D2206091119091070123"],
                ["14", "2gb-dia", "D2206291910482445815"],
                ["15", "500mb-dia", "D181029075347_215318"],
                ["15", "1gb-dia", "D2206091119091070123"],
                ["15", "2gb-dia", "D2206291910482445815"],
                ["16", "500mb-dia", "D181029075545_215323"],
                ["16", "1gb-dia", "D2206291907323030471"],
                ["16", "2gb-dia", "D2206291911183379323"],
                ["17", "500mb-dia", "D181029075545_215323"],
                ["17", "1gb-dia", "D2206291907323030471"],
                ["17", "2gb-dia", "D2206291911183379323"],
                ["18", "500mb-dia", "D181029075545_215323"],
                ["18", "1gb-dia", "D2206291907323030471"],
                ["18", "2gb-dia", "D2206291911183379323"],
                ["19", "500mb-dia", "D181029075545_215323"],
                ["19", "1gb-dia", "D2206291907323030471"],
                ["19", "2gb-dia", "D2206291911183379323"],
                ["20", "500mb-dia", "D181029075545_215323"],
                ["20", "1gb-dia", "D2206291907323030471"],
                ["20", "2gb-dia", "D2206291911183379323"],
                ["21", "500mb-dia", "D181029075646_215328"],
                ["21", "1gb-dia", "D2206091119350589636"],
                ["21", "2gb-dia", "D2206291911447523252"],
                ["22", "500mb-dia", "D181029075646_215328"],
                ["22", "1gb-dia", "D2206091119350589636"],
                ["22", "2gb-dia", "D2206291911447523252"],
                ["23", "500mb-dia", "D181029075646_215328"],
                ["23", "1gb-dia", "D2206091119350589636"],
                ["23", "2gb-dia", "D2206291911447523252"],
                ["24", "500mb-dia", "D181029075646_215328"],
                ["24", "1gb-dia", "D2206091119350589636"],
                ["24", "2gb-dia", "D2206291911447523252"],
                ["25", "500mb-dia", "D181029075646_215328"],
                ["25", "1gb-dia", "D2206091119350589636"],
                ["25", "2gb-dia", "D2206291911447523252"],
                ["26", "500mb-dia", "D181029075646_215328"],
                ["26", "1gb-dia", "D2206091119350589636"],
                ["26", "2gb-dia", "D2206291911447523252"],
                ["27", "500mb-dia", "D181029075646_215328"],
                ["27", "1gb-dia", "D2206091119350589636"],
                ["27", "2gb-dia", "D2206291911447523252"],
                ["28", "500mb-dia", "D181029075646_215328"],
                ["28", "1gb-dia", "D2206091119350589636"],
                ["28", "2gb-dia", "D2206291911447523252"],
                ["29", "500mb-dia", "D181029075646_215328"],
                ["29", "1gb-dia", "D2206091119350589636"],
                ["29", "2gb-dia", "D2206291911447523252"],
                ["30", "500mb-dia", "D181029075646_215328"],
                ["30", "1gb-dia", "D2206091119350589636"],
                ["30", "2gb-dia", "D2206291911447523252"],
            ], 
        }
          
        # Verificar Planos    
        try:
            planListSel = next((item[2] for item in planList.get(product, []) if item[0] == day and item[1] == dataDay), None)            
        except KeyError:
            planListSel = 0
        return planListSel
        
            
    @staticmethod
    def mobileData(iccid):
                
        url_api = f'{settings.APICM_URL}/aep/APP_getSubscriberAllQuota_SBO/v1'
        parsed_url = urlparse(url_api)
        api_token = ApiCM.get_token()
        childOrderId = ApiCM.childOrderId(iccid)

        # Verificar se token foi obtido com sucesso
        if api_token == 'error' or not api_token:
            return 0

        # Gerar data atual Pequim
        beijing_tz = pytz.timezone("Asia/Shanghai")
        date_today = datetime.now(beijing_tz).strftime("%Y%m%d")

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCM.generate_password_digest(ApiCM.app_secret)

        # Cabeçalhos da requisição
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCM.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"'
        }

        # Corpo da requisição
        payload = json.dumps({
            "accessToken": api_token,
            "iccid": iccid,
            "childOrderId": childOrderId,
            "ext": {"todayFlow": 2}
        })

        # Fazer a requisição POST com tempo limite
        try:
            conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=100)
            conn.request("POST", parsed_url.path, payload, headers)
            res = conn.getresponse()            
            # Verificar o status da resposta
            data = res.read()
            data_dict = json.loads(data)
            
            try:
                history_quota = data_dict["historyQuota"]
                times_x = [entry for entry in history_quota if entry["time"] == date_today]
                soma_qtaconsumption = sum(float(entry["qtaconsumption"]) for entry in times_x)
                mobile_data = soma_qtaconsumption
                return mobile_data
            except (KeyError, IndexError, TypeError) as e:
                print(f">>>>>>>>>>>>>>>>>>> Erro ao processar dados de uso: {e}")
                return 0
                            
        except Exception as e:
            return 0
        finally:
            if 'conn' in locals():
                conn.close()
        
        # # Resultado
        # print(f">>>>>>>>>>>>>>>>>>> Status da resposta: {data}")
        # return data
        


class ApiCMHK:
    """
    Cliente HTTP para a API da operadora **China Mobile (CMHK)**.

    Usa autenticação por assinatura HMAC-SHA256 com nonce e timestamp.
    As credenciais ``app_key`` e ``app_secret`` são lidas das configurações
    do Django (``settings.APICMHK_KEY`` e ``settings.APICMHK_SECRET``).
    """
        
    app_key = settings.APICMHK_KEY
    app_secret = settings.APICMHK_SECRET
    app_url = settings.APICMHK_URL

    @staticmethod
    def generate_password_digest(app_secret):
        nonce = str(int(time.time() * 1000))
        created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        digest = base64.b64encode(hashlib.sha256((nonce + created + app_secret).encode('utf-8')).digest()).decode('utf-8')
        return nonce, created, digest
    
    @staticmethod
    def get_token():
        
        api_token = cache.get('api_cmhk_token')
        if api_token:
            return api_token
        
        logger.info(">>>>>>>>>>>>>>>>>>> Obtendo token de acesso para API CMHK...")
        # URL do endpoint
        url_api = f'{ApiCMHK.app_url}/aep/APP_getAccessToken_SBO/v1'
        parsed_url = urlparse(url_api)

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCMHK.generate_password_digest(ApiCMHK.app_secret)

        # Corpo da requisição
        payload = json.dumps({
            "id": ApiCMHK.app_key,
            "type": "106",
        })

        # Cabeçalhos da requisição
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCMHK.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"',
        }

        conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
        conn.request("POST", parsed_url.path, payload, headers)
        res = conn.getresponse()
        data = res.read()
                
        # Verificar status da requisição        
        if res.status != 200:
            result_token = 'error'
        else:
            try:
                if data:
                    data_dict = json.loads(data)
                    result_token = data_dict.get('accessToken')
                    if result_token:
                        cache.set('api_cmhk_token', result_token, timeout=540)
                else:
                    result_token = 'error: resposta vazia'
            except json.JSONDecodeError:
                result_token = 'error: JSON malformado'

        conn.close()
            
        return result_token

    @staticmethod
    def childOrderId(iccid):

        logger.info(f">>>>>>>>>>>>>>>>>>> Acessando childOrderId CMHK {iccid}")

        url_api = f'{ApiCMHK.app_url}/aep/APP_getSubedUserDataBundle_SBO/v1'
        parsed_url = urlparse(url_api)
        api_token = ApiCMHK.get_token()
        
        # Verificar se token foi obtido com sucesso
        if api_token == 'error' or not api_token:
            logger.info(f">>>>>>>>>>>>>>>>>>> Erro ao obter token de acesso para API CMHK")
            return None

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCMHK.generate_password_digest(ApiCMHK.app_secret)

        # Cabeçalhos da requisição
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCMHK.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"'
        }

        # Pedido status=1: em uso (spec 3.2.6)
        payload = json.dumps({
            "accessToken": api_token,
            "iccid": iccid,
            "status": "1",
            "language": "2",
        })

        # Fazer a requisição POST com tempo limite
        try:
            conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
            conn.request("POST", parsed_url.path, payload, headers)
            res = conn.getresponse()

            # Verificar o status da resposta               
            try:
                data = res.read()
                data_dict = json.loads(data)
                return _cm_subscription_key(data_dict)
            except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                return None
                
        except Exception as e:
            return None
        finally:
            if 'conn' in locals():
                conn.close()
               
    @staticmethod
    def mobileData(iccid):
                
        url_api = f'{ApiCMHK.app_url}/aep/APP_getSubscriberAllQuota_SBO/v1'
        parsed_url = urlparse(url_api)
        api_token = ApiCMHK.get_token()
        childOrderId = ApiCMHK.childOrderId(iccid)

        if api_token == 'error' or not api_token:
            return 0

        # Gerar data atual Pequim
        beijing_tz = pytz.timezone("Asia/Shanghai")
        date_today = datetime.now(beijing_tz).strftime("%Y%m%d")

        # Gerar PasswordDigest
        nonce, created, password_digest = ApiCMHK.generate_password_digest(ApiCMHK.app_secret)

        # Cabeçalhos da requisição
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{ApiCMHK.app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"'
        }

        payload = _cm_quota_payload(api_token, iccid, date_today, childOrderId)

        # Fazer a requisição POST com tempo limite
        try:
            conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
            conn.request("POST", parsed_url.path, payload, headers)
            res = conn.getresponse()            
            # Verificar o status da resposta
            data = res.read()
            data_dict = json.loads(data)
            
            try:
                return _cm_daily_quota(data_dict, date_today)
            except (KeyError, IndexError, TypeError) as e:
                logger.error(f">>>>>>>>>>>>>>>>>>> Erro ao processar dados de uso CMHK: {e}")
                return 0
                            
        except Exception as e:
            return 0
        finally:
            if 'conn' in locals():
                conn.close()



class ApiAR:
    @staticmethod
    def getToken():
        
        # Verificar token
        token_api = cache.get('api_ar_token')
        if token_api:
            return token_api
        
        url_api = f'{settings.APIAIRALO_URL}/token'

        payload_token = {
            "client_id": settings.APIAIRALO_KEY,
            "client_secret": settings.APIAIRALO_SECRET,
        }

        headers_token = {
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.request("POST", url_api, headers=headers_token, json=payload_token)
            response.raise_for_status()
            response_data = response.json()
            token_api = response_data['data']['access_token']
            cache.set('api_ar_token', token_api, timeout=3600)
            return token_api
        except requests.exceptions.RequestException as e:
            print(f"Erro ao obter token de acesso para API Airalo: {e}")
            token_api = None
            return token_api

    @staticmethod
    def selPlan(day, dataDay, product, paises, voz):
        
        if voz == True:
            planList = {
                # EUA Flex
                "976": [
                    ["7", "1gb-periodo", "change-plus-7days-1gb"],
                    ["15", "2gb-periodo", "change-plus-15days-2gb"],
                    ["30", "3gb-periodo", "change-plus-30days-3gb"],
                    ["30", "5gb-periodo", "change-plus-30days-5gb"],
                    ["30", "10gb-periodo", "change-plus-30days-10gb"],
                    ["30", "20gb-periodo", "change-plus-30days-20gb"],
                ], 
            }
        elif paises == False:
            planList = {
                # Europa Flex (E)
                "4816": [
                    ["7", "1gb-periodo", "eu-connect-in-7days-1gb"],
                    ["15", "2gb-periodo", "eu-connect-in-15days-2gb"],
                    ["30", "3gb-periodo", "eu-connect-in-30days-3gb"],
                    ["30", "5gb-periodo", "eu-connect-in-30days-5gb"],
                    ["30", "10gb-periodo", "eu-connect-in-30days-10gb"],
                    ["30", "20gb-periodo", "eu-connect-in-30days-20gb"],
                ],
                # EUA Flex
                "976": [
                    ["7", "1gb-periodo", "change-in-7days-1gb"],
                    ["15", "2gb-periodo", "change-in-15days-2gb"],
                    ["30", "3gb-periodo", "change-in-30days-3gb"],
                    ["30", "5gb-periodo", "change-in-30days-5gb"],
                    ["30", "10gb-periodo", "change-in-30days-10gb"],
                    ["30", "20gb-periodo", "change-in-30days-20gb"],
                ], 
                # A. Norte Flex
                "981": [
                    ["7", "1gb-periodo", "americanmex-in-7days-1gb"],
                    ["15", "2gb-periodo", "americanmex-in-15days-2gb"],
                    ["30", "3gb-periodo", "americanmex-in-30days-3gb"],
                    ["30", "5gb-periodo", "americanmex-in-30days-5gb"],
                    ["30", "10gb-periodo", "americanmex-in-30days-10gb"],
                    ["30", "20gb-periodo", "americanmex-in-30days-20gb"],
                ],
                # A. Sul Flex
                "3734": [
                    ["7", "1gb-periodo", "latamlink-7days-1gb"],
                    ["15", "2gb-periodo", "latamlink-15days-2gb"],
                    ["30", "3gb-periodo", "latamlink-30days-3gb"],
                    ["30", "5gb-periodo", "latamlink-30days-5gb"],
                    ["30", "10gb-periodo", "latamlink-30days-10gb"],
                    ["30", "20gb-periodo", "latamlink-30days-20gb"],
                ],
                # Caribe Flex
                "4718": [
                    ["7", "1gb-periodo", "island-hopper-in-7days-1gb"],
                    ["15", "2gb-periodo", "island-hopper-in-15days-2gb"],
                    ["30", "3gb-periodo", "island-hopper-in-30days-3gb"],
                    ["30", "5gb-periodo", "island-hopper-in-30days-5gb"],
                    ["30", "10gb-periodo", "island-hopper-in-30days-10gb"],
                    ["30", "20gb-periodo", "island-hopper-in-30days-20gb"],
                ],
                # Oceania Flex
                "4735": [
                    ["7", "1gb-periodo", "oceanlink-in-7days-1gb"],
                    ["15", "2gb-periodo", "oceanlink-in-15days-2gb"],
                    ["30", "3gb-periodo", "oceanlink-in-30days-3gb"],
                    ["30", "5gb-periodo", "oceanlink-in-30days-5gb"],
                    ["30", "10gb-periodo", "oceanlink-in-30days-10gb"],
                    ["30", "20gb-periodo", "oceanlink-in-30days-20gb"],
                ],
                # Japão Flex
                "4740": [
                    ["7", "1gb-periodo", "moshi-moshi-7days-1gb"],
                    ["15", "2gb-periodo", "moshi-moshi-15days-2gb"],
                    ["30", "3gb-periodo", "moshi-moshi-30days-3gb"],
                    ["30", "5gb-periodo", "moshi-moshi-30days-5gb"],
                    ["30", "10gb-periodo", "moshi-moshi-30days-10gb"],
                    ["30", "20gb-periodo", "moshi-moshi-30days-20gb"],
                ],
                # Africa Flex
                "4763": [
                    ["7", "1gb-periodo", "hello-africa-in-7days-1gb"],
                    ["15", "2gb-periodo", "hello-africa-in-15days-2gb"],
                    ["30", "3gb-periodo", "hello-africa-in-30days-3gb"],
                    ["30", "5gb-periodo", "hello-africa-in-30days-5gb"],
                    ["30", "10gb-periodo", "hello-africa-in-30days-10gb"],
                    ["30", "20gb-periodo", "hello-africa-in-30days-20gb"],
                ],
                # Asia Flex
                "4768": [
                    ["7", "1gb-periodo", "asialink-7days-1gb-"],
                    ["15", "2gb-periodo", "asialink-15days-2gb"],
                    ["30", "3gb-periodo", "asialink-30days-3gb-"],
                    ["30", "5gb-periodo", "asialink-30days-5gb-"],
                    ["30", "10gb-periodo", "asialink-30days-10gb-"],
                    ["30", "20gb-periodo", "asialink-30days-20gb-"],
                ],
                # Oriente Flex
                "4769": [
                    ["7", "1gb-periodo", "menalink-7days-1gb"],
                    ["15", "2gb-periodo", "menalink-15days-2gb"],
                    ["30", "3gb-periodo", "menalink-30days-3gb"],
                    ["30", "5gb-periodo", "menalink-30days-5gb"],
                    ["30", "10gb-periodo", "menalink-30days-10gb"],
                    ["30", "20gb-periodo", "menalink-30days-20gb"],
                ],
            }
        elif paises == True:
            planList = {
                # Europa Flex (E)
                "4816": [
                    ["7", "1gb-periodo", "eurolink-7days-1gb"],
                    ["15", "2gb-periodo", "eurolink-15days-2gb"],
                    ["30", "3gb-periodo", "eurolink-30days-3gb"],
                    ["30", "5gb-periodo", "eurolink-30days-5gb"],
                    ["30", "10gb-periodo", "eurolink-30days-10gb"],
                    ["30", "20gb-periodo", "eurolink-30days-20gb"],
                ],
            }
          
          
        # Verificar Planos    
        try:
            planListSel = next((item[2] for item in planList.get(product, []) if item[0] == day and item[1] == dataDay), None)            
        except KeyError:
            planListSel = 0
        return planListSel
    
    @staticmethod
    def addESimAR(iccid, qrcode_url):
        lpa = None
        try:
            qr_url = qrcodeChange.resolve_qr_url(qrcode_url)
            if qr_url:
                lpa = qrcodeChange.read_qr_code(qr_url)
        except Exception as e:
            logging.getLogger('apps.sims').error(
                'Erro ao ler LPA do eSIM Airalo %s: %s', iccid, e, exc_info=True
            )
        add_sim = Sims(
            sim=iccid,
            lpa=lpa,
            link=qrcode_url,
            type_sim='esim',
            operator='AR',
            sim_status='AT',
        )
        add_sim.save()
        return add_sim.id


# eSIM EUA T-Mobile — SIM compartilhado (ICCID placeholder + QR fixo no S3)
TM_ESIM_PADRAO_PK = 465
TM_ESIM_PADRAO_LINK = '/media/890100000000000000F.jpeg'
TM_ESIM_PADRAO_LPA = 'LPA:1$T-MOBILE.GDSB.NET$'


def ensure_tm_esim_padrao_lpa(sim=None):
    """Garante link + LPA no SIM padrão TM usado por todos os eSIM EUA."""
    if sim is None:
        sim = Sims.objects.filter(pk=TM_ESIM_PADRAO_PK).first()
    if sim is None:
        return None

    changed = False
    if not sim.link or str(sim.link).strip() in ('', '-'):
        sim.link = TM_ESIM_PADRAO_LINK
        changed = True

    lpa = (sim.lpa or '').strip()
    if not lpa.startswith('LPA:'):
        new_lpa = None
        try:
            qr_url = qrcodeChange.resolve_qr_url(sim.link)
            if qr_url:
                new_lpa = qrcodeChange.read_qr_code(qr_url)
        except Exception as e:
            logging.getLogger('apps.sims').error(
                'Erro ao ler LPA do SIM padrão TM: %s', e, exc_info=True
            )
        if not new_lpa or not str(new_lpa).startswith('LPA:'):
            new_lpa = TM_ESIM_PADRAO_LPA
        sim.lpa = new_lpa
        changed = True

    if changed:
        sim.save(update_fields=['link', 'lpa'])
    return sim


class qrcodeChange():
    """Utilitarios para leitura e geracao de QR codes de eSIMs."""

    @staticmethod
    def resolve_qr_url(link):
        if not link or str(link).strip() in ('', '-'):
            return None
        link = str(link).strip()
        if link.startswith('http://') or link.startswith('https://'):
            return link
        return f"{settings.URL_CDN}{link}"

    @staticmethod
    def read_qr_code(file_path):
        parsed_url = urlparse(file_path)

        if parsed_url.scheme in ('http', 'https'):
            with urlopen(file_path, timeout=HTTP_TIMEOUT) as response:
                image_bytes = response.read()
            qr_image = cv2.imdecode(np.frombuffer(image_bytes, dtype=np.uint8), cv2.IMREAD_COLOR)
        else:
            qr_image = cv2.imread(file_path)

        if qr_image is None or qr_image.size == 0:
            raise ValueError(f'Nao foi possivel carregar a imagem do QR code: {file_path}')

        qr_detector = cv2.QRCodeDetector()
        data, points, _ = qr_detector.detectAndDecode(qr_image)
        print(f">>>>> Decoded data: {data}")
        if data:
            return data
        return None

    @staticmethod
    def build_qr_file(lpa, sim):
        qr_image = qrcodeChange.convert_qr_code(lpa)
        qr_image = qr_image.get_image() if hasattr(qr_image, 'get_image') else qr_image

        image_buffer = io.BytesIO()
        qr_image.save(image_buffer, format='JPEG')
        return ContentFile(image_buffer.getvalue(), name=f'{sim}.jpg')

    @staticmethod
    def convert_qr_code(data):
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill='black', back_color='white')
        return img

class selectPlanCMHK():
    """
    Seleção de plano para API CMHK.
    """
    @staticmethod
    def selectPlanList(selList):
        plans = {
            # EUA Ilimitado
            "976": "list_cmhk_eua_ilimitado",
            # Europa Controle
            "971": "list_cmhk_europa_controle",
            # América do Sul Controle
            "3734": "list_cmhk_america_sul_flex",
            "3564": "list_cmhk_america_sul_controle",
            # América do Norte Controle
            "980": "list_cmhk_america_norte_controle",
            # World / Global
            "975": "list_cmhk_world",
            # Ásia
            "4768": "list_cmhk_asia",
            # Oriente Médio
            "4769": "list_cmhk_oriente_medio",
            # Japão
            "4740": "list_cmhk_japao",
        }
        return plans.get(selList)

    @staticmethod
    def selectPlanCod(plan, day, data):
        data = str(data)
        data_alias = {
            '500mb-dia': '500mb',
            '1gb-dia': '1gb',
            '2gb-dia': '2gb',
            '3gb-dia': '3gb',
            'ilimitado': 'ilimitado',
            '1gb-periodo': '1gb',
            '2gb-periodo': '2gb',
            '3gb-periodo': '3gb',
            '5gb-periodo': '5gb',
            '7gb-periodo': '7gb',
            '10gb-periodo': '10gb',
            '15gb-periodo': '15gb',
            '20gb-periodo': '20gb',
            '30gb-periodo': '30gb',
            # legado
            '5gb-30dias': '5gb',
            '10gb-30dias': '10gb',
            '20gb-30dias': '20gb',
            '30gb-30dias': '30gb',
            '500mb': '500mb',
            '1gb': '1gb',
            '2gb': '2gb',
            '3gb': '3gb',
        }
        data_norm = data_alias.get(data, data)
        list_name = selectPlanCMHK.selectPlanList(str(plan))
        if not list_name:
            return None

        lists = {
            "list_cmhk_eua_ilimitado": [
                ["5", "ilimitado", "D2507041834474444919"],
                ["6", "ilimitado", "D2507041835061850091"],
                ["7", "ilimitado", "D2206291902418913108"],
                ["8", "ilimitado", "D2507041835183109834"],
                ["9", "ilimitado", "D2507041835298493969"],
                ["10", "ilimitado", "D2206291903110126531"],
                ["11", "ilimitado", "D2507041835524217762"],
                ["12", "ilimitado", "D2206291903377239037"],
                ["13", "ilimitado", "D2507041836086587855"],
                ["14", "ilimitado", "D2507041836214451081"],
                ["15", "ilimitado", "D2206291904065180225"],
                ["16", "ilimitado", "D2507041836343978752"],
                ["17", "ilimitado", "D2507041836461178710"],
                ["18", "ilimitado", "D2507041836585211745"],
                ["19", "ilimitado", "D2507041837120232847"],
                ["20", "ilimitado", "D2206291904352751421"],
                ["21", "ilimitado", "D2507041837270238206"],
                ["22", "ilimitado", "D2507041837408965982"],
                ["23", "ilimitado", "D2507041837590758810"],
                ["24", "ilimitado", "D2507041838148111441"],
                ["25", "ilimitado", "D2507041838323040278"],
                ["26", "ilimitado", "D2507041838446179260"],
                ["27", "ilimitado", "D2507041838566156896"],
                ["28", "ilimitado", "D2507041839090644368"],
                ["29", "ilimitado", "D2507041839314898204"],
                ["30", "ilimitado", "D2206291904591156033"],
            ],
            "list_cmhk_europa_controle": [
                ["5", "1gb", "D2603301603424791858"],
                ["6", "1gb", "D2608031722595117057"],
                ["7", "1gb", "D2603301604146200942"],
                ["8", "1gb", "D2608031722596745200"],
                ["9", "1gb", "D2608031722599099973"],
                ["10", "1gb", "D2603301605014500880"],
                ["11", "1gb", "D2608031723000808387"],
                ["12", "1gb", "D2603301608514338458"],
                ["13", "1gb", "D2608031723002451866"],
                ["14", "1gb", "D2608031723004321471"],
                ["15", "1gb", "D2603301609156527770"],
                ["16", "1gb", "D2608031723006432978"],
                ["17", "1gb", "D2608031723008003693"],
                ["18", "1gb", "D2608031723009645556"],
                ["19", "1gb", "D2608031723011001574"],
                ["20", "1gb", "D2603301616458057394"],
                ["21", "1gb", "D2608031723012468441"],
                ["22", "1gb", "D2608031723014009750"],
                ["23", "1gb", "D2608031723015411154"],
                ["24", "1gb", "D2608031723017248570"],
                ["25", "1gb", "D2603301617149172574"],
                ["26", "1gb", "D2608031723018715825"],
                ["27", "1gb", "D2608031723022739462"],
                ["28", "1gb", "D2608031723024503415"],
                ["29", "1gb", "D2608031723026327268"],
                ["30", "1gb", "D2603301617449452333"],
                ["5", "2gb", "D2603301620456107556"],
                ["6", "2gb", "D2608031723034791575"],
                ["7", "2gb", "D2603301622097750902"],
                ["8", "2gb", "D2608031723036639577"],
                ["9", "2gb", "D2608031723038216117"],
                ["10", "2gb", "D2603131656329053978"],
                ["11", "2gb", "D2608031723039743664"],
                ["12", "2gb", "D2603301623209232100"],
                ["13", "2gb", "D2608031723041258209"],
                ["14", "2gb", "D2608031723042634283"],
                ["15", "2gb", "D2603301624530188599"],
                ["16", "2gb", "D2608031723044391989"],
                ["17", "2gb", "D2608031723045919716"],
                ["18", "2gb", "D2608031723047512373"],
                ["19", "2gb", "D2608031723048897713"],
                ["20", "2gb", "D2603301625450392778"],
                ["21", "2gb", "D2608031723050374584"],
                ["22", "2gb", "D2608031723051814488"],
                ["23", "2gb", "D2608031723053271216"],
                ["24", "2gb", "D2608031723054681744"],
                ["25", "2gb", "D2603301626184161820"],
                ["26", "2gb", "D2608031723056363905"],
                ["27", "2gb", "D2608031723058034321"],
                ["28", "2gb", "D2608031723059742081"],
                ["29", "2gb", "D2608031723061502545"],
                ["30", "2gb", "D2604011624223458088"],
                ["5", "3gb", "D2604011626035679216"],
                ["6", "3gb", "D2608031723068766491"],
                ["7", "3gb", "D2604011627527062746"],
                ["8", "3gb", "D2608031723070228911"],
                ["9", "3gb", "D2608031723071724260"],
                ["10", "3gb", "D2604011628154547466"],
                ["11", "3gb", "D2608031723073397093"],
                ["12", "3gb", "D2604011628319030448"],
                ["13", "3gb", "D2608031723074873636"],
                ["14", "3gb", "D2608031723076358880"],
                ["15", "3gb", "D2604011628492551931"],
                ["16", "3gb", "D2608031723077809387"],
                ["17", "3gb", "D2608031723079407606"],
                ["18", "3gb", "D2608031723080948846"],
                ["19", "3gb", "D2608031723082354593"],
                ["20", "3gb", "D2604011629076922282"],
                ["21", "3gb", "D2608031723083724863"],
                ["22", "3gb", "D2608031723085091175"],
                ["23", "3gb", "D2608031723086405041"],
                ["24", "3gb", "D2608031723087707572"],
                ["25", "3gb", "D2604011629277461865"],
                ["26", "3gb", "D2608031723089046589"],
                ["27", "3gb", "D2608031723090652428"],
                ["28", "3gb", "D2608031723092149528"],
                ["29", "3gb", "D2608031723093766329"],
                ["30", "3gb", "D2604011629528753205"],
            ],
            "list_cmhk_europa_flex": [
                ["30", "30gb", "D2603172339547713924"],
                ["30", "20gb", "D2603131713120302567"],
                ["30", "15gb", "D2604011634253740665"],
                ["30", "10gb", "D2603131712440636521"],
                ["30", "5gb", "D2604011633363004903"],
                ["30", "3gb", "D2604011632294750898"],
            ],
            "list_cmhk_america_sul_controle": [
                ["5", "500mb", "D2404031210062193114"],
                ["6", "500mb", "D2511101750575937390"],
                ["7", "500mb", "D2404031210226737497"],
                ["8", "500mb", "D2511101750576589447"],
                ["9", "500mb", "D2511101750577226834"],
                ["10", "500mb", "D2404031210358569469"],
                ["11", "500mb", "D2511101750577847201"],
                ["12", "500mb", "D2511101750578521030"],
                ["13", "500mb", "D2511101750579269366"],
                ["14", "500mb", "D2511101750579978123"],
                ["15", "500mb", "D2404031210506288539"],
                ["16", "500mb", "D2511101750580587788"],
                ["17", "500mb", "D2511101750581296220"],
                ["18", "500mb", "D2511101750581960044"],
                ["19", "500mb", "D2511101750582662446"],
                ["20", "500mb", "D2404031211046731495"],
                ["21", "500mb", "D2511101750583307000"],
                ["22", "500mb", "D2511101750583959736"],
                ["23", "500mb", "D2511101750584626614"],
                ["24", "500mb", "D2511101750585265675"],
                ["25", "500mb", "D2511101750585870033"],
                ["26", "500mb", "D2511101750586552607"],
                ["27", "500mb", "D2511101750587176024"],
                ["28", "500mb", "D2511101750587810388"],
                ["29", "500mb", "D2511101750588419467"],
                ["30", "500mb", "D2404031211172035310"],
                ["5", "1gb", "D2404031212486801615"],
                ["6", "1gb", "D2511101750591649561"],
                ["7", "1gb", "D2404031213010518789"],
                ["8", "1gb", "D2511101750592233375"],
                ["9", "1gb", "D2511101750592871875"],
                ["10", "1gb", "D2404031213148743416"],
                ["11", "1gb", "D2511101750593480714"],
                ["12", "1gb", "D2511101750594146304"],
                ["13", "1gb", "D2511101750594775595"],
                ["14", "1gb", "D2511101750595370667"],
                ["15", "1gb", "D2404031213254297691"],
                ["16", "1gb", "D2511101750595960048"],
                ["17", "1gb", "D2511101750596607221"],
                ["18", "1gb", "D2511101750597200460"],
                ["19", "1gb", "D2511101750597807525"],
                ["20", "1gb", "D2404031213365262561"],
                ["21", "1gb", "D2511101750598371760"],
                ["22", "1gb", "D2511101750598981838"],
                ["23", "1gb", "D2511101750599635582"],
                ["24", "1gb", "D2511101751000390332"],
                ["25", "1gb", "D2511101751001053823"],
                ["26", "1gb", "D2511101751001669970"],
                ["27", "1gb", "D2511101751002406977"],
                ["28", "1gb", "D2511101751003230719"],
                ["29", "1gb", "D2511101751003958612"],
                ["30", "1gb", "D2404031213486570202"],
                ["5", "2gb", "D2404031214315532898"],
                ["6", "2gb", "D2511101751007495461"],
                ["7", "2gb", "D2404031214448357348"],
                ["8", "2gb", "D2511101751008244591"],
                ["9", "2gb", "D2511101751008866060"],
                ["10", "2gb", "D2404031214563569617"],
                ["11", "2gb", "D2511101751009457878"],
                ["12", "2gb", "D2511101751010145076"],
                ["13", "2gb", "D2511101751010796797"],
                ["14", "2gb", "D2511101751011499346"],
                ["15", "2gb", "D2404031215086886884"],
                ["16", "2gb", "D2511101751012110233"],
                ["17", "2gb", "D2511101751012794096"],
                ["18", "2gb", "D2511101751013452853"],
                ["19", "2gb", "D2511101751014155788"],
                ["20", "2gb", "D2404031215208679205"],
                ["21", "2gb", "D2511101751014883879"],
                ["22", "2gb", "D2511101751015537517"],
                ["23", "2gb", "D2511101751016267470"],
                ["24", "2gb", "D2511101751017088442"],
                ["25", "2gb", "D2511101751017840743"],
                ["26", "2gb", "D2511101751018521774"],
                ["27", "2gb", "D2511101751019187903"],
                ["28", "2gb", "D2511101751019872685"],
                ["29", "2gb", "D2511101751020488742"],
                ["30", "2gb", "D2404031215315038594"],
            ],
            "list_cmhk_america_sul_flex": [
                ["30", "30gb", "D2511101800420058994"],
                ["30", "20gb", "D2511101800205942878"],
                ["30", "15gb", "D2511101759527393271"],
                ["30", "10gb", "D2511101759293142371"],
                ["30", "7gb", "D2511101758300572721"],
                ["30", "5gb", "D2511101755098329684"],
                ["30", "3gb", "D2511101753459409829"],
                ["30", "1gb", "D2511101754204897217"],
            ],
            "list_cmhk_america_norte_controle": [
                ["5", "500mb", "D2511101750438713823"],
                ["6", "500mb", "D2511101750439269129"],
                ["7", "500mb", "D181029074947_215300"],
                ["8", "500mb", "D2511101750439771051"],
                ["9", "500mb", "D2511101750440359734"],
                ["10", "500mb", "D181029075127_215305"],
                ["11", "500mb", "D2511101750440918863"],
                ["12", "500mb", "D181029075231_215312"],
                ["13", "500mb", "D2511101750441456628"],
                ["14", "500mb", "D2511101750442089663"],
                ["15", "500mb", "D181029075347_215318"],
                ["16", "500mb", "D2511101750442595567"],
                ["17", "500mb", "D2511101750443266019"],
                ["18", "500mb", "D2511101750443834519"],
                ["19", "500mb", "D2511101750444379567"],
                ["20", "500mb", "D181029075545_215323"],
                ["21", "500mb", "D2511101750444855004"],
                ["22", "500mb", "D2511101750445444444"],
                ["23", "500mb", "D2511101750446085174"],
                ["24", "500mb", "D2511101750446685154"],
                ["25", "500mb", "D2511101750447183936"],
                ["26", "500mb", "D2511101750447851422"],
                ["27", "500mb", "D2511101750448414566"],
                ["28", "500mb", "D2511101750449062412"],
                ["29", "500mb", "D2511101750449641823"],
                ["30", "500mb", "D181029075646_215328"],
                ["5", "1gb", "D2511101750452806819"],
                ["6", "1gb", "D2511101750453415091"],
                ["7", "1gb", "D2206091118158677818"],
                ["8", "1gb", "D2511101750454054534"],
                ["9", "1gb", "D2511101750454610268"],
                ["10", "1gb", "D2206091118433144508"],
                ["11", "1gb", "D2511101750455139736"],
                ["12", "1gb", "D2206291906432072367"],
                ["13", "1gb", "D2511101750455668986"],
                ["14", "1gb", "D2511101750456168193"],
                ["15", "1gb", "D2206091119091070123"],
                ["16", "1gb", "D2511101750456858856"],
                ["17", "1gb", "D2511101750457546960"],
                ["18", "1gb", "D2511101750458270257"],
                ["19", "1gb", "D2511101750458793793"],
                ["20", "1gb", "D2206291907323030471"],
                ["21", "1gb", "D2511101750459346058"],
                ["22", "1gb", "D2511101750459917762"],
                ["23", "1gb", "D2511101750460476550"],
                ["24", "1gb", "D2511101750461260079"],
                ["25", "1gb", "D2511101750462016237"],
                ["26", "1gb", "D2511101750462598403"],
                ["27", "1gb", "D2511101750463207394"],
                ["28", "1gb", "D2511101750463762037"],
                ["29", "1gb", "D2511101750464447250"],
                ["30", "1gb", "D2206091119350589636"],
                ["5", "2gb", "D2511101750467408383"],
                ["6", "2gb", "D2511101750468049685"],
                ["7", "2gb", "D2206291909256195940"],
                ["8", "2gb", "D2511101750468863839"],
                ["9", "2gb", "D2511101750469505344"],
                ["10", "2gb", "D2206291910012200492"],
                ["11", "2gb", "D2511101750470011360"],
                ["12", "2gb", "D2206291910234719163"],
                ["13", "2gb", "D2511101750470618964"],
                ["14", "2gb", "D2511101750471127037"],
                ["15", "2gb", "D2206291910482445815"],
                ["16", "2gb", "D2511101750471675954"],
                ["17", "2gb", "D2511101750472183889"],
                ["18", "2gb", "D2511101750472935033"],
                ["19", "2gb", "D2511101750473627991"],
                ["20", "2gb", "D2206291911183379323"],
                ["21", "2gb", "D2511101750474182773"],
                ["22", "2gb", "D2511101750474783137"],
                ["23", "2gb", "D2511101750475305658"],
                ["24", "2gb", "D2511101750476026465"],
                ["25", "2gb", "D2511101750476513607"],
                ["26", "2gb", "D2511101750477025779"],
                ["27", "2gb", "D2511101750477520810"],
                ["28", "2gb", "D2511101750478047613"],
                ["29", "2gb", "D2511101750478522705"],
                ["30", "2gb", "D2206291911447523252"],
            ],
            "list_cmhk_world": [
                ["5", "500mb", "D181030042539_227624"],
                ["6", "500mb", "D2511131726296607991"],
                ["7", "500mb", "D181030043319_227719"],
                ["8", "500mb", "D2511131726301408813"],
                ["9", "500mb", "D2511131726305863694"],
                ["10", "500mb", "D181030044052_227812"],
                ["11", "500mb", "D2511131726310735625"],
                ["12", "500mb", "D2511131726314910136"],
                ["13", "500mb", "D2511131726320286199"],
                ["14", "500mb", "D2511131726325023991"],
                ["15", "500mb", "D181030060952_227953"],
                ["16", "500mb", "D2511131726329846436"],
                ["17", "500mb", "D2511131726334225644"],
                ["18", "500mb", "D2511131726338988844"],
                ["19", "500mb", "D2511131726343583570"],
                ["20", "500mb", "D210520111201_567505"],
                ["21", "500mb", "D2511131726348122799"],
                ["22", "500mb", "D2511131726352615277"],
                ["23", "500mb", "D2511131726357476233"],
                ["24", "500mb", "D2511131726362164000"],
                ["25", "500mb", "D210521020847_567890"],
                ["26", "500mb", "D2511131726366826185"],
                ["27", "500mb", "D2511131726371456785"],
                ["28", "500mb", "D2511131726375976103"],
                ["29", "500mb", "D2511131726380630188"],
                ["30", "500mb", "D181030062003_228049"],
                ["5", "1gb", "D2205171902194598628"],
                ["6", "1gb", "D2511131726394745227"],
                ["7", "1gb", "D2205171902519779100"],
                ["8", "1gb", "D2511131726399627968"],
                ["9", "1gb", "D2511131726404173697"],
                ["10", "1gb", "D2205171903285254520"],
                ["11", "1gb", "D2511131726409279449"],
                ["12", "1gb", "D2511131726414208428"],
                ["13", "1gb", "D2511131726418850296"],
                ["14", "1gb", "D2511131726423634217"],
                ["15", "1gb", "D2205171904079201878"],
                ["16", "1gb", "D2511131726428213758"],
                ["17", "1gb", "D2511131726433445226"],
                ["18", "1gb", "D2511131726437875206"],
                ["19", "1gb", "D2511131726442570985"],
                ["20", "1gb", "D2205171904426262385"],
                ["21", "1gb", "D2511131726447008730"],
                ["22", "1gb", "D2511131726451504193"],
                ["23", "1gb", "D2511131726456344593"],
                ["24", "1gb", "D2511131726460590923"],
                ["25", "1gb", "D2205171905123822954"],
                ["26", "1gb", "D2511131726465231305"],
                ["27", "1gb", "D2511131726469739008"],
                ["28", "1gb", "D2511131726474244304"],
                ["29", "1gb", "D2511131726478974564"],
                ["30", "1gb", "D2205171905428070570"],
                ["5", "2gb", "D2206301059342263262"],
                ["6", "2gb", "D2511131726493363829"],
                ["7", "2gb", "D2206301100122278918"],
                ["8", "2gb", "D2511131726498048099"],
                ["9", "2gb", "D2511131726502649598"],
                ["10", "2gb", "D2206301100537072952"],
                ["11", "2gb", "D2511131726507096856"],
                ["12", "2gb", "D2511131726511637063"],
                ["13", "2gb", "D2511131726515982597"],
                ["14", "2gb", "D2511131726520669842"],
                ["15", "2gb", "D2206301101255910272"],
                ["16", "2gb", "D2511131726525162310"],
                ["17", "2gb", "D2511131726529790544"],
                ["18", "2gb", "D2511131726534730963"],
                ["19", "2gb", "D2511131726539405283"],
                ["20", "2gb", "D2206301102116254489"],
                ["21", "2gb", "D2511131726545338773"],
                ["22", "2gb", "D2511131726549699231"],
                ["23", "2gb", "D2511131726554144405"],
                ["24", "2gb", "D2511131726558936014"],
                ["25", "2gb", "D2206301102507299017"],
                ["26", "2gb", "D2511131726563717203"],
                ["27", "2gb", "D2511131726568175834"],
                ["28", "2gb", "D2511131726573086759"],
                ["29", "2gb", "D2511131726577478572"],
                ["30", "2gb", "D2206301103268430586"],
            ],
            "list_cmhk_asia": [
                ["5", "500mb", "D2409301750189921381"],
                ["6", "500mb", "D2511101751115669948"],
                ["7", "500mb", "D2511101751116457667"],
                ["8", "500mb", "D2212221201272604702"],
                ["9", "500mb", "D2511101751117269644"],
                ["10", "500mb", "D2511101751118136878"],
                ["11", "500mb", "D2511101751118916219"],
                ["12", "500mb", "D2212221202118022965"],
                ["13", "500mb", "D2511101751119732115"],
                ["14", "500mb", "D2511101751120600146"],
                ["15", "500mb", "D2212221202434770811"],
                ["16", "500mb", "D2511101751121460707"],
                ["17", "500mb", "D2511101751122473522"],
                ["18", "500mb", "D2511101751123262957"],
                ["19", "500mb", "D2511101751124082118"],
                ["20", "500mb", "D2511101751124915113"],
                ["21", "500mb", "D2511101751125796134"],
                ["22", "500mb", "D2511101751126658298"],
                ["23", "500mb", "D2511101751127474833"],
                ["24", "500mb", "D2511101751128345159"],
                ["25", "500mb", "D2511101751129174986"],
                ["26", "500mb", "D2511101751130014709"],
                ["27", "500mb", "D2511101751130878786"],
                ["28", "500mb", "D2511101751131739703"],
                ["29", "500mb", "D2511101751132543753"],
                ["30", "500mb", "D2212221203147022339"],
                ["5", "1gb", "D2409301751305586374"],
                ["6", "1gb", "D2511101751137031436"],
                ["7", "1gb", "D2511101751137851058"],
                ["8", "1gb", "D2212221203579364735"],
                ["9", "1gb", "D2511101751138704781"],
                ["10", "1gb", "D2511101751139606346"],
                ["11", "1gb", "D2511101751140407506"],
                ["12", "1gb", "D2212221204387202195"],
                ["13", "1gb", "D2511101751141267205"],
                ["14", "1gb", "D2511101751142217090"],
                ["15", "1gb", "D2212221206199951986"],
                ["16", "1gb", "D2511101751143107565"],
                ["17", "1gb", "D2511101751143922817"],
                ["18", "1gb", "D2511101751144700187"],
                ["19", "1gb", "D2511101751145493244"],
                ["20", "1gb", "D2511101751146386127"],
                ["21", "1gb", "D2511101751147320447"],
                ["22", "1gb", "D2511101751148175857"],
                ["23", "1gb", "D2511101751149125500"],
                ["24", "1gb", "D2511101751150054098"],
                ["25", "1gb", "D2511101751150921949"],
                ["26", "1gb", "D2511101751151846527"],
                ["27", "1gb", "D2511101751152786348"],
                ["28", "1gb", "D2511101751153663967"],
                ["29", "1gb", "D2511101751154588810"],
                ["30", "1gb", "D2212221206582387944"],
                ["5", "2gb", "D2409301752231044836"],
                ["6", "2gb", "D2511101751159071542"],
                ["7", "2gb", "D2511101751159872498"],
                ["8", "2gb", "D2212221207344588124"],
                ["9", "2gb", "D2511101751160763660"],
                ["10", "2gb", "D2511101751161574858"],
                ["11", "2gb", "D2511101751162539303"],
                ["12", "2gb", "D2212221208012444949"],
                ["13", "2gb", "D2511101751163341049"],
                ["14", "2gb", "D2511101751164161436"],
                ["15", "2gb", "D2212221208395801279"],
                ["16", "2gb", "D2511101751164971149"],
                ["17", "2gb", "D2511101751165832630"],
                ["18", "2gb", "D2511101751166681556"],
                ["19", "2gb", "D2511101751167483595"],
                ["20", "2gb", "D2511101751168368537"],
                ["21", "2gb", "D2511101751169277433"],
                ["22", "2gb", "D2511101751170061879"],
                ["23", "2gb", "D2511101751170882904"],
                ["24", "2gb", "D2511101751171818961"],
                ["25", "2gb", "D2511101751172752986"],
                ["26", "2gb", "D2511101751173618863"],
                ["27", "2gb", "D2511101751174473256"],
                ["28", "2gb", "D2511101751175302956"],
                ["29", "2gb", "D2511101751176116434"],
                ["30", "2gb", "D2212221209088976898"],
            ],
            "list_cmhk_oriente_medio": [
                ["5", "500mb", "D2409301700516117555"],
                ["6", "500mb", "D2511101751066348452"],
                ["7", "500mb", "D2409301703316275854"],
                ["8", "500mb", "D2511101751067102594"],
                ["9", "500mb", "D2511101751067734469"],
                ["10", "500mb", "D2409301704032662902"],
                ["11", "500mb", "D2511101751068360288"],
                ["12", "500mb", "D2511101751069019976"],
                ["13", "500mb", "D2511101751069654090"],
                ["14", "500mb", "D2511101751070325847"],
                ["15", "500mb", "D2409301704173032153"],
                ["16", "500mb", "D2511101751070950929"],
                ["17", "500mb", "D2511101751071601045"],
                ["18", "500mb", "D2511101751072331283"],
                ["19", "500mb", "D2511101751073009995"],
                ["20", "500mb", "D2409301704309735842"],
                ["21", "500mb", "D2511101751073641766"],
                ["22", "500mb", "D2511101751074262991"],
                ["23", "500mb", "D2511101751074912431"],
                ["24", "500mb", "D2511101751075543005"],
                ["25", "500mb", "D2511101751076185260"],
                ["26", "500mb", "D2511101751076880246"],
                ["27", "500mb", "D2511101751077521618"],
                ["28", "500mb", "D2511101751078189457"],
                ["29", "500mb", "D2511101751078888552"],
                ["30", "500mb", "D2409301704438980133"],
                ["5", "1gb", "D2409301705280009971"],
                ["6", "1gb", "D2511101751082293976"],
                ["7", "1gb", "D2409301705449737787"],
                ["8", "1gb", "D2511101751082935584"],
                ["9", "1gb", "D2511101751083593907"],
                ["10", "1gb", "D2409301706086810985"],
                ["11", "1gb", "D2511101751084190148"],
                ["12", "1gb", "D2511101751084946397"],
                ["13", "1gb", "D2511101751085621444"],
                ["14", "1gb", "D2511101751086269435"],
                ["15", "1gb", "D2409301706270341743"],
                ["16", "1gb", "D2511101751086957927"],
                ["17", "1gb", "D2511101751087588448"],
                ["18", "1gb", "D2511101751088188620"],
                ["19", "1gb", "D2511101751088894767"],
                ["20", "1gb", "D2409301706436177900"],
                ["21", "1gb", "D2511101751089571498"],
                ["22", "1gb", "D2511101751090206492"],
                ["23", "1gb", "D2511101751090856548"],
                ["24", "1gb", "D2511101751091586871"],
                ["25", "1gb", "D2511101751092243871"],
                ["26", "1gb", "D2511101751092908519"],
                ["27", "1gb", "D2511101751093552864"],
                ["28", "1gb", "D2511101751094170190"],
                ["29", "1gb", "D2511101751094848343"],
                ["30", "1gb", "D2409301707000944515"],
                ["5", "2gb", "D2409301707277828103"],
                ["6", "2gb", "D2511101751098229628"],
                ["7", "2gb", "D2409301707538718417"],
                ["8", "2gb", "D2511101751098923099"],
                ["9", "2gb", "D2511101751099679435"],
                ["10", "2gb", "D2409301708147920984"],
                ["11", "2gb", "D2511101751100431205"],
                ["12", "2gb", "D2511101751101062224"],
                ["13", "2gb", "D2511101751101676976"],
                ["14", "2gb", "D2511101751102445462"],
                ["15", "2gb", "D2409301708307924164"],
                ["16", "2gb", "D2511101751103116304"],
                ["17", "2gb", "D2511101751103765427"],
                ["18", "2gb", "D2511101751104409650"],
                ["19", "2gb", "D2511101751105117537"],
                ["20", "2gb", "D2409301708472281118"],
                ["21", "2gb", "D2511101751105798673"],
                ["22", "2gb", "D2511101751106490459"],
                ["23", "2gb", "D2511101751107113020"],
                ["24", "2gb", "D2511101751107815502"],
                ["25", "2gb", "D2511101751108533429"],
                ["26", "2gb", "D2511101751109197583"],
                ["27", "2gb", "D2511101751109948355"],
                ["28", "2gb", "D2511101751110783293"],
                ["29", "2gb", "D2511101751111407507"],
                ["30", "2gb", "D2409301709042412089"],
            ],
            "list_cmhk_japao": [
                ["5", "1gb", "D2206171459265750624"],
                ["6", "1gb", "D2510311751408222818"],
                ["7", "1gb", "D190114031109_750533"],
                ["8", "1gb", "D2206291732444380143"],
                ["9", "1gb", "D2510311751408671945"],
                ["10", "1gb", "D2206171500041726584"],
                ["11", "1gb", "D2510311751409187852"],
                ["12", "1gb", "D2206291733522598975"],
                ["13", "1gb", "D2510311751409631137"],
                ["14", "1gb", "D2510311751410128498"],
                ["15", "1gb", "D2212051718069480240"],
                ["16", "1gb", "D2510311751410756709"],
                ["17", "1gb", "D2510311751411192362"],
                ["18", "1gb", "D2510311751411815846"],
                ["19", "1gb", "D2510311751412246280"],
                ["20", "1gb", "D2510311751412681751"],
                ["21", "1gb", "D2510311751413258247"],
                ["22", "1gb", "D2510311751413723997"],
                ["23", "1gb", "D2510311751414230987"],
                ["24", "1gb", "D2510311751414757252"],
                ["25", "1gb", "D2510311751415173119"],
                ["26", "1gb", "D2510311751415630655"],
                ["27", "1gb", "D2510311751416084465"],
                ["28", "1gb", "D2510311751416544933"],
                ["29", "1gb", "D2510311751417059604"],
                ["30", "1gb", "D2212051718231244957"],
                ["5", "2gb", "D2206291736017128099"],
                ["6", "2gb", "D2510311751418223641"],
                ["7", "2gb", "D2206291736273235857"],
                ["8", "2gb", "D2206291736546738743"],
                ["9", "2gb", "D2510311751418814791"],
                ["10", "2gb", "D2206291737376685419"],
                ["11", "2gb", "D2510311751419239519"],
                ["12", "2gb", "D2206291738043899151"],
                ["13", "2gb", "D2510311751419700482"],
                ["14", "2gb", "D2510311751420133336"],
                ["15", "2gb", "D2212051719405616299"],
                ["16", "2gb", "D2510311751420600899"],
                ["17", "2gb", "D2510311751421040442"],
                ["18", "2gb", "D2510311751421532700"],
                ["19", "2gb", "D2510311751422088913"],
                ["20", "2gb", "D2510311751422598263"],
                ["21", "2gb", "D2510311751423030751"],
                ["22", "2gb", "D2510311751423570761"],
                ["23", "2gb", "D2510311751424115130"],
                ["24", "2gb", "D2510311751424563232"],
                ["25", "2gb", "D2510311751425029373"],
                ["26", "2gb", "D2510311751425581864"],
                ["27", "2gb", "D2510311751426030770"],
                ["28", "2gb", "D2510311751426537708"],
                ["29", "2gb", "D2510311751427109462"],
                ["30", "2gb", "D2212051720000900238"],
                ["5", "3gb", "D2303221203026117974"],
                ["6", "3gb", "D2510311751428623509"],
                ["7", "3gb", "D2303221204483583107"],
                ["8", "3gb", "D2303221206146148829"],
                ["9", "3gb", "D2510311751429079714"],
                ["10", "3gb", "D2303221208337912190"],
                ["11", "3gb", "D2510311751429522663"],
                ["12", "3gb", "D2303221209192899239"],
                ["13", "3gb", "D2510311751429999973"],
                ["14", "3gb", "D2510311751430454948"],
                ["15", "3gb", "D2303221210004774259"],
                ["16", "3gb", "D2510311751430938898"],
                ["17", "3gb", "D2510311751431348611"],
                ["18", "3gb", "D2510311751431911141"],
                ["19", "3gb", "D2510311751432524089"],
                ["20", "3gb", "D2510311751433041663"],
                ["21", "3gb", "D2510311751433616247"],
                ["22", "3gb", "D2510311751434109318"],
                ["23", "3gb", "D2510311751434534202"],
                ["24", "3gb", "D2510311751434997597"],
                ["25", "3gb", "D2510311751435417338"],
                ["26", "3gb", "D2510311751435905814"],
                ["27", "3gb", "D2510311751436395489"],
                ["28", "3gb", "D2510311751436863402"],
                ["29", "3gb", "D2510311751437331395"],
                ["30", "3gb", "D2303221210419424049"],
            ],
        }

        plan_list = lists.get(list_name)
        if not plan_list:
            return None

        day = str(day)
        data_norm = str(data_norm)
        for plan_day, plan_data, cod in plan_list:
            if plan_day == day and plan_data == data_norm:
                return cod
        return None
