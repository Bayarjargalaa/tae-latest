from django.db import migrations

# ХТ / борлуулагч борлуулалтын төлөвлөгөөнөөс зөвхөн өөрийн хариуцсан сувгийнхаа төлөвлөгөөг харна (засахгүй)
SALES_REP_POSITIONS = ['Худалдааны төлөөлөгч', 'Борлуулагч']


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for position_name in SALES_REP_POSITIONS:
        MenuPermission.objects.update_or_create(
            position_name=position_name,
            menu_key='sales_plan',
            defaults={'is_visible': True},
        )


def unseed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(position_name__in=SALES_REP_POSITIONS, menu_key='sales_plan').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0109_salesplan_items_excluded'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
