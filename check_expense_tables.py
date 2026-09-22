"""
Зардлын тайлангийн хүснэгтүүдийг шалгах
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

# OpenDataGeneralLedger шалгах
print("=" * 80)
print("OpenDataGeneralLedger хүснэгт шалгаж байна...")
print("=" * 80)

with connection.cursor() as cursor:
    # Хүснэгт байгаа эсэхийг шалгах
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name = 'OpenDataGeneralLedger'
    """)
    exists = cursor.fetchone()[0]
    
    if exists:
        print(f"✓ OpenDataGeneralLedger олдсон")
        
        # Багануудыг шалгах
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'OpenDataGeneralLedger'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print(f"\nНийт {len(columns)} баганатай:")
        for col_name, col_type in columns[:20]:  # Эхний 20 баганыг харуулах
            print(f"  - {col_name}: {col_type}")
        
        # 520101 дансны жишээ өгөгдөл шалгах
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'OpenDataGeneralLedger'
            AND column_name ILIKE '%account%'
        """)
        account_cols = cursor.fetchall()
        if account_cols:
            print(f"\nAccount-тай холбоотой багануud: {[col[0] for col in account_cols]}")
    else:
        print("✗ OpenDataGeneralLedger олдсонгүй")

# OpenDataSaleRefund шалгах
print("\n" + "=" * 80)
print("OpenDataSaleRefund хүснэгт шалгаж байна...")
print("=" * 80)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT COUNT(*) 
        FROM information_schema.tables 
        WHERE table_name = 'OpenDataSaleRefund'
    """)
    exists = cursor.fetchone()[0]
    
    if exists:
        print(f"✓ OpenDataSaleRefund олдсон")
        
        cursor.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'OpenDataSaleRefund'
            ORDER BY ordinal_position
        """)
        columns = cursor.fetchall()
        print(f"\nНийт {len(columns)} баганатай:")
        for col_name, col_type in columns:
            print(f"  - {col_name}: {col_type}")
    else:
        print("✗ OpenDataSaleRefund олдсонгүй")

print("\n" + "=" * 80)
