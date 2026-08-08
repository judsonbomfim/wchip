"""Locks Redis para tasks periódicas do Celery (anti-overlap / anti-duplicata)."""

from __future__ import annotations

import inspect
import logging
import uuid
from functools import wraps
from typing import Callable, Optional, TypeVar

import redis
from django.conf import settings

logger = logging.getLogger(__name__)

F = TypeVar('F', bound=Callable)

_redis_client: Optional[redis.Redis] = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        url = settings.CELERY_BROKER_URL
        if not url:
            raise RuntimeError('CELERY_BROKER_URL não configurado para locks de task')
        _redis_client = redis.from_url(url, decode_responses=True)
    return _redis_client


def periodic_task_lock(
    *,
    name: Optional[str] = None,
    timeout: int = 140,
    skip_if_id: bool = True,
) -> Callable[[F], F]:
    """
    Decorator: se outro worker já segura o lock, a execução é ignorada.

    Se a task aceita ``id`` e foi chamada com ``id`` não-nulo (ativação
    pontual), o lock é ignorado para não bloquear disparos manuais.
    ``timeout`` deve ser um pouco maior que o ``time_limit`` da task
    (padrão 140s quando a task não define time_limit).
    """

    def decorator(func: F) -> F:
        lock_name = name or func.__name__
        lock_key = f'celery:lock:{lock_name}'
        sig = inspect.signature(func)
        has_id = 'id' in sig.parameters

        @wraps(func)
        def wrapper(*args, **kwargs):
            if skip_if_id and has_id:
                bound = sig.bind_partial(*args, **kwargs)
                bound.apply_defaults()
                if bound.arguments.get('id') is not None:
                    return func(*args, **kwargs)

            client = _get_redis()
            token = uuid.uuid4().hex
            acquired = client.set(lock_key, token, nx=True, ex=timeout)
            if not acquired:
                logger.warning(
                    'Task %s skipped: lock held (%s, ttl=%ss)',
                    lock_name,
                    lock_key,
                    timeout,
                )
                return None

            try:
                return func(*args, **kwargs)
            finally:
                if client.get(lock_key) == token:
                    client.delete(lock_key)

        return wrapper  # type: ignore[return-value]

    return decorator
