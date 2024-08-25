from django.contrib.auth.models import User
from rolepermissions.decorators import has_permission_decorator
import csv
from django.http import HttpResponse
from datetime import date, datetime, timedelta
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.contrib import messages
from django.conf import settings
from apps.orders.models import Orders, Notes
from apps.sims.models import Sims
from apps.send_email.tasks import send_email_sims
from apps.sims.tasks import simDeactivateTC, simActivateTC
from .classes import ApiStore, StatusStore, DateFormats
from .tasks import order_import, orders_up_status
import pandas as pd


#Date today
today = datetime.now()

# Order list
@login_required(login_url='/login/')
@has_permission_decorator('view_orders')
def orders_list(request):
    global orders_l
    orders_l = ''

    url_cdn = settings.URL_CDN

    orders_all = Orders.objects.filter().order_by('-id')
    sims = Sims.objects.all().order_by('-id')
    orders_l = orders_all

    if request.method == 'GET':

        ord_name_f = request.GET.get('ord_name')
        ord_order_f = request.GET.get('ord_order')
        ord_sim_f = request.GET.get('ord_sim')
        oper_f = request.GET.get('oper')
        ord_st_f = request.GET.get('ord_st')

    if request.method == 'POST':

        ord_name_f = request.POST.get('ord_name_f')
        ord_order_f = request.POST.get('ord_order_f')  
        ord_sim_f = request.POST.get('ord_sim_f')
        oper_f = request.POST.get('oper_f')
        ord_st_f = request.POST.get('ord_st_f')

        if 'up_status' in request.POST:
            ord_id = request.POST.getlist('ord_id')
            ord_s = request.POST.get('ord_staus')
            id_user = request.user.id
            if ord_s != '':
                orders_up_status.delay(ord_id, ord_s,id_user)                               

     # FIlters

    url_filter = ''

    if ord_name_f:
        orders_l = orders_l.filter(client__icontains=ord_name_f)
        url_filter += f"&ord_name={ord_name_f}"

    if ord_order_f: 
        orders_l = orders_l.filter(item_id__icontains=ord_order_f)   
        url_filter += f"&ord_order={ord_order_f}"

    if ord_sim_f: 
        orders_l = orders_l.filter(id_sim__sim__icontains=ord_sim_f)
        url_filter += f"&ord_sim={ord_sim_f}"

    if oper_f: 
        orders_l = orders_l.filter(id_sim__operator__icontains=oper_f)
        url_filter += f"&oper={oper_f}"

    if ord_st_f: 
        orders_l = orders_l.filter(order_status__icontains=ord_st_f)
        url_filter += f"&ord_st={ord_st_f}"

    ord_status = Orders.order_status.field.choices
    oper_list = Sims.operator.field.choices

    # Listar status dos pedidos
    ord_st_list = []
    for ord_s in ord_status:
        ord = orders_all.filter(order_status=ord_s[0]).count()
        ord_st_list.append((ord_s[0],ord_s[1],ord))

    # Paginação
    paginator = Paginator(orders_l, 50)
    page = request.GET.get('page')
    orders = paginator.get_page(page)

    from rolepermissions.permissions import available_perm_status

    context = {
        'url_cdn': url_cdn,
        'orders_l': orders_l,
        'orders': orders,
        'sims': sims,
        'ord_st_list': ord_st_list,
        'oper_list': oper_list,
        'url_filter': url_filter,
    }
    return render(request, 'painel/orders/index.html', context)


