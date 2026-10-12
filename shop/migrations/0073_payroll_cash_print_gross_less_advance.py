from django.db import migrations


def forward(apps, schema_editor):
    """Бэлэн цалингийн хэвлэх загвар: "Урьдчилгаа"-ийн ард "Олговол зохих" багана, хүснэгт бүрийг тусдаа A4 хуудсанд."""
    PayrollSetting = apps.get_model('shop', 'PayrollSetting')
    for setting in PayrollSetting.objects.all():
        config = setting.print_columns or {}
        cash = config.get('cash')
        if not cash:
            continue  # хадгалаагүй бол анхдагч загвар (payroll_print.DEFAULT_PRINT_COLUMNS) хэрэглэгдэнэ
        for slot in ('p1a', 'p1b', 'p2a', 'p2b'):
            keys = cash.get(slot) or []
            if 'advance' in keys and 'gross_less_advance' not in keys:
                keys.insert(keys.index('advance') + 1, 'gross_less_advance')
        cash['separate_pages'] = True
        setting.print_columns = config
        setting.save(update_fields=['print_columns'])


def backward(apps, schema_editor):
    PayrollSetting = apps.get_model('shop', 'PayrollSetting')
    for setting in PayrollSetting.objects.all():
        cash = (setting.print_columns or {}).get('cash')
        if not cash:
            continue
        for slot in ('p1a', 'p1b', 'p2a', 'p2b'):
            if 'gross_less_advance' in (cash.get(slot) or []):
                cash[slot].remove('gross_less_advance')
        cash['separate_pages'] = False
        setting.save(update_fields=['print_columns'])


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0072_seed_cash_bank_accounts_menu_permission'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
