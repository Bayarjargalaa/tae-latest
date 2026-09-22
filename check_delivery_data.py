"""
Түгээлтийн тайлангийн өгөгдлийг шалгах
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSaleHeader
from django.db.models import Count

# OpenDataSaleHeader-с өгөгдөл байгаа эсэхийг шалгах
total_count = OpenDataSaleHeader.objects.count()
print(f"Нийт OpenDataSaleHeader бичлэг: {total_count:,}")

# Distributors
distributors = OpenDataSaleHeader.objects.values_list('distributorid', 'distributorname').distinct()
print(f"\nНийт түгээгчид: {len(distributors)}")
for dist_id, dist_name in list(distributors)[:10]:
    print(f"  - {dist_name} ({dist_id})")

# Сүүлийн 10 бичлэг
recent = OpenDataSaleHeader.objects.order_by('-documentdate')[:10]
print(f"\nСүүлийн 10 бичлэг:")
for rec in recent:
    print(f"  {rec.documentdate} | {rec.distributorname} | {rec.payamount}₮")

# DocumentDate талбарын төрөл шалгах
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT data_type 
        FROM information_schema.columns 
        WHERE table_name = 'OpenDataSaleHeader' 
        AND column_name = 'DocumentDate'
    """)
    result = cursor.fetchone()
    print(f"\nDocumentDate талбарын төрөл: {result[0] if result else 'Unknown'}")
