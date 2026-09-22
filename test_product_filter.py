import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale, OpenDataItem
from django.db.models import Sum, Count, FloatField, DateField
from django.db.models.functions import Cast

# Огноо сонгосон шүүлт
date_from = datetime.strptime('2024-01-01', '%Y-%m-%d').date()
date_to = datetime.strptime('2024-12-31', '%Y-%m-%d').date()

# sales_qs - огноогоор шүүсэн
sales_qs = OpenDataSale.objects.all()
sales_qs = sales_qs.annotate(
    date_field=Cast('documentdate', DateField())
)
sales_qs = sales_qs.filter(date_field__gte=date_from, date_field__lte=date_to)

print(f'Огноогоор шүүлсэн: {sales_qs.count()} бичлэг')

# product_qs = sales_qs (бараагаар шүүлээгүй)
product_qs = sales_qs

# _get_product_analysis() функц дуурайх
product_name = None  # Бараа сонгоогүй

if product_name:
    product_qs = product_qs.filter(itemname__icontains=product_name)

product_stats = product_qs.values('itemname', 'brandname').annotate(
    revenue=Sum(Cast('payamount', FloatField())),
    qty=Sum(Cast('qty', FloatField())),
    orders=Count('documentpkid', distinct=True),
    customers=Count('customername', distinct=True)
).order_by('-revenue')[:50]

print(f'\nБарааны тоо (top 50): {product_stats.count()}')
print('\nЭхний 5 бараа:')
for i, item in enumerate(product_stats[:5], 1):
    print(f'{i}. {item["itemname"][:60]} - {item["revenue"]:.0f}₮')

if product_stats.count() == 0:
    print('\n❌ АСУУДАЛ: product_stats хоосон байна!')
else:
    print(f'\n✅ {product_stats.count()} бараа олдлоо')
