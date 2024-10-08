from django.core.management.base import BaseCommand
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Limpa o cache do Django'

    def handle(self, *args, **kwargs):
        cache.clear()
        self.stdout.write(self.style.SUCCESS('Cache limpo com sucesso'))