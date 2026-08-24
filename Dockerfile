FROM python:3.12.1-slim-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /djangoweb

COPY requirements.txt .

RUN apt-get update && apt-get install -y nano libglib2.0-0 libgomp1 && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    adduser --disabled-password --no-create-home duser

COPY . .

COPY entrypoint.sh ./scripts/entrypoint.sh

RUN chmod +x /djangoweb/scripts/entrypoint.sh && \
    mkdir -p /djangoweb/logs && \
    touch /djangoweb/logs/django.log && \
    touch /djangoweb/logs/celery.log && \
    touch /djangoweb/logs/api_calls.log && \
    touch /djangoweb/logs/performance.log && \
    chown -R duser:duser /djangoweb

USER duser

EXPOSE 8000
