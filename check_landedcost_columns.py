"""OpenDataLandedCost хүснэгтийн багануудыг шалгах"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Хүснэгтийн бүх багануудыг харах
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns 
        WHERE table_schema = 'public' 
        AND table_name = 'OpenDataLandedCost'
        ORDER BY ordinal_position;
    """)
    columns = cursor.fetchall()
    
    print("=== OpenDataLandedCost хүснэгтийн бүтэц ===")
    if columns:
        print(f"Нийт {len(columns)} багана байна:\n")
        for col_name, data_type, nullable in columns:
            print(f"  {col_name:25} {data_type:20} (nullable: {nullable})")
    else:
        print("❌ Багана олдсонгүй!")
        
    # Онцгой анхаарах талбарууд
    print("\n=== Эрэх талбарууд ===")
    important_fields = ['TotalCost', 'totalcost', 'CustomsFee', 'customsfee', 'TransportCost', 'transportcost']
    column_names_lower = [col[0].lower() for col in columns]
    
    for field in important_fields:
        if field.lower() in column_names_lower:
            actual_name = [col[0] for col in columns if col[0].lower() == field.lower()][0]
            print(f"  ✅ {field} → {actual_name}")
        else:
            print(f"  ❌ {field} → БАЙХГҮЙ!")
