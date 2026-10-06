"""OpenData* хүснэгтүүдийн тайлангийн индексийг үүсгэнэ (синк хүснэгтийг дахин үүсгэсний дараа)."""
from django.core.management.base import BaseCommand

from datamigration.opendata_indexes import OPENDATA_INDEXES, ensure_indexes


class Command(BaseCommand):
    help = 'OpenData хүснэгтүүдийн тайлангийн индексийг үүсгэж, статистикийг шинэчилнэ'

    def add_arguments(self, parser):
        parser.add_argument('--table', action='append', help='Зөвхөн энэ хүснэгт (давтаж болно)')

    def handle(self, *args, **options):
        tables = options.get('table') or list(OPENDATA_INDEXES)
        created = ensure_indexes(tables)
        self.stdout.write(self.style.SUCCESS(f'{created} index(es) created ({len(tables)} tables)'))
