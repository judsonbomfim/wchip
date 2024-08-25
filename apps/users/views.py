from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import auth
from django.contrib import messages


# Create your views here.
def login(request):
    
    if request.method == 'GET':
        
        return render(request, 'painel/users/login.html')

    if request.method == 'POST':
        name_form = request.POST['name_form']
        pass_form = request.POST['pass_form']
        user_f = auth.authenticate(
            request,
            username=name_form,
            password=pass_form
        )
        if user_f is not None:
            auth.login(request, user_f)
            messages.success(request, f'{name_form} logado com sucesso!')
            return redirect('dashboard')
        else:
            messages.error(request, 'Usuário ou senha inválidos')
            return redirect('login')

@login_required(login_url='/login/')
def logout(request):
    auth.logout(request)
    messages.success(request, 'Logout efetuado com sucesso!')
    return render(request, 'painel/users/login.html')
