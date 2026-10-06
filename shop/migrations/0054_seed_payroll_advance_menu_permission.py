from django.db import migrations

ADVANCE_MENU_KEYS = {'payroll_card': 'payroll_advance_card', 'payroll_cash': 'payroll_advance_cash'}


def seed(apps, schema_editor):
    # Урьдчилгааны цэсийг тухайн (карт/бэлэн) цалин бодолт харагддаг албан тушаалуудад нээнэ
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for payroll_key, advance_key in ADVANCE_MENU_KEYS.items():
        positions = MenuPermission.objects.filter(menu_key=payroll_key, is_visible=True).values_list('position_name', flat=True)
        for position_name in positions:
            MenuPermission.objects.get_or_create(position_name=position_name, menu_key=advance_key, defaults={'is_visible': True})


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=ADVANCE_MENU_KEYS.values()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0053_payrollsetting_advance_day'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
