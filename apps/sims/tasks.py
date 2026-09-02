import time
import logging
from celery import shared_task
from urllib.parse import urlparse
import http.client
import json
from django.conf import settings
import pytz

from .classes import (
    ApiCM,
    ApiCMHK,
    ApiTC,
    ApiAR,
    RateLimitExceeded,
    selectPlanCMHK,
    TM_ESIM_PADRAO_PK,
    ensure_tm_esim_padrao_lpa,
)
from apps.orders.models import Orders, Notes
from apps.orders.classes import NotesAdd, UpdateOrder, UpdateStore
from apps.sims.models import Sims
from datetime import datetime, timedelta
from django.utils import timezone
import pandas as pd
from django.core.exceptions import ObjectDoesNotExist
import requests
from django.core.cache import cache
from apps.send_email.tasks import send_email_sims
from core.celery_locks import periodic_task_lock

# Configurar logger para este módulo
logger = logging.getLogger('apps.sims')


@shared_task
def sims_in_orders():
    from apps.orders.tasks import orders_up_status

    orders = Orders.objects.filter(order_status='AS')
    logger.info(f'>>>>>>>>>> sims_in_orders iniciada — {orders.count()} pedido(s) AS')
    
    global n_item_total
    n_item_total = 0
    global msg_ord
    msg_info = []
    global msg_error
    msg_error = []
    
    for ord in orders:
        
        logger.info(f'>>>>>>>>>> Processando pedido {ord.order_id}')
        
        id_id_i = ord.id
        id_item_i = Orders.objects.get(pk=id_id_i)
        order_id_i = ord.order_id
        product_i = ord.product
        type_sim_i = ord.type_sim
        cell_imei = ord.cell_imei
        id_sim_i = id_item_i.id_sim
        esim_eua = type_sim_i == 'esim' and product_i == '001' # EUA Ilimitado
        
        # Se já houver SIM   
        if id_sim_i != None:
            if ord.order_status == 'AS':
                if esim_eua and cell_imei == None:
                    id_item_i.order_status = 'AI'
                else:
                    id_item_i.order_status = 'AA'
                id_item_i.save()
        else:    
            # Notes
            def addNote(t_note):
                add_sim = Notes( 
                    id_item = id_item_i,
                    note = t_note,
                    type_note = 'S',
                )
                add_sim.save()

            # Definir Operadora
            if type_sim_i == 'sim':        
                oper_sel_i = 'TM'
            else:
                oper_sel_i = 'CMHK'
                        
            # Select SIM
            if esim_eua:
                sim_ds = ensure_tm_esim_padrao_lpa(
                    Sims.objects.filter(pk=TM_ESIM_PADRAO_PK).first()
                )
                if not sim_ds:
                    addNote('SIM padrão TM (eSIM EUA) não encontrado')
                    continue
                addNote('eSIM EUA - SIM padrão adicionado')
            else:
                sim_ds = Sims.objects.all().order_by('id').filter(operator=oper_sel_i, type_sim=type_sim_i, sim_status='DS').first()
                if sim_ds:
                    pass
                else:
                    addNote('SIM indisponível ou fora de estoque')
                    order_put = Orders.objects.get(pk=id_id_i)
                    order_put.order_status = 'SE'
                    order_put.save()
                    continue
            
            # update order
            # Save SIMs
            if type_sim_i == 'esim' and not esim_eua:
                status_ord = 'AA'
                addNote('Alterado para Agd. Ativação')
            elif esim_eua: 
                status_ord = 'AI'
                addNote('Aguardando IMEI')
            elif type_sim_i == 'sim': status_ord = 'ES'
            
            order_put = Orders.objects.get(pk=id_id_i)
            order_put.id_sim = sim_ds
            order_put.order_status = status_ord
            order_put.save()
            
            # Verification esim x eua
            if not esim_eua:           
                # update sim
                sim_put = sim_ds
                sim_put.sim_status = 'AT'
                sim_put.save()
                _sim = sim_put.sim
                addNote(f'(e)SIM {_sim} adicionado')
            
            # Atualizar pedido no site
                        
            orders_up_status.delay(id_id_i, status_ord)
            
            n_item_total += 1
    

