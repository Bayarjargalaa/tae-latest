import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

print("=" * 100)
print("PostgreSQL DATABASE-ЫН БҮХБАГАНА/VIEW-ҮҮД")
print("=" * 100)

with connection.cursor() as cursor:
    # Tables болон Views-үүдийг авах
    cursor.execute("""
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND (table_type = 'BASE TABLE' OR table_type = 'VIEW')
        ORDER BY table_type, table_name;
    """)
    
    results = cursor.fetchall()
    
    print(f"\nНийт: {len(results)}")
    print("-" * 100)
    
    current_type = None
    for table_name, table_type in results:
        if current_type != table_type:
            current_type = table_type
            print(f"\n📊 {table_type}:")
            print("-" * 100)
        print(f"  • {table_name}")

print("\n" + "=" * 100)
print("OPENDATASALEHEADER БАЙГАА ЭСЭХИЙГ ШАЛГАХ")
print("=" * 100)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND LOWER(table_name) LIKE '%saleheader%';
    """)
    
    results = cursor.fetchall()
    
    if results:
        print("\n✅ SaleHeader-тэй холбоотой:")
        for table_name, table_type in results:
            print(f"  • {table_name} ({table_type})")
            
            # Баганын мэдээлэл авах
            cursor.execute(f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_name = '{table_name}'
                ORDER BY ordinal_position;
            """)
            columns = cursor.fetchall()
            
            print(f"\n    Багануд ({len(columns)}):")
            for col_name, data_type, nullable in columns:
                null_str = "NULL" if nullable == "YES" else "NOT NULL"
                print(f"      - {col_name:30} {data_type:20} {null_str}")
    else:
        print("\n❌ SaleHeader нэртэй table/view олдсонгүй")

print("\n" + "=" * 100)
print("DELIVERY/DISTRIBUTION-ТЭЙ ХОЛБООТОЙ TABLE/VIEW")
print("=" * 100)

with connection.cursor() as cursor:
    cursor.execute("""
        SELECT table_name, table_type
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND (LOWER(table_name) LIKE '%delivery%' 
             OR LOWER(table_name) LIKE '%distribution%'
             OR LOWER(table_name) LIKE '%dispatch%'
             OR LOWER(table_name) LIKE '%route%'
             OR LOWER(table_name) LIKE '%driver%');
    """)
    
    results = cursor.fetchall()
    
    if results:
        print("\n✅ Түгээлт-тэй холбоотой:")
        for table_name, table_type in results:
            print(f"  • {table_name} ({table_type})")
    else:
        print("\n❌ Түгээлттэй холбоотой table/view олдсонгүй")
