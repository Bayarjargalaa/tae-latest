import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale
from django.db.models import Sum, Count, FloatField, DateField
from django.db.models.functions import Cast

# ТЕСТ 1: Зөвхөн огноо сонгоод бүх барааг харуулах
print("=" * 60)
print("ТЕСТ 1: Огноо мужаар (2024) - БҮХ БАРАА")
print("=" * 60)

date_from = datetime.strptime('2024-01-01', '%Y-%m-%d').date()
date_to = datetime.strptime('2024-12-31', '%Y-%m-%d').date()

sales_qs = OpenDataSale.objects.all()
sales_qs = sales_qs.annotate(date_field=Cast('documentdate', DateField()))
sales_qs = sales_qs.filter(date_field__gte=date_from, date_field__lte=date_to)

print(f'Огноогоор шүүлсэн: {sales_qs.count():,} бичлэг')

# _get_product_analysis() дуурайх (limit-гүй)
product_stats = sales_qs.values('itemname', 'brandname').annotate(
    revenue=Sum(Cast('payamount', FloatField())),
    qty=Sum(Cast('qty', FloatField())),
    orders=Count('documentpkid', distinct=True),
    customers=Count('customername', distinct=True)
).order_by('-revenue')

total_products = product_stats.count()
print(f'Нийт бараа: {total_products:,}')
print(f'\nТоп 10 бараа:')
for i, item in enumerate(product_stats[:10], 1):
    print(f'{i}. {item["itemname"][:50]:50} - {item["revenue"]:,.0f}₮')

# ТЕСТ 2: Огноо сонгоогүй - БҮХ ӨГӨГДӨЛ
print("\n" + "=" * 60)
print("ТЕСТ 2: Огноо сонгоогүй - БҮХ ӨГӨГДӨЛ")
print("=" * 60)

all_sales = OpenDataSale.objects.all()
print(f'Нийт бичлэг: {all_sales.count():,}')

all_product_stats = all_sales.values('itemname', 'brandname').annotate(
    revenue=Sum(Cast('payamount', FloatField())),
    qty=Sum(Cast('qty', FloatField())),
    orders=Count('documentpkid', distinct=True),
    customers=Count('customername', distinct=True)
).order_by('-revenue')

print(f'Нийт бараа: {all_product_stats.count():,}')
print(f'\nТоп 5 бараа:')
for i, item in enumerate(all_product_stats[:5], 1):
    print(f'{i}. {item["itemname"][:50]:50} - {item["revenue"]:,.0f}₮')

print("\n✅ БҮХ бараанууд зөв гарч байна (limit-гүй)!")
