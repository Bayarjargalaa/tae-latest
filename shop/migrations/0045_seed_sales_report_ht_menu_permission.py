from django.db import migrations


def seed_sales_report_ht_permission(apps, schema_editor):
    """Борлуулалт - "Борлуулалтын тайлан ХТ-р" цэсийг "Борлуулалтын тайлан" (sales_report) цэс харагддаг бүх
    албан тушаалд нээнэ - шинэ цэс opt-in горимоор анхдагчаар нуугддаг тул."""
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='sales_report', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        MenuPermission.objects.get_or_create(
            position_name=position_name,
            menu_key='sales_report_ht',
            defaults={'is_visible': True},
        )


def unseed_sales_report_ht_permission(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    MenuPermission.objects.filter(menu_key='sales_report_ht').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0044_remove_manual_savings'),
    ]

    operations = [
        migrations.RunPython(seed_sales_report_ht_permission, unseed_sales_report_ht_permission),
    ]
