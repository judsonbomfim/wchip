from celery import shared_task
import os
import http.client
import json
import time
from django.conf import settings
from .classes import ApiTC
from apps.orders.models import Orders, Notes
from apps.orders.classes import ApiStore, StatusStore, NotesAdd, UpdateOrder
from apps.send_email.tasks import send_email_sims
from apps.sims.models import Sims
from datetime import datetime
import pytz
import pandas as pd

@shared_task
def sims_in_orders():
    
    orders = Orders.objects.filter(order_status='AS')
    
    global n_item_total
    n_item_total = 0
    global msg_ord
    msg_info = []
    global msg_error
    msg_error = []
    
    for ord in orders:
        
        id_id_i = ord.id
        id_item_i = Orders.objects.get(pk=id_id_i)
        order_id_i = ord.order_id
        product_i = ord.product
        type_sim_i = ord.type_sim
        esim_eua = type_sim_i == 'esim' and (product_i == '977' or product_i == '980')
        id_sim_i = id_item_i.id_sim
        
        # Se já houver SIM   
        if id_sim_i != None:
            if ord.order_status == 'AS':
                sim_put = Sims.objects.get(pk=id_sim_i.id)
                if esim_eua:
                    sim_put.sim_status = 'AI'
                else:
                    sim_put.sim_status = 'AA'
                sim_put.save()
        else:    
            # Notes
            def addNote(t_note):
                add_sim = Notes( 
                    id_item = id_item_i,
                    note = t_note,
                    type_note = 'S',
                )
                add_sim.save()

            # Escolher operadora
            if product_i == '981':
                operator_i = 'VR'
            elif product_i == '977' or product_i == '980':
                operator_i = 'TM'
            elif product_i == '975':
                operator_i = 'CM'
            else: operator_i = 'TC'
            
            # Select SIM
            if esim_eua:
                sim_ds = Sims.objects.all().get(pk=0)
            else:
                sim_ds = Sims.objects.all().order_by('id').filter(operator=operator_i, type_sim=type_sim_i, sim_status='DS').first()
                if sim_ds:
                    pass
                else:
                    print('>>>>>>>>>>>>>>>>>>>>>>> SIMs indisponíveis!')
                    continue
            
            # update order
            # Save SIMs
            if type_sim_i == 'esim':
                if product_i == '977' or product_i == '980' or product_i == '981': 
                    status_ord = 'AI'
                else: status_ord = 'EE'
            else: status_ord = 'ES'
            
            order_put = Orders.objects.get(pk=id_id_i)
            order_put.id_sim_id = sim_ds.id            
            order_put.order_status = status_ord
            order_put.save()
            
            # Verification esim x eua
            if esim_eua:
                send_email_sims.delay(id_id_i)
                addNote(f'eSIM EUA - SIM padrão adicionado')
                msg_info.append(f'Pedido {order_id_i} atualizados com sucesso')
                continue
            
            # update sim
            sim_put = Sims.objects.get(pk=sim_ds.id)
            sim_put.sim_status = 'AT'
            sim_put.save()
            sim_e = sim_put.sim 
            
            addNote(f'(e)SIM {sim_e} adicionado')
            
            msg_info.append(f'Pedido {order_id_i} atualizados com sucesso')
            
            n_item_total += 1
    
        print('>>>>>>>>>>>>>>>>>>>>>>> SIMs atribuidos!')
    
@shared_task
def simActivateTC(id=None):
    
    from apps.orders.tasks import up_order_st_store    
        
    london_tz = pytz.timezone('Europe/London')
    today = datetime.now(london_tz).date()

    print('>>>>>>>>>> ATIVAÇÂO INICIADA')
    
    # Selecionar pedidos
    if id is None:
        orders_all = Orders.objects.filter(order_status='AA', id_sim__operator='TC', activation_date__lte=today)
    else:
        orders_all = Orders.objects.filter(pk=id)
            
    # Checar conexão com API
    def error_api():
        print('>>>>>>>>>> ERRO API')
        # Checar Status
        UpdateOrder.upStatus(id_item,'EA')
        # Adicionar nota
        NotesAdd.addNote(order,f'{iccid} com erro na Telcon. Verificar erro.')
        error = 'error_apiResult'
        return error     
    
    for order in orders_all:
        
        order = Orders.objects.get(pk=order.id)
        order_id = order.order_id
        id_item = order.id
        try:
            iccid = order.id_sim.sim
        except Exception:
            iccid = None
            continue
        dataDay = order.data_day
        
        # Variaveis globais        
        endpointId = None
        simStatus = None
        note = ''
        process = False
        token_api = None  
        
        # Verificar EndPointID / Status
        try:
            token_api = ApiTC.get_token()
            conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
            headers = ApiTC.get_headers(token_api)
            get_iccid = ApiTC.get_iccid(iccid, headers)
            endpointId = get_iccid[0]
            simStatus = get_iccid[1]
            print('>>>>>>>>>> endpointId',endpointId)
            print('>>>>>>>>>> simStatus',simStatus)  
        except Exception:            
            error_api()
            continue
        ##
        
        # Alterar plano
        ApiTC.planChange(endpointId,headers,dataDay)
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
                print('simStatus == Active')
                # Adicionar nota
                NotesAdd.addNote(order,f'{iccid} já estava ativado na Telcon')
                # Alterar Status
                UpdateOrder.upStatus(id_item,'AT')
                continue
            
            elif simStatus == 'Suspended':
                print('simStatus == Suspended')
                payload = json.dumps({
                    "Request": {
                        "endPointId": f"{endpointId}",
                        "requestParam": {
                            "lifeCycle": "A",
                            "reason": "1"
                        }
                    }
                })
                conn.request("POST", "/api/EndPointLifeCycleChange", payload, headers)
                # Adicionar nota
                note = f'{iccid} reativado com sucesso na Telcon'
                
                process = True
                
            else:
                print('simStatus == Other')
                # Alterar status
                UpdateOrder.upStatus(id_item,'EA')
                NotesAdd.addNote(order,f'{iccid} com erro na Telcon. Verificar erro.')
                continue
        
        if process == True:            
            
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
            
            print('>>>>>>>>>> resultCode', resultCode)
            print('>>>>>>>>>> resultDescription', resultDescription)
            
            if resultCode == 0:
                # Alterar status
                UpdateOrder.upStatus(id_item,'AT')
                up_order_st_store.delay(order_id,'ativado')
                StatusStore.upStatus(order_id,'ativado')
                # Adicionar nota
                NotesAdd.addNote(order,f'{note} TC: {resultDescription}')
            else:
                # Alterar status
                UpdateOrder.upStatus(id_item,'EA')
                # Adicionar nota
                NotesAdd.addNote(order,f'TC: {resultDescription}')
                
    print('>>>>>>>>>> ATIVAÇÂO FINALIZADA')

