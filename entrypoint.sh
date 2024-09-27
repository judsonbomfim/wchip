#!/bin/sh

python3 manage.py migrate
python3 manage.py collectstatic --noinput
nohup gunicorn core.wsgi:application --bind 0.0.0.0:8000 --log-level=info &
nohup celery -A core worker -B --loglevel=info