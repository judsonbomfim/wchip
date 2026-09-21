# syntax=docker/dockerfile:1

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /djangoweb

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /djangoweb

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 duser \
    && useradd --uid 10001 --gid 10001 --system --no-create-home duser

COPY --from=builder /opt/venv /opt/venv
COPY --chown=duser:duser . .
COPY --chown=duser:duser entrypoint.sh /djangoweb/scripts/entrypoint.sh

RUN chmod +x /djangoweb/scripts/entrypoint.sh \
    && mkdir -p /djangoweb/logs \
    && touch /djangoweb/logs/django.log \
        /djangoweb/logs/celery.log \
        /djangoweb/logs/api_calls.log \
        /djangoweb/logs/performance.log \
        /djangoweb/logs/app.log \
        /djangoweb/logs/error.log \
        /djangoweb/logs/sims.log \
        /djangoweb/logs/orders.log \
    && chown -R duser:duser /djangoweb

USER duser

EXPOSE 8000

ENTRYPOINT ["/djangoweb/scripts/entrypoint.sh"]
CMD ["web"]

# Celery/beat do not listen on 8000 — treat that as healthy (worker, not web).
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
    CMD python -c "import socket,sys,urllib.request;s=socket.socket();s.settimeout(2);ok=s.connect_ex(('127.0.0.1',8000));s.close();sys.exit(0 if ok else (0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/',timeout=4).status==200 else 1))"
