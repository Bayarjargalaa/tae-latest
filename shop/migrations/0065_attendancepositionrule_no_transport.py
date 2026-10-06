from django.db import migrations, models

# Унааны мөнгө бодохгүй албан тушаалууд
NO_TRANSPORT_POSITIONS = ['Имарт худалдагч']


def seed_no_transport(apps, schema_editor):
    AttendancePositionRule = apps.get_model('shop', 'AttendancePositionRule')
    for position_name in NO_TRANSPORT_POSITIONS:
        AttendancePositionRule.objects.update_or_create(
            position_name=position_name,
            defaults={'no_transport': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0064_unloading_fees'),
    ]

    operations = [
        migrations.AddField(
            model_name='attendancepositionrule',
            name='no_transport',
            field=models.BooleanField(default=False, verbose_name='Унааны мөнгө бодохгүй'),
        ),
        # Буцаахад талбар өөрөө устах тул өгөгдлийн алхамд буцаах үйлдэл хэрэггүй
        migrations.RunPython(seed_no_transport, migrations.RunPython.noop),
    ]
