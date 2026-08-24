from venv import logger

from django.contrib.auth.models import User
from rolepermissions.decorators import has_permission_decorator
from rolepermissions.checkers import has_permission
from django.core.exceptions import PermissionDenied
import csv
from django.http import HttpResponse, JsonResponse
from datetime import date, datetime, timedelta
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.conf import settings
from django.db import DataError
from django.db.models import Count, Q
from django.urls import reverse
from urllib.parse import urlencode
from apps.orders.models import Orders, Notes
from apps.sims.models import Sims
from apps.sims.classes import ApiTC, ApiCM, ApiCMHK
from apps.send_email.tasks import send_email_sims, send_tracking
from apps.sims.tasks import simDeactivateTC, simActivateTC
from .classes import ApiStore, StatusStore, DateFormats
from .tasks import orders_up_status
import pandas as pd



#Date today
today = datetime.now()

ORDERS_LIST_PER_PAGE_CHOICES = (25, 50, 100, 200)
ORDERS_LIST_DEFAULT_PER_PAGE = 50


def _orders_list_params(request):
    """Lê filtros da listagem (GET/POST) e normaliza per_page."""
    src = request.POST if request.method == 'POST' else request.GET
    q = (src.get('q') or '').strip()
    oper_f = (src.get('oper') or src.get('oper_f') or '').strip()
    ord_st_f = (src.get('ord_st') or src.get('ord_st_f') or '').strip()
    # Compatibilidade com filtros antigos
    ord_name_f = (src.get('ord_name') or src.get('ord_name_f') or '').strip()
    ord_order_f = (src.get('ord_order') or src.get('ord_order_f') or '').strip()
    ord_sim_f = (src.get('ord_sim') or src.get('ord_sim_f') or '').strip()

    try:
        per_page = int(src.get('per_page') or ORDERS_LIST_DEFAULT_PER_PAGE)
    except (TypeError, ValueError):
        per_page = ORDERS_LIST_DEFAULT_PER_PAGE
    if per_page not in ORDERS_LIST_PER_PAGE_CHOICES:
        per_page = ORDERS_LIST_DEFAULT_PER_PAGE

    return {
        'q': q,
        'oper': oper_f,
        'ord_st': ord_st_f,
        'ord_name': ord_name_f,
        'ord_order': ord_order_f,
        'ord_sim': ord_sim_f,
        'per_page': per_page,
    }


def _apply_orders_list_filters(qs, params):
    q = params.get('q')
    if q:
        qs = qs.filter(
            Q(client__icontains=q)
            | Q(item_id__icontains=q)
            | Q(id_sim__sim__icontains=q)
        )

    if params.get('ord_name'):
        qs = qs.filter(client__icontains=params['ord_name'])
    if params.get('ord_order'):
        qs = qs.filter(item_id__icontains=params['ord_order'])
    if params.get('ord_sim'):
        qs = qs.filter(id_sim__sim__icontains=params['ord_sim'])
    if params.get('oper'):
        qs = qs.filter(id_sim__operator=params['oper'])
    if params.get('ord_st'):
        qs = qs.filter(order_status=params['ord_st'])
    return qs


def _orders_list_url_filter(params):
    query = {}
    if params.get('q'):
        query['q'] = params['q']
    if params.get('ord_name'):
        query['ord_name'] = params['ord_name']
    if params.get('ord_order'):
        query['ord_order'] = params['ord_order']
    if params.get('ord_sim'):
        query['ord_sim'] = params['ord_sim']
    if params.get('oper'):
        query['oper'] = params['oper']
    if params.get('ord_st'):
        query['ord_st'] = params['ord_st']
    if params.get('per_page') and params['per_page'] != ORDERS_LIST_DEFAULT_PER_PAGE:
        query['per_page'] = params['per_page']
    return f'&{urlencode(query)}' if query else ''


def _orders_list_redirect(params=None):
    url = reverse('orders_list')
    if not params:
        return redirect(url)
    query = _orders_list_url_filter(params)
    return redirect(f'{url}?{query[1:]}' if query else url)