@shared_task
@periodic_task_lock(timeout=140)
def simActivateTC(id=None):
    from apps.orders.tasks import orders_up_status
    
    # dia anterior
    tz = pytz.timezone(settings.TIME_ZONE)
    today = datetime.now(tz).date()
    tomorrow = today +timedelta(days=1)

    logger.info(f'>>>>>>>>>> ATIVAÇÂO TC INICIADA')
    
    # Selecionar pedidos
    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim__operator='TC', activation_date__lte=tomorrow)
    else:
        orders_all = Orders.objects.filter(pk=id)
            
    # Checar conexão com API
    def error_api():
        logger.info(f'>>>>>>>>>> ERRO API')
        # Checar Status
        UpdateOrder.upStatus(id_item,'EA')
        # Adicionar nota
        NotesAdd.addNote(order,f'ERRO API: {iccid} com erro na Telcon. Verificar erro.')
        error = 'error_apiResult'
        return error
    
    try:
        token_api = ApiTC.get_token()
    except Exception as e:
        logger.error(f'>>>>>>>>>> ERRO ao obter token TC: {e}', exc_info=True)
        return

    time.sleep(0.5)
    headers = ApiTC.get_headers(token_api)

    for order in orders_all:
        conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
                        
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        logger.info(f'>>>>>>>>>> TC - Processando pedido {order_id}')
        id_item = order.id
        try:
            iccid = order.id_sim.sim
        except Exception:
            logger.warning(f'Pedido {order_id} sem SIM associado. Pulando.')
            continue
        day = order.days
        dataDay = order.data_day
        product = order.product
        # Variaveis globais        
        endpointId = None
        simStatus = None
        note = ''
        process = False
                
        # Verificar EndPointID / Status
        try:
            time.sleep(0.5)
            get_iccid = ApiTC.get_iccid(iccid, headers)
            endpointId = get_iccid[0]
            simStatus = get_iccid[1]
        except Exception:            
            error_api()
            continue
        
        # Alterar plano
        time.sleep(0.5)
        data_plan = ApiTC.planChange(endpointId,headers,day,dataDay,product)
        if data_plan == 0:
            UpdateOrder.upStatus(id_item,'EA')
            NotesAdd.addNote(order,f'{iccid} Plano não alterado. Verificar plano {dataDay} - TC: Plano não encontrado.')
            continue
        NotesAdd.addNote(order,f'{iccid} Plano alterado para {dataDay}')    

        if simStatus == 'Pre-Active':
            # Ativar SIM na operadora
            payload = json.dumps({
                "Request": {
                    "endPointId": f"{endpointId}"
                }
            })
            conn.request("POST", "/api/EndPointActivation", payload, headers)
            # Adicionar nota
            note = f'{iccid} ativado com sucesso na Telcon'
            
            process = True
            
        else:
            # Alterar SIM na operadora
            if simStatus == 'Active':
                logger.info(f'simStatus == Active')
                # Adicionar nota
                NotesAdd.addNote(order,f'{iccid} já estava ativado na Telcon')
                # Alterar Status
                orders_up_status.delay(order.id, 'AT')
                continue
            
            elif simStatus == 'Suspended':
                logger.info(f'simStatus == Suspended')
                payload = json.dumps({
                    "Request": {
                        "endPointId": f"{endpointId}",
                        "requestParam": {
                            "lifeCycle": "A",
                            "reason": "1"
                        }
                    }
                })
                time.sleep(0.5)
                conn.request("POST", "/api/EndPointLifeCycleChange", payload, headers)
                # Adicionar nota
                note = f'{iccid} reativado com sucesso na Telcon'
                
                process = True
                
            else:
                logger.info(f'simStatus == Other')
                # Alterar status
                UpdateOrder.upStatus(id_item,'EA')
                NotesAdd.addNote(order,f'{iccid} com erro de ativação na Telcon. Verificar erro.')
                continue
        
        if process == True:            
            
            time.sleep(0.5)            
            res = conn.getresponse()
            data = json.loads(res.read())
            resultCode = int(data["Response"]["resultCode"])
            resultDescription = data["Response"]["resultParam"]["resultDescription"]
            try:
                resultCode = int(data["Response"]["resultCode"])
                resultDescription = data["Response"]["resultParam"]["resultDescription"]
            except Exception:
                resultCode = None
                resultDescription = None
            
            if resultCode == 0:
                # Alterar status
                orders_up_status.delay(order.id, 'AT')
                # Adicionar nota
                NotesAdd.addNote(order,f'{note} TC: {resultDescription}')
            else:
                # Alterar status
                UpdateOrder.upStatus(id_item,'EA')
                # Adicionar nota
                NotesAdd.addNote(order,f'TC: {resultDescription}')
        
        # Fecha a conexão
        conn.close()
                
    logger.info(f'>>>>>>>>>> ATIVAÇÂO TC FINALIZADA')


