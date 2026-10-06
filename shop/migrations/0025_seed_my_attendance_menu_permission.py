from django.db import migrations


def seed_my_attendance_permission(apps, schema_editor):
    """Хувийн мэдээлэл - "Цагийн бүртгэл" цэсийг "Миний мэдээлэл" (profile) цэс харагддаг бүх
    албан тушаалд нээнэ - шинэ цэс opt-in горимоор анхдагчаар нуугддаг тул."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='profile', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(
            position_name=position_name,
            menu_key='my_attendance',
            defaults={'is_visible': True},
        )


def unseed_my_attendance_permission(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(menu_key='my_attendance').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0024_employeefingerprint_unique_nonblank_device_user_id'),
    ]

    operations = [
        migrations.RunPython(seed_my_attendance_permission, unseed_my_attendance_permission),
    ]