@shared_task
def simDeactivateTC(id=None):
    
    from apps.orders.tasks import up_order_st_store    
    
    timezone = pytz.timezone('Europe/London')
    min_hour = 23  # hora
    min_minute = 45  # 45 minutos

    current_hour = datetime.now(timezone).hour
    current_minute = datetime.now(timezone).minute
            
    # Timezone / Hoje
    today = pd.Timestamp.now(tz=timezone).date()

    # Selecionar pedidos
    if id is None:
        if current_hour < min_hour or (current_hour == min_hour and current_minute < min_minute):
            # Se for depois da hora mínima, execute a tarefa
            return
        else:
            orders_all = Orders.objects.filter(order_status='AT', id_sim__operator='TC')
    else:
        orders_all = Orders.objects.filter(pk=id)
        
    # Se não houver pedidos, encerre a execução
    if not orders_all.exists():
        print('Não há pedidos que correspondam aos critérios de filtro.')
        return
    
    fields_df = ['id', 'order_id', 'id_sim__sim', 'days', 'activation_date']
    orders_df = pd.DataFrame((orders_all.values(*fields_df)))
    orders_df['activation_date'] = pd.to_datetime(orders_df['activation_date'])
    orders_df['return_date'] = orders_df['activation_date'] + pd.to_timedelta(orders_df['days'], unit='d') - pd.to_timedelta(1, unit='d')

    if id is None:
        orders_df = orders_df.loc[orders_df['return_date'].dt.date == today]
    
    # Verificar se há pedidos para desativar
    if orders_df is None:
        print('>>>>>>>>>> Nenhum pedido para desativar')
        return
    
    def error_api():
        print('>>>>>>>>>> ERRO API')
        # Alterar status
        UpdateOrder.upStatus(id_item,'ED')
        # Adicionar nota
        NotesAdd.addNote(order,f'{iccid} com erro na Telcon. Verificar erro.')
        error = 'error_api Result'
        return error       

    print('>>>>>>>>>> DESATIVAÇÂO INICIADA')
    
    for index, o in orders_df.iterrows():
        
        order = Orders.objects.get(pk=o['id'])
        order_id = order.order_id
        id_item = order.id
        iccid = order.id_sim.sim
        
        note = ''
        resultCode = None
        resultDescription = None        
        endpointId = None
        simStatus = None
        token_api = None    
         
        # Get EndPointID / Status
        try:
            # Gerar tokem de acesso a API
            token_api = ApiTC.get_token()
            conn = http.client.HTTPSConnection(settings.APITC_HTTPCONN)
            headers = ApiTC.get_headers(token_api, cookie=True)
            get_iccid = ApiTC.get_iccid(iccid, headers)
            endpointId = get_iccid[0]
            simStatus = get_iccid[1] 
        except Exception:            
            error_api()
            continue      
        ##

        # Variaveis globais
        payload = json.dumps({
            "Request": {
                "endPointId": f"{endpointId}",
                "requestParam": {
                    "lifeCycle": "S",
                    "reason": "1"
                }
            }
        })
        
        conn.request("POST", "/api/EndPointLifeCycleChange", payload, headers)
        # Adicionar nota
            
        res = conn.getresponse()
        data = json.loads(res.read())
        try:
            resultCode = int(data["Response"]["resultCode"])
            resultDescription = data["Response"]["resultParam"]["resultDescription"]
        except Exception:
            resultCode = None
            resultDescription = None

        if resultCode == 0:
            if id is None:
                print('>>>>>>>>>> Alterar status')                
                # Alterar status                
                UpdateOrder.upStatus(id_item,'DE')
                up_order_st_store.delay(order.id,'desativado')
                sim_put = Sims.objects.get(pk=order.id_sim.id)
                sim_put.sim_status = 'DE'
                sim_put.save()
            # Adicionar nota
            NotesAdd.addNote(order,f'{iccid} desativado com sucesso na Telcon. TC: {resultDescription}')
        else:
            print('>>>>>>>>>> ERRO DESATIVADO')
            if id is None:
                # Alterar status
                UpdateOrder.upStatus(id_item,'ED')
            # Adicionar nota
            NotesAdd.addNote(order,f'{iccid} com erro na Telcon. Verificar erro. TC: {resultDescription}')
                
    print('>>>>>>>>>> DESATIVAÇÂO FINALIZADA')

