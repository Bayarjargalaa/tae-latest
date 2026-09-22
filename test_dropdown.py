import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataItem, OpenDataSale

# Барааны жагсаалт (dropdown-д байх ёстой)
products_list = OpenDataItem.objects.filter(
    activestatus='Y'
).exclude(name__isnull=True).exclude(name='').order_by('name')[:500]

print(f'Нийт активтай бараа (null биш): {products_list.count()}')
print('\nЭхний 10 бараа:')
for i, p in enumerate(products_list[:10], 1):
    print(f'{i}. {p.name[:60]}')

# Харилцагчийн жагсаалт (dropdown-д байх ёстой)
customers_list = OpenDataSale.objects.values_list(
    'customername', flat=True
).distinct().exclude(customername__isnull=True).exclude(customername='')[:500]

print(f'\n\nНийт харилцагч (null биш): {customers_list.count()}')
print('\nЭхний 10 харилцагч:')
for i, c in enumerate(customers_list[:10], 1):
    print(f'{i}. {c[:60]}')

print('\n✅ Бүх dropdown жагсаалтууд зөв ажиллах ёстой!')
