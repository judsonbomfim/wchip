# Agenda Celery Beat (anti-duplicata)

A agenda canônica vive em `CELERY_BEAT_SCHEDULE` em `core/settings.py`.
No startup do serviço `celery_beat`, o comando `sync_celery_beat` faz upsert
dessas entradas no banco e **remove PeriodicTask órfãs** (nomes fora do settings).

## Operação

1. **Alterar a agenda** = editar `CELERY_BEAT_SCHEDULE` e redeployar (ou reiniciar
   o container `celery_beat`). Não criar PeriodicTask novas no Admin.
2. **Admin**: use só para enable/disable de tasks já existentes.
3. **Um único beat**: o compose fixa `deploy.replicas: 1` e
   `container_name: celery_beat`. Nunca escale o serviço beat.
4. **Locks Redis**: tasks periódicas usam `core.celery_locks.periodic_task_lock`
   (`celery:lock:<nome>`). Se a run anterior ainda estiver em andamento, a nova
   é ignorada com log `Task ... skipped: lock held`. Chamadas com `id` não usam lock.

Sincronizar manualmente:

```bash
python manage.py sync_celery_beat
```

## Tasks no settings

| Chave | Task | Frequência |
|-------|------|------------|
| `task__2_min_orders_auto` | `orders_auto` | ~2 min (grupo A) |
| `task__2_min_activate_TC` | `simActivateTC` | ~2 min (grupo A) |
| `task__2_min_activate_EO` | `simActivateEO` | ~2 min (grupo B) |
| `task__2_min_activate_CM` | `simActivateCM` | ~2 min (grupo A) |
| `task__2_min_activate_AR` | `simActivateAR` | ~2 min (grupo B) |
| `task__deactivate_TC` | `simDeactivateTC` | diário 00:00 |
| `task__deactivate_all` | `simDeactivateAll` | diário 00:00 |

## Verificação pós-deploy

```bash
docker ps | grep celery_beat

python manage.py shell -c "
from django_celery_beat.models import PeriodicTask
for t in PeriodicTask.objects.all().order_by('name'):
    print(t.name, t.task, t.enabled)
"
```
