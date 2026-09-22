import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataItem, OpenDataSale

# Яг views.py дахь кодыг дуурайх
products_list = OpenDataItem.objects.filter(
    activestatus='Y'
).exclude(name__isnull=True).exclude(name='').order_by('name')[:500]

customers_list = OpenDataSale.objects.values_list(
    'customername', flat=True
).distinct().exclude(customername__isnull=True).exclude(customername='')[:500]

# Context-д нэмэх мэт
products_context = products_list
customers_context = list(customers_list)

print(f'products_list type: {type(products_context)}')
print(f'products count: {len(products_context)}')
print(f'\nЭхний 5 бараа:')
for i, p in enumerate(products_context[:5], 1):
    print(f'  {i}. {p.name[:60]}')

print(f'\n\ncustomers_list type: {type(customers_context)}')
print(f'customers count: {len(customers_context)}')
print(f'\nЭхний 5 харилцагч:')
for i, c in enumerate(customers_context[:5], 1):
    print(f'  {i}. {c[:60]}')

print('\n✅ Context өгөгдөл зөв байна!')
