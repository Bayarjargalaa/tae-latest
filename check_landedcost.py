"""OpenDataLandedCost хүснэгт байгаа эсэхийг шалгах"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Хүснэгт/view байгаа эсэхийг шалгах
    cursor.execute("""
        SELECT table_name, table_type 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name ILIKE '%landedcost%'
        ORDER BY table_name;
    """)
    results = cursor.fetchall()
    
    print("=== OpenDataLandedCost хүснэгт/view хайлт ===")
    if results:
        for table_name, table_type in results:
            print(f"Олдсон: {table_name} (Төрөл: {table_type})")
    else:
        print("❌ OpenDataLandedCost хүснэгт эсвэл view олдсонгүй!")
        print("\n=== БҮГД OpenData хүснэгтүүд ===")
        cursor.execute("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE 'OpenData%'
            ORDER BY table_name;
        """)
        all_opendata = cursor.fetchall()
        for table_name, table_type in all_opendata:
            print(f"  - {table_name} ({table_type})")
