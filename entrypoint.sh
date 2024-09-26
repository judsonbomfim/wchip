#!/bin/sh

python manage.py migrate
python manage.py collectstatic --noinput
nohup --config gunicorn_config.py core.wsgi:application --bind 0.0.0.0:8000 --log-level=info &
nohup celery -A core worker -B --loglevel=info


python3 manage.py makemigrations
python3 manage.py migrate --noinput
python3 manage.py collectstatic --noinput
gunicorn --config gunicorn_config.py core.wsgi:application