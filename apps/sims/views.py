from django.contrib.auth.decorators import login_required
from rolepermissions.decorators import has_permission_decorator
from django.shortcuts import render
from django.http import HttpResponse
from django.urls import reverse
from datetime import date
from django.core.paginator import Paginator
from django.contrib import messages
from django.conf import settings
from django.core.files.storage import default_storage
import csv
import imghdr
import boto3

from apps.sims.models import Sims
from apps.orders.models import Orders
from apps.orders.classes import ApiStore
from .tasks import sims_in_orders


# Script Upload S3
def get_s3_client():
    return boto3.client(
        's3', 
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID, 
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY
    )

def upload_file_to_s3(file):
    s3 = get_s3_client()
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    file_path = f"{settings.MEDIA_LOCATION}/{file.name}"
    s3.upload_fileobj(file, bucket_name, file_path)
    return default_storage.url(file_path)

@login_required(login_url='/login/')
@has_permission_decorator('view_sims')
def sims_list(request):
    global sims_l
    sims_l = ''
    
    sims_all = Sims.objects.all().order_by('-id')
    sims_l = sims_all
    url_cdn = settings.URL_CDN
    
    if request.method == 'GET':
        
        sim_f = request.GET.get('sim')
        sim_type_f = request.GET.get('sim_type')    
        sim_status_f = request.GET.get('sim_status')
        sim_oper_f = request.GET.get('sim_oper')
    
    if request.method == 'POST':
        
        sim_f = request.POST.get('sim_f')
        sim_type_f = request.POST.get('sim_type_f')       
        sim_status_f = request.POST.get('sim_status_f')
        sim_oper_f = request.POST.get('sim_oper_f')
            
        if 'up_status' in request.POST:
                sim_id = request.POST.getlist('sim_id')
                sim_st = request.POST.get('sim_st')
                if sim_id and sim_st:
                    for o_id in sim_id:
                        sim = Sims.objects.get(pk=o_id)
                        sim.sim_status = sim_st
                        sim.save()
                        
                    messages.success(request,f'SIM(s) atualizado(s) com sucesso!')
                else:
                    messages.info(request,f'Você precisa marcar alguma opção')
    
    # FIlters
    
    url_filter = ''
    
    if sim_f:
        sims_l = sims_l.filter(sim__icontains=sim_f)
        url_filter += f"&sim={sim_f}"

    if sim_type_f: 
        sims_l = sims_l.filter(type_sim__icontains=sim_type_f)        
        url_filter += f"&sim_type={sim_type_f}"
    
    if sim_status_f: 
        sims_l = sims_l.filter(sim_status__icontains=sim_status_f)
        url_filter += f"&sim_status={sim_status_f}"
    
    if sim_oper_f: 
        sims_l = sims_l.filter(operator__icontains=sim_oper_f)
        url_filter += f"&sim_oper={sim_oper_f}"
        
    
    sims_types = Sims.type_sim.field.choices
    sims_status = Sims.sim_status.field.choices
    sims_oper = Sims.operator.field.choices
    
    paginator = Paginator(sims_l, 50)
    page = request.GET.get('page')
    sims = paginator.get_page(page)
    
    # Verificar estoque de operadoras
    sim_tm = sims_all.filter(sim_status='DS',operator='TM', type_sim='sim').count()
    esim_tm = sims_all.filter(sim_status='DS',operator='TM', type_sim='esim').count()
    sim_cm = sims_all.filter(sim_status='DS',operator='CM', type_sim='sim').count()
    esim_cm = sims_all.filter(sim_status='DS',operator='CM', type_sim='esim').count()
    sim_tc = sims_all.filter(sim_status='DS',operator='TC', type_sim='sim').count()
    esim_tc = sims_all.filter(sim_status='DS',operator='TC', type_sim='esim').count()
    
    url = reverse('sims_index')
    
    context= {
        'url': url,
        'url_cdn': url_cdn,
        'sims': sims,
        'sims_types': sims_types,
        'sims_status': sims_status,
        'sims_oper': sims_oper,
        'sim_tm': sim_tm,
        'esim_tm': esim_tm,
        'sim_cm': sim_cm,
        'esim_cm': esim_cm,
        'sim_tc': sim_tc,
        'esim_tc': esim_tc,
        'url_filter': url_filter,
    }
       
    return render(request, 'painel/sims/index.html', context)