# Order list
@login_required(login_url='/login/')
@has_permission_decorator('view_orders')
def orders_list(request):
    url_cdn = settings.URL_CDN
    params = _orders_list_params(request)

    if request.method == 'POST' and 'up_status' in request.POST:
        ord_id = request.POST.getlist('ord_id')
        ord_s = request.POST.get('ord_staus') or request.POST.get('ord_status')
        id_user = request.user.id
        if ord_s and ord_id:
            orders_up_status.delay(ord_id, ord_s, id_user)
        return _orders_list_redirect(params)

    orders_base = Orders.objects.all().order_by('-id')
    orders_l = _apply_orders_list_filters(orders_base, params)
    orders_count = orders_l.count()

    status_counts = {
        row['order_status']: row['total']
        for row in Orders.objects.values('order_status').annotate(total=Count('id'))
    }
    ord_st_list = [
        (code, label, status_counts.get(code, 0))
        for code, label in Orders.order_status.field.choices
    ]
    oper_list = Sims.operator.field.choices

    paginator = Paginator(orders_l.select_related('id_sim'), params['per_page'])
    orders = paginator.get_page(request.GET.get('page') or request.POST.get('page') or 1)
    url_filter = _orders_list_url_filter(params)

    request.session['orders_list_filters'] = {
        'q': params['q'],
        'oper': params['oper'],
        'ord_st': params['ord_st'],
        'ord_name': params['ord_name'],
        'ord_order': params['ord_order'],
        'ord_sim': params['ord_sim'],
    }

    context = {
        'url_cdn': url_cdn,
        'link_esim_android': settings.LINK_ESIM_ANDROID,
        'link_esim_ios': settings.LINK_ESIM_IOS,
        'orders_l': orders_l,
        'orders': orders,
        'ord_st_list': ord_st_list,
        'oper_list': oper_list,
        'url_filter': url_filter,
        'q': params['q'],
        'oper_f': params['oper'],
        'ord_st_f': params['ord_st'],
        'per_page': params['per_page'],
        'per_page_choices': ORDERS_LIST_PER_PAGE_CHOICES,
        'orders_count': orders_count,
    }
    return render(request, 'painel/orders/index.html', context)


@login_required(login_url='/login/')
@has_permission_decorator('view_orders')
def ord_details(request, order_id):
    data_d = {
        '500mb-dia': '500',
        '1gb-dia': '1000',
        '2gb-dia': '2000',
        '1gb': '1000',
        '2gb': '2000',
        'ilimitado': 'Ilimitado',
        '1gb-periodo': '1000',
        '2gb-periodo': '2000',
        '3gb-periodo': '3000',
        '5gb-periodo': '5000',
        '10gb-periodo': '10000',
        '20gb-periodo': '20000',
        '30gb-periodo': '30000',
    }

    order = get_object_or_404(Orders, pk=order_id)
    name = order.client
    sim = order.id_sim.sim if order.id_sim else ''
    data_day = data_d.get(order.data_day, '') if order.data_day else ''
    data_day_d = order.get_data_day_display() if order.data_day else ''
    operator = order.id_sim.operator if order.id_sim else ''
    product = order.get_product_display()
    mobile_data_f = '0.00'
    percent_used = 0
    mobile_data = ''

    if operator == 'TC' and sim:
        mobile_data = ApiTC.mobileData(sim)
    elif operator == 'CM' and sim:
        mobile_data = ApiCM.mobileData(sim)
    elif operator == 'CMHK' and sim:
        mobile_data = ApiCMHK.mobileData(sim)

    if mobile_data != '' and mobile_data is not None:
        try:
            mobile_data_f = f"{float(mobile_data):.2f}"
        except (TypeError, ValueError):
            mobile_data_f = '0.00'

    if data_day and data_day != 'Ilimitado':
        try:
            total_data = float(data_day)
            used_data = float(mobile_data) if mobile_data not in ('', None) else 0.0
            percent_used = round((used_data / total_data) * 100, 2) if total_data else 0
        except Exception:
            percent_used = 0

    operator_label = order.id_sim.get_operator_display() if order.id_sim else operator
    return JsonResponse({
        'name': name,
        'sim': sim,
        'data_day': data_day,
        'data_day_d': data_day_d,
        'operator': operator_label or operator,
        'product': product,
        'mobile_data': mobile_data_f,
        'percent_used': percent_used,
    })


