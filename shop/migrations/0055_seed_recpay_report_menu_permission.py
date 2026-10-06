from django.db import migrations

REPORT_MENU_KEYS = ['receivable_report', 'payable_report']


def seed(apps, schema_editor):
    """Санхүү - Авлагын / Өглөгийн тайлан цэсийг "Зардлын тооцоолол сараар" (expense_report) цэс харагддаг албан
    тушаалуудад нээнэ - шинэ цэс opt-in горимоор анхдагчаар нуугддаг тул."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='expense_report', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        for key in REPORT_MENU_KEYS:
            MenuPermission.objects.get_or_create(position_name=position_name, menu_key=key, defaults={'is_visible': True})


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=REPORT_MENU_KEYS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0054_seed_payroll_advance_menu_permission'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
