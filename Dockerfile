FROM python:3.12.1-slim-bullseye
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /djangoweb

COPY requirements.txt .

RUN apt-get update && apt-get install -y --no-install-recommends nano libglib2.0-0 libgomp1 && \
    rm -rf /var/lib/apt/lists/* && \
    pip install --upgrade pip && \
    pip install -r requirements.txt && \
    adduser --disabled-password --no-create-home --uid 10001 duser

COPY . .

COPY entrypoint.sh ./scripts/entrypoint.sh

RUN chmod +x /djangoweb/scripts/entrypoint.sh && \
    mkdir -p /djangoweb/logs && \
    touch /djangoweb/logs/django.log && \
    touch /djangoweb/logs/celery.log && \
    touch /djangoweb/logs/api_calls.log && \
    touch /djangoweb/logs/performance.log && \
    chown -R duser:duser /djangoweb

EXPOSE 8000

ENTRYPOINT ["/djangoweb/scripts/entrypoint.sh"]
CMD ["web"]
