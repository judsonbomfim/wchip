import logging
from celery import shared_task
from django.shortcuts import redirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from apps.orders.models import Orders, Notes
from apps.orders.classes import ApiStore, StatusStore

logger = logging.getLogger('apps.send_email')

@shared_task
def send_email_sims(id=None):
    
    logger.info(f">>>>>>>>>>>>>>>>>>> Tarefa send_email_sims iniciada para id: {id}")
    
    orders_all = None
    if id == None:
        orders_all = Orders.objects.filter(order_status='EE')
    else:
        orders_all = Orders.objects.filter(pk=id)
    
    logger.info(f">>>>>>>>>>>>>>>>>>> Iniciando envio de email para {len(orders_all)} pedidos com status 'EE'")
        
    url_site = settings.URL_CDN
    url_img = f'{url_site}/email/'

    
    for order in orders_all:
        id = order.id
        name = order.client
        client_email = order.email
        order_id = order.item_id
        order_st = order.order_status
        try: qrcode = order.id_sim.link
        except: qrcode = None
        activation_date = order.activation_date
        product = f'{order.get_product_display()} {order.get_data_day_display()}'
        days = order.days     
        product_plan = order.product
        try: type_sim = order.id_sim.type_sim
        except: continue            
        countries = order.countries
        
        logger.info(f">>>>>>>>>>>>>>>>>>> Enviando email para pedido #{order_id} - Cliente: {name} - E-mail: {client_email}")
        
        context = {
            'url_site': url_site,
            'url_img': url_img,
            'name': name,
            'order_id': order_id,
            'qrcode': qrcode,
            'activation_date': activation_date,
            'product': product,
            'days': days,
            'product_plan': product_plan,
            'type_sim': type_sim,
            'countries': countries,        
        }
        html_content = render_to_string('painel/emails/send_email.html', context)
        text_content = strip_tags(html_content)
        if type_sim == 'esim':
            subject = f"Entrega do eSIM PEDIDO #{order_id}"
        else:
            subject = f"Informações PEDIDO #{order_id}"
        email = EmailMultiAlternatives(
            #subject
            subject,
            #content
            text_content,
            #from email
            settings.DEFAULT_FROM_EMAIL,
            #to
            [client_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        logger.info(f">>>>>>>>>>>>>>>>>>> E-mail enviado com sucesso para pedido #{order_id}")
        
        # if order_st != 'CN' and type_sim == 'esim':
        #     if product_plan == '980' or product_plan == '977':
        #         # Update Order
        #         order = Orders.objects.get(pk=id)
        #         order.order_status = 'AI'
        #         order.save()
        #         # Update Store
        #     else:
        #         # Update Order
        #         order = Orders.objects.get(pk=id)
        #         order.order_status = 'AA'
        #         order.save()
        #         # Update Store
        #         apiStore = ApiStore.conectApiStore()
        #         status_def_sis = StatusStore.st_sis_site()            
        #         update_store = {
        #             'status': status_def_sis['AA']
        #         }
        #         apiStore.put(f'orders/{order.order_id}', update_store).json()
        
        # Add note
        add_note = Notes( 
            id_item = order,
            id_user = None,
            note = 'E-mail enviado com sucesso!',
            type_note = 'S',
        )
        add_note.save()

@shared_task
def send_tracking(id=None):
    
    orders_all = None
    if id == None:
        orders_all = Orders.objects.filter(order_status='EE')
    else:
        orders_all = Orders.objects.filter(pk=id)
        
    url_site = settings.URL_CDN
    url_img = f'{url_site}/email/'

    
    for order in orders_all:
        id = order.id
        name = order.client
        client_email = order.email
        order_id = order.item_id
        order_st = order.order_status
        product = f'{order.get_product_display()} {order.get_data_day_display()}'
        tracking = order.tracking
        
        context = {
            'url_site': url_site,
            'url_img': url_img,
            'name': name,
            'order_id': order_id,
            'product': product,
            'tracking': tracking,
        }
        html_content = render_to_string('painel/emails/send_email_tracking.html', context)
        text_content = strip_tags(html_content)
        subject = f"RASTREIO DO PEDIDO #{order_id}"
        email = EmailMultiAlternatives(
            #subject
            subject,
            #content
            text_content,
            #from email
            settings.DEFAULT_FROM_EMAIL,
            #to
            [client_email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send()
        
        # Add note
        add_note = Notes( 
            id_item = order,
            id_user = None,
            note = 'E-mail de rastreio enviado com sucesso!',
            type_note = 'S',
        )
        add_note.save()
    
    url_site = settings.URL_CDN
    url_img = f'{url_site}/email/'
 