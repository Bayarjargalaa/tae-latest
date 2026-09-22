import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale, OpenDataItem
from django.db.models import Sum, Count, FloatField, DateField
from django.db.models.functions import Cast

print("=" * 60)
print("ШАЛГАЛТ: Бараагаар tab анх ачаалахад")
print("=" * 60)

# Яг views.py дахь логикийг дуурайх
# 1. sales_qs - БҮХ өгөгдөл (огноо сонгоогүй)
sales_qs = OpenDataSale.objects.all()
print(f'sales_qs count: {sales_qs.count():,}')

# 2. product_filter = None (бараа сонгоогүй)
product_filter = None

# 3. product_qs = sales_qs
product_qs = sales_qs

# 4. Filters (бүгд None)
category_filter = None
customer_filter = None
brand_filter = None

if product_filter:
    print('  ✓ product_filter-ээр шүүнэ')
    product_qs = product_qs.filter(itemname__icontains=product_filter)

if category_filter:
    print('  ✓ category_filter-ээр шүүнэ')

if customer_filter:
    print('  ✓ customer_filter-ээр шүүнэ')

if brand_filter:
    print('  ✓ brand_filter-ээр шүүнэ')

print(f'\nШүүлтийн дараа product_qs count: {product_qs.count():,}')

# 5. _get_product_analysis() дуурайх
if product_filter:
    product_qs_filtered = product_qs.filter(itemname__icontains=product_filter)
else:
    product_qs_filtered = product_qs

product_stats = product_qs_filtered.values('itemname', 'brandname').annotate(
    revenue=Sum(Cast('payamount', FloatField())),
    qty=Sum(Cast('qty', FloatField())),
    orders=Count('documentpkid', distinct=True),
    customers=Count('customername', distinct=True)
).order_by('-revenue')

print(f'\nproduct_stats count: {product_stats.count():,}')
print(f'Эхний 5 бараа:')
for i, item in enumerate(product_stats[:5], 1):
    print(f'{i}. {item["itemname"][:50]:50} - {item["revenue"]:,.0f}₮')

if product_stats.count() == 0:
    print('\n❌ АСУУДАЛ: product_stats хоосон байна!')
    print('Энэ нь template дээр {% empty %} блок руу орно')
else:
    print(f'\n✅ {product_stats.count()} бараа олдлоо - template-д харагдах ёстой')
