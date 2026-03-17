# celery.py
from __future__ import absolute_import, unicode_literals
from celery import Celery
import os
from urllib.parse import urlparse

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

# Usa Redis simples por padrão e ativa Sentinel apenas quando configurado via ambiente.
sentinel_master = os.getenv('CELERY_REDIS_MASTER_NAME', '').strip()
sentinel_nodes = os.getenv('CELERY_REDIS_SENTINELS', '').strip()

if sentinel_master and sentinel_nodes:
    sentinels = []
    for node in sentinel_nodes.split(','):
        host, _, port = node.strip().partition(':')
        if host and port:
            sentinels.append((host, int(port)))

    parsed_broker = urlparse(app.conf.broker_url)
    parsed_backend = urlparse(app.conf.result_backend)
    broker_db = parsed_broker.path or '/0'
    backend_db = parsed_backend.path or broker_db

    app.conf.update(
        broker_url=f'sentinel://{sentinel_master}{broker_db}',
        result_backend=f'redis://{sentinel_master}{backend_db}',
        broker_transport_options={
            'master_name': sentinel_master,
            'sentinels': sentinels,
            'socket_timeout': 0.1,
        },
    )

app.autodiscover_tasks()