import http.client
import json
from django.conf import settings


class ApiTC:

    # Get tokem de acesso a API
    @staticmethod
    def get_token():
        payload_token = json.dumps({
            "username": settings.APITC_USERNAME,
            "password": settings.APITC_PASSWORD
        })
        headers_token = {
            'Content-Type': 'application/json',
            'X-Requested-With': 'XMLHttpRequest'
        }
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        conn.request("POST", "/api/login", payload_token, headers_token)
        res_token = conn.getresponse()
        data_token = json.loads(res_token.read())
        token_api = data_token["AccessToken"]
        print('>>>>>>>>>>>>>>>> token_api',token_api)
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
        return headers


    # Get EndPointID / Status
    @staticmethod
    def get_iccid(iccid, headers):
        payload_endpointId = ''
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
        conn.request(
            "GET", f"/api/fetchSIM?iccid={iccid}", payload_endpointId, headers)
        res_endpointId = conn.getresponse()
        data_endpointId = json.loads(res_endpointId.read())
        simStatus = data_endpointId["Response"]["responseParam"]["rows"][0]['simStatus']
        endpointId = data_endpointId["Response"]["responseParam"]["rows"][0]['endPointId']
        return endpointId, simStatus


    # Pl0an Change
    @staticmethod
    def planChange(endpointId,headers,dataDay):  
        planList = {
            '500mb-dia': '572960',
            '1gb': '572961',
            '2gb': '572963',
        }
        plan_list = json.loads(planList[dataDay])       
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
        return data_plan
    
class OperatorSelect():
    @staticmethod
    def opSel():
        # Plano / Operadora
        operSel = {
            '981': 'VR',
            '980': 'TM',
            '979': 'TC',
            '976': 'TC',
            '977': 'TM',
            '975': 'CM', 
            '974': 'TC', 
            '971': 'TC', 
        }
        return operSel
