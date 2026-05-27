from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.send_email.tasks import send_email_sims
from apps.send_email.models import Templates

@login_required(login_url='/login/')
def send_email(request,id):
    send_email_sims.delay(id=id)    
    messages.success(request,f'E-mail enviado com sucesso!!')
    return redirect('orders_list')    


@login_required(login_url='/login/')
def send_email_esims():
    send_email_sims.delay()


@login_required(login_url='/login/')
def send_tracking():
    send_tracking.delay()

    
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