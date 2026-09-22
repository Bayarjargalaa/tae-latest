"""Check actual column names in database"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

def get_table_columns(table_name):
    """Get all column names and types for a table"""
    with connection.cursor() as cursor:
        cursor.execute(f"""
            SELECT column_name, data_type, udt_name
            FROM information_schema.columns
            WHERE table_name = '{table_name}'
            ORDER BY ordinal_position;
        """)
        return cursor.fetchall()

print("=" * 80)
print("OpenDataGeneralLedger columns:")
print("=" * 80)
for col in get_table_columns('OpenDataGeneralLedger'):
    print(f"{col[0]:30} {col[1]:15} ({col[2]})")

print("\n" + "=" * 80)
print("OpenDataSaleRefund columns:")
print("=" * 80)
for col in get_table_columns('OpenDataSaleRefund'):
    print(f"{col[0]:30} {col[1]:15} ({col[2]})")