@shared_task
@periodic_task_lock(timeout=330)
def simDeactivateTC(id=None):
    from apps.orders.tasks import orders_up_status
    

    timezone = pytz.timezone(settings.TIME_ZONE)

    now = datetime.now(timezone)
    yesterday = now.date() - timedelta(days=1)

    # Selecionar pedidos
    if id is None:       
        orders_to_process = Orders.objects.filter(order_status='AT', id_sim__operator__in=['TC', 'TI']).order_by('-id')
    else:
        orders_to_process = Orders.objects.filter(pk=id)

    if not orders_to_process.exists():
        logger.info(f'Não há pedidos que correspondam aos critérios de filtro.')
        return
    
    logger.info(f'>>>>>>>>>> INICIANDO VERIFICAÇÃO DE DESATIVAÇÃO TC <<<<<<<<<<')

    def error_api(order_item, iccid_val, detail=None):
        print(f'>>>>>>>>>> ERRO API PARA O PEDIDO {order_item.order_id} <<<<<<<<<<')
        UpdateOrder.upStatus(order_item.id, 'ED')
        detail_msg = f' TC: {detail}' if detail else ''
        NotesAdd.addNote(
            order_item,
            f'ERRO API: {iccid_val} com erro na Telcon. Verificar erro.{detail_msg}'
        )

    def rate_limit_skip(order_item, iccid_val, detail=None):
        # Não marca ED: pedido permanece AT para nova tentativa no próximo ciclo
        detail_msg = f' TC: {detail}' if detail else ''
        logger.warning(
            f'Rate limit Telcon no pedido {order_item.order_id}; mantendo AT.{detail_msg}'
        )
        NotesAdd.addNote(
            order_item,
            f'RATE LIMIT: {iccid_val} — desativação adiada por limite da API Telcon.{detail_msg}'
        )

    def mark_deactivated(order_item, iccid_val, result_description):
        print(f'Pedido {order_item.order_id} desativado com sucesso.')
        order_item.refresh_from_db()
        already_deactivated = order_item.order_status == 'DE'

        if id is None and not already_deactivated:
            # skip_sim_deactivate evita loop orders_up_status → simDeactivateTC
            orders_up_status.delay(
                order_item.id, 'DE', skip_sim_deactivate=True
            )
            sim_put = Sims.objects.get(pk=order_item.id_sim.id)
            sim_put.sim_status = 'DE'
            sim_put.save()

        # Evita nota duplicada quando orders_up_status reentrava na desativação
        if already_deactivated:
            logger.info(
                f'Pedido {order_item.order_id} já estava DE; nota de sucesso omitida'
            )
            return

        NotesAdd.addNote(
            order_item,
            f'{iccid_val} desativado com sucesso na Telcon. TC: {result_description}'
        )

    # Token único para o lote (evita login extra por pedido)
    try:
        token_api = ApiTC.get_token()
        headers = ApiTC.get_headers(token_api, cookie=True)
    except RateLimitExceeded as e:
        logger.error(f'Rate limit ao obter token TC: {e}')
        return
    except Exception as e:
        logger.error(f'Falha ao obter token TC para desativação: {e}', exc_info=True)
        return

    max_retries = 3

    for order in orders_to_process:
        # Garante que activation_date e days não são nulos
        if order.activation_date is None or order.days is None:
            continue

        # Calcula a data de desativação
        # A lógica é: data de ativação + (duração do plano - 1 dia)
        deactivation_date = order.activation_date + timedelta(days=order.days - 1)

        # Se um ID específico não foi passado, só desativa se a data for ontem ou anterior
        if id is None and deactivation_date > yesterday:
            continue

        print(f'Iniciando desativação para o pedido {order.order_id}')
        
        try:
            iccid = order.id_sim.sim
        except (AttributeError, ObjectDoesNotExist):
            print(f"Pedido {order.order_id} sem SIM associado. Pulando.")
            continue

        data = None
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                get_iccid_result = ApiTC.get_iccid(iccid, headers)
                endpointId = get_iccid_result[0]
                data = ApiTC.endpoint_lifecycle_change(
                    endpointId, headers, life_cycle='S', reason='1'
                )
                last_error = None
                break
            except RateLimitExceeded as e:
                last_error = e
                logger.warning(
                    f'Rate limit no pedido {order.order_id} '
                    f'(tentativa {attempt}/{max_retries}): {e}'
                )
                time.sleep(ApiTC.RATE_RETRY_WAIT * attempt)
            except Exception as e:
                last_error = e
                logger.error(
                    f"Erro inesperado ao processar desativação do pedido {order.order_id}: {e}",
                    exc_info=True
                )
                error_api(order, iccid, detail=str(e))
                data = None
                break

        if isinstance(last_error, RateLimitExceeded):
            rate_limit_skip(order, iccid, detail=str(last_error))
            continue

        if data is None:
            continue
                
        # Verificar resultado da desativação
        response = data.get("Response") or {}
        resultCode = int(response.get("resultCode", -1))
        resultParam = response.get("resultParam") or {}
        resultDescription = resultParam.get("resultDescription", str(data))
        apiResultCode = str(resultParam.get("resultCode", ""))

        if ApiTC.is_rate_limit_message(resultDescription):
            rate_limit_skip(order, iccid, detail=resultDescription)
            continue

        # 0 = sucesso; 1254 = já está no mesmo lifecycle (já suspenso)
        if resultCode == 0 or apiResultCode == "1254":
            mark_deactivated(order, iccid, resultDescription)
        else:
            print(f'Erro ao desativar pedido {order.order_id}.')
            if id is None:
                UpdateOrder.upStatus(order.id, 'ED')
            NotesAdd.addNote(
                order,
                f'ERRO DESATIVADO: {iccid} com erro na Telcon. TC: {resultDescription}'
            )
                
    logger.info(f'>>>>>>>>>> DESATIVAÇÃO TC FINALIZADA <<<<<<<<<<')