@login_required(login_url='/login/')
@has_permission_decorator('add_sims')
def sims_add_sim(request):
    
    from rolepermissions.permissions import available_perm_status
    
    global orders_l
    orders_l = ''

    orders_all = Orders.objects.all().order_by('-id').filter(order_status='AS').filter(id_sim=None)
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
        
        # Salvar Pedido com SIM
        if 'save_sims' in request.POST:
            order_ids = request.POST.getlist('ord_id')
            for order_id in order_ids:
                ord_id = int(order_id)
                order = Orders.objects.get(id=ord_id)
                item_id = order.order_id
                ord_oper = request.POST.get(f'ord_oper_{ord_id}')
                ord_sim = request.POST.get(f'ord_sim_{ord_id}')
                
                print(f'item_id >>>>>>>>> {item_id}')
                
                if ord_sim != '':
                    # Salvar SIM
                    add_sim = Sims(
                        sim = ord_sim,
                        type_sim = 'sim',
                        operator = ord_oper,
                        sim_status = 'AT'
                    )
                    add_sim.save()
                    sim_id = add_sim.id
                    # Salvar Pedido
                    order.id_sim = add_sim
                    order.order_status = 'AE'                
                    order.save()
                    #ALterar status no site
                    try:
                        apiStore = ApiStore.conectApiStore()
                        update_store = {
                                'status': 'agd-envio'
                            }
                        apiStore.put(f'orders/{item_id}', update_store).json()
                        
                        apiStore = ApiStore.conectApiStore()
                        update_store = {
                                'status': 'agd-envio'
                            }
                        apiStore.put(f'orders/{order_id}', update_store).json()
                                        
                    except Exception as e:
                        messages.error(request,f'Erro ao atualizar status do pedido {order} no site: {e}')
                    
            messages.success(request,f'SIM(s) atualizado(s) com sucesso!')        
    
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
    shipp_list = Orders.shipping.field.choices
    
    # Listar status dos pedidos
    ord_st_list = []
    for ord_s in ord_status:
        ord = orders_all.filter(order_status=ord_s[0]).count()
        ord_st_list.append((ord_s[0],ord_s[1],ord))
    
    # Paginação
    paginator = Paginator(orders_l, 50)
    page = request.GET.get('page')
    orders = paginator.get_page(page)
    
    print(f'orders >>>>>>>>> {orders}')
    print(f'orders_l >>>>>>>>> {orders_l}')

    context = {
        'orders_l': orders_l,
        'orders': orders,
        'oper': '',
        'ord_st_list': ord_st_list,
        'oper_list': oper_list,
        'shipp_list': shipp_list,
        'url_filter': url_filter,
    }
    return render(request, 'painel/sims/add-sim.html', context)

@login_required(login_url='/login/')
@has_permission_decorator('edit_sims')
def sims_add_esim(request):
    if request.method == "GET":
        
        operator_list = Sims.operator.field.choices
        
        context = {
            'operator_list': operator_list,
        }
        
        return render(request, 'painel/sims/add-esim.html', context)
    
    if request.method == 'POST':
                
        type_sim = request.POST.get('type_sim')
        operator = request.POST.get('operator')
        esims = request.FILES.getlist('esim')
 
        if type_sim == '' or operator == '' or esims == '':
            messages.error(request,'Preencha todos os campos')
            return render(request, 'painel/sims/add-esim.html')
                           
        
        for sim_img in esims:
            sim_i = sim_img.name.split('.')
            
            print(sim_img.name)
            print(sim_img)
            
            fileurl = ''
            if imghdr.what(sim_img):
                fileurl = upload_file_to_s3(sim_img)
                fileurl = fileurl.replace(settings.URL_CDN,'')
            else:
                messages.error(request,'O arquivo não é uma imagem. Verifique por favor!')
                return render(request, 'painel/sims/add-esim.html')           

            
            sims_all = Sims.objects.all().filter(sim=sim_i[0]).filter(type_sim='esim')
            if sims_all:
                messages.info(request,f'O SIM {sim_i[0]} já está cadastrado no sistema')
                continue
            # Save SIMs
            add_sim = Sims(
                sim = sim_i[0],
                link = fileurl,
                type_sim = type_sim,
                operator = operator
            )
            add_sim.save()

        messages.success(request,'Lista gravada com sucesso')
        return render(request, 'painel/sims/add-esim.html')

