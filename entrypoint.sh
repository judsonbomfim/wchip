#!/bin/sh

# python3 manage.py migrate
# python3 manage.py collectstatic --noinput
# nohup gunicorn core.wsgi:application --bind 0.0.0.0:8000 --log-level=info &
# nohup celery -A core worker -B --loglevel=info


if [ "$DATABASE" = "postgres" ]
then
    echo "Waiting for postgres..."

    while ! nc -z $SQL_HOST $SQL_PORT; do
      sleep 0.1
    done

    echo "PostgreSQL started"
fi

python manage.py flush --no-input
python manage.py migrate
python manage.py collectstatic --no-input --clear
nohup celery -A core worker -B --loglevel=info

exec "$@"