@shared_task
@periodic_task_lock(timeout=330)
def simDeactivateAll(id=None):
    from apps.orders.tasks import orders_up_status

    timezone = pytz.timezone(settings.TIME_ZONE)

    now = datetime.now(timezone)
    yesterday = now.date() - timedelta(days=1)

    # Selecionar pedidos: só ATIVADOS, excluindo TC/TI (esses vão em simDeactivateTC).
    # exclude(AT, TC/TI) sozinho está errado — inclui DE/CC/etc. e reprocessa todo dia.
    if id is None:
        orders_to_process = (
            Orders.objects.filter(order_status='AT')
            .exclude(id_sim__operator__in=['TC', 'TI'])
            .order_by('-id')
        )
    else:
        orders_to_process = Orders.objects.filter(pk=id)

    if not orders_to_process.exists():
        return
    
    logger.info(f'>>>>>>>>>> INICIANDO VERIFICAÇÃO DE DESATIVAÇÃO ALL <<<<<<<<<<')

    for order in orders_to_process:
        # Garante que activation_date e days não são nulos
        if order.activation_date is None or order.days is None:
            continue

        # Calcula a data de desativação
        # A lógica é: data de ativação + (duração do plano - 1 dia)
        deactivation_date = order.activation_date + timedelta(days=order.days - 1)

        # Se um ID específico não foi passado, só desativa se a data for ontem ou anterior
        if id is None and deactivation_date > yesterday:
            continue

        print(f'Iniciando desativação para o pedido {order.order_id}')
        
        try:
            iccid = order.id_sim.sim
        except (AttributeError, ObjectDoesNotExist):
            print(f"Pedido {order.order_id} sem SIM associado. Pulando.")
            continue

        if id is None:
            # Reserva atômica AT→DE para não reprocessar em execução concorrente
            claimed = Orders.objects.filter(pk=order.id, order_status='AT').update(
                order_status='DE'
            )
            if claimed == 0:
                logger.info(
                    f'Pedido {order.order_id} já não está AT. Ignorando.'
                )
                continue
            # previous_status='AT': status já foi gravado no claim acima
            orders_up_status.delay(order.id, 'DE', previous_status='AT')
            sim_put = Sims.objects.get(pk=order.id_sim.id)
            sim_put.sim_status = 'DE'
            sim_put.save()
            NotesAdd.addNote(
                order, f'{iccid} desativado com sucesso. Processo automático'
            )
        
    logger.info(f'>>>>>>>>>> DESATIVAÇÃO ALL FINALIZADA <<<<<<<<<<')


