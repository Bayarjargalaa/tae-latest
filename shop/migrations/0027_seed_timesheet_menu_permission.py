from django.db import migrations


def seed_timesheet_permission(apps, schema_editor):
    """Хүний нөөц - "Хоног бүртгэл" цэсийг "Цаг бүртгэл" (attendance_calc) цэс харагддаг бүх
    албан тушаалд нээнэ - шинэ цэс opt-in горимоор анхдагчаар нуугддаг тул."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='attendance_calc', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(
            position_name=position_name,
            menu_key='timesheet',
            defaults={'is_visible': True},
        )


def unseed_timesheet_permission(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(menu_key='timesheet').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0026_timesheet'),
    ]

    operations = [
        migrations.RunPython(seed_timesheet_permission, unseed_timesheet_permission),
    ]
