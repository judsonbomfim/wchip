import os

from woocommerce import API
import environ
from django.conf import settings
from apps.orders.models import Orders, Notes

# Inicialize o `environ`
env = environ.Env(
    DEBUG=(bool, False)
)  

class DateFormats():
    # Date - 2023-05-16T18:40:27
    @staticmethod
    def dateHour(dh):
        date = dh[0:10]
        hour = dh[11:19]
        date_hour = f'{date} {hour}'
        return date_hour
    # Date - 17/06/2023
    @staticmethod
    def dateF(d):
        dia = d[0:2]
        mes = d[3:5]
        ano = d[6:10]
        dataForm = f'{ano}-{mes}-{dia}'
        return dataForm
    # Date - 2023-05-17 00:56:18+00:00 > 00/00/00
    @staticmethod
    def dateDMA(dma):
        ano = dma[2:4]
        mes = dma[5:7]
        dia = dma[8:10]
        data_dma = f'{dia}/{mes}/{ano}'
        return data_dma

# Conect woocommerce api
class ApiStore():
    @staticmethod
    def conectApiStore():
        wcapi = API(
            url = str(os.getenv('url_site')),
            consumer_key = str(os.getenv('consumer_key')),
            consumer_secret = str(os.getenv('consumer_secret')),
            wp_api = True,
            version = 'wc/v3',
            timeout = 5000
        )
        return wcapi

class StatusStore():
    @staticmethod
    def st_sis_site():
        status_sis_site = {
            'AA': 'agd-ativacao',
            'AE': 'agd-envio',
            'AG': 'agencia',
            'AS': 'em-andamento',
            'AI': 'em-andamento',
            'AT': 'ativado',
            'CC': 'cancelled',
            'CN': 'completed', 
            'DE': 'desativado', 
            'DA': 'data-em-aberto',
            'DS': 'desativado', 
            'EI': 'em-andamento',
            'EE': 'em-andamento',
            'ES': 'em-separacao',
            'MB': 'motoboy',
            'PV': 'agd-ativacao',
            'RE': 'reembolsar',
            'RB': 'reembolsado',
            'RC': 'reembolso-parcial',
            'RS': 'reuso',
            'RT': 'retirada',
        }
        return status_sis_site

class UpdateStore():
    @staticmethod
    def upStore(order_id=None, status_g=None):
        
        apiStore = ApiStore.conectApiStore()
        
        update_store = {}
        
        # Preparar status geral
        if status_g is not None:
            status_sis_site = StatusStore.st_sis_site()
            if status_g in status_sis_site:
                update_store['status'] = status_sis_site[status_g]
        
        # Fazer a requisição
        if update_store:
            try:
                response = apiStore.put(f'orders/{order_id}', update_store)
                if response.status_code in [200, 201]:
                    return True
                else:
                    return False                    
            except Exception as e:
                print(f"Erro ao atualizar pedido {order_id} na loja: {e}")
                return False        

class NoteStore():
    @staticmethod
    def addNoteStore(order_id,note,user_name='Sistema'):
        order_id = order_id
        note = note
        user_name = user_name
        apiStore = ApiStore.conectApiStore()
        note_i = f'{user_name} - {note}'        
        add_note = {
            "note": note_i
        }
        apiStore.post(f'orders/{order_id}/notes', add_note).json()        

class DateFormats():
    # Date - 2023-05-16T18:40:27
    @staticmethod
    def dateHour(dh):
        date = dh[0:10]
        hour = dh[11:19]
        date_hour = f'{date} {hour}'
        return date_hour
    # Date - 17/06/2023
    @staticmethod
    def dateF(d):
        dia = d[0:2]
        mes = d[3:5]
        ano = d[6:10]
        dataForm = f'{ano}-{mes}-{dia}'
        return dataForm
    # Date - 2023-05-17 00:56:18+00:00 > 00/00/00
    @staticmethod
    def dateDMA(dma):
        ano = dma[2:4]
        mes = dma[5:7]
        dia = dma[8:10]
        data_dma = f'{dia}/{mes}/{ano}'
        return data_dma

class NotesAdd():
    @staticmethod
    def addNote(id_item,note,id_user=None,type_note='S'):
        add_sim = Notes( 
            id_item = id_item,
            id_user = id_user,
            note = note,
            type_note = type_note,
        )
        add_sim.save()

class UpdateOrder():
    @staticmethod
    def upStatus(order_id,order_st):
        order = Orders.objects.get(pk=order_id)
        order.order_status = order_st
        order.save()