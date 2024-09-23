from woocommerce import API
import environ
from django.conf import settings
from apps.orders.models import Orders, Notes

# Inicialize o `environ`
env = environ.Env(
    DEBUG=(bool, False)
)

# Conect woocommerce api
class ApiStore():
    @staticmethod
    def conectApiStore():
        wcapi = API(
            url = str(env('url_site')),
            consumer_key = str(env('consumer_key')),
            consumer_secret = str(env('consumer_secret')),
            wp_api = True,
            version = 'wc/v3',
            timeout = 5000
        )
        return wcapi

    @staticmethod
    def updateEsimStore(order_id):    
        url_painel = str(settings.env('URL_PAINEL'))
        esims_order = Orders.objects.filter(order_id=order_id).filter(id_sim__link__isnull=False)
        esims_list = ''
        update_store = {"meta_data":[{"key": "campo_esims","value": ''}]}
        if esims_order:
            for esims_o in esims_order:
                link_sim = esims_o.id_sim.link              
                esims_list = esims_list + f"<img src='{url_painel}{link_sim}' style='width: 300px; margin:40px;'>"
                update_store = {
                    "meta_data": [
                        {
                            "key": "campo_esims",
                            "value": esims_list
                        }
                    ]
                }
        else:
            pass
        # Conect Store
        apiStore = ApiStore.conectApiStore()
        apiStore.put(f'orders/{order_id}', update_store).json() 

class StatusStore():
    @staticmethod
    def st_sis_site():
        status_sis_site = {
            'AA': 'agd-ativacao',
            'AE': 'agd-envio',
            'AG': 'agencia',
            'AS': 'em-separacao',
            'AT': 'ativado',
            'CN': 'completed', 
            'DA': 'data-em-aberto', 
            'DS': 'desativado', 
            'ES': 'em-separacao',
            'MB': 'motoboy',
            'RE': 'reembolsar',
            'RS': 'reuso',
            'RT': 'retirada',
        }
        return status_sis_site
    
    @staticmethod
    def upStatus(order_id,order_st):
        apiStore = ApiStore.conectApiStore()
        update_store = {
                'status': order_st
            }
        apiStore.put(f'orders/{order_id}', update_store).json()
        

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
