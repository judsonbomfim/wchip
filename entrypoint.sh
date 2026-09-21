#!/bin/sh
set -e

mkdir -p /djangoweb/logs
if [ "$(id -u)" = "0" ]; then
  chown -R duser:duser /djangoweb/logs
fi

as_duser() {
  if [ "$(id -u)" = "0" ]; then
    su -s /bin/sh duser -c "$(printf '%q ' "$@")"
  else
    "$@"
  fi
}

as_duser_exec() {
  if [ "$(id -u)" = "0" ]; then
    exec su -s /bin/sh duser -c "exec $(printf '%q ' "$@")"
  else
    exec "$@"
  fi
}

ensure_log_files() {
  as_duser sh -c '
    for f in django.log celery.log api_calls.log performance.log app.log error.log sims.log orders.log; do
      touch "/djangoweb/logs/$f"
    done
  '
}

if [ "$1" = "/djangoweb/scripts/entrypoint.sh" ] && [ "$#" -eq 1 ]; then
  set -- web
fi

if [ "$1" = "web" ]; then
  ensure_log_files
  as_duser sh -c '
    set -e
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
    exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --log-level=info --timeout 300
  '
fi

ensure_log_files
as_duser_exec "$@"
