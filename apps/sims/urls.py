from django.urls import path
from . import views

urlpatterns = [
    path('listar/', views.sims_list, name='sims_index'),
    path('adicionar/sim/', views.sims_add_sim, name='sims_add_sim'),
    path('adicionar/esim/', views.sims_add_esim, name='sims_add_esim'),
    path('sims/pedidos', views.sims_ord, name='sims_ord'),
    path('estoque/exportar', views.exportSIMs, name='exportSIMs'),
    path('delsim', views.delSIMs, name='delsim'),
    path('delsimtc', views.delSimTC, name='delsimtc'),
    # path('verificar', views.verify_sim, name='verify_sim'),

]