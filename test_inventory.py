import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataInventory

print("=" * 70)
print("OpenDataInventory өгөгдөл шалгах")
print("=" * 70)

# Нийт өгөгдөл
total = OpenDataInventory.objects.count()
print(f'\nНийт бичлэг: {total:,}')

if total == 0:
    print('❌ Өгөгдөл байхгүй байна!')
else:
    # Агуулахын нэрүүд
    warehouses = OpenDataInventory.objects.values_list('warehousename', flat=True).distinct()
    print(f'\nАгуулахын нэрүүд:')
    for wh in warehouses:
        if wh:
            count = OpenDataInventory.objects.filter(warehousename=wh).count()
            print(f'  - {wh}: {count:,} бичлэг')
    
    # Сүүлийн 10 бичлэг
    print(f'\nСүүлийн 10 бичлэг:')
    latest = OpenDataInventory.objects.order_by('-documentdate')[:10]
    for inv in latest:
        print(f'  {inv.documentdate} | {inv.warehousename} | {inv.itemname[:40]} | Үлдэгдэл: {inv.endqty}')
    
    # Огнооны хүрээ
    from django.db.models import Min, Max
    date_range = OpenDataInventory.objects.aggregate(
        earliest=Min('documentdate'),
        latest=Max('documentdate')
    )
    print(f'\nОгнооны хүрээ: {date_range["earliest"]} - {date_range["latest"]}')
