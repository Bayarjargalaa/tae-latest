from django.db import migrations

# Түгээлтийн машины жагсаалтыг нягтлан харна (Ерөнхий нягтлан бүх цэсийг үргэлж харна)
POSITIONS = ['Нягтлан', 'Тооцооны Нягтлан']


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for position_name in POSITIONS:
        MenuPermission.objects.update_or_create(
            position_name=position_name, menu_key='delivery_trips', defaults={'is_visible': True},
        )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key='delivery_trips', position_name__in=POSITIONS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0090_seed_delivery_trip_menu_permission'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
