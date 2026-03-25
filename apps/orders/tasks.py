from django.contrib.auth.models import User
from celery import shared_task
from django.utils.text import slugify
from datetime import datetime, timedelta
from .classes import ApiStore, NotesAdd, StatusStore, DateFormats, UpdateOrder
from apps.orders.models import Orders, Notes
from apps.sims.models import Sims
from apps.sims.tasks import sims_in_orders, simDeactivateTC, simActivateTC
from apps.sims.classes import OperatorSelect
import time
from apps.send_email.tasks import send_email_sims
import logging

# Configurar logger para este módulo
logger = logging.getLogger('apps.orders')

@shared_task
def order_import():
    date_now = datetime.now()
    
    try:
        apiStore = ApiStore.conectApiStore()
    except Exception as e:
        logger.error(f'Erro ao conectar com API da loja: {e}')
        return
    
    global n_item_total
    n_item_total = 0
    global msg_info
    msg_info = []
    global msg_error
    msg_error = []
    
    # Definir números de páginas
    per_page = 100
    order_status_filter = ['pg-confirmado', 'processing']
    try:
        order_p = apiStore.get('orders', params={'status': order_status_filter, 'per_page': per_page})
    except Exception as e:
        logger.error(f'[{date_now}] Erro ao buscar pedidos na loja: {e}', exc_info=True)
        return
    
    if order_p.status_code != 200:
        logger.error(f'[{date_now}] Erro ao buscar pedidos: {order_p.status_code} - {order_p.text}')
        return
    
    total_pages = int(order_p.headers.get('X-WP-TotalPages', 1))
    n_page = 1
    # orders_all = Orders.objects.all()
    
    logger.info(f'[{date_now}] Iniciando importação de pedidos')
        
    while n_page <= total_pages:
        logger.info(f'Buscando página {n_page} de {total_pages}')
        
        # Pedidos com status 'processing'
        try:
            page_response = apiStore.get(
                'orders',
                params={
                    'order': 'asc',
                    'status': order_status_filter,
                    'per_page': per_page,
                    'page': n_page,
                }
            )
        except Exception as e:
            logger.error(f'Erro ao buscar página {n_page} na loja: {e}', exc_info=True)
            n_page += 1
            continue

        if page_response.status_code != 200:
            logger.error(f'Erro ao buscar página {n_page}: {page_response.status_code} - {page_response.text}')
            n_page += 1
            continue

        ord = page_response.json()
        if not isinstance(ord, list):
            logger.error(f'Resposta inesperada na página {n_page}: {ord}')
            n_page += 1
            continue

        # Listar pedidos         
        for order in ord:
            
            n_item = 1
            id_ord = order["id"]
            client_id_i = order['customer_id']
            
            # Verificar pedido repetido
            id_sis = Orders.objects.filter(order_id=id_ord)
            if id_sis:
                continue
            else: pass

            logger.info(f'Processando pedido ID: {order["id"]}')
            
            # Listar itens do pedido
            for item in order['line_items']:
                
                # Especificar produtos a serem listados
                products = Orders.product.field.choices
                prod_sel = []
                for code, name in products:
                    prod_sel.append(int(code))
                if item['product_id'] not in prod_sel:
                    continue
                                
                qtd = item['quantity']
                q_i = 1 
                
                while q_i <= qtd:
                    order_id_i = order['id']
                    logger.info(f'Inserindo pedido {order_id_i}')
                    
                    item_id_i = f'{order_id_i}-{n_item}'
                    client_i = f'{order["billing"]["first_name"]} {order["billing"]["last_name"]}'
                    email_i = order['billing']['email']
                    product_i = item['product_id']
                    
                    qty_i = 1
                    if order['coupon_lines']:
                        coupon_i = order['coupon_lines'][0]['code']
                    else: coupon_i = '-'
                    # Definir valor padrão para variáveis
                    ord_chip_nun_i = '-'
                    countries_i = False
                    cell_mod_i = False
                    type_sim_i = "sim"
                    data_day_i = None
                    days_i = None
                    activation_date_i = None
                    # Percorrer itens do pedido
                    for i in item['meta_data']:
                        if i['key'] == 'pa_tipo-de-sim':
                            tipe_sim = i['display_value'].split(' ')
                            sim_t = tipe_sim[0].strip().lower()
                            if sim_t == 'esim' : type_sim_i = 'esim'
                            else: type_sim_i = 'sim'
                        if i['key'] == 'pa_franquia': data_day_i = i['value']
                        if i['key'] == 'pa_dias': days_i = i['value']
                        if 'Visitará' in i['key']:
                            if i['display_value'] == 'Sim': countries_i = True 
                            else: countries_i = False
                        if i['key'] == 'Data de Ativação': activation_date_i = i['value']
                        if i['key'] == 'Modelo e marca de celular': cell_mod_i = i['value']
                        if i['key'] == 'Número de pedido ou do chip': ord_chip_nun_i = i['value']
                    shipping_i = order['shipping_lines'][0]['method_title']
                    order_status_i = 'AS'
                    
                    order_date_i = DateFormats.dateHour(order['date_created'])
                    # notes_i = 0
                    
                    # Definir status do pedido
                    # ('AG', 'Aerop. GRU'),
                    # ('FG', 'Frete Grátis'),
                    # ('FN', 'Frete Normal'),
                    # ('EV', 'Entrega VIP'),
                    # ('SD', 'SEDEX'),
                    
                    if 'Grátis' in shipping_i:
                        shipping_i = 'FG'
                        order_status_i = 'AS'
                    elif 'e-mail' in shipping_i:
                        shipping_i = 'EM'
                        if product_i == 977:
                            order_status_i = 'AI'
                        else:
                            order_status_i = 'AS'
                    elif 'Pac' in shipping_i:
                        shipping_i = 'PC'
                        order_status_i = 'AS'
                    elif 'SEDEX' in shipping_i:
                        shipping_i = 'SD'
                        order_status_i = 'AS'
                    elif 'Loggi' in shipping_i:
                        shipping_i = 'LG'
                        order_status_i = 'AS'
                    elif 'SP' in shipping_i:
                        shipping_i = 'RS'
                        order_status_i = 'RS'
                    elif type_sim_i == "esim":
                        order_status_i = 'AS'
                        
                    # Definir Operadora                   
                    oper_sel = OperatorSelect.opSelSim()
                    oper_sim_i = oper_sel.get(str(product_i), '')
                    
                    # Definir variáveis para salvar no banco de dados                            
                    order_add = Orders(                    
                        order_id = order_id_i,
                        item_id = item_id_i,
                        client_id = client_id_i,
                        client = client_i,
                        email = email_i,
                        product = product_i,
                        data_day = data_day_i,
                        qty = qty_i,
                        coupon = coupon_i,
                        days = days_i,
                        countries = countries_i,
                        cell_mod = cell_mod_i,
                        ord_chip_nun = ord_chip_nun_i,
                        shipping = shipping_i,
                        order_date = order_date_i,
                        activation_date = activation_date_i,
                        order_status = order_status_i,
                        type_sim = type_sim_i,
                        oper_sim = oper_sim_i
                        # notes = notes_i
                    )
                    
                    # Salvar itens no banco de dados
                    register = order_add.save()
                    try:
                        register
                    except:
                        msg_error.append(f'Pedido {order_id_i} deu um erro ao importar')
                    
                    # id_user = None
                    # if getpass.getuser():
                    #     id_user = getpass.getuser()
                    
                    # Save Notes
                    add_sim = Notes( 
                        id_item = Orders.objects.get(pk=order_add.id),
                        id_user = None,
                        note = f'Pedido importado para o sistema',
                        type_note = 'S',
                    )
                    add_sim.save()
                    
                    # Alterar status
                    # Status sis : Status Loja
                    status_def_sis = StatusStore.st_sis_site()
                    if order_status_i in status_def_sis:
                        status_ped = {
                            'status': status_def_sis[order_status_i]
                        }
                        try:
                            apiStore.put(f'orders/{order_id_i}', status_ped).json()
                        except:
                            msg_error.append(f'{order_id_i} - Falha ao atualizar status na loja!')
                    
                    # Definir variáveis
                    q_i += 1 
                    n_item += 1
                    n_item_total += 1
                    
                    msg_info.append(f'Pedido {order_id_i} atualizados com sucesso')
                    
        n_page += 1
    
    # Status 
    if n_item_total == 0:
        logger.info(f'>>>>>>>>>>>>>>>>>>>>>>> Não há pedido(s) para atualizar!')
    else:
        logger.info(f'>>>>>>>>>>>>>>>>>>>>>>> Pedidos importados com sucesso')