@login_required(login_url='/login/')
def ord_export(request):
    if not (
        request.user.is_superuser
        or has_permission(request.user, 'export_orders')
        or has_permission(request.user, 'export_activations')
    ):
        raise PermissionDenied
    list_status = dict(Orders.order_status.field.choices)
    list_oper = dict(Sims.operator.field.choices)
    list_prod = dict(Orders.product.field.choices)
    list_data = dict(Orders.data_day.field.choices)

    filters = request.session.get('orders_list_filters')
    if filters is None:
        messages.error(
            request,
            'Nenhum dado disponível para exportação. Abra a lista de pedidos antes de exportar.',
        )
        return redirect('orders_list')

    qs = _apply_orders_list_filters(Orders.objects.all().order_by('-id'), filters)
    data = [
        ['Pedido', 'Cliente', '(e)SIM', 'Operadora', 'Produto', 'Países', 'Voz', 'Dias', 'Data Aivação', 'Data Término', 'Status']
    ]

    for row in qs.values(
        'item_id', 'client', 'id_sim__sim', 'id_sim__operator',
        'product', 'data_day', 'countries', 'voice', 'days',
        'activation_date', 'order_status',
    ):
        ad = row.get('activation_date')
        days_val = row.get('days') or 0
        ret = (ad + timedelta(days=days_val - 1)) if (ad and days_val) else None
        prod = list_prod.get(row['product'], row['product'] or '')
        data_day_disp = list_data.get(row.get('data_day'), row.get('data_day') or '')
        ord_data = '' if not data_day_disp or data_day_disp == 'Ilimitado' else data_day_disp
        ord_product = f'{prod} {ord_data}'.strip()
        data.append([
            row['item_id'],
            row['client'],
            row['id_sim__sim'],
            list_oper.get(row['id_sim__operator'], ''),
            ord_product,
            'SIM' if row['countries'] else '',
            'SIM' if row['voice'] else '',
            row['days'],
            DateFormats.dateDMA(str(ad)) if ad else '',
            DateFormats.dateDMA(str(ret)) if ret else '',
            list_status.get(row['order_status'], row['order_status']),
        ])

    data_atual = date.today()
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Pedidos-{data_atual}.csv"'
    writer = csv.writer(response)
    for csv_row in data:
        writer.writerow(csv_row)
    return response


