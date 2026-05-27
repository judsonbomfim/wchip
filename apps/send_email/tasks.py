import logging
from celery import shared_task
from django.shortcuts import redirect
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from apps.orders.models import Orders, Notes
from apps.orders.classes import ApiStore, StatusStore
from apps.send_email.models import Templates

logger = logging.getLogger('apps.send_email')


def _get_email_templates():
    """Carrega os três templates de e-mail do banco de uma só vez."""
    qs = Templates.objects.filter(slug__in=['esim_eua', 'esim_other', 'sim_all'])
    return {t.slug: t.content for t in qs}


@shared_task
def send_email_sims(id=None):
        
    orders_all = None
    if id == None:
        orders_all = Orders.objects.filter(order_status='EE')
    else:
        orders_all = Orders.objects.filter(pk=id)
            
    url_site = settings.URL_CDN
    url_img = f'{url_site}/email/'

    email_templates = _get_email_templates()

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
        operator = order.id_sim.operator
                
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
            'tracking': order.tracking,
            'operator': operator,
            'esim_eua_content': email_templates.get('esim_eua', ''),
            'esim_other_content': email_templates.get('esim_other', ''),
            'sim_all_content': email_templates.get('sim_all', ''),
        }
        try:
            html_content = render_to_string('painel/emails/send_email.html', context)
        except Exception as e:
            logger.error(
                '>>>>>>>>>>>>>>>>>>> ERRO ao renderizar template do pedido #%s - Cliente: %s - Erro: %s',
                order_id,
                client_email,
                str(e),
                exc_info=True,
            )
            continue

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
        
        try:
            email.send()
            logger.info(f">>>>>>>>>>>>>>>>>>> E-mail enviado com sucesso para pedido #{order_id}")
        except Exception as e:
            logger.error(f">>>>>>>>>>>>>>>>>>> ERRO ao enviar email para pedido #{order_id} - Cliente: {client_email} - Erro: {str(e)}", exc_info=True)
            continue
        
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
        
        try:
            email.send()
            logger.info(f">>>>>>>>>>>>>>>>>>> E-mail de rastreio enviado com sucesso para pedido #{order_id}")
        except Exception as e:
            logger.error(f">>>>>>>>>>>>>>>>>>> ERRO ao enviar email de rastreio para pedido #{order_id} - Cliente: {client_email} - Erro: {str(e)}", exc_info=True)
            continue
        add_note = Notes( 
            id_item = order,
            id_user = None,
            note = 'E-mail de rastreio enviado com sucesso!',
            type_note = 'S',
        )
        add_note.save()
    
    url_site = settings.URL_CDN
    url_img = f'{url_site}/email/'
 