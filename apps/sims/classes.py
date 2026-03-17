import base64
from datetime import datetime
import hashlib
import http.client
import json
import time
from urllib.parse import urlparse
from django.conf import settings
from django.core.cache import cache
import pytz
import requests

from apps.sims.models import Sims

    
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
            '977': 'TM',
            '975': 'CM', 
            '974': 'TC', #
            '971': 'TC', 
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
            '977': 'TM',
            '975': 'CM', 
            '4816': 'AR', #
            '971': 'TC', 
        } 
        return operSelESim

class ApiTC:

    # Get tokem de acesso a API
    @staticmethod
    def get_token():
        # Verificar token
        token_api = cache.get('api_tc_token')
        if token_api:
            return token_api

        time.sleep(0.5)        
        
        payload_token = json.dumps({
            "username": settings.APITC_USERNAME,
            "password": settings.APITC_PASSWORD
        })
        
        headers_token = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest',
        }
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        conn.request("POST", "/api/login", payload_token, headers_token)
        res_token = conn.getresponse()
        data_token = json.loads(res_token.read())
        token_api = data_token["AccessToken"]
        # Gravar token
        cache.set('api_tc_token', token_api, timeout=540)
        conn.close()
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
        time.sleep(0.5)
        payload_endpointId = ''
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        conn.request(
            "GET", f"/api/fetchSIM?iccid={iccid}", payload_endpointId, headers)
        res_endpointId = conn.getresponse()
        data_endpointId = json.loads(res_endpointId.read())
        simStatus = data_endpointId["Response"]["responseParam"]["rows"][0]['simStatus']
        endpointId = data_endpointId["Response"]["responseParam"]["rows"][0]['endPointId']
        conn.close()
        return endpointId, simStatus


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
            plan_list = next((item[2] for item in planList.get(product, []) if item[0] == day and item[1] == dataDay), None)      
            payload = json.dumps({
                "Request": {
                    "endPointId": endpointId,
                    "requestParam": {
                        "planId": plan_list
                    }
                }
            })    
            conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
            conn.request("POST", "/api/ChangePlan", payload, headers)
            res_plan = conn.getresponse()
            data_plan = res_plan.read()
            conn.close()       
        except KeyError:
            data_plan = 0
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
        

class ApiAR:
    @staticmethod
    def getToken():
        
        # Verificar token
        token_api = cache.get('api_ar_token')
        if token_api:
            return token_api
        
        url_api = f'{settings.APIAIRALO_URL}/token'

        payload_token = {
            "client_id": settings.APIAIRALO_CLIENT_ID,
            "client_secret": settings.APIAIRALO_CLIENT_SECRET,
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
    def selPlan(day, dataDay, product):
        
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
          
        # Verificar Planos    
        try:
            planListSel = next((item[2] for item in planList.get(product, []) if item[0] == day and item[1] == dataDay), None)            
        except KeyError:
            planListSel = 0
        return planListSel
    
    @staticmethod
    def addESimAR(iccid, qrcode):
        add_sim = Sims(
            sim = iccid,
            link = qrcode,
            type_sim = 'esim',
            operator = 'AR',
            sim_status = 'AT'
        )
        add_sim.save()        
        id_sim = add_sim.id
        return id_sim