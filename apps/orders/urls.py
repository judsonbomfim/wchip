from django.urls import path
from . import views

urlpatterns = [
    path('listar/', views.orders_list, name='orders_list'),
    path('detalhes/<int:order_id>', views.ord_details, name='ord_details'),
    path('listar/exportar/', views.ord_export, name='ord_export'),
    path('adicionar/', views.ord_add, name='ord_add'),
    path('editar/<int:id>', views.ord_edit, name='ord_edit'),
    path('enviar/esims/', views.send_esims, name='send_esims'),
    path('ativacoes/', views.orders_activations, name='orders_activations'),
    path('ativacoes/exportar', views.ord_export_act, name='ord_export_act'),
    
    # path('texto/', views.textImg, name='text_img'),
    # path('esimstore/', views.esimExpSis, name='esimstore'),
]