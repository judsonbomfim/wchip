from django.db import models
from django.contrib.auth.models import User
from apps.sims.models import Sims

PRODUCT = [
    ('981', 'Norte Verizon'),
    ('980', 'Norte T-Mobile'),
    ('979', 'EUA Flex'),
    ('976', 'EUA Controle'),
    ('977', 'EUA Ilimitado'),
    ('975', 'Mundo'),
    ('974', 'Europa Flex'),
    ('971', 'Europa Controle'),
]

DATA = [
    ('500mb-dia', '500MB/Dia'),
    ('1gb-dia', '1GB / Dia'),
    ('2gb-dia', '2GB / Dia'),
    ('5gb-mes', '5GB / Mês'),
    ('10gb-mes', '10GB / Mês'),
    ('20gb-mes', '20GB / Mês'),
    ('30gb-mes', '30GB / Mês'),
    ('ilimitado', 'Ilimitado'),
]

ORDER_STATUS = [
    ('AA', 'Agd. Ativação'),
    ('AE', 'Agd. Envio'),
    ('AG', 'Agência'),
    ('AS', 'Atribuir SIM'),
    ('AI', 'Atribuir IMEI'),
    ('AT', 'Ativado'),
    ('CC', 'Cancelado'),
    ('CN', 'Concluido'),
    ('DE', 'Desativado'),
    ('DA', 'Data em Aberto'),
    ('EA', 'Erro Ativação'),
    ('ED', 'Erro Desativação'),
    ('EE', 'Enviar E-mail'),
    ('ES', 'Em Separação'),
    ('MB', 'Motoboy'),
    ('PC', 'Pag. Confirmado!'),
    ('PR', 'Processando'),
    ('RE', 'Reembolsar'),
    ('RB', 'Reembolsado'),
    ('RS', 'Reuso'),
    ('RP', 'Reprocessar'),
    ('RT', 'Retirada'),
    ('VS', 'Verificar SIM'),
]

SHIPMENTS = [
    ('FN', 'Frete Normal'),
    ('FE', 'Frete Expresso'),
    ('RT', 'Retirada'),
    ('MD', 'Mordomo'),
]

SHIP = [
    ('FN', 'Frete Normal'),
    ('FE', 'Frete Expresso'),
    ('RT', 'Retirada'),
    ('MD', 'Mordomo'),
]

class Orders(models.Model):
    id = models.AutoField(primary_key=True)
    order_id = models.IntegerField(default=0)
    item_id = models.CharField(max_length=15)
    client_id = models.IntegerField(null=True)  # Temporariamente permitindo nulo
    client = models.CharField(max_length=70)
    email = models.CharField(max_length=70, null=True, blank=True)
    product = models.CharField(max_length=50, choices=PRODUCT)
    data_day = models.CharField(max_length=30, choices=DATA)
    qty = models.IntegerField()
    coupon = models.CharField(max_length=25, default='')
    days = models.IntegerField()
    countries = models.BooleanField(default=False)
    cell_mod = models.CharField(max_length=45, null=True, blank=True)
    cell_imei = models.CharField(max_length=35, null=True, blank=True)
    cell_eid = models.CharField(max_length=35, null=True, blank=True)
    ord_chip_nun = models.CharField(max_length=35, null=True, blank=True)
    shipping = models.CharField(max_length=20, choices=SHIPMENTS, default='FN')
    ship = models.CharField(max_length=20, choices=SHIP, default='FN')
    order_date = models.DateTimeField()
    activation_date = models.DateField()
    order_status = models.CharField(max_length=20, choices=ORDER_STATUS, default='PR')
    type_sim = models.CharField(max_length=4, null=True, blank=True, default='sim')
    oper_sim = models.CharField(max_length=2, null=True, blank=True)
    id_sim = models.ForeignKey(Sims, on_delete=models.DO_NOTHING, null=True, blank=True)
    tracking = models.CharField(max_length=25, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'orders'
        verbose_name = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering = ['order_id']

TYPE_NOTE = [
    ('S', 'Sistema'),
    ('P', 'Privada'),
]

class Notes(models.Model):
    id = models.AutoField(primary_key=True)
    id_item = models.ForeignKey(Orders, on_delete=models.DO_NOTHING, related_name='order_notes', default='')
    id_user = models.ForeignKey(User, on_delete=models.DO_NOTHING, related_name='user_notes', default='', null=True, blank=True)
    note = models.TextField()
    type_note = models.CharField(max_length=1, choices=TYPE_NOTE, default='S')
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = 'notes'
        verbose_name = 'Nota'
        verbose_name_plural = 'Notas'
        ordering = ['-id']
    def __str__(self):
        return str(self.id_item)