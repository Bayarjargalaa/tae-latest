"""
Хурууны хээ таних төхөөрөмжөөс ирцийн бүртгэлийг татаж, өгөгдлийн санд хадгалах management command.

Ашиглах:
    python manage.py sync_attendance

Windows Task Scheduler-аар тогтмол (жиш: 15 минут тутам) ажиллуулж болно.
"""
import sys

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Хурууны хээ таних төхөөрөмжөөс ирцийн бүртгэлийг татаж AttendanceRawLog-д хадгална'

    def add_arguments(self, parser):
        parser.add_argument('--ip', type=str, default=None, help='Төхөөрөмжийн IP хаяг (default: settings.ATTENDANCE_DEVICE_IP)')
        parser.add_argument('--port', type=int, default=None, help='Төхөөрөмжийн порт (default: settings.ATTENDANCE_DEVICE_PORT)')

    def handle(self, *args, **options):
        # Windows-ийн console (cp1252 гэх мэт) кирилл үсгийг дэмждэггүй тул Task Scheduler-аар
        # ажиллуулахад UnicodeEncodeError өгдгийг сэргийлнэ
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass

        from shop.services.attendance import sync_from_device

        try:
            fetched, created = sync_from_device(ip=options['ip'], port=options['port'])
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Төхөөрөмжтэй холбогдоход алдаа гарлаа: {e}'))
            return

        self.stdout.write(self.style.SUCCESS(
            f'Төхөөрөмжөөс {fetched} бүртгэл татагдлаа, шинээр {created} мөр хадгалагдлаа.'
        ))
