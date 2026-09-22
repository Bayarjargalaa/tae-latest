import os

from django.conf import settings
from django.db import migrations


def seed_from_xlsx(apps, schema_editor):
    """data/users.xlsx (эсвэл хуучин staticfiles/users.xlsx) файлд хадгалагдаж байсан
    'ажилтны код <-> төхөөрөмжийн код' харгалзааг EmployeeFingerprint хүснэгтэд нэг удаа хуулна."""
    try:
        import pandas as pd
    except ImportError:
        return

    path = os.path.join(settings.BASE_DIR, 'data', 'users.xlsx')
    if not os.path.exists(path):
        path = os.path.join(settings.BASE_DIR, 'staticfiles', 'users.xlsx')
    if not os.path.exists(path):
        return

    df = pd.read_excel(path, dtype={'User ID': str, 'Empoyee ID': str})
    df = df.rename(columns={'Empoyee ID': 'Employee ID'})

    EmployeeFingerprint = apps.get_model('shop', 'EmployeeFingerprint')

    for _, row in df.iterrows():
        employee_code = str(row.get('Employee ID') or '').strip()
        if not employee_code or employee_code.lower() == 'nan':
            continue
        device_user_id = str(row.get('User ID') or '').strip()
        if device_user_id.lower() == 'nan':
            device_user_id = ''
        EmployeeFingerprint.objects.update_or_create(
            employee_code=employee_code,
            defaults={'device_user_id': device_user_id},
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0022_employeefingerprint'),
    ]

    operations = [
        migrations.RunPython(seed_from_xlsx, noop_reverse),
    ]