# Order Edit
@login_required(login_url='/login/')
@has_permission_decorator('edit_orders')
def ord_add(request):
    max_bigint = 9223372036854775807
    ord_status = Orders.order_status.field.choices
    ord_product = Orders.product.field.choices
    ord_data_day = Orders.data_day.field.choices
    ord_operators = Sims.operator.field.choices
    days = list(range(1, 31))

    context = {
        'ord_status': ord_status,
        'ord_product': ord_product,
        'ord_data_day': ord_data_day,
        'ord_operators': ord_operators,
        'ord_days': days,
    }

    if request.method == 'GET':
        return render(request, 'painel/orders/add.html', context)
    
    order_id = (request.POST.get('order_id') or '').strip()
    client = request.POST.get('client')
    email = request.POST.get('email')
    cell_mod = request.POST.get('cell_mod')
    days_value = request.POST.get('days')
    product = request.POST.get('product')
    data_day = request.POST.get('data_day')
    type_sim = request.POST.get('type_sim')
    operator = request.POST.get('operator')
    shipping = (request.POST.get('shipping') or '').strip()
    sim = request.POST.get('sim').strip()
    activation_date = request.POST.get('activation_date')
    cell_imei = request.POST.get('cell_imei')
    cell_eid = request.POST.get('cell_eid')
    tracking = request.POST.get('tracking')
    countries = request.POST.get('countries') == 'True'
    voice = request.POST.get('voice') == 'True'
    ord_st = request.POST.get('ord_st_f')
    ord_note = request.POST.get('ord_note')

    if not order_id or not client or not product or not data_day or not days_value or not activation_date or not ord_st or not shipping:
        messages.error(request, 'Preencha todos os campos obrigatórios para criar o pedido.')
        return render(request, 'painel/orders/add.html', context)

    try:
        order_id_int = int(order_id)
    except ValueError:
        messages.error(request, 'O número do pedido precisa ser numérico.')
        return render(request, 'painel/orders/add.html', context)

    if order_id_int < 0 or order_id_int > max_bigint:
        messages.error(request, 'Número do pedido fora do limite suportado.')
        return render(request, 'painel/orders/add.html', context)

    try:
        days_int = int(days_value)
    except ValueError:
        messages.error(request, 'Selecione um número de dias válido.')
        return render(request, 'painel/orders/add.html', context)

    if len(shipping) > 40:
        messages.error(request, 'O frete deve ter no máximo 40 caracteres.')
        return render(request, 'painel/orders/add.html', context)

    item_cont = Orders.objects.filter(order_id=order_id_int).count() + 1
    item_id = f'{order_id_int}-{item_cont}'

    id_sim = None
    if sim:
        if Sims.objects.filter(sim=sim, sim_status='AT').exists():
            messages.error(request, f'O SIM {sim} já está cadastrado no sistema.')
            return render(request, 'painel/orders/add.html', context)

        sim_exists = Sims.objects.filter(sim=sim).first()
        if sim_exists:
            sim_exists.sim_status = 'AT'
            sim_exists.type_sim = type_sim
            sim_exists.operator = operator
            sim_exists.save()
            id_sim = sim_exists
        else:
            id_sim = Sims.objects.create(
                sim=sim,
                type_sim=type_sim,
                operator=operator,
                sim_status='AT',
            )
    try:
        order = Orders.objects.create(
            order_id=order_id_int,
            item_id=item_id,
            client=client,
            email=email,
            product=product,
            data_day=data_day,
            qty=1,
            days=days_int,
            cell_mod=cell_mod,
            cell_imei=cell_imei,
            cell_eid=cell_eid,
            activation_date=activation_date,
            order_date=datetime.now(),
            order_status=ord_st,
            shipping=shipping,
            type_sim=type_sim,
            oper_sim=operator,
            id_sim=id_sim,
            tracking=tracking,
            countries=countries,
            voice=voice,
        )
    except DataError:
        messages.error(request, 'Erro de limite de dados no banco. Execute as migrações do app orders e tente novamente.')
        return render(request, 'painel/orders/add.html', context)

    if ord_note:
        Notes.objects.create(
            id_item=order,
            id_user=User.objects.get(pk=request.user.id),
            note=ord_note,
            type_note='S',
        )

    messages.success(request, f'Pedido {order.item_id} criado com sucesso!')
    return redirect('orders_list')


