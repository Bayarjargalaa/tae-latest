from django.db import migrations


def seed(apps, schema_editor):
    """Хүний нөөц - "Борлуулалтын нэмэгдэл бодох" цэсийг "Картын цалин бодолт" харагддаг албан тушаалуудад нээнэ."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='payroll_card', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(position_name=position_name, menu_key='sales_bonus', defaults={'is_visible': True})


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key='sales_bonus').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0056_sales_bonus'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
