"""MSSQL-ээс нэг (эсвэл хэд хэдэн) хүснэгтийг хурдан татна: python manage.py sync_table OpenDataEmployee"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from datamigration.sync import sync_view


class Command(BaseCommand):
    help = 'MSSQL view-г нэрээр нь PostgreSQL рүү хурдан татна (жиш: OpenDataEmployee)'

    def add_arguments(self, parser):
        parser.add_argument('tables', nargs='+', help='Хүснэгт/view-ийн нэр (OpenDataEmployee г.м.)')
        parser.add_argument('--database', help='MSSQL өгөгдлийн сан (заагаагүй бол автоматаар хайна)')

    def handle(self, *args, **options):
        import sys
        from shop.models import OpenDataSyncLog

        # Windows консол (cp1252) кирилл мессежээр унахгүй
        for stream in (sys.stdout, sys.stderr):
            try:
                stream.reconfigure(errors='replace')
            except (AttributeError, ValueError):
                pass

        failed = False
        for table in options['tables']:
            log = OpenDataSyncLog.objects.create(table_name=table, message='command')
            try:
                result = sync_view(table, options.get('database'), log=lambda t: self.stdout.write(f'  {table}: {t}'))
                log.status, log.rows, log.seconds, log.database = 'success', result['rows'], result['seconds'], result['database']
                log.message = f"fetch {result['steps']['fetch']}s, write {result['steps']['write']}s, post {result['steps']['post']}s"
                self.stdout.write(self.style.SUCCESS(f"{table}: {result['rows']} rows, {result['seconds']}s ({result['database']})"))
            except Exception as e:
                failed = True
                log.status, log.message = 'error', str(e)
                self.stdout.write(self.style.ERROR(f'{table}: {e}'))
            log.finished_at = timezone.now()
            log.save()
        if failed:
            raise CommandError('Some tables failed')
