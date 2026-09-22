import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataItem, OpenDataSale

print(f"Нийт бараа: {OpenDataItem.objects.count()}")

# ActiveStatus-ийн утгууд шалгах
statuses = OpenDataItem.objects.values_list('activestatus', flat=True).distinct()
print(f"\nБайгаа статусууд: {list(statuses)}")

print("\nЭхний 10 бүтээгдэхүүн:")
for p in OpenDataItem.objects.all()[:10]:
    print(f"  Status: [{p.activestatus}] - {p.name[:50] if p.name else 'NULL'}")

# Активтай барааны тоо
active_count = OpenDataItem.objects.filter(activestatus='Y').count()
print(f"\n\nАктивтай бараа: {active_count}")

# Эхний 10 активтай барааны нэр
active_items = OpenDataItem.objects.filter(activestatus='Y').order_by('name')[:10]
print('\nЭхний 10 активтай бараа:')
for i, item in enumerate(active_items, 1):
    print(f'{i}. {item.name[:60] if item.name else "NULL"}')

# OpenDataSale-аас давхардаагүй харилцагчид
customers_count = OpenDataSale.objects.values_list('customername', flat=True).distinct().count()
print(f'\n\nНийт давхардаагүй харилцагч: {customers_count}')

customers = OpenDataSale.objects.values_list('customername', flat=True).distinct()[:10]
print('\nЭхний 10 харилцагч:')
for i, cust in enumerate(customers, 1):
    if cust:
        print(f'{i}. {cust[:60]}')
    else:
        print(f'{i}. NULL')
