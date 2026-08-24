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
            sim = iccid,
            lpa = lpa,
            link = qrcode_url,
            type_sim = 'esim',
            operator = 'AR',
            sim_status = 'AT'
        )
        add_sim.save()        
        id_sim = add_sim.id
        return id_sim


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
            "4816": "list_cmhk_europe",
            "974": "list_cmhk_europe",
            "971": "list_cmhk_europe",
            "3734": "list_cmhk_south_america",
            "3564": "list_cmhk_south_america",
            "4768": "list_cmhk_asia",
            "4740": "list_cmhk_asia",
            "981": "list_cmhk_north_america",
            "980": "list_cmhk_north_america",
            "4763": "list_cmhk_africa",
            "4769": "list_cmhk_middle_east",
            "4735": "list_cmhk_oceania",
            "4718": "list_cmhk_central_america",
            "4752": "list_cmhk_central_america",
            "975": "list_cmhk_global",
            "976": "list_cmhk_eua_premium",
            "977": "list_cmhk_eua_premium",
            "001": "list_cmhk_eua_premium",
            "chip-internacional-europa": "list_cmhk_europe",
            "chip-internacional-america-do-sul": "list_cmhk_south_america",
            "chip-internacional-asia": "list_cmhk_asia",
            "chip-internacional-america-do-norte": "list_cmhk_north_america",
            "chip-internacional-africa": "list_cmhk_africa",
            "chip-internacional-oriente-medio": "list_cmhk_middle_east",
            "chip-internacional-oceania": "list_cmhk_oceania",
            "chip-internacional-america-central": "list_cmhk_central_america",
            "chip-internacional-global": "list_cmhk_global",
            "chip-internacional-eua-premium": "list_cmhk_eua_premium",
            # legado
            "chip-internacional-europa-ilimitado": "list_cmhk_europe",
            "chip-internacional-europa-premium": "list_cmhk_europe",
            "chip-internacional-europa-1gb-total": "list_cmhk_europe_1gb_total",
        }
        return plans.get(selList)

    @staticmethod
    def selectPlanCod(plan, day, data):
        data_alias = {
            '1gb-dia': '1gb',
            '2gb-dia': '1gb',
            '1gb': '1gb',
        }
        data = data_alias.get(str(data), data)
        list_name = selectPlanCMHK.selectPlanList(str(plan))
        if not list_name:
            return None

        lists = {
            "list_cmhk_europe": [
                ["2", "500mb-dia", "D2608172143314216552"],
                ["3", "500mb-dia", "D2608172143031731652"],
                ["4", "500mb-dia", "D2608172142302602092"],
                ["5", "500mb-dia", "D2608120537106737634"],
                ["6", "500mb-dia", "D2608120539528108753"],
                ["7", "500mb-dia", "D2608120537479070013"],
                ["8", "500mb-dia", "D2608120540367887830"],
                ["9", "500mb-dia", "D2608120540542753049"],
                ["10", "500mb-dia", "D2608120541088293336"],
                ["11", "500mb-dia", "D2608120541374421848"],
                ["12", "500mb-dia", "D2608120541533835778"],
                ["13", "500mb-dia", "D2608120542081607519"],
                ["14", "500mb-dia", "D2608120542232759760"],
                ["15", "500mb-dia", "D2608120542383300555"],
                ["16", "500mb-dia", "D2608120542554163252"],
                ["17", "500mb-dia", "D2608120543150402135"],
                ["18", "500mb-dia", "D2608120543311054820"],
                ["19", "500mb-dia", "D2608120543437562331"],
                ["20", "500mb-dia", "D2608120544032508052"],
                ["21", "500mb-dia", "D2608120544188933568"],
                ["22", "500mb-dia", "D2608120544310463154"],
                ["23", "500mb-dia", "D2608120544441795925"],
                ["24", "500mb-dia", "D2608120544577153240"],
                ["25", "500mb-dia", "D2608120545108427277"],
                ["26", "500mb-dia", "D2608120545228212629"],
                ["27", "500mb-dia", "D2608120545352985052"],
                ["28", "500mb-dia", "D2608120545467785293"],
                ["29", "500mb-dia", "D2608120546014452426"],
                ["30", "500mb-dia", "D2608120546166584636"],
                ["31", "500mb-dia", "D2608120546570663594"],
                ["2", "1gb", "D2608172146546542019"],
                ["3", "1gb", "D2608172146091505647"],
                ["4", "1gb", "D2608172144598925053"],
                ["5", "1gb", "D2608120601461748128"],
                ["6", "1gb", "D2608120602309073482"],
                ["7", "1gb", "D2608120602435898889"],
                ["8", "1gb", "D2608120602544092011"],
                ["9", "1gb", "D2608120603042427198"],
                ["10", "1gb", "D2608120603155252616"],
                ["11", "1gb", "D2608120603283102023"],
                ["12", "1gb", "D2608120603394583493"],
                ["13", "1gb", "D2608120603485942721"],
                ["14", "1gb", "D2608120604005143708"],
                ["15", "1gb", "D2608120604114408350"],
                ["16", "1gb", "D2608120604216072945"],
                ["17", "1gb", "D2608120604324879582"],
                ["18", "1gb", "D2608120604405429759"],
                ["19", "1gb", "D2608120604506861972"],
                ["20", "1gb", "D2608120605003642212"],
                ["21", "1gb", "D2608120605123161731"],
                ["22", "1gb", "D2608120605209210413"],
                ["23", "1gb", "D2608120605315529426"],
                ["24", "1gb", "D2608120605426248309"],
                ["25", "1gb", "D2608120605511844444"],
                ["26", "1gb", "D2608120606018934501"],
                ["27", "1gb", "D2608120606118732903"],
                ["28", "1gb", "D2608120606235123932"],
                ["29", "1gb", "D2608120606373383350"],
                ["30", "1gb", "D2608120606466864190"],
                ["31", "1gb", "D2608120606545891000"],
                ["2", "ilimitado", "D2608172226018174267"],
                ["3", "ilimitado", "D2608172225360116806"],
                ["4", "ilimitado", "D2608172225107458913"],
                ["5", "ilimitado", "D2608172224170373384"],
                ["6", "ilimitado", "D2608120508284342465"],
                ["7", "ilimitado", "D2608172227149505429"],
                ["8", "ilimitado", "D2608120508559981535"],
                ["9", "ilimitado", "D2608172228253231298"],
                ["10", "ilimitado", "D2608172228541784166"],
                ["11", "ilimitado", "D2608120509176496993"],
                ["12", "ilimitado", "D2608172230186510270"],
                ["13", "ilimitado", "D2608120509436356839"],
                ["14", "ilimitado", "D2608172230500428536"],
                ["15", "ilimitado", "D2608120510086333541"],
                ["16", "ilimitado", "D2608172231209710725"],
                ["17", "ilimitado", "D2608172231457311969"],
                ["18", "ilimitado", "D2608172232103700066"],
                ["19", "ilimitado", "D2608172232326493620"],
                ["20", "ilimitado", "D2608120510545194035"],
                ["21", "ilimitado", "D2608172233088744033"],
                ["22", "ilimitado", "D2608172233417584024"],
                ["23", "ilimitado", "D2608172234101923668"],
                ["24", "ilimitado", "D2608172234290726541"],
                ["25", "ilimitado", "D2608172234470919473"],
                ["26", "ilimitado", "D2608172235059518822"],
                ["27", "ilimitado", "D2608172235255444973"],
                ["28", "ilimitado", "D2608172236028785982"],
                ["29", "ilimitado", "D2608172236272257877"],
                ["30", "ilimitado", "D2608172236524364868"],
                ["31", "ilimitado", "D2608120120391706913"],
            ],
            "list_cmhk_europe_1gb_total": [
                ["5", "1gb", "D2608120938062723580"],
            ],
            "list_cmhk_south_america": [
                ["2", "500mb-dia", "D2608172355494440297"],
                ["3", "500mb-dia", "D2608172355347608227"],
                ["4", "500mb-dia", "D2608172354542781211"],
                ["5", "500mb-dia", "D2608120733502907418"],
                ["6", "500mb-dia", "D2608120734184634301"],
                ["7", "500mb-dia", "D2608120734466340953"],
                ["8", "500mb-dia", "D2608120735006380262"],
                ["9", "500mb-dia", "D2608120735115912290"],
                ["10", "500mb-dia", "D2608120735215193377"],
                ["11", "500mb-dia", "D2608120735288910574"],
                ["12", "500mb-dia", "D2608120736024877126"],
                ["13", "500mb-dia", "D2608120736102591094"],
                ["14", "500mb-dia", "D2608120736193712495"],
                ["15", "500mb-dia", "D2608120736273286335"],
                ["16", "500mb-dia", "D2608120736372427830"],
                ["17", "500mb-dia", "D2608120736491714678"],
                ["18", "500mb-dia", "D2608120736593615351"],
                ["19", "500mb-dia", "D2608120737110923309"],
                ["20", "500mb-dia", "D2608120737237821830"],
                ["21", "500mb-dia", "D2608120737376740057"],
                ["22", "500mb-dia", "D2608120737554037945"],
                ["23", "500mb-dia", "D2608120738037957575"],
                ["24", "500mb-dia", "D2608120738129573728"],
                ["25", "500mb-dia", "D2608120738238758002"],
                ["26", "500mb-dia", "D2608120738379659682"],
                ["27", "500mb-dia", "D2608120738490736615"],
                ["28", "500mb-dia", "D2608120738589592587"],
                ["29", "500mb-dia", "D2608120739104725041"],
                ["30", "500mb-dia", "D2608120739238509542"],
                ["31", "500mb-dia", "D2608120739506422788"],
                ["2", "1gb", "D2608172358045961024"],
                ["3", "1gb", "D2608172357466020930"],
                ["4", "1gb", "D2608172357048687923"],
                ["5", "1gb", "D2608120750329815588"],
                ["6", "1gb", "D2608120751451194902"],
                ["7", "1gb", "D2608120751549434161"],
                ["8", "1gb", "D2608120752045856174"],
                ["9", "1gb", "D2608120752123732900"],
                ["10", "1gb", "D2608120752216297753"],
                ["11", "1gb", "D2608120752449200934"],
                ["12", "1gb", "D2608120752564822421"],
                ["13", "1gb", "D2608120753086167717"],
                ["14", "1gb", "D2608120753203282280"],
                ["15", "1gb", "D2608120753321329152"],
                ["16", "1gb", "D2608120753459653033"],
                ["17", "1gb", "D2608120753581740442"],
                ["18", "1gb", "D2608120754092417257"],
                ["19", "1gb", "D2608120754198555270"],
                ["20", "1gb", "D2608120754313647198"],
                ["21", "1gb", "D2608120754452331402"],
                ["22", "1gb", "D2608120754571286666"],
                ["23", "1gb", "D2608120755240640790"],
                ["24", "1gb", "D2608120755368247232"],
                ["25", "1gb", "D2608120755493547788"],
                ["26", "1gb", "D2608120756006635986"],
                ["27", "1gb", "D2608120756128657074"],
                ["28", "1gb", "D2608120756262811108"],
                ["29", "1gb", "D2608120756396664665"],
                ["30", "1gb", "D2608120756524031752"],
                ["31", "1gb", "D2608120757068261802"],
                ["2", "ilimitado", "D2608180006549655674"],
                ["3", "ilimitado", "D2608180006317494917"],
                ["4", "ilimitado", "D2608180006101050159"],
                ["5", "ilimitado", "D2608120727534836145"],
                ["6", "ilimitado", "D2608180009089714525"],
                ["7", "ilimitado", "D2608120728228433022"],
                ["8", "ilimitado", "D2608180009326902438"],
                ["9", "ilimitado", "D2608180009544352081"],
                ["10", "ilimitado", "D2608120728362768219"],
                ["11", "ilimitado", "D2608180010140431454"],
                ["12", "ilimitado", "D2608120728466334199"],
                ["13", "ilimitado", "D2608180010353621576"],
                ["14", "ilimitado", "D2608180011047481788"],
                ["15", "ilimitado", "D2608120728590689724"],
                ["16", "ilimitado", "D2608180011291648369"],
                ["17", "ilimitado", "D2608180022065363558"],
                ["18", "ilimitado", "D2608180022221921790"],
                ["19", "ilimitado", "D2608180022368110404"],
                ["20", "ilimitado", "D2608120729095524136"],
                ["21", "ilimitado", "D2608180023508362790"],
                ["22", "ilimitado", "D2608180024079461566"],
                ["23", "ilimitado", "D2608180024195427773"],
                ["24", "ilimitado", "D2608180024355394479"],
                ["25", "ilimitado", "D2608180024497627557"],
                ["26", "ilimitado", "D2608180025053795560"],
                ["27", "ilimitado", "D2608180025279346941"],
                ["28", "ilimitado", "D2608180025420331447"],
                ["29", "ilimitado", "D2608180025551701377"],
                ["30", "ilimitado", "D2608120729260624668"],
                ["31", "ilimitado", "D2608180027136794831"],
            ],
            "list_cmhk_asia": [
                ["2", "500mb-dia", "D2608180232451989874"],
                ["3", "500mb-dia", "D2608180232322962185"],
                ["4", "500mb-dia", "D2608180232128109176"],
                ["5", "500mb-dia", "D2608120826499911584"],
                ["6", "500mb-dia", "D2608120830257648571"],
                ["7", "500mb-dia", "D2608120830598887316"],
                ["8", "500mb-dia", "D2608120831102066255"],
                ["9", "500mb-dia", "D2608120831169377374"],
                ["10", "500mb-dia", "D2608120831251691924"],
                ["11", "500mb-dia", "D2608120831319618607"],
                ["12", "500mb-dia", "D2608120831396685145"],
                ["13", "500mb-dia", "D2608120831482989892"],
                ["14", "500mb-dia", "D2608120831548905583"],
                ["15", "500mb-dia", "D2608120832019050427"],
                ["16", "500mb-dia", "D2608120832101286090"],
                ["17", "500mb-dia", "D2608120832179198831"],
                ["18", "500mb-dia", "D2608120832258939058"],
                ["19", "500mb-dia", "D2608120832362301056"],
                ["20", "500mb-dia", "D2608120832436267924"],
                ["21", "500mb-dia", "D2608120832563359730"],
                ["22", "500mb-dia", "D2608120833048801100"],
                ["23", "500mb-dia", "D2608120833123602001"],
                ["24", "500mb-dia", "D2608120833202434466"],
                ["25", "500mb-dia", "D2608120833277633020"],
                ["26", "500mb-dia", "D2608120833358490467"],
                ["27", "500mb-dia", "D2608120833451704352"],
                ["28", "500mb-dia", "D2608120833538513160"],
                ["29", "500mb-dia", "D2608120834027040314"],
                ["30", "500mb-dia", "D2608120834148195875"],
                ["31", "500mb-dia", "D2608120834241163973"],
                ["2", "1gb", "D2608180320376277181"],
                ["3", "1gb", "D2608180320268169844"],
                ["4", "1gb", "D2608180319440880974"],
                ["5", "1gb", "D2608120842147808605"],
                ["6", "1gb", "D2608120842535956609"],
                ["7", "1gb", "D2608120843014178753"],
                ["8", "1gb", "D2608120843102879899"],
                ["9", "1gb", "D2608120843186362921"],
                ["10", "1gb", "D2608120843276014904"],
                ["11", "1gb", "D2608120843353755631"],
                ["12", "1gb", "D2608120843431725268"],
                ["13", "1gb", "D2608120843509770803"],
                ["14", "1gb", "D2608120843581912410"],
                ["15", "1gb", "D2608120844080333813"],
                ["16", "1gb", "D2608120844163792052"],
                ["17", "1gb", "D2608120844238866422"],
                ["18", "1gb", "D2608120844338458881"],
                ["19", "1gb", "D2608120844424757483"],
                ["20", "1gb", "D2608120844498516216"],
                ["21", "1gb", "D2608120844572856348"],
                ["22", "1gb", "D2608120845065062324"],
                ["23", "1gb", "D2608120845151815020"],
                ["24", "1gb", "D2608120845222470767"],
                ["25", "1gb", "D2608120845295704158"],
                ["26", "1gb", "D2608120845374156634"],
                ["27", "1gb", "D2608120845583571431"],
                ["28", "1gb", "D2608120846107447013"],
                ["29", "1gb", "D2608120858527853066"],
                ["30", "1gb", "D2608120859099345745"],
                ["31", "1gb", "D2608120859227892387"],
                ["2", "ilimitado", "D2608180223260232710"],
                ["3", "ilimitado", "D2608180223136229129"],
                ["4", "ilimitado", "D2608180223012396692"],
                ["5", "ilimitado", "D2608120815100561433"],
                ["6", "ilimitado", "D2608180224229064969"],
                ["7", "ilimitado", "D2608120815309021243"],
                ["8", "ilimitado", "D2608180224464219546"],
                ["9", "ilimitado", "D2608180225087781926"],
                ["10", "ilimitado", "D2608120815410946699"],
                ["11", "ilimitado", "D2608180225294421863"],
                ["12", "ilimitado", "D2608120815507330627"],
                ["13", "ilimitado", "D2608180225512303203"],
                ["14", "ilimitado", "D2608180226032956132"],
                ["15", "ilimitado", "D2608120816031511310"],
                ["16", "ilimitado", "D2608180226364513935"],
                ["17", "ilimitado", "D2608180226505631640"],
                ["18", "ilimitado", "D2608180227051159312"],
                ["19", "ilimitado", "D2608180227191744102"],
                ["20", "ilimitado", "D2608120816116868874"],
                ["21", "ilimitado", "D2608180228025446382"],
                ["22", "ilimitado", "D2608180228160228349"],
                ["23", "ilimitado", "D2608180228277865658"],
                ["24", "ilimitado", "D2608180228446147598"],
                ["25", "ilimitado", "D2608180228582913213"],
                ["26", "ilimitado", "D2608180229162000802"],
                ["27", "ilimitado", "D2608180229299309314"],
                ["28", "ilimitado", "D2608180229445469347"],
                ["29", "ilimitado", "D2608180229590016013"],
                ["30", "ilimitado", "D2608120816197750293"],
                ["31", "ilimitado", "D2608180438045656259"],
            ],
            "list_cmhk_north_america": [
                ["2", "500mb-dia", "D2608180429433836835"],
                ["3", "500mb-dia", "D2608180429005772609"],
                ["4", "500mb-dia", "D2608180428475432827"],
                ["5", "500mb-dia", "D2608120912230560623"],
                ["6", "500mb-dia", "D2608120912410265975"],
                ["7", "500mb-dia", "D2608120912528075183"],
                ["8", "500mb-dia", "D2608120913042183941"],
                ["9", "500mb-dia", "D2608120913147430363"],
                ["10", "500mb-dia", "D2608120913270003660"],
                ["11", "500mb-dia", "D2608120913379744098"],
                ["12", "500mb-dia", "D2608120913482459801"],
                ["13", "500mb-dia", "D2608120913595826116"],
                ["14", "500mb-dia", "D2608120914146595001"],
                ["15", "500mb-dia", "D2608120914282308329"],
                ["16", "500mb-dia", "D2608120914389830061"],
                ["17", "500mb-dia", "D2608120914577162678"],
                ["18", "500mb-dia", "D2608120915086887257"],
                ["19", "500mb-dia", "D2608120915195575147"],
                ["20", "500mb-dia", "D2608120915337633293"],
                ["21", "500mb-dia", "D2608120915464401272"],
                ["22", "500mb-dia", "D2608120916040235616"],
                ["23", "500mb-dia", "D2608120916158246614"],
                ["24", "500mb-dia", "D2608120916264515345"],
                ["25", "500mb-dia", "D2608120916400417889"],
                ["26", "500mb-dia", "D2608120916521949794"],
                ["27", "500mb-dia", "D2608120917047689397"],
                ["28", "500mb-dia", "D2608120917186333143"],
                ["29", "500mb-dia", "D2608120917326212733"],
                ["30", "500mb-dia", "D2608120917459922839"],
                ["31", "500mb-dia", "D2608120918022049750"],
                ["2", "1gb", "D2608180431326457662"],
                ["3", "1gb", "D2608180431179433763"],
                ["4", "1gb", "D2608180430482233585"],
                ["5", "1gb", "D2608120922487995701"],
                ["6", "1gb", "D2608120923280792831"],
                ["7", "1gb", "D2608120923498726995"],
                ["8", "1gb", "D2608120924038180092"],
                ["9", "1gb", "D2608120924181177088"],
                ["10", "1gb", "D2608120924376077247"],
                ["11", "1gb", "D2608120924499659991"],
                ["12", "1gb", "D2608120925025330887"],
                ["13", "1gb", "D2608120925202294137"],
                ["14", "1gb", "D2608120925318416620"],
                ["15", "1gb", "D2608120925443090422"],
                ["16", "1gb", "D2608120925560827420"],
                ["17", "1gb", "D2608120926076365864"],
                ["18", "1gb", "D2608120926200810580"],
                ["19", "1gb", "D2608120926324335009"],
                ["20", "1gb", "D2608120926450985572"],
                ["21", "1gb", "D2608120927008428732"],
                ["22", "1gb", "D2608120927132235323"],
                ["23", "1gb", "D2608120927267676433"],
                ["24", "1gb", "D2608120927398260789"],
                ["25", "1gb", "D2608120927517921926"],
                ["26", "1gb", "D2608120928030749031"],
                ["27", "1gb", "D2608120928145519773"],
                ["28", "1gb", "D2608120928245582373"],
                ["29", "1gb", "D2608120928448369355"],
                ["30", "1gb", "D2608120928563278527"],
                ["31", "1gb", "D2608120929132526249"],
                ["2", "ilimitado", "D2608180440254556065"],
                ["3", "ilimitado", "D2608180440145314932"],
                ["4", "ilimitado", "D2608180439597623667"],
                ["5", "ilimitado", "D2608120908516953557"],
                ["6", "ilimitado", "D2608180439360337554"],
                ["7", "ilimitado", "D2608120909272574773"],
                ["8", "ilimitado", "D2608180441193108445"],
                ["9", "ilimitado", "D2608180441310255780"],
                ["10", "ilimitado", "D2608120909384961368"],
                ["11", "ilimitado", "D2608180441563354777"],
                ["12", "ilimitado", "D2608120909505404440"],
                ["13", "ilimitado", "D2608180442185184735"],
                ["14", "ilimitado", "D2608180442379656636"],
                ["15", "ilimitado", "D2608120909590799704"],
                ["16", "ilimitado", "D2608180442579595053"],
                ["17", "ilimitado", "D2608180443107863021"],
                ["18", "ilimitado", "D2608180443268110502"],
                ["19", "ilimitado", "D2608180443405684039"],
                ["20", "ilimitado", "D2608120910087120834"],
                ["21", "ilimitado", "D2608180444242342857"],
                ["22", "ilimitado", "D2608180445388825581"],
                ["23", "ilimitado", "D2608180445559778748"],
                ["24", "ilimitado", "D2608180446152087838"],
                ["25", "ilimitado", "D2608180446275238413"],
                ["26", "ilimitado", "D2608180446434230397"],
                ["27", "ilimitado", "D2608180447018656049"],
                ["28", "ilimitado", "D2608180447141445245"],
                ["29", "ilimitado", "D2608180447282266005"],
                ["30", "ilimitado", "D2608120910212831833"],
                ["31", "ilimitado", "D2608180448261140605"],
            ],
            "list_cmhk_africa": [
                ["2", "500mb-dia", "D2608180515362822599"],
                ["3", "500mb-dia", "D2608180515239839862"],
                ["4", "500mb-dia", "D2608180515049714293"],
                ["5", "500mb-dia", "D2608140338450832489"],
                ["6", "500mb-dia", "D2608140339127434141"],
                ["7", "500mb-dia", "D2608140339287432001"],
                ["8", "500mb-dia", "D2608140339416140951"],
                ["9", "500mb-dia", "D2608140339591830531"],
                ["10", "500mb-dia", "D2608140340171115370"],
                ["11", "500mb-dia", "D2608140340313382067"],
                ["12", "500mb-dia", "D2608140340436030857"],
                ["13", "500mb-dia", "D2608140340558860847"],
                ["14", "500mb-dia", "D2608140341101526258"],
                ["15", "500mb-dia", "D2608140341242284883"],
                ["16", "500mb-dia", "D2608140341395271850"],
                ["17", "500mb-dia", "D2608140341564755238"],
                ["18", "500mb-dia", "D2608140342104935802"],
                ["19", "500mb-dia", "D2608140342224950133"],
                ["20", "500mb-dia", "D2608140342381781233"],
                ["21", "500mb-dia", "D2608140342507594137"],
                ["22", "500mb-dia", "D2608140343032476981"],
                ["23", "500mb-dia", "D2608140343204822490"],
                ["24", "500mb-dia", "D2608140343350905354"],
                ["25", "500mb-dia", "D2608140343502871597"],
                ["26", "500mb-dia", "D2608140344083568594"],
                ["27", "500mb-dia", "D2608140344198395885"],
                ["28", "500mb-dia", "D2608140344327377374"],
                ["29", "500mb-dia", "D2608140344451955470"],
                ["30", "500mb-dia", "D2608140344578925407"],
                ["31", "500mb-dia", "D2608140345118607342"],
                ["2", "1gb", "D2608180517091204783"],
                ["3", "1gb", "D2608180516581390914"],
                ["4", "1gb", "D2608180516436171400"],
                ["5", "1gb", "D2608140346215461647"],
                ["6", "1gb", "D2608140347014912842"],
                ["7", "1gb", "D2608140347143362349"],
                ["8", "1gb", "D2608140347278401868"],
                ["9", "1gb", "D2608140347406816152"],
                ["10", "1gb", "D2608140347540639661"],
                ["11", "1gb", "D2608140348123341715"],
                ["12", "1gb", "D2608140348246248666"],
                ["13", "1gb", "D2608140348390311174"],
                ["14", "1gb", "D2608140348506490935"],
                ["15", "1gb", "D2608142232053784436"],
                ["16", "1gb", "D2608142232188367257"],
                ["17", "1gb", "D2608142232349081654"],
                ["18", "1gb", "D2608142232597598620"],
                ["19", "1gb", "D2608142233234615515"],
                ["20", "1gb", "D2608142233367141272"],
                ["21", "1gb", "D2608142233512062899"],
                ["22", "1gb", "D2608142234032542945"],
                ["23", "1gb", "D2608142234155861729"],
                ["24", "1gb", "D2608142234362225521"],
                ["25", "1gb", "D2608142234491237401"],
                ["26", "1gb", "D2608142235027419433"],
                ["27", "1gb", "D2608142235168108033"],
                ["28", "1gb", "D2608142235317530457"],
                ["29", "1gb", "D2608142235438450376"],
                ["30", "1gb", "D2608142235561421605"],
                ["31", "1gb", "D2608142236099158712"],
                ["2", "ilimitado", "D2608180505573949030"],
                ["3", "ilimitado", "D2608180505437351079"],
                ["4", "ilimitado", "D2608180505324675242"],
                ["5", "ilimitado", "D2608140333227531606"],
                ["6", "ilimitado", "D2608180506589858882"],
                ["7", "ilimitado", "D2608140334012528877"],
                ["8", "ilimitado", "D2608180507217876048"],
                ["9", "ilimitado", "D2608180507410751501"],
                ["10", "ilimitado", "D2608140334130763486"],
                ["11", "ilimitado", "D2608180508034845165"],
                ["12", "ilimitado", "D2608140334265585703"],
                ["13", "ilimitado", "D2608180508502811965"],
                ["14", "ilimitado", "D2608180509135574366"],
                ["15", "ilimitado", "D2608140334402965319"],
                ["16", "ilimitado", "D2608180509379581396"],
                ["17", "ilimitado", "D2608180509570788303"],
                ["18", "ilimitado", "D2608180510094848299"],
                ["19", "ilimitado", "D2608180510235662408"],
                ["20", "ilimitado", "D2608140334546129835"],
                ["21", "ilimitado", "D2608180511054735144"],
                ["22", "ilimitado", "D2608180511175232924"],
                ["23", "ilimitado", "D2608180511295639483"],
                ["24", "ilimitado", "D2608180511414817226"],
                ["25", "ilimitado", "D2608180511541286186"],
                ["26", "ilimitado", "D2608180512079713055"],
                ["27", "ilimitado", "D2608180512208540632"],
                ["28", "ilimitado", "D2608180512331991163"],
                ["29", "ilimitado", "D2608180512458271133"],
                ["30", "ilimitado", "D2608140335093619962"],
                ["31", "ilimitado", "D2608180513008041629"],
            ],
            "list_cmhk_middle_east": [
                ["2", "500mb-dia", "D2608182310206032770"],
                ["3", "500mb-dia", "D2608182310086691643"],
                ["4", "500mb-dia", "D2608182309564710704"],
                ["5", "500mb-dia", "D2608142253476338106"],
                ["6", "500mb-dia", "D2608142254089146203"],
                ["7", "500mb-dia", "D2608142254274509455"],
                ["8", "500mb-dia", "D2608142254416205688"],
                ["9", "500mb-dia", "D2608142254539636475"],
                ["10", "500mb-dia", "D2608142255063801065"],
                ["11", "500mb-dia", "D2608142255186061594"],
                ["12", "500mb-dia", "D2608142255393502888"],
                ["13", "500mb-dia", "D2608142255497733664"],
                ["14", "500mb-dia", "D2608142256005789501"],
                ["15", "500mb-dia", "D2608142256136142108"],
                ["16", "500mb-dia", "D2608142256334109088"],
                ["17", "500mb-dia", "D2608142256457448914"],
                ["18", "500mb-dia", "D2608142256561305081"],
                ["19", "500mb-dia", "D2608142257071991709"],
                ["20", "500mb-dia", "D2608142257205783530"],
                ["21", "500mb-dia", "D2608142257329711134"],
                ["22", "500mb-dia", "D2608142257445430132"],
                ["23", "500mb-dia", "D2608142257560550132"],
                ["24", "500mb-dia", "D2608142258074947006"],
                ["25", "500mb-dia", "D2608142258188412416"],
                ["26", "500mb-dia", "D2608142258342947121"],
                ["27", "500mb-dia", "D2608142258497984405"],
                ["28", "500mb-dia", "D2608142259018772009"],
                ["29", "500mb-dia", "D2608142259146283587"],
                ["30", "500mb-dia", "D2608142259318585195"],
                ["31", "500mb-dia", "D2608142259466832807"],
                ["2", "1gb", "D2608182312389249756"],
                ["3", "1gb", "D2608182311586128574"],
                ["4", "1gb", "D2608182311361282239"],
                ["5", "1gb", "D2608142301133467200"],
                ["6", "1gb", "D2608142301567310120"],
                ["7", "1gb", "D2608142302109021124"],
                ["8", "1gb", "D2608142302241490370"],
                ["9", "1gb", "D2608142302369162037"],
                ["10", "1gb", "D2608142302496297759"],
                ["11", "1gb", "D2608142303077315207"],
                ["12", "1gb", "D2608142303234340367"],
                ["13", "1gb", "D2608142303353732562"],
                ["14", "1gb", "D2608142305083633641"],
                ["15", "1gb", "D2608142305223786868"],
                ["16", "1gb", "D2608142305465461609"],
                ["17", "1gb", "D2608142305578612814"],
                ["18", "1gb", "D2608142306094859903"],
                ["19", "1gb", "D2608142306202485251"],
                ["20", "1gb", "D2608142306322958891"],
                ["21", "1gb", "D2608142306446877415"],
                ["22", "1gb", "D2608142306575101756"],
                ["23", "1gb", "D2608142307085349677"],
                ["24", "1gb", "D2608142307210007827"],
                ["25", "1gb", "D2608142307315893781"],
                ["26", "1gb", "D2608142307430664302"],
                ["27", "1gb", "D2608142307577566511"],
                ["28", "1gb", "D2608142308108768412"],
                ["29", "1gb", "D2608142308223527028"],
                ["30", "1gb", "D2608142308346859419"],
                ["31", "1gb", "D2608142308484963245"],
                ["2", "ilimitado", "D2608182147002160853"],
                ["3", "ilimitado", "D2608182146490710083"],
                ["4", "ilimitado", "D2608142249074632089"],
                ["5", "ilimitado", "D2608142249074632089"],
                ["6", "ilimitado", "D2608182147545940091"],
                ["7", "ilimitado", "D2608142249394138828"],
                ["8", "ilimitado", "D2608182148149069086"],
                ["9", "ilimitado", "D2608182148273989372"],
                ["10", "ilimitado", "D2608142249502825765"],
                ["11", "ilimitado", "D2608182149082811023"],
                ["12", "ilimitado", "D2608142249588309345"],
                ["13", "ilimitado", "D2608182149370315200"],
                ["14", "ilimitado", "D2608182149574212066"],
                ["15", "ilimitado", "D2608142250089374950"],
                ["16", "ilimitado", "D2608182150320297113"],
                ["17", "ilimitado", "D2608182151020293499"],
                ["18", "ilimitado", "D2608182151276987452"],
                ["19", "ilimitado", "D2608182151475948948"],
                ["20", "ilimitado", "D2608142250215385041"],
                ["21", "ilimitado", "D2608182152076581364"],
                ["22", "ilimitado", "D2608182152490865366"],
                ["23", "ilimitado", "D2608182153227704522"],
                ["24", "ilimitado", "D2608182153416197060"],
                ["25", "ilimitado", "D2608182153578287473"],
                ["26", "ilimitado", "D2608182154188997471"],
                ["27", "ilimitado", "D2608182154386727896"],
                ["28", "ilimitado", "D2608182154564389994"],
                ["29", "ilimitado", "D2608182155193045548"],
                ["30", "ilimitado", "D2608142250343877479"],
                ["31", "ilimitado", "D2608182155397837418"],
            ],
            "list_cmhk_oceania": [
                ["2", "500mb-dia", "D2608182349312759763"],
                ["3", "500mb-dia", "D2608182349180627592"],
                ["4", "500mb-dia", "D2608182348105081051"],
                ["5", "500mb-dia", "D2608142337256637707"],
                ["6", "500mb-dia", "D2608142338159392964"],
                ["7", "500mb-dia", "D2608142338299467323"],
                ["8", "500mb-dia", "D2608142338453522118"],
                ["9", "500mb-dia", "D2608142339016827422"],
                ["10", "500mb-dia", "D2608142339167396653"],
                ["11", "500mb-dia", "D2608142352585361391"],
                ["12", "500mb-dia", "D2608142353238496063"],
                ["13", "500mb-dia", "D2608142353358396958"],
                ["14", "500mb-dia", "D2608142353489536982"],
                ["15", "500mb-dia", "D2608142354000517311"],
                ["16", "500mb-dia", "D2608142354131901001"],
                ["17", "500mb-dia", "D2608142354259845825"],
                ["18", "500mb-dia", "D2608142355352880038"],
                ["19", "500mb-dia", "D2608142355554388893"],
                ["20", "500mb-dia", "D2608142356093243492"],
                ["21", "500mb-dia", "D2608142356215240748"],
                ["22", "500mb-dia", "D2608142356470371923"],
                ["23", "500mb-dia", "D2608142356594799577"],
                ["24", "500mb-dia", "D2608142357115152492"],
                ["25", "500mb-dia", "D2608142357230682614"],
                ["26", "500mb-dia", "D2608142357406287669"],
                ["27", "500mb-dia", "D2608142357520386832"],
                ["28", "500mb-dia", "D2608142358029234495"],
                ["29", "500mb-dia", "D2608150000089157186"],
                ["30", "500mb-dia", "D2608150000222842687"],
                ["31", "500mb-dia", "D2608150000335872021"],
                ["2", "1gb", "D2608182351020382569"],
                ["3", "1gb", "D2608182350499927437"],
                ["4", "1gb", "D2608182350347234392"],
                ["5", "1gb", "D2608150001543095343"],
                ["6", "1gb", "D2608150002220016335"],
                ["7", "1gb", "D2608150002347543576"],
                ["8", "1gb", "D2608150002467134717"],
                ["9", "1gb", "D2608150002587106981"],
                ["10", "1gb", "D2608150003137250313"],
                ["11", "1gb", "D2608150003257192999"],
                ["12", "1gb", "D2608150003416048311"],
                ["13", "1gb", "D2608150003570388304"],
                ["14", "1gb", "D2608150004082093941"],
                ["15", "1gb", "D2608150004242607788"],
                ["16", "1gb", "D2608150004389543503"],
                ["17", "1gb", "D2608150005042059755"],
                ["18", "1gb", "D2608150005213671671"],
                ["19", "1gb", "D2608150005391009173"],
                ["20", "1gb", "D2608150005522979974"],
                ["21", "1gb", "D2608150006092083764"],
                ["22", "1gb", "D2608150006227629598"],
                ["23", "1gb", "D2608150006367583566"],
                ["24", "1gb", "D2608150006486926009"],
                ["25", "1gb", "D2608150007029404289"],
                ["26", "1gb", "D2608150007150728636"],
                ["27", "1gb", "D2608150007275012196"],
                ["28", "1gb", "D2608150007401536755"],
                ["29", "1gb", "D2608150007538632889"],
                ["30", "1gb", "D2608150008089915671"],
                ["31", "1gb", "D2608150008220094815"],
                ["2", "ilimitado", "D2608182328207486914"],
                ["3", "ilimitado", "D2608182328100699234"],
                ["4", "ilimitado", "D2608182327584707939"],
                ["5", "ilimitado", "D2608142325403268221"],
                ["6", "ilimitado", "D2608182329170138254"],
                ["7", "ilimitado", "D2608142326107821613"],
                ["8", "ilimitado", "D2608182329377126941"],
                ["9", "ilimitado", "D2608182329583150400"],
                ["10", "ilimitado", "D2608142326238197895"],
                ["11", "ilimitado", "D2608182330107908693"],
                ["12", "ilimitado", "D2608142326358617748"],
                ["13", "ilimitado", "D2608182331045876066"],
                ["14", "ilimitado", "D2608182331163302141"],
                ["15", "ilimitado", "D2608142326495100416"],
                ["16", "ilimitado", "D2608182331517940167"],
                ["17", "ilimitado", "D2608182332041889388"],
                ["18", "ilimitado", "D2608182332171811710"],
                ["19", "ilimitado", "D2608182332297794784"],
                ["20", "ilimitado", "D2608142327202456738"],
                ["21", "ilimitado", "D2608182333189483235"],
                ["22", "ilimitado", "D2608182333354540420"],
                ["23", "ilimitado", "D2608182333490639055"],
                ["24", "ilimitado", "D2608182334042036653"],
                ["25", "ilimitado", "D2608182334242602757"],
                ["26", "ilimitado", "D2608182334430998678"],
                ["27", "ilimitado", "D2608182335013579198"],
                ["28", "ilimitado", "D2608182335192813428"],
                ["29", "ilimitado", "D2608182335331934770"],
                ["30", "ilimitado", "D2608142327335514916"],
                ["31", "ilimitado", "D2608182327283947623"],
            ],
            "list_cmhk_central_america": [
                ["2", "500mb-dia", "D2608190037262234920"],
                ["3", "500mb-dia", "D2608190037150927977"],
                ["4", "500mb-dia", "D2608190036566025172"],
                ["5", "500mb-dia", "D2608150039396574490"],
                ["6", "500mb-dia", "D2608150040064489752"],
                ["7", "500mb-dia", "D2608150040254081589"],
                ["8", "500mb-dia", "D2608150040403447081"],
                ["9", "500mb-dia", "D2608150040535483211"],
                ["10", "500mb-dia", "D2608150041077506343"],
                ["11", "500mb-dia", "D2608150041256892084"],
                ["12", "500mb-dia", "D2608150041382605965"],
                ["13", "500mb-dia", "D2608150041508969946"],
                ["14", "500mb-dia", "D2608150042084595913"],
                ["15", "500mb-dia", "D2608150042529212977"],
                ["16", "500mb-dia", "D2608150043062677960"],
                ["17", "500mb-dia", "D2608150043215055955"],
                ["18", "500mb-dia", "D2608150043367549808"],
                ["19", "500mb-dia", "D2608150043525247657"],
                ["20", "500mb-dia", "D2608150044138141482"],
                ["21", "500mb-dia", "D2608150044273408071"],
                ["22", "500mb-dia", "D2608150044435754321"],
                ["23", "500mb-dia", "D2608150045026778510"],
                ["24", "500mb-dia", "D2608150045149097482"],
                ["25", "500mb-dia", "D2608150045320368945"],
                ["26", "500mb-dia", "D2608150045503204278"],
                ["27", "500mb-dia", "D2608150046094647649"],
                ["28", "500mb-dia", "D2608150046240192639"],
                ["29", "500mb-dia", "D2608150046424557189"],
                ["30", "500mb-dia", "D2608150046559651870"],
                ["31", "500mb-dia", "D2608150047098898880"],
                ["2", "1gb", "D2608190039080249269"],
                ["3", "1gb", "D2608190038567070652"],
                ["4", "1gb", "D2608190038341658749"],
                ["5", "1gb", "D2608150050037871823"],
                ["6", "1gb", "D2608150050495334295"],
                ["7", "1gb", "D2608150051038640089"],
                ["8", "1gb", "D2608150051167832435"],
                ["9", "1gb", "D2608150051384016154"],
                ["10", "1gb", "D2608150051574729619"],
                ["11", "1gb", "D2608150052172229521"],
                ["12", "1gb", "D2608150052303566334"],
                ["13", "1gb", "D2608150052518543612"],
                ["14", "1gb", "D2608150053056945703"],
                ["15", "1gb", "D2608150053234707506"],
                ["16", "1gb", "D2608150053393556501"],
                ["17", "1gb", "D2608150053560892400"],
                ["18", "1gb", "D2608150054140607753"],
                ["19", "1gb", "D2608150054298421567"],
                ["20", "1gb", "D2608150054435655292"],
                ["21", "1gb", "D2608150055007987289"],
                ["22", "1gb", "D2608150055215633441"],
                ["23", "1gb", "D2608150055454852005"],
                ["24", "1gb", "D2608150055586459409"],
                ["25", "1gb", "D2608150056114322000"],
                ["26", "1gb", "D2608150056275898841"],
                ["27", "1gb", "D2608150056454100763"],
                ["28", "1gb", "D2608150057019178540"],
                ["29", "1gb", "D2608150057155588459"],
                ["30", "1gb", "D2608150057299045035"],
                ["31", "1gb", "D2608150057478668994"],
                ["2", "ilimitado", "D2608190013589141564"],
                ["3", "ilimitado", "D2608190013460723204"],
                ["4", "ilimitado", "D2608190013342883906"],
                ["5", "ilimitado", "D2608150033037912854"],
                ["6", "ilimitado", "D2608190015069486493"],
                ["7", "ilimitado", "D2608150035089699970"],
                ["8", "ilimitado", "D2608190015283245857"],
                ["9", "ilimitado", "D2608190015436175419"],
                ["10", "ilimitado", "D2608150035329773565"],
                ["11", "ilimitado", "D2608190016123469902"],
                ["12", "ilimitado", "D2608150035451367526"],
                ["13", "ilimitado", "D2608190016333978672"],
                ["14", "ilimitado", "D2608190016451768101"],
                ["15", "ilimitado", "D2608150036013206272"],
                ["16", "ilimitado", "D2608190017254653203"],
                ["17", "ilimitado", "D2608190017518731582"],
                ["18", "ilimitado", "D2608190018138573849"],
                ["19", "ilimitado", "D2608190018376408633"],
                ["20", "ilimitado", "D2608150036236873902"],
                ["21", "ilimitado", "D2608190019055170206"],
                ["22", "ilimitado", "D2608190019286061956"],
                ["23", "ilimitado", "D2608190019412314309"],
                ["24", "ilimitado", "D2608190019557034899"],
                ["25", "ilimitado", "D2608190020153326563"],
                ["26", "ilimitado", "D2608190020277080911"],
                ["27", "ilimitado", "D2608190020406202762"],
                ["28", "ilimitado", "D2608190021004781038"],
                ["29", "ilimitado", "D2608190021139311710"],
                ["30", "ilimitado", "D2608150036385833000"],
                ["31", "ilimitado", "D2608190021301690489"],
            ],
            "list_cmhk_global": [
                ["2", "500mb-dia", "D2608190123211486720"],
                ["3", "500mb-dia", "D2608190123391843059"],
                ["4", "500mb-dia", "D2608190124146989659"],
                ["5", "500mb-dia", "D2608190124290231418"],
                ["6", "500mb-dia", "D2608190124452927771"],
                ["7", "500mb-dia", "D2608190125040655305"],
                ["8", "500mb-dia", "D2608190125203384598"],
                ["9", "500mb-dia", "D2608190125427376521"],
                ["10", "500mb-dia", "D2608190126037249721"],
                ["11", "500mb-dia", "D2608190126204737918"],
                ["12", "500mb-dia", "D2608190126339699102"],
                ["13", "500mb-dia", "D2608190126461452265"],
                ["14", "500mb-dia", "D2608190127001141718"],
                ["15", "500mb-dia", "D2608190127155751262"],
                ["16", "500mb-dia", "D2608190127304161080"],
                ["17", "500mb-dia", "D2608190127523699251"],
                ["18", "500mb-dia", "D2608190128216481109"],
                ["19", "500mb-dia", "D2608190128445886370"],
                ["20", "500mb-dia", "D2608190128598325055"],
                ["21", "500mb-dia", "D2608190129141457640"],
                ["22", "500mb-dia", "D2608190129285149925"],
                ["23", "500mb-dia", "D2608190129427319551"],
                ["24", "500mb-dia", "D2608190129576730221"],
                ["25", "500mb-dia", "D2608190130180954551"],
                ["26", "500mb-dia", "D2608190130335142575"],
                ["27", "500mb-dia", "D2608190130489121831"],
                ["28", "500mb-dia", "D2608190131035176383"],
                ["29", "500mb-dia", "D2608190131187639467"],
                ["30", "500mb-dia", "D2608190131395865699"],
                ["31", "500mb-dia", "D2608190131551631315"],
                ["2", "1gb", "D2608190138190814524"],
                ["3", "1gb", "D2608190138398056038"],
                ["4", "1gb", "D2608190138537185905"],
                ["5", "1gb", "D2608190139068010083"],
                ["6", "1gb", "D2608190139249859961"],
                ["7", "1gb", "D2608190139470129273"],
                ["8", "1gb", "D2608190140170973239"],
                ["9", "1gb", "D2608190140544328332"],
                ["10", "1gb", "D2608190141139757047"],
                ["11", "1gb", "D2608190141270449161"],
                ["12", "1gb", "D2608190141420290701"],
                ["13", "1gb", "D2608190141550945281"],
                ["14", "1gb", "D2608190142185262794"],
                ["15", "1gb", "D2608190142333894462"],
                ["16", "1gb", "D2608190142471862476"],
                ["17", "1gb", "D2608190143043694027"],
                ["18", "1gb", "D2608190143230741901"],
                ["19", "1gb", "D2608190143475182106"],
                ["20", "1gb", "D2608190144037863024"],
                ["21", "1gb", "D2608190144210245892"],
                ["22", "1gb", "D2608190144366175167"],
                ["23", "1gb", "D2608190144518606704"],
                ["24", "1gb", "D2608190145061620267"],
                ["25", "1gb", "D2608190145295256088"],
                ["26", "1gb", "D2608190145457099809"],
                ["27", "1gb", "D2608190146022999636"],
                ["28", "1gb", "D2608190146320156339"],
                ["29", "1gb", "D2608190146483429569"],
                ["30", "1gb", "D2608190147035914306"],
                ["31", "1gb", "D2608190147198537026"],
                ["2", "ilimitado", "D2608190102379218701"],
                ["3", "ilimitado", "D2608190102500461899"],
                ["4", "ilimitado", "D2608190103029367908"],
                ["5", "ilimitado", "D2608190103149759229"],
                ["6", "ilimitado", "D2608190103281340774"],
                ["7", "ilimitado", "D2608190103450120707"],
                ["8", "ilimitado", "D2608190103584433560"],
                ["9", "ilimitado", "D2608190104152678324"],
                ["10", "ilimitado", "D2608190104328819253"],
                ["11", "ilimitado", "D2608190105272701713"],
                ["12", "ilimitado", "D2608190105452575019"],
                ["13", "ilimitado", "D2608190105577067373"],
                ["14", "ilimitado", "D2608190106124556533"],
                ["15", "ilimitado", "D2608190107119957371"],
                ["16", "ilimitado", "D2608190107275610937"],
                ["17", "ilimitado", "D2608190107430535087"],
                ["18", "ilimitado", "D2608190108005999647"],
                ["19", "ilimitado", "D2608190108230977273"],
                ["20", "ilimitado", "D2608190108444256379"],
                ["21", "ilimitado", "D2608190109016814375"],
                ["22", "ilimitado", "D2608190109228628192"],
                ["23", "ilimitado", "D2608190109376994641"],
                ["24", "ilimitado", "D2608190109558837098"],
                ["25", "ilimitado", "D2608190110177613424"],
                ["26", "ilimitado", "D2608190110337751573"],
                ["27", "ilimitado", "D2608190111416582610"],
                ["28", "ilimitado", "D2608190111596477601"],
                ["29", "ilimitado", "D2608190112219043457"],
                ["30", "ilimitado", "D2608190112366733189"],
                ["31", "ilimitado", "D2608190112532483138"],
            ],
            "list_cmhk_eua_premium": [
                ["2", "500mb-dia", "D2608200154347598265"],
                ["3", "500mb-dia", "D2608200154502453593"],
                ["4", "500mb-dia", "D2608200155025413354"],
                ["5", "500mb-dia", "D2608200155175857422"],
                ["6", "500mb-dia", "D2608200155287211579"],
                ["7", "500mb-dia", "D2608200155395335306"],
                ["8", "500mb-dia", "D2608200156263820785"],
                ["9", "500mb-dia", "D2608200156388351962"],
                ["10", "500mb-dia", "D2608200156530746828"],
                ["11", "500mb-dia", "D2608200157079072609"],
                ["12", "500mb-dia", "D2608200157213978967"],
                ["13", "500mb-dia", "D2608200157346474060"],
                ["14", "500mb-dia", "D2608200157533978153"],
                ["15", "500mb-dia", "D2608200158137154151"],
                ["16", "500mb-dia", "D2608200158302289934"],
                ["17", "500mb-dia", "D2608200158478286107"],
                ["18", "500mb-dia", "D2608200159032408451"],
                ["19", "500mb-dia", "D2608200159192691772"],
                ["20", "500mb-dia", "D2608200159353193903"],
                ["21", "500mb-dia", "D2608200159493994653"],
                ["22", "500mb-dia", "D2608200200030049970"],
                ["23", "500mb-dia", "D2608200200167300651"],
                ["24", "500mb-dia", "D2608200200300533314"],
                ["25", "500mb-dia", "D2608200200459463254"],
                ["26", "500mb-dia", "D2608200201033267210"],
                ["27", "500mb-dia", "D2608200201196268715"],
                ["28", "500mb-dia", "D2608200201342293483"],
                ["29", "500mb-dia", "D2608200201486552976"],
                ["30", "500mb-dia", "D2608200202068083962"],
                ["31", "500mb-dia", "D2608200202237285851"],
                ["2", "1gb", "D2608200209073858997"],
                ["3", "1gb", "D2608200209267251745"],
                ["4", "1gb", "D2608200209456117797"],
                ["5", "1gb", "D2608200209569396140"],
                ["6", "1gb", "D2608200210098191069"],
                ["7", "1gb", "D2608200210262395676"],
                ["8", "1gb", "D2608200210457194162"],
                ["9", "1gb", "D2608200210595789515"],
                ["10", "1gb", "D2608200211163050043"],
                ["11", "1gb", "D2608200212053395236"],
                ["12", "1gb", "D2608200212265120500"],
                ["13", "1gb", "D2608200212395228025"],
                ["14", "1gb", "D2608200212528236095"],
                ["15", "1gb", "D2608200213052317989"],
                ["16", "1gb", "D2608200213220297473"],
                ["17", "1gb", "D2608200213358069522"],
                ["18", "1gb", "D2608200213516059031"],
                ["19", "1gb", "D2608200214047753185"],
                ["20", "1gb", "D2608200214176890253"],
                ["21", "1gb", "D2608200214297002964"],
                ["22", "1gb", "D2608200214422167558"],
                ["23", "1gb", "D2608200215179090952"],
                ["24", "1gb", "D2608200215310796353"],
                ["25", "1gb", "D2608200215445136368"],
                ["26", "1gb", "D2608200215583073149"],
                ["27", "1gb", "D2608200216121604834"],
                ["28", "1gb", "D2608200216261341846"],
                ["29", "1gb", "D2608200216386258674"],
                ["30", "1gb", "D2608200216532263942"],
                ["31", "1gb", "D2608200217072275821"],
            ],
        }

        plan_list = lists.get(list_name)
        if not plan_list:
            return None

        day = str(day)
        data = str(data)
        for plan_day, plan_data, cod in plan_list:
            if plan_day == day and plan_data == data:
                return cod
        return None
        
