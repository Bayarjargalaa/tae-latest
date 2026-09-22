"""
OpenDataSale view-ийн бүх талбаруудыг шалгах
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

# PostgreSQL-с OpenDataSale view-ийн бүх багануудыг авах
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT column_name, data_type, character_maximum_length
        FROM information_schema.columns
        WHERE table_name = 'OpenDataSale'
        ORDER BY ordinal_position;
    """)
    
    columns = cursor.fetchall()
    
    print("=" * 80)
    print("OpenDataSale VIEW-ийн бүх талбарууд:")
    print("=" * 80)
    print(f"{'Талбарын нэр':<40} {'Төрөл':<20} {'Урт':<10}")
    print("-" * 80)
    
    for col_name, data_type, max_length in columns:
        length_str = str(max_length) if max_length else '-'
        print(f"{col_name:<40} {data_type:<20} {length_str:<10}")
    
    print("-" * 80)
    print(f"Нийт талбарууд: {len(columns)}")
    print("=" * 80)
    
    # AmountNonVat байгаа эсэхийг онцлон харуулах
    amountnonvat_exists = any(col[0].lower() == 'amountnonvat' for col in columns)
    print(f"\n✓ AmountNonVat талбар байгаа эсэх: {'ТИЙМ ✓' if amountnonvat_exists else 'ҮГҮЙ ✗'}")
    
    # Санхүүгийн талбаруудыг жагсаах
    finance_fields = [col[0] for col in columns if any(keyword in col[0].lower() for keyword in ['amount', 'price', 'cost', 'pay', 'vat'])]
    if finance_fields:
        print(f"\nСанхүүгийн холбоотой талбарууд ({len(finance_fields)}):")
        for field in finance_fields:
            print(f"  - {field}")