@login_required(login_url='/login/')
@has_permission_decorator('edit_orders')
def ord_edit(request,id):
    if request.method == 'GET':
            
        order = Orders.objects.get(pk=id)
        ord_status = Orders.order_status.field.choices
        ord_product = Orders.product.field.choices
        ord_data_day = Orders.data_day.field.choices
        ord_operators = Sims.operator.field.choices
        
        days = list(range(1, 31))
        
        context = {
            'order': order,
            'ord_status': ord_status,
            'ord_product': ord_product,
            'ord_data_day': ord_data_day,
            'ord_operators': ord_operators,
            'ord_days': days,
        }
        return render(request, 'painel/orders/edit.html', context)
        
    if request.method == 'POST':
        
        logger.info(f'>>>>>>>>>> EDITAR PEDIDO')
        
        global msg_info
        msg_info = []
        global msg_error
        msg_error = []
        global id_sim
        id_sim = ''
        global ord_st
        ord_st = ''
        global update_store
        update_store = {}
        
        order = Orders.objects.get(pk=id)
        order_id = order.order_id
        try: order_sim = order.id_sim.sim
        except: order_sim = ''
        try: sim_id = int(order.id_sim.id)
        except: sim_id = ''
        days = request.POST.get('days')
        product = request.POST.get('product')
        data_day = request.POST.get('data_day')
        type_sim = request.POST.get('type_sim')
        operator = request.POST.get('operator')
        sim = request.POST.get('sim')
        activation_date = request.POST.get('activation_date')
        email = request.POST.get('email')
        cell_imei = request.POST.get('cell_imei')
        cell_eid = request.POST.get('cell_eid')
        lpa = (request.POST.get('lpa') or '').strip()
        tracking = request.POST.get('tracking')
        ord_st = request.POST.get('ord_st_f')
        ord_note = request.POST.get('ord_note')
        up_oper = request.POST.get('upOper')
        esim_v = None
                
        # Update SIM in Order and update SIM
        def updateSIM():
            # Update SIM
            sim_put = Sims.objects.get(pk=sim_id)            
            sim_put.sim_status = 'TC'
            sim_put.save()
            # Delete SIM in Order
            order_put = Orders.objects.get(pk=order.id)
            order_put.id_sim_id = ''
            order_put.save()
        
        # Insert SIM in Order
        def insertSIM(ord_st=None):
            sim_up = Sims.objects.filter(sim_status='DS', type_sim=type_sim, operator=operator).first()
            logger.info(f'>>>>>>>>>> SIM UP:',sim_up)
            if sim_up:
                sim_put = Sims.objects.get(pk=sim_up.id)
                if order_sim != '':
                    # Update SIM
                    updateSIM()
                sim_put.sim_status = 'AT'
                sim_put.save()
                
                if type_sim == 'esim': 
                    ord_st = 'AA'
                else: ord_st = ord_st
                
                order_put = Orders.objects.get(pk=order.id)
                order_put.id_sim_id = sim_put.id
                order_put.order_status = ord_st
                order_put.save()
            else:       
                msg_error.append(f'Não há estoque de {operator} - {type_sim} no sistema')
                logger.info(f'>>>>>>>>>> Não há estoque de SIMs')
                        
        # Liberar SIMs
        if ord_st == 'CC' or ord_st == 'DE' or ord_st == 'RE':
            logger.info(f'>>>>>>>>>> Liberar SIMs')
            if order_sim != '':
                # Change TC
                if order.id_sim.operator == 'TC':
                    simDeactivateTC(id=order.id)
                
                # Update SIM
                sim_put = Sims.objects.get(pk=sim_id)
                sim_put.sim_status = 'DE'
                sim_put.save()    

        # Activate TC
        if ord_st == 'AT' and order.order_status != 'AT' and operator == 'TC':
            simActivateTC(id=order.id)

        # Se SIM preenchico
        if sim:
            if order_sim != '':
                # Alterar status no sistema e no site
                updateSIM()
            
            sims_all = Sims.objects.all().filter(sim=sim)
            if sims_all:
                # Attualizar SIM
                sim_put = Sims.objects.get(sim=sim)            
                sim_put.sim_status = 'AT'
                sim_put.save()
                # Atualizar pedido
                order_put = Orders.objects.get(pk=order.id)
                order_put.id_sim_id = sim_put
                order_put.save()
            else:
                # Save SIMs - Insert Stock
                add_sim = Sims( 
                    sim = sim,
                    type_sim = type_sim,
                    operator = operator,
                    sim_status = 'AT',
                )
                add_sim.save()
            
                # Update order
                order_put = order
                order_put.id_sim_id = add_sim.id
                order_put.save()
                up_plan = True # verificação para nota
        else:
            # Troca de SIM
            if order_sim != '':
                if order.id_sim.operator != operator or order.id_sim.type_sim != type_sim or up_oper != None:
                    updateSIM()
                    insertSIM(ord_st)
                    up_plan = True # verificação para nota
                    
                    # Update SIM
                    esim_v = True             
            else:             
                if product != '974' and type_sim != 'esim':
                    insertSIM(ord_st)
                    up_plan = True # verificação para nota
        
        
        # if tracking != order.tracking:
        #     send_tracking(id=order.id)           
            
                    
        # Update Order
        if activation_date == '':
            activation_date = order.activation_date
        if email == '':
            email = order.email
                
        order_put = Orders.objects.get(pk=order.id)
        order_put.days = days
        order_put.product = product
        order_put.data_day = data_day
        order_put.activation_date = activation_date
        order_put.email = email
        order_put.cell_imei = cell_imei
        order_put.cell_eid = cell_eid
        order_put.tracking = tracking
        order_put.order_status = ord_st
        order_put.type_sim = type_sim
        order_put.oper_sim = operator
        order_put.save()

        if order_put.id_sim_id:
            sim_lpa = Sims.objects.filter(pk=order_put.id_sim_id).first()
            if sim_lpa is not None:
                sim_lpa.lpa = lpa or None
                sim_lpa.save(update_fields=['lpa'])
        
        # Notes
        def addNote(t_note):
            add_sim = Notes( 
                id_item = Orders.objects.get(pk=order.id),
                id_user = User.objects.get(pk=request.user.id),
                note = t_note,
                type_note = 'S',
            )
            add_sim.save()
        # Save Notes
        if ord_note:
            addNote(ord_note)
        # Date Notes
        if activation_date != order.activation_date:
            addNote(f'Alteração de {DateFormats.dateDMA(str(order.activation_date))} para {DateFormats.dateDMA(str(activation_date))}')
        # SIM Notes
        if sim:
            addNote(f'Alteração de {order_sim} para {sim}')
        # Plan Notes
        try:
            if up_plan:
                addNote(f'Plano alterado')
        except: pass
        
        # Conect Store
        apiStore = ApiStore.conectApiStore() 
            
        # Status Notes
        if ord_st != order.order_status:
            # Alterar status
            # Status sis : Status Loja
            orders_up_status.delay([order.id], ord_st, request.user.id)
                       
            # Enviar email
            if ord_st == 'AT' or (ord_st == 'AA' and operator != 'AR'):
                send_email_sims(id=order_id)                
                messages.success(request,'E-mail enviado com sucesso para o cliente!')     
        
        for msg_e in msg_error:
            messages.error(request,msg_e)
        for msg_o in msg_info:
            messages.info(request,msg_o)
        messages.success(request,f'Pedido {order.order_id} atualizado com sucesso!')
        return redirect('orders_list')


