import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale
from django.db.models import Sum, Count, FloatField, DateField
from django.db.models.functions import Cast

# Хэрэглэгчийн сонгосон огноо (server log-оос)
print("=" * 60)
print("БОДИТ ШҮҮЛТ: 2026-02-01 - 2026-02-12")
print("=" * 60)

date_from = datetime.strptime('2026-02-01', '%Y-%m-%d').date()
date_to = datetime.strptime('2026-02-12', '%Y-%m-%d').date()

sales_qs = OpenDataSale.objects.all()
sales_qs = sales_qs.annotate(date_field=Cast('documentdate', DateField()))
sales_qs = sales_qs.filter(date_field__gte=date_from, date_field__lte=date_to)

print(f'Огноогоор шүүлсэн: {sales_qs.count():,} бичлэг')

if sales_qs.count() == 0:
    print('\n❌ ХООСОН! Энэ огнооны хүрээнд өгөгдөл байхгүй!')
else:
    # Барааны жагсаалт
    product_stats = sales_qs.values('itemname', 'brandname').annotate(
        revenue=Sum(Cast('payamount', FloatField())),
        qty=Sum(Cast('qty', FloatField())),
        orders=Count('documentpkid', distinct=True),
        customers=Count('customername', distinct=True)
    ).order_by('-revenue')
    
    total_products = product_stats.count()
    print(f'Нийт бараа: {total_products:,}')
    
    if total_products > 0:
        print(f'\nЭхний 15 бараа:')
        for i, item in enumerate(product_stats[:15], 1):
            print(f'{i}. {item["itemname"][:50]:50} - {item["revenue"]:,.0f}₮')
        
        print(f'\n✅ {total_products} бараа олдлоо!')
    else:
        print('\n❌ Бараа олдсонгүй!')

# Сүүлийн 5 огнооны өгөгдөл байгаа эсэхийг шалгах
print("\n" + "=" * 60)
print("ДАТАНЫ ХАМГИЙН СҮҮЛИЙН ОГНООNУУД:")
print("=" * 60)

latest_dates = OpenDataSale.objects.all().annotate(
    date_field=Cast('documentdate', DateField())
).values('date_field').annotate(
    count=Count('documentpkid')
).order_by('-date_field')[:10]

for date_record in latest_dates:
    print(f'{date_record["date_field"]} - {date_record["count"]:,} бичлэг')