@shared_task
@periodic_task_lock(timeout=140)
def simActivateEO(id=None):
    from apps.orders.tasks import orders_up_status
          
    tz = pytz.timezone(settings.TIME_ZONE)
    today = datetime.now(tz).date()
    tomorrow = today + timedelta(days=1)
    
    logger.info(f'>>>>>>>>>> ATIVAÇÂO EO INICIADA')
    
    # Selecionar pedidos
    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim__operator__in=['TM', 'VR'], activation_date__lte=tomorrow)
    else:
        orders_all = Orders.objects.filter(pk=id)        
    
    for order in orders_all:
        
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        id_item = order.id
        operator = order.id_sim.operator
        if order.id_sim.type_sim == 'sim':
            iccid = order.id_sim.sim
            imei = ""
        else:
            iccid = order.cell_eid
            imei = order.cell_imei
        activation_date = order.activation_date
        days = order.days
        carrier = 'T-Mobile' if operator == 'TM' else 'Verizon MVNO'
        plan = ''
        
        if operator == 'TM':
            plan = '$50'
            if days in [5, 6]:
                days = 7
            elif days >= 20:
                days = 30
                plan = '$50B'
            else:
                pass
        elif operator == 'VR':
            plan = '50$'
            if days in [5, 6]:
                days = 7
            elif days >= 14:
                days = 30
            else:
                pass
                
        # Dados para a solicitação
        url = settings.APIEO_URL
        payload = {
            "planName": plan,
            "carrier": carrier,
            "day": int(days),
            "sim": iccid,
            "activationDate": activation_date.strftime("%Y-%m-%d"),
            "imei": imei,
            'comment': str(order_id)
        }

        required_fields = ["planName", "carrier", "day", "sim"]
        missing_fields = [field for field in required_fields if not payload.get(field)]
        if missing_fields:
            logger.error(
                'EO payload invalido para pedido %s. Campos ausentes: %s | payload=%s',
                order_id,
                ', '.join(missing_fields),
                payload,
            )
            UpdateOrder.upStatus(id_item,'EA')
            NotesAdd.addNote(order, f'Erro EO: campos obrigatorios ausentes ({", ".join(missing_fields)}).')
            continue
                
        # Cabeçalhos da solicitação
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.APIEO_TOKEN}'
        }
        status_code = None
        response_text = ''
        response_data = {}
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            status_code = response.status_code
            response_text = response.text or ''
            try:
                response_data = response.json() if response_text.strip() else {}
            except ValueError:
                response_data = {}
            if status_code != 200:
                logger.warning(
                    'EO resposta não-200 | pedido=%s | http=%s | headers=%s',
                    order_id,
                    status_code,
                    dict(response.headers),
                )
        except Exception as e:
            logger.error('EO erro de conexão pedido=%s erro=%s', order_id, e, exc_info=True)
            response_data = {'success': False, 'error': str(e)}

        # Verifica o código de resposta
        if response_data.get('success') is True:
            # Alterar status
            orders_up_status.delay(order.id, 'AT')
            # Adicionar nota
            NotesAdd.addNote(order, f'{iccid} enviado para ativação na T-Mobile/Verizon. HTTP {status_code}')
        else:
            error_msg = (
                response_data.get('error')
                or response_data.get('message')
                or response_data.get('detail')
                or response_text
                or 'sem corpo na resposta da API EO'
            )
            logger.error(
                'EO falha na ativação | pedido=%s | http=%s | payload=%s | response_body=%s',
                order_id,
                status_code,
                payload,
                response_text or response_data or 'sem resposta',
            )
            # Alterar status
            UpdateOrder.upStatus(id_item, 'EA')
            # Adicionar nota
            NotesAdd.addNote(order, f'Erro EO (HTTP {status_code}): {iccid}. {str(error_msg)[:300]}')

                
    logger.info(f'>>>>>>>>>> ATIVAÇÂO EO FINALIZADA')


