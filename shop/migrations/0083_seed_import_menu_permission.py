from django.db import migrations

# Импортын захиалга бүртгэнэ (засах эрх) - Гадаад харилцаа; Замын мэдээ үзнэ - захирлууд, ХТ
SEED = {
    'import_orders': ['Гадаад харилцаа'],
    'import_tracking': ['Гадаад харилцаа', 'Захирал', 'Ерөнхий захирал', 'Худалдааны төлөөлөгч', 'Борлуулагч'],
}


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for menu_key, positions in SEED.items():
        for position_name in positions:
            MenuPermission.objects.update_or_create(
                position_name=position_name, menu_key=menu_key, defaults={'is_visible': True},
            )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0082_import_shipment'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
