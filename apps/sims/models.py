from django.db import models

SIM_STATUS = [
    ('AT', 'Ativado'),
    ('CC', 'Cancelado'),    
    ('DS', 'Disponível'),
    ('DE', 'Desativado'),
    ('IN', 'Indisponível'),
    ('TC', 'Troca'),
]
SIM_OPERATOR = [
    ('TM', 'T-Mobile'), 
    ('CM', 'China Mobile'),
    ('TC', 'Telcom'),
    ('VR', 'Verizon'),
]
SIM_TYPES = [
    ('sim', 'SIM (Físico)'),   
    ('esim', 'eSIM (Virtual)'),
]

class Sims(models.Model):
    id = models.AutoField(primary_key=True, serialize=False)
    sim = models.CharField(max_length=25)
    link = models.URLField(null=True, blank=True, default='-')
    type_sim =  models.CharField(max_length=20, choices=SIM_TYPES, default='sim')
    operator = models.CharField(max_length=20, choices=SIM_OPERATOR)
    sim_status = models.CharField(max_length=20, choices=SIM_STATUS, default='DS')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        db_table = 'sims'
        verbose_name = 'Sim'
        verbose_name_plural = 'Sims'
        ordering = ['id']
    def __str__(self):
        return self.sim