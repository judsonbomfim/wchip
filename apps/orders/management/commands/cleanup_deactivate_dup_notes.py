"""
Remove notas duplicadas geradas pelo bug de re-desativação diária (simDeactivateAll).

Padrões tratados:
  1) "Alterado de Desativado para Desativado" — sempre ruído; remove todas.
  2) "{iccid} desativado com sucesso. Processo automático" — mantém a mais
     antiga por pedido (item) e remove as demais.

Uso:
  python manage.py cleanup_deactivate_dup_notes          # dry-run (só lista)
  python manage.py cleanup_deactivate_dup_notes --apply  # apaga de fato
"""

from django.core.management.base import BaseCommand

from apps.orders.models import Notes


STATUS_NOOP = 'Alterado de Desativado para Desativado'
SUCCESS_SUFFIX = 'desativado com sucesso. Processo automático'


class Command(BaseCommand):
    help = (
        'Remove notas duplicadas de desativação automática '
        '(Desativado→Desativado e reprocessamentos diários).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Aplica a exclusão. Sem esta flag, apenas simula (dry-run).',
        )
        parser.add_argument(
            '--order-id',
            type=int,
            default=None,
            help='Limita ao order_id da loja (ex.: 12345). Sem filtro = todos.',
        )
        parser.add_argument(
            '--item-pk',
            type=int,
            default=None,
            help='Limita ao pk interno do item (orders.id).',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        order_id = options['order_id']
        item_pk = options['item_pk']

        base = Notes.objects.filter(type_note='S')
        if order_id is not None:
            base = base.filter(id_item__order_id=order_id)
        if item_pk is not None:
            base = base.filter(id_item_id=item_pk)

        # 1) Notas de status no-op (sempre removíveis)
        noop_qs = base.filter(note=STATUS_NOOP)
        noop_ids = list(noop_qs.values_list('id', flat=True))

        # 2) Notas de sucesso do processo automático: keep oldest per item
        success_qs = base.filter(note__endswith=SUCCESS_SUFFIX).order_by(
            'id_item_id', 'created_at', 'id'
        )
        keep_by_item = {}
        success_dup_ids = []
        for note in success_qs.iterator():
            item_id = note.id_item_id
            if item_id not in keep_by_item:
                keep_by_item[item_id] = note.id
            else:
                success_dup_ids.append(note.id)

        delete_ids = sorted(set(noop_ids) | set(success_dup_ids))

        self.stdout.write(
            self.style.NOTICE(
                f'Modo: {"APPLY (apagando)" if apply else "DRY-RUN (somente listagem)"}'
            )
        )
        self.stdout.write(f'Notas "Desativado → Desativado": {len(noop_ids)}')
        self.stdout.write(
            f'Notas de sucesso automáticas duplicadas: {len(success_dup_ids)} '
            f'(mantém 1 por item; itens com nota mantida: {len(keep_by_item)})'
        )
        self.stdout.write(f'Total a remover: {len(delete_ids)}')

        if not delete_ids:
            self.stdout.write(self.style.SUCCESS('Nada a remover.'))
            return

        # Amostra para auditoria
        sample = (
            Notes.objects.filter(id__in=delete_ids[:20])
            .select_related('id_item')
            .order_by('id')
        )
        self.stdout.write('\nAmostra (até 20):')
        for n in sample:
            preview = (n.note or '').replace('\n', ' ')[:90]
            self.stdout.write(
                f'  id={n.id} order={n.id_item.order_id} item_pk={n.id_item_id} '
                f'at={n.created_at:%d/%m/%Y %H:%M} | {preview}'
            )

        if not apply:
            self.stdout.write(
                self.style.WARNING(
                    '\nDry-run concluído. Rode com --apply para apagar.'
                )
            )
            return

        deleted, _ = Notes.objects.filter(id__in=delete_ids).delete()
        self.stdout.write(
            self.style.SUCCESS(f'\nRemovidas {deleted} nota(s) com sucesso.')
        )
