from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from apps.send_email.tasks import send_email_sims

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