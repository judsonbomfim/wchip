#!/bin/sh

echo "Criando diretório de logs..."
mkdir -p /djangoweb/logs
touch /djangoweb/logs/django.log
touch /djangoweb/logs/celery.log
touch /djangoweb/logs/api_calls.log
touch /djangoweb/logs/performance.log

echo "Executando migrações..."
python manage.py migrate

echo "Sincronizando grupos e permissões de roles..."
python manage.py sync_roles --all_permissions

if [ "${COLLECTSTATIC_ON_STARTUP:-false}" = "true" ]; then
    echo "Executando collectstatic..."
    python manage.py collectstatic --noinput
else
    echo "COLLECTSTATIC_ON_STARTUP=false: collectstatic ignorado no startup"
fi

echo "Iniciando Gunicorn..."
gunicorn core.wsgi:application --bind 0.0.0.0:8000 --log-level=info --timeout 300

# Nota: Celery worker e beat agora rodam em containers dedicados
# Veja docker-compose.yml: serviços 'celery' e 'celery_beat'