@shared_task
@periodic_task_lock(timeout=140)
def simActivateCM(id=None):
    
    import base64
    import hashlib
    import json
    import http.client
    from urllib.parse import urlparse
    import time 
    
    tz = pytz.timezone("Europe/Lisbon")
    today = datetime.now(tz).date()

    logger.info(f'>>>>>>>>>> ATIVAÇÂO CM INICIADA')
    
    # Selecionar pedidos
    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim__operator='CM', activation_date__lte=today)
    else:
        orders_all = Orders.objects.filter(pk=id)    
    
    if orders_all != None:
        # Gerar Token
        api_token = ApiCM.get_token()
        
        if api_token == "error":
            logger.info(f'>>>>>>>>>> ERRO DE TOKEN')
            return
    
    for order in orders_all:
        
        # Aguardar 1 segundo
        time.sleep(0.5)
        
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        order_item = order.id
        order_product = order.product
        order_day = str(order.days)
        order_data = str(order.data_day)
        order_sim = order.id_sim.sim
        
        print(f'>>>>>>>>>> ATIVANDO SIM {order_sim} - {order_id}')
        
        def errorData(data_dict=None):
            # Adicionar Nota
            note = f'Erro ao ativar o SIM {order_sim}. Verificar manualmente. ERRO: {data_dict}'
            NotesAdd.addNote(order, note)
            # Alterar status do sistema
            UpdateOrder.upStatus(order_item, 'EA')
        
        def generate_password_digest(app_secret):
            nonce = str(int(time.time() * 1000))
            created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            digest = base64.b64encode(hashlib.sha256((nonce + created + app_secret).encode('utf-8')).digest()).decode('utf-8')
            return nonce, created, digest
        
        # Selecionar plano
        plan_code = ApiCM.selPlan(order_day, order_data, order_product)
        
        # Verificar se plan_code foi definido
        if plan_code is None:
            # Inserir nota e alterar status do sistema
            NotesAdd.addNote(order, f"Nenhum plano correspondente encontrado para {order_day} e {order_data}.")
            errorData()
            continue

        # URL do endpoint
        url_api = f'{settings.APICM_URL}/aep/APP_createOrder_SBO/v1'
        parsed_url = urlparse(url_api)
        app_key = settings.APICM_KEY
        app_secret = settings.APICM_SECRET

        # Gerar PasswordDigest
        nonce, created, password_digest = generate_password_digest(app_secret)

        # Cabeçalhos da requisição
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"',
        }

        # Corpo da requisição
        payload = json.dumps({
            "accessToken": api_token,
            "dataBundleId": plan_code,
            "ICCID": order_sim,
            "thirdOrderId": order_item,
            "includeCard":"0",
            "is_Refuel":"1",
            "quantity":"1",
        })
        
        # Fazer a requisição POST com tempo limite
        conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
        conn.request("POST", parsed_url.path, payload, headers)
        res = conn.getresponse()

        # Verificar o status da resposta
        data = res.read()
        
        if res.status != 200:
            errorData(data.decode("utf-8"))
        else:
            data_dict = json.loads(data)
            result_data = data_dict.get('description')
            if result_data != 'Success':
                errorData(data_dict)
            else:
                # Adicionar Nota
                note = f'SIM {order_sim} ativado na China Mobile.'
                NotesAdd.addNote(order, note)
                # Alterar status do sistema
                UpdateOrder.upStatus(order_item, 'AT')
                UpdateStore.upStore(order_id=order_id, status_g='AT')

        conn.close()

    logger.info(f'>>>>>>>>>> ATIVAÇÂO CM FINALIZADA')


