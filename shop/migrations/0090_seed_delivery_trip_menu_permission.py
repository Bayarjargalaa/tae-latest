from django.db import migrations

# Түгээлтийн машины бүртгэлийг харуул хөтөлнө
SEED = {
    'delivery_trips': ['Харуул'],
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
        ('shop', '0089_delivery_trip'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