@shared_task
def orders_auto():
    logger.info('Iniciando orders_auto')
    order_import.delay()
    time.sleep(5)
    sims_in_orders.delay()
    time.sleep(10)
    send_email_sims.delay()

@shared_task
def orders_up_status(ord_id, ord_s, id_user):

    ord_id = ord_id
    ord_s = ord_s
    
    for o_id in ord_id:
        
        logger.info(f'Processando order ID: {o_id}')
        
        order = Orders.objects.get(pk=o_id)
        user = User.objects.get(pk=id_user)
        
        order_id = order.id
        order_st = order.order_status
        order_plan = order.get_product_display()
        try: type_sim = order.id_sim.type_sim
        except: type_sim = 'esim'
        apiStore = ApiStore.conectApiStore()

        # Save status System
        order.order_status = ord_s
        order.save()
        
        if ord_s == 'CC' or ord_s == 'DE' or ord_s == 'RE':
            if order.id_sim:                
                # Change TC
                if order.id_sim.operator == 'TC' and order.order_status != 'ED':
                    simDeactivateTC(id=order.id)
                
                # Update SIM
                sim_put = Sims.objects.get(pk=order.id_sim.id)
                sim_put.sim_status = 'DE'
                sim_put.save()
 
        # Ativar SIM TC
        if ord_s == 'AT' and order.id_sim.operator == 'TC':
            if order.order_status == 'EA':
                # Alterar status
                UpdateOrder.upStatus(order.id,'AT')
                up_order_st_store.delay(order.id,'ativado')
                StatusStore.upStatus(order.id,'ativado')
                # Adicionar nota
                NotesAdd.addNote(order,f'SIM ativado')
            else:
                simActivateTC(id=order.id)
        
        # Ver. Status Cancelled in items
        order_itens = 0
        order_ver = Orders.objects.filter(order_id=order.order_id)
        for ord_v in order_ver:
            if ord_v.order_status != 'CC':
                order_itens += 1 
        
        # Status sis : Status Loja
        status_sis_site = StatusStore.st_sis_site()
        # Só cancelar se todos os itens estiverem cancelados
        if order_itens == 0 and ord_s == 'CC':
            logger.info(f'--------------------------- Alterar STATUS Cancelled')         
            update_store = {
                'status': 'cancelled'
            }
            apiStore.put(f'orders/{order.order_id}', update_store).json()
        elif ord_s != 'CC' or ord_s != 'DE':
            logger.info(f'--------------------------- Alterar STATUS Loja')            
            if ord_s in status_sis_site:
                update_store = {
                    'status': status_sis_site[ord_s]
                }
                apiStore.put(f'orders/{order.order_id}', update_store).json()
                
        # Save Notes
        def addNote(t_note):
            add_sim = Notes( 
                id_item = Orders.objects.get(pk=order.id),
                id_user = user,
                note = t_note,
                type_note = 'S',
            )
            add_sim.save()
        
        ord_status = Orders.order_status.field.choices
        for st in ord_status:
            if order_st == st[0] :
                addNote(f'Alterado de {st[1]} para {order.get_order_status_display()}')
        
        # Enviar email
        if ord_s == 'AT' or (ord_s == 'AA' and sim_put.operator != 'AR'):   
            logger.info(f'--------------------------- Enviar email AT/AA')         
            send_email_sims.delay(id=order_id)
        # if ord_s == 'CN' and (type_sim == 'sim' or order_plan == 'USA'):
        #     send_email_sims.delay(id=order.id)


@shared_task
def up_order_st_store(order_id,order_st):
    logger.info(f'>>>>>>>>>> Alterando status do site')
    apiStore = ApiStore.conectApiStore()
    update_store = {
            'status': order_st
        }
    apiStore.put(f'orders/{order_id}', update_store).json()