@login_required(login_url='/login/')
@has_permission_decorator('add_ord_sims')
def sims_ord(request):
    if request.method == "GET":
        return render(request, 'painel/sims/sim-order.html')
    
    if request.method == 'POST':
        
        sims_in_orders.delay()
        messages.success(request, f'Processando SIMs... Aguarde alguns minutos e atualize a página de pedidos')        
        
    return render(request, 'painel/sims/sim-order.html')

@login_required(login_url='/login/')
@has_permission_decorator('export_activations')
def exportSIMs(request):
    
    sims_all = Sims.objects.all().order_by('id')
    data = [
        ['ID', 'SIM', 'Tipo', 'Operadora', 'Status']
    ]
    for sim in sims_all:
        data.append([sim.id,sim.sim,sim.type_sim,sim.operator,sim.sim_status])
    
    data_atual = date.today()
    # Crie um objeto CSVWriter para escrever os dados no formato CSV
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="Estoque SIMs-{data_atual}.csv"'
    writer = csv.writer(response)

    # Escreva os dados no objeto CSVWriter
    for row in data:
        writer.writerow(row)

    return response

@login_required(login_url='/login/')
def delSIMs(request):
    orders = Orders.objects.all()
    
    sims_cc = Sims.objects.filter(sim_status='CC')
    sims_tc = Sims.objects.filter(sim_status='TC')
    
    for sim in sims_cc:
        if orders.filter(id_sim=sim.id):
            continue
        sim.delete()
    
    for sim in sims_tc:
        if orders.filter(id_sim=sim.id):
            continue
        sim.delete()
    
    return HttpResponse('SIMs deletados com sucesso')

@login_required(login_url='/login/')
def delSimTC(request):
    list_icc = {
        '8932042000002327335',
        '8932042000002327334',
        '8932042000002327333',
        '8932042000002327332',
        '8932042000002327331',
        '8932042000002327330',
        '8932042000002327329',
        '8932042000002327328',
        '8932042000002327327',
        '8932042000002327326',
    }
    
    sims = Sims.objects.filter(type_sim='esim', operator='TC')
    
    for sim in sims:
        sim_iccid = sim.sim
        if sim_iccid not in list_icc:
            sim.orders_set.all().update(id_sim=None)  # Set foreign key to NULL in related Order objects
            sim.delete()
            print(f'SIM {sim_iccid} deletado com sucesso!')
        else:
            print(f'SIM {sim_iccid} não deletado!')
    
    print('>>>>>>>>>>>>>>>>>>> FINALIZADO')
    return HttpResponse('SIMs deletados com sucesso')


# @login_required(login_url='/login/')
# def verify_sim(request):
#     simsAT = Sims.objects.all().filter(sim_status='AT').filter(type_sim='sim')
#     simsDS = Sims.objects.all().filter(sim_status='DS').filter(type_sim='sim')
#     simsTC = Sims.objects.all().filter(sim_status='TC')
#     orders = Orders.objects.all()

#     print('>>>>>> SIMs Ativados sem pedidos')
#     print('----------------------------------')
#     for simAT in simsAT:    
#         if orders.filter(id_sim__sim=simAT.sim):
#             continue
#         else:
#             print(simAT.sim,simAT.type_sim)
            
#     print('>>>>>> SIMs Disponíveis com pedidos')
#     print('----------------------------------')
#     for simDS in simsDS:
#         if orders.filter(id_sim__sim=simDS.sim):
#             print(simDS.sim,simDS.type_sim)
#         else:
#             continue
    
#     print('>>>>>> SIMs Troca com pedidos')
#     print('----------------------------------')
#     for simTC in simsTC:
#         if orders.filter(id_sim__sim=simTC.sim):
#             print(simTC.sim,simDS.type_sim)
#         else:
#             continue
            
#     return HttpResponse('Links corrigidos com sucesso')