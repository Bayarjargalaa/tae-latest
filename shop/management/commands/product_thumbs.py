"""Барааны зургийн картын thumbnail-ийг урьдчилан үүсгэнэ (services.product_images) - эхний хандалт удаан болохоос сэргийлнэ."""
from django.core.management.base import BaseCommand

from shop.models import ProductExtension
from shop.services.product_images import fallback_files, make_thumb


class Command(BaseCommand):
    help = 'Барааны зургийн thumbnail үүсгэх (байгааг алгасна)'

    def handle(self, *args, **options):
        names = set(fallback_files().values())
        for ext in ProductExtension.objects.all():
            names.update(f.name for f in (ext.image_main, ext.image_2, ext.image_3) if f)
        failed = [name for name in sorted(names) if not make_thumb(name)]
        self.stdout.write(f'{len(names) - len(failed)} thumbnail бэлэн, {len(failed)} алдаатай')
        for name in failed:
            self.stdout.write(f'  алдаа: {name}')
