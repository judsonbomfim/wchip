"""Sincroniza CELERY_BEAT_SCHEDULE com PeriodicTask e remove órfãos."""

from django.conf import settings
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, PeriodicTasks
from django_celery_beat.schedulers import ModelEntry

# Entrada padrão instalada pelo DatabaseScheduler — não remover.
_KEEP_NAMES = frozenset({'celery.backend_cleanup'})


class Command(BaseCommand):
    help = (
        'Upsert PeriodicTask a partir de CELERY_BEAT_SCHEDULE e remove '
        'tarefas órfãs (nomes fora do settings).'
    )

    def handle(self, *args, **options):
        schedule = getattr(settings, 'CELERY_BEAT_SCHEDULE', None) or {}
        expected = set(schedule.keys()) | _KEEP_NAMES

        created = updated = 0
        for name, entry in schedule.items():
            existed = PeriodicTask.objects.filter(name=name).exists()
            ModelEntry.from_entry(name, app=None, **entry)
            if existed:
                updated += 1
                self.stdout.write(f'updated: {name}')
            else:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'created: {name}'))

        orphans = PeriodicTask.objects.exclude(name__in=expected)
        deleted = 0
        for orphan in orphans.iterator():
            self.stdout.write(self.style.WARNING(f'removed orphan: {orphan.name} ({orphan.task})'))
            orphan.delete()
            deleted += 1

        PeriodicTasks.update_changed()

        self.stdout.write(
            self.style.SUCCESS(
                f'sync_celery_beat done: created={created} updated={updated} deleted={deleted}'
            )
        )
