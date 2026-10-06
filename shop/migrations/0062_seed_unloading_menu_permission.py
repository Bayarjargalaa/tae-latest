from django.db import migrations


def seed(apps, schema_editor):
    """Хангамж - "Ачаа буулгалт" цэсийг "Татан авалтын тайлан" харагддаг албан тушаалуудад нээнэ."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='purchase_report', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(position_name=position_name, menu_key='unloading', defaults={'is_visible': True})


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key='unloading').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0061_unloading'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
