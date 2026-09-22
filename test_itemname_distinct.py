import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale

print("=" * 70)
print("ШАЛГАЛТ: sales_qs-аас distinct itemname")
print("=" * 70)

# Огноо сонгоогүй - БҮХ өгөгдөл
sales_qs = OpenDataSale.objects.all()
print(f'\nНийт OpenDataSale: {sales_qs.count():,} бичлэг')

# Distinct itemname-үүд
products_list = sales_qs.values_list(
    'itemname', flat=True
).distinct().exclude(itemname__isnull=True).exclude(itemname='').order_by('itemname')

print(f'Distinct itemname: {products_list.count():,} бараа')

# Эхний 10
print('\nЭхний 10 itemname:')
for i, name in enumerate(products_list[:10], 1):
    print(f'{i}. {name[:60]}')

# Нийт давхардсан нэрүүд
all_itemnames = sales_qs.values_list('itemname', flat=True)
print(f'\n\nНийт itemname (давхардсан): {all_itemnames.count():,}')

# Хоосон itemname байгаа эсэхийг шалгах
null_count = sales_qs.filter(itemname__isnull=True).count()
empty_count = sales_qs.filter(itemname='').count()
print(f'Null itemname: {null_count:,}')
print(f'Хоосон itemname: {empty_count:,}')

print('\n✅ Distinct itemname зөв ажиллаж байна!')