@shared_task(time_limit=110, soft_time_limit=100)
@periodic_task_lock(timeout=140)
def simActivateCMHK(id=None):
    import base64
    import hashlib
    import json
    import http.client
    from urllib.parse import urlparse
    import time

    tz = pytz.timezone(settings.TIME_ZONE)
    today = datetime.now(tz).date()
    # tomorrow = today + timedelta(days=1)

    logger.info('>>>>>>>>>> ATIVAÇÂO CMHK INICIADA')

    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim__operator='CMHK', activation_date__lte=today)
    else:
        orders_all = Orders.objects.filter(pk=id)

    if orders_all.count() == 0:
        logger.info('>>>>>>>>>> ATIVAÇÂO CMHK FINALIZADA')
        return

    api_token = ApiCMHK.get_token()
    if api_token == "error":
        logger.error('>>>>>>>>>> ERRO DE TOKEN CMHK')
        return

    for order in orders_all:
        time.sleep(0.5)
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        order_item = order.id
        order_product = order.product
        order_day = str(order.days)
        order_data = str(order.data_day)
        order_sim = order.id_sim.sim

        logger.info(f'>>>>>>>>>> ATIVANDO SIM CMHK {order_sim} - {order_id}')

        def errorData(data_dict=None):
            note = f'Erro ao ativar o SIM {order_sim}. Verificar manualmente. ERRO: {data_dict}'
            NotesAdd.addNote(order, note)
            UpdateOrder.upStatus(order_item, 'EA')

        def generate_password_digest(app_secret):
            nonce = str(int(time.time() * 1000))
            created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            digest = base64.b64encode(hashlib.sha256((nonce + created + app_secret).encode('utf-8')).digest()).decode('utf-8')
            return nonce, created, digest

        plan_code = selectPlanCMHK.selectPlanCod(order_product, order_day, order_data)
        if plan_code is None:
            NotesAdd.addNote(order, f'ERRO AO DEFINIR PLANO CMHK {order_product} - {order_day} - {order_data}')
            errorData()
            continue

        url_api = f'{settings.APICMHK_URL}/aep/APP_createOrder_SBO/v1'
        parsed_url = urlparse(url_api)
        app_key = settings.APICMHK_KEY
        app_secret = settings.APICMHK_SECRET
        nonce, created, password_digest = generate_password_digest(app_secret)
        headers = {
            'Content-Type': 'application/json',
            "Accept": "application/json",
            "Authorization": 'WSSE realm="SDP", profile="UsernameToken", type="Appkey"',
            "X-WSSE": f'UsernameToken Username="{app_key}", PasswordDigest="{password_digest}", Nonce="{nonce}", Created="{created}"',
        }
        payload = json.dumps({
            "accessToken": api_token,
            "dataBundleId": plan_code,
            "ICCID": order_sim,
            "thirdOrderId": order_item,
            "includeCard": "0",
            "is_Refuel": "1",
            "quantity": "1",
        })
        conn = http.client.HTTPSConnection(parsed_url.hostname, parsed_url.port, timeout=10)
        conn.request("POST", parsed_url.path, payload, headers)
        res = conn.getresponse()
        data = res.read()
        if res.status != 200:
            errorData(data.decode("utf-8"))
        else:
            data_dict = json.loads(data)
            result_data = data_dict.get('description')
            if result_data != 'Success':
                errorData(data_dict)
            else:
                NotesAdd.addNote(order, f'SIM {order_sim} ativado na CMHK com sucesso')
                UpdateOrder.upStatus(order_item, 'AT')
                UpdateStore.upStore(order_id=order_id, status_g='AT')
        conn.close()

    logger.info('>>>>>>>>>> ATIVAÇÂO CMHK FINALIZADA')

            