@login_required(login_url='/login/')
@has_permission_decorator('export_orders')
def ord_export_act(request):
    
    list_status = dict(Orders.order_status.field.choices)
    list_oper = dict(Sims.operator.field.choices)
    
    orders_all = request.session.get('orders_act')
    data = [
        ['Pedido', 'Cliente', '(e)SIM', 'Operadora', 'Produto', 'Países', 'Dias', 'Data Aivação', 'Data Término', 'Status']
    ]
    
    for ord in orders_all:
        ord_operator = list_oper[ord['id_sim__operator']]
        if ord['data_day'] != 'Ilimitado': 
            ord_data = ord['data_day']
        else: ord_data = ''
        ord_product = f"{ord['product']} {ord_data}"
        ord_date_start = DateFormats.dateDMA(str(ord['activation_date']))
        ord_date_end = DateFormats.dateDMA(str(ord['return_date']))
        if ord['countries'] == True:
            ord_countries = 'SIM'
        else: ord_countries = ''
        ord_status = list_status[ord['order_status']]
        
        data.append([ord['item_id'],ord['client'],ord['id_sim__sim'],ord_operator,ord_product,ord_countries,ord['days'],ord_date_start,ord_date_end,ord_status])
        
    data_atual = date.today()
    
    # Crie um objeto CSVWriter para escrever os dados no formato CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Ativacoes-{data_atual}.csv"'
    writer = csv.writer(response)
    
    # Escreva os dados no objeto CSVWriter
    for row in data:
        writer.writerow(row)
    return response 


@login_required(login_url='/login/')
def send_esims(request):
    if request.method == 'GET':
        return render(request, 'painel/orders/send_esim.html')
    if request.method == 'POST':
        # Orderm Import       
        send_email_sims.delay()
        messages.success(request, 'Processando emails... Aguarde alguns minutos e atualize a página de pedidos')
        return redirect('send_esims')


