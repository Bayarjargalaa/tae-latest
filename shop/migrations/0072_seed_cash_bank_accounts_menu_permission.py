from django.db import migrations

DIRECTOR_POSITIONS = ['Захирал', 'Ерөнхий захирал']


def seed(apps, schema_editor):
    """Хүний нөөц - "Бэлэн цалингийн данс" цэсийг захирлууд болон "Бэлэн цалин бодолт" харагддаг албан тушаалуудад нээнэ."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = set(DIRECTOR_POSITIONS) | set(
        MenuPermission.objects.filter(menu_key='payroll_cash', is_visible=True).values_list('position_name', flat=True)
    )
    for position_name in positions:
        MenuPermission.objects.update_or_create(
            position_name=position_name, menu_key='cash_bank_accounts', defaults={'is_visible': True},
        )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key='cash_bank_accounts').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0071_sales_bonus_altjin_seller'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