@shared_task
@periodic_task_lock(timeout=140)
def simActivateAR(id=None):
    
    tz = pytz.timezone(settings.TIME_ZONE)
    today = datetime.now(tz).date()
    tomorrow = today +timedelta(days=80)
    
    logger.info(f'>>>>>>>>>> ATIVAÇÂO AR INICIADA')
    
    # Selecionar pedidos
    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim=351, activation_date__lte=tomorrow)
        if not orders_all.exists():
            logger.info(f'>>>>>>>>>> Nenhum pedidos encontrados para ativação AR')
            return
    else:
        orders_all = Orders.objects.filter(pk=id)    
    
    if orders_all != None:
        # Gerar Token
        try:
            api_token = ApiAR.getToken()
        except Exception as e:
            logger.error(str(e), exc_info=True)
            logger.info(f'>>>>>>>>>> ERRO DE TOKEN')
            return
    
    for order in orders_all:
        logger.info(f'>>>>>>>>>> INICIANDO ATIVAÇÃO AR PARA O PEDIDO {order.order_id}')
        
        # Aguardar 1 segundo
        time.sleep(0.5)
        
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        order_item = order.id
        order_product = order.product
        order_day = str(order.days)
        order_data = str(order.data_day)
        order_sim = order.id_sim.sim
        order_client = order.client
        order_paises = order.countries
        order_voz = order.voice
        list_plan = []
                
        def errorData(data_dict=None):
            # Adicionar Nota
            note = f'Erro ao ativar o SIM {order_sim}. Verificar manualmente. ERRO: {data_dict}'
            NotesAdd.addNote(order, note)
            # Alterar status do sistema
            UpdateOrder.upStatus(order_item, 'EA')
        
        # Selecionar plano
        try:
            plan_code = ApiAR.selPlan(order_day, order_data, order_product, order_paises, order_voz)
            logger.info(f'Plano selecionado para o pedido {order.order_id}: {plan_code}')
        except Exception as e:
            logger.error(str(e), exc_info=True)
            plan_code = None

        
        # Verificar se plan_code foi definido
        if plan_code is None:
            # Inserir nota e alterar status do sistema
            NotesAdd.addNote(order, f"Nenhum plano correspondente encontrado para {order_day} e {order_data}.")
            errorData()
            continue

        # URL do endpoint
        url_api = f'{settings.APIAIRALO_URL}/orders'

        payload = {
            "quantity": "1",
            "package_id": plan_code,
            "type": "sim",
            "description": f"{order_item} - {order_client}",
        }
        files = []
        headers = {
        'Accept': 'application/json',
        'Authorization': f'Bearer {api_token}'
        }

        try:
            response = requests.post(url_api, headers=headers, json=payload, timeout=30)
        except Exception as e:
            logger.error(str(e), exc_info=True)
            errorData(str(e))
            continue
        
        response_json = response.json()
        if response_json.get('meta', {}).get('message') != "success":
            logger.error(f'Erro na resposta da API Airalo: {response_json}')
            errorData(response_json)
            continue
        else:
            iccid = response_json['data']['sims'][0]['iccid']
            qrcode = response_json['data']['sims'][0]['qrcode_url']
            # Inserir no estoque
            id_sim = ApiAR.addESimAR(iccid, qrcode)
            sim = Sims.objects.get(pk=id_sim)
            # Atualizar pedido
            order_put = Orders.objects.get(pk=order.id)
            order_put.id_sim_id = sim.id
            order_put.order_status = 'AT'
            order_put.save()            
            
            # Adicionar Nota
            note = f'SIM {iccid} ativado na Airalo.'
            NotesAdd.addNote(order, note)
            UpdateStore.upStore(
                order_id = order_id,
                status_g = 'AT',
            )
            # Enviar email
            send_email_sims.delay(id=order_item)
            
            
    logger.info(f'>>>>>>>>>> ATIVAÇÃO AR FINALIZADA')

    