@login_required(login_url='/login/')
@has_permission_decorator('list_activations')
def orders_activations(request):
    global orders_l
    orders_l = []
    url_filter = ''
    activGoing_f = None
    activGoing_1 = None
    activGoing_2 = None
    activReturn_f = None
    activReturn_1 = None
    activReturn_2 = None
    oper_f = None
    ord_st_f = None

        
    fields_df = ['id', 'item_id','client', 'id_sim__sim', 'id_sim__link', 'id_sim__type_sim', 'id_sim__operator', 'oper_sim', 'product', 'data_day', 'countries', 'days', 'cell_mod', 'cell_eid', 'cell_imei', 'activation_date', 'order_status']

    product_choice_dict = dict(Orders.product.field.choices)
    data_choice_dict = dict(Orders.data_day.field.choices)
    status_choice_dict = dict(Orders.order_status.field.choices)
    
    today = datetime.now()
    days60 = today - timedelta(days=60)
    
    orders_all = Orders.objects.filter(activation_date__gte=days60).order_by('activation_date')
    
    orders_df = pd.DataFrame(orders_all.values(*fields_df), columns=fields_df)
    
    
    orders_df['product'] = orders_df['product'].map(product_choice_dict)
    orders_df['data_day'] = orders_df['data_day'].map(data_choice_dict)
    orders_df['id_sim__operator'] = orders_df['id_sim__operator'].fillna('')
    orders_df['oper_sim'] = orders_df['oper_sim'].fillna('')
    orders_df['id_sim__operator'] = orders_df['id_sim__operator'].where(
        orders_df['id_sim__operator'] != '',
        orders_df['oper_sim']
    )
    orders_df['activation_date'] = pd.to_datetime(orders_df['activation_date'])
    orders_df['return_date'] = orders_df['activation_date'] + pd.to_timedelta(orders_df['days'], unit='d') - pd.to_timedelta(1, unit='d')
    
    orders_l = orders_df
    
    if request.method == 'GET':
        
        if request.GET.get('activGoing_1'): activGoing_1 = request.GET.get('activGoing_1')
        if request.GET.get('activGoing_2'): activGoing_2 = request.GET.get('activGoing_2')
        if request.GET.get('activReturn_1'): activReturn_1 = request.GET.get('activReturn_1')
        if request.GET.get('activReturn_2'): activReturn_2 = request.GET.get('activReturn_2')
        if request.GET.get('oper'): oper_f = request.GET.get('oper')
        if request.GET.get('ord_st'): ord_st_f = request.GET.get('ord_st')        

    if request.method == 'POST':

        if request.POST.get('activGoing_f'): activGoing_f = request.POST.get('activGoing_f')
        if request.POST.get('activReturn_f') : activReturn_f = request.POST.get('activReturn_f')
        if request.POST.get('oper_f'): oper_f = request.POST.get('oper_f')
        if request.POST.get('ord_st_f'): ord_st_f = request.POST.get('ord_st_f')
        
        if activGoing_f is not None:
            activGoing = [item.strip() for item in activGoing_f.split('-')]
            activGoing_1 = DateFormats.dateF(activGoing[0])
            try: 
                activGoing_2 = DateFormats.dateF(activGoing[1])
                orders_l = orders_l[(orders_l['activation_date'] >= activGoing_1) & (orders_l['activation_date'] <= activGoing_2)]
                url_filter += f"&activGoing_1={activGoing_1}&activGoing_2={activGoing_2}"
            except:
                orders_l = orders_l[(orders_l['activation_date'] == activGoing_1)]
                url_filter += f"&activGoing_1={activGoing_1}"  
                
        
        if activReturn_f is not None:
            activReturn = [item.strip() for item in activReturn_f.split('-')]
            activReturn_1 = DateFormats.dateF(activReturn[0])
            try: 
                activReturn_2 = DateFormats.dateF(activReturn[1])
                orders_l = orders_l[(orders_l['return_date'] >= activReturn_1) & (orders_l['return_date'] <= activReturn_2)]
                url_filter += f"&activReturn_1={activReturn_1}&activReturn_2={activReturn_2}"
            except:
                orders_l = orders_l[(orders_l['return_date'] == activReturn_1)]
                url_filter += f"&activReturn_1={activReturn_1}"
            
        if oper_f is not None:
            orders_l = orders_l[(orders_l['id_sim__operator'] == oper_f)]
            url_filter += f"&oper={oper_f}"
            

        if ord_st_f is not None:
            orders_l = orders_l[(orders_l['order_status'] == ord_st_f)]
            url_filter += f"&ord_st={ord_st_f}"


        if 'up_status' in request.POST:
            ord_id = request.POST.getlist('ord_id')
            ord_s = request.POST.get('ord_staus')
            id_user = request.user.id

            orders_up_status.delay(ord_id, ord_s,id_user)                        

    
        # End up_status / POST

    sims = Sims.objects.all()
    ord_status = Orders.order_status.field.choices
    oper_list = Sims.operator.field.choices

    # Listar status dos pedidos
    ord_st_list = []
    for ord_s in ord_status:
        ord = len(orders_l[orders_l['order_status'] == ord_s[0]])
        ord_st_list.append((ord_s[0],ord_s[1],ord))
        
    # Listar ativações pendentes por operadora
    activList = orders_df[orders_df['order_status'] == 'AA']
    activList = activList.groupby(['id_sim__operator']).size().reset_index(name='countActiv')
    countActivAll = activList['countActiv'].sum()
    try: countActivTM = activList[activList['id_sim__operator'] == 'TM']['countActiv'].values[0]
    except: countActivTM = 0
    try: countActivCM = activList[activList['id_sim__operator'] == 'CM']['countActiv'].values[0]
    except: countActivCM = 0
    try: countActivCMHK = activList[activList['id_sim__operator'] == 'CMHK']['countActiv'].values[0]
    except: countActivCMHK = 0
    try: countActivTC = activList[activList['id_sim__operator'] == 'TC']['countActiv'].values[0]
    except: countActivTC = 0
    try: countActivVR = activList[activList['id_sim__operator'] == 'VR']['countActiv'].values[0]
    except: countActivVR = 0
    
    
    # Save in session
    orders_act = orders_l.copy()
    orders_act['activation_date'] = orders_act['activation_date'].astype(str)
    orders_act['return_date'] = orders_act['return_date'].astype(str)
    orders_act = orders_act.to_dict(orient='records')
    request.session['orders_act'] = orders_act
    # List
    orders_l = orders_l.to_dict('records')
  
    
    # Paginação
    paginator = Paginator(orders_l, 100)
    page = request.GET.get('page', 1)
    orders = paginator.get_page(page)
    
    context = {
        'orders_l': orders_l,
        'orders': orders,
        'sims': sims,
        'ord_st_list': ord_st_list,
        'oper_list': oper_list,
        'ord_status': ord_status,        
        'url_filter': url_filter,
        'status_choice_dict': status_choice_dict,
        'countActivAll': countActivAll,
        'countActivTM': countActivTM,
        'countActivCM': countActivCM,
        'countActivCMHK': countActivCMHK,
        'countActivTC': countActivTC,
        'countActivVR': countActivVR,
        'oper_f': oper_f or '',
        'ord_st_f': ord_st_f or '',

    }
    return render(request, 'painel/orders/activations.html', context)
    

