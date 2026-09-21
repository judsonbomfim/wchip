#!/bin/sh
set -e

echo "Criando diretório de logs..."
mkdir -p /djangoweb/logs
touch /djangoweb/logs/django.log
touch /djangoweb/logs/celery.log
touch /djangoweb/logs/api_calls.log
touch /djangoweb/logs/performance.log
touch /djangoweb/logs/app.log
touch /djangoweb/logs/error.log
touch /djangoweb/logs/sims.log
touch /djangoweb/logs/orders.log

if [ "$1" != "web" ]; then
    exec "$@"
fi

echo "Executando migrações..."
python manage.py migrate --noinput

echo "Sincronizando grupos e permissões de roles..."
python manage.py sync_roles --all_permissions

if [ "${COLLECTSTATIC_ON_STARTUP:-false}" = "true" ]; then
    echo "Executando collectstatic..."
    python manage.py collectstatic --noinput
else
    echo "COLLECTSTATIC_ON_STARTUP=false: collectstatic ignorado no startup"
fi

echo "Iniciando Gunicorn..."
exec gunicorn core.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-3}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    --max-requests 500 \
    --max-requests-jitter 50 \
    --access-logfile - \
    --error-logfile - \
    --log-level=info \
    --forwarded-allow-ips="${GUNICORN_FORWARDED_ALLOW_IPS:-*}"
