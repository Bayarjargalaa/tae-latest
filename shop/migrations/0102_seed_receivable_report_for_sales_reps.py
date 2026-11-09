from django.db import migrations

# ХТ / борлуулагч авлагын тайланд зөвхөн өөрийн хариуцсан сувгийн харилцагчдыг харна (shop.views._recpay_scope)
SALES_REP_POSITIONS = ['Худалдааны төлөөлөгч', 'Борлуулагч']


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for position_name in SALES_REP_POSITIONS:
        MenuPermission.objects.update_or_create(
            position_name=position_name,
            menu_key='receivable_report',
            defaults={'is_visible': True},
        )


def unseed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(position_name__in=SALES_REP_POSITIONS, menu_key='receivable_report').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0101_fuel_source'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