# Order Edit
@login_required(login_url='/login/')
@has_permission_decorator('edit_orders')
def ord_edit(request,id):
    if request.method == 'GET':
            
        order = Orders.objects.get(pk=id)
        ord_status = Orders.order_status.field.choices
        ord_product = Orders.product.field.choices
        ord_data_day = Orders.data_day.field.choices
        
        context = {
            'order': order,
            'ord_status': ord_status,
            'ord_product': ord_product,
            'ord_data_day': ord_data_day,
            'days': range(1, 31),
        }
        return render(request, 'painel/orders/edit.html', context)
        
    if request.method == 'POST':
        
        print('>>>>>>>>>> EDITAR PEDIDO')
        
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
            if sim_up:
                sim_put = Sims.objects.get(pk=sim_up.id)
                if order_sim != '':
                    # Update SIM
                    updateSIM()
                sim_put.sim_status = 'AT'
                sim_put.save()
                
                if type_sim == 'esim': 
                    ord_st = 'EE'
                else: ord_st = ord_st
                
                order_put = Orders.objects.get(pk=order.id)
                order_put.id_sim_id = sim_put.id
                order_put.order_status = ord_st
                order_put.save()
            else:       
                msg_error.append(f'Não há estoque de {operator} - {type_sim} no sistema')
                        
        # Liberar SIMs
        if ord_st == 'CC' or ord_st == 'DE' or ord_st == 'RE':
            print('>>>>>>>>>> Liberar SIMs')
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
            # Verificar se Operadora e Tipo de SIM estão marcados
            if operator != None and type_sim != None:
                if order_sim != '':
                    # Alterar status no sistema e no site
                    updateSIM()
                
                sims_all = Sims.objects.all().filter(sim=sim)
                if sims_all:
                        messages.info(request,f'O SIM {sim} já está cadastrado no sistema')
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
                msg_error.append(f'Você precisa selecionar o tipo de SIM e a Operadora')
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
                if operator != None and type_sim != None:
                    if product != '974' and type_sim != 'esim':
                        insertSIM(ord_st)
                        up_plan = True # verificação para nota
            
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
        order_put.save()
        
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
            status_sis_site = StatusStore.st_sis_site()
            if ord_st in status_sis_site:            
                
                update_store = {
                    'status': status_sis_site[ord_st]
                }
            apiStore.put(f'orders/{order.order_id}', update_store).json()
            
            # Salvar notas    
            ord_status = Orders.order_status.field.choices
            for st in ord_status:
                if ord_st == st[0] :
                    addNote(f'Alterado de {order.get_order_status_display()} para {st[1]}')
            
            # Enviar email
            if ord_st == 'CN' and type_sim == 'sim':
                send_email_sims(id=order_id)
                
                addNote(f'E-mail enviado com sucesso!')
                messages.success(request,'E-mail enviado com sucesso!')     
        
        if type_sim == 'esim' or esim_v == True:
            # Enviar eSIM para site
            ApiStore.updateEsimStore(order_id) 
        
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
@has_permission_decorator('export_activations')
def ord_export_op(request):
    
    sims_op = Sims.operator.field.choices
    context= {
        'sims_op': sims_op,
    } 
    
    if request.method == 'POST':
        
        ord_op_f = request.POST.get('ord_op_f')
        
        orders_all = Orders.objects.all().order_by('id').filter(order_status='AA')
        
        if ord_op_f != 'op_all':
            orders_all = orders_all.filter(id_sim_id__operator__icontains=ord_op_f)
            
        # Crie uma lista com os dados que você deseja exportar para o CSV
        data = [
            ['Data Compra', 'Pedido', '(e)SIM', 'EID', 'IMEI','Plano', 'Dias', 'Data Aivação', 'Operadora', 'Países']
        ]
        
        ord_prod_list = Orders.product.field.choices
        
        for ord in orders_all:
            ord_date = DateFormats.dateDMA(str(ord.order_date))
            if ord.data_day != 'ilimitado': 
                ord_data = ord.get_data_day_display()
            else: ord_data = ''
            ord_product = f'{ord_prod_list[ord.product]} {ord_data}'
            ord_date_act = DateFormats.dateDMA(str(ord.activation_date))
            if ord.id_sim:
                ord_op = ord.id_sim.get_operator_display()
                ord_sim = ord.id_sim.sim
            else:
                ord_op = '-'
                ord_sim = '-'
            if ord.countries == True:
                ord_countries = 'SIM'
            else: ord_countries = ''
            data.append([ord_date,ord.item_id,ord_sim,ord.cell_eid,ord.cell_imei,ord_product,ord.days,ord_date_act,ord_op,ord_countries])

        data_atual = date.today()
        
        # Crie um objeto CSVWriter para escrever os dados no formato CSV
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="Ativacoes-{data_atual}-{ord_op_f}.csv"'
        writer = csv.writer(response)

        # Escreva os dados no objeto CSVWriter
        for row in data:
            writer.writerow(row)

        messages.success(request, 'Arquivo CSV baixado com sucesso!')
        return response 
    
    return render(request, 'painel/orders/export_op.html', context)


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

        
    fields_df = ['id', 'item_id','client', 'id_sim__sim', 'id_sim__link', 'id_sim__type_sim', 'id_sim__operator', 'product', 'data_day', 'countries', 'days', 'cell_mod', 'cell_eid', 'cell_imei', 'activation_date', 'order_status']

    product_choice_dict = dict(Orders.product.field.choices)
    data_choice_dict = dict(Orders.data_day.field.choices)
    status_choice_dict = dict(Orders.order_status.field.choices)
    
    today = datetime.now()
    days60 = today - timedelta(days=60)
    
    orders_all = Orders.objects.filter(activation_date__gte=days60).order_by('activation_date')
    
    orders_df = pd.DataFrame((orders_all.values(*fields_df)))
    
    
    orders_df['product'] = orders_df['product'].map(product_choice_dict)
    orders_df['data_day'] = orders_df['data_day'].map(data_choice_dict)
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
    shipp_list = Orders.shipping.field.choices
    oper_list = Sims.operator.field.choices

    # Listar status dos pedidos
    ord_st_list = []
    for ord_s in ord_status:
        ord = len(orders_l[orders_l['order_status'] == ord_s[0]])
        ord_st_list.append((ord_s[0],ord_s[1],ord))
        
    # Listar ativações
    today = datetime.now().date()
    activList = orders_l[orders_l['activation_date'].dt.date > today]
    activList = activList.groupby(['id_sim__operator']).size().reset_index(name='countActiv')
    countActivAll = countActivAll = activList['countActiv'].sum()
    try: countActivTM = activList[activList['id_sim__operator'] == 'TM']['countActiv'].values[0]
    except: countActivTM = 0
    try: countActivCM = activList[activList['id_sim__operator'] == 'CM']['countActiv'].values[0]
    except: countActivCM = 0
    try: countActivTC = activList[activList['id_sim__operator'] == 'TC']['countActiv'].values[0]
    except: countActivTC = 0
    
    
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
        'shipp_list': shipp_list,
        'oper_list': oper_list,
        'ord_status': ord_status,        
        'url_filter': url_filter,
        'status_choice_dict': status_choice_dict,
        'countActivAll': countActivAll,
        'countActivTM': countActivTM,
        'countActivCM': countActivCM,
        'countActivTC': countActivTC,
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