from django.db import migrations

# ХТ-үүд зөвхөн өөрийн хариуцсан сувгийг харна (shop/services/sales_ht_access.py) тул цэсийг нээнэ
SALES_REP_POSITIONS = ['Худалдааны төлөөлөгч', 'Борлуулагч']


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for position_name in SALES_REP_POSITIONS:
        MenuPermission.objects.update_or_create(
            position_name=position_name,
            menu_key='sales_report_ht',
            defaults={'is_visible': True},
        )


def unseed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(position_name__in=SALES_REP_POSITIONS, menu_key='sales_report_ht').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0045_seed_sales_report_ht_menu_permission'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
