from decimal import Decimal

from django.db import migrations

DEFAULT_RATE = Decimal('12000')
POSITION_RATES = {'Харуул': Decimal('15000')}


def seed(apps, schema_editor):
    """Хоолны мөнгө: анхдагч 12,000₮ (өдөрт), харуул 15,000₮."""
    PayrollSetting = apps.get_model('shop', 'PayrollSetting')
    AttendancePositionRule = apps.get_model('shop', 'AttendancePositionRule')
    setting, _ = PayrollSetting.objects.get_or_create(pk=1)
    setting.meal_allowance_per_day = DEFAULT_RATE
    setting.save(update_fields=['meal_allowance_per_day'])
    for position_name, rate in POSITION_RATES.items():
        AttendancePositionRule.objects.update_or_create(
            position_name=position_name, defaults={'meal_allowance_per_day': rate},
        )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'PayrollSetting').objects.update(meal_allowance_per_day=0)
    apps.get_model('shop', 'AttendancePositionRule').objects.filter(
        position_name__in=POSITION_RATES).update(meal_allowance_per_day=None)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0076_meal_eats_and_position_rate'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
