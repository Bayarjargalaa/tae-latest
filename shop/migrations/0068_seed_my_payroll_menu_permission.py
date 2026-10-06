from django.db import migrations

# shop.services.sales_bonus.DEFAULT_SETTINGS['position_schemes']-ийн албан тушаалууд
SALES_BONUS_POSITIONS = {'Нярав', 'Худалдааны төлөөлөгч', 'Борлуулагч', 'Түгээгч'}


def seed(apps, schema_editor):
    """Хувийн мэдээлэл - "Цалингийн мэдээлэл" цэсийг "Миний мэдээлэл" (profile) харагддаг бүх албан тушаалд,
    "Борлуулалтын нэмэгдэл" цэсийг тэдгээрээс борлуулалтын нэмэгдлийн хүснэгттэй, эсвэл нэмэгдэл бодогдсон
    ажилтантай (жиш: няравыг орлосон) албан тушаалуудад нээнэ."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    PayrollSetting = apps.get_model('shop', 'PayrollSetting')
    SalesBonusEntry = apps.get_model('shop', 'SalesBonusEntry')
    OpenDataEmployee = apps.get_model('datamigration', 'OpenDataEmployee')

    bonus_positions = set(SALES_BONUS_POSITIONS)
    for setting in PayrollSetting.objects.all():
        bonus_positions |= set(((setting.sales_bonus_settings or {}).get('position_schemes') or {}).keys())
    bonus_codes = set(SalesBonusEntry.objects.values_list('employee_code', flat=True))
    bonus_positions |= set(OpenDataEmployee.objects.filter(id__in=bonus_codes).values_list('positionname', flat=True))

    positions = MenuPermission.objects.filter(menu_key='profile', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(position_name=position_name, menu_key='my_payroll', defaults={'is_visible': True})
        if position_name in bonus_positions:
            MenuPermission.objects.get_or_create(
                position_name=position_name, menu_key='my_sales_bonus', defaults={'is_visible': True},
            )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=['my_payroll', 'my_sales_bonus']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0067_payrollentry_overrides'),
        ('datamigration', '0002_opendatageneralledger_opendatalandedcost_and_more'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
