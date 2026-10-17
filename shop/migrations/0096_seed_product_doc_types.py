from django.db import migrations

# (нэр, хугацаа хянах эсэх, эрэмбэ) - бусад төрлийг "Шинжилгээний бичиг" хяналтын хуудаснаас нэмнэ
DOC_TYPES = [
    ('Шинжилгээний бичиг', True, 10),
    ('Эрүүл ахуйн гэрчилгээ', True, 20),
    ('Гарал үүслийн гэрчилгээ', True, 30),
    ('Бусад', False, 90),
]
# Шинэ хяналтын хуудасны цэсний эрх (superuser, Ерөнхий нягтлан үргэлж эрхтэй)
MENU_SEED = {'product_certificates': ['Гадаад харилцаа']}


def seed(apps, schema_editor):
    ProductDocType = apps.get_model('shop', 'ProductDocType')
    ProductAttachment = apps.get_model('shop', 'ProductAttachment')
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for name, tracks, order in DOC_TYPES:
        ProductDocType.objects.get_or_create(name=name, defaults={'tracks_expiry': tracks, 'sort_order': order})
    # Өмнө хавсаргасан бүх файл шинжилгээний бичиг гэж хавсаргагдсан
    ProductAttachment.objects.filter(doc_type__isnull=True).update(
        doc_type=ProductDocType.objects.get(name=DOC_TYPES[0][0]))
    for menu_key, positions in MENU_SEED.items():
        for position_name in positions:
            MenuPermission.objects.update_or_create(
                position_name=position_name, menu_key=menu_key, defaults={'is_visible': True},
            )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=list(MENU_SEED)).delete()
    apps.get_model('shop', 'ProductAttachment').objects.update(doc_type=None)
    apps.get_model('shop', 'ProductDocType').objects.filter(name__in=[n for n, _, _ in DOC_TYPES]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0095_product_doc_type'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
