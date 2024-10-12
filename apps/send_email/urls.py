from django.urls import path
from . import views

urlpatterns = [
    path('enviar/<int:id>', views.send_email, name='send_email'),
    path('enviar_esims', views.send_email_esims, name='send_email_esims'),
    path('visualizar', views.visualizar, name='visualizar'),
]