# def textImg(request):
#     # Carrega a imagem em escala de cinza
#     img = cv2.imread('static/imei2.jpg', cv2.IMREAD_GRAYSCALE)
#     # Extrai o texto da imagem
#     texto = pytesseract.image_to_string(img)
#     textos = texto.split()
#     txt = []
#     for t in textos:
#         txt.append(f'{t}<br>')
    
#     return HttpResponse(txt)

# def esimExpSis(request):
    
        
#     apiStore = ApiStore.conectApiStore()
#     # Get the order
#     order_id = 54085
    
#     # Add the meta data
#     meta_data_list = {
#         "meta_data":[
#             {
#                 "key": "campo_esims",
#                 "value": "<img src='https://painel.acasadochip.com/media/8932042000002302486.jpeg' style='width: 300px; margin:40px;'><img src='https://painel.acasadochip.com/media/8932042000002302486.jpeg' style='width: 300px; margin:40px;'>"
#             },
#         ]
#     }

#     # Update the order
#     apiStore.put(f"orders/{order_id}", meta_data_list).json()    
#     return HttpResponse('eSIM enviado!')

# # def vendasSem(request):
# apiStore = conectApiStore()
# dateNow = datetime.datetime.now()  

# dateSem = datetime.datetime.now() - datetime.timedelta(days=7)
# vendasDaSemana = apiStore.get('reports/sales', params={'date_min': dateSem, 'date_max': dateNow})