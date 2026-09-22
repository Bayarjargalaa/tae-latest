from datetime import time

from django.db import migrations

DEFAULT_RULES = {
    'Худалдааны төлөөлөгч': time(9, 0),
    'Үйлчлэгч': time(9, 0),
    'Тогооч': time(10, 0),
    'Нярав': time(8, 0),
    'Түгээгч': time(8, 0),
    'Туслах ажилтан': time(8, 0),
}


def seed_rules(apps, schema_editor):
    AttendancePositionRule = apps.get_model('shop', 'AttendancePositionRule')
    for position_name, start_time in DEFAULT_RULES.items():
        AttendancePositionRule.objects.update_or_create(
            position_name=position_name,
            defaults={'start_time': start_time},
        )


def remove_rules(apps, schema_editor):
    AttendancePositionRule = apps.get_model('shop', 'AttendancePositionRule')
    AttendancePositionRule.objects.filter(position_name__in=DEFAULT_RULES.keys()).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0020_attendancepositionrule'),
    ]

    operations = [
        migrations.RunPython(seed_rules, remove_rules),
    ]
