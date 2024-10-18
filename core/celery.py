# celery.py
from __future__ import absolute_import, unicode_literals
from celery import Celery
import os

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

app = Celery('core')

CELERY_CONFIG = {
    "CELERY_TASK_SERIALIZER": "json",
    "CELERY_ACCEPT_CONTENT": ["json"],
    "CELERY_RESULT_SERIALIZER": "json",
    "CELERY_RESULT_BACKEND": None,
    "CELERY_TIMEZONE": "America/Sao_Paulo",
    "CELERY_ENABLE_UTC": True,
    "CELERY_ENABLE_REMOTE_CONTROL": False,
}

app.config_from_object('django.conf:settings', namespace='CELERY')

# Configuração do Redis com suporte a failover
app.conf.update(
    broker_url='redis://master.redis:6379/0',
    result_backend='redis://master.redis:6379/0',
    broker_transport_options={
        'master_name': 'mymaster',
        'sentinels': [('sentinel1.redis', 26379), ('sentinel2.redis', 26379)],
        'socket_timeout': 0.1,
    },
)

app.autodiscover_tasks()