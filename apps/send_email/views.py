import logging
from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.contrib import messages
from kombu.exceptions import OperationalError
from apps.send_email.tasks import send_email_sims, send_tracking as send_tracking_task
from apps.send_email.models import Templates

logger = logging.getLogger('apps.send_email')

@login_required(login_url='/login/')
def send_email(request,id):
    try:
        send_email_sims.delay(id=id)
        messages.success(request, 'E-mail enfileirado com sucesso!')
    except OperationalError:
        logger.exception('Falha na fila Celery ao enfileirar envio do pedido #%s', id)
        send_email_sims(id=id)
        messages.warning(request, 'Fila indisponivel. E-mail enviado em modo direto.')
    except Exception:
        logger.exception('Erro inesperado ao enfileirar envio do pedido #%s', id)
        messages.error(request, 'Nao foi possivel iniciar o envio de e-mail.')
    return redirect('orders_list')    


@login_required(login_url='/login/')
@require_POST
def send_email_esims(request):
    send_email_sims.delay()
    messages.success(request, 'Envio em lote enfileirado com sucesso!')
    return redirect('orders_list')


@login_required(login_url='/login/')
@require_POST
def send_tracking(request):
    send_tracking_task.delay()
    messages.success(request, 'Envio de rastreio enfileirado com sucesso!')
    return redirect('orders_list')

    
@login_required(login_url='/login/')
def visualizar(request):
    return render(request, 'painel/emails/send_email.html')


@login_required(login_url='/login/')
def edit_templates(request):
    template_defs = [
        ('esim_eua', 'eSIM EUA'),
        ('esim_other', 'eSIM Outros'),
        ('sim_all', 'SIM Fisico'),
    ]

    if request.method == 'POST':
        for slug, name in template_defs:
            content = request.POST.get(f'content_{slug}', '')
            Templates.objects.update_or_create(
                slug=slug,
                defaults={'name': name, 'content': content},
            )

        messages.success(request, 'Templates atualizados com sucesso.')
        return redirect('email_templates_edit')

    existing_templates = {
        item.slug: item
        for item in Templates.objects.filter(
            slug__in=[slug for slug, _ in template_defs]
        )
    }

    templates_data = []
    for slug, name in template_defs:
        template_obj = existing_templates.get(slug)
        templates_data.append(
            {
                'slug': slug,
                'name': name,
                'content': template_obj.content if template_obj else '',
            }
        )

    return render(
        request,
        'painel/emails/edit_template.html',
        {'templates_data': templates_data},
    )