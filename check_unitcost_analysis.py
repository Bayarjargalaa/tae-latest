import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale
from django.db.models import Count, Min, Max, Avg, Q
from django.db.models.functions import Cast
from django.db.models import FloatField

print("=" * 100)
print("OPENDATASALE - UNITCOST ДҮГНЭЛТ")
print("=" * 100)

# Нийт мөрийн тоо
total_records = OpenDataSale.objects.count()
print(f"\nНийт мөр: {total_records:,}")

# UnitCost NULL эсвэл хоосон
null_count = OpenDataSale.objects.filter(Q(unitcost__isnull=True) | Q(unitcost='')).count()
print(f"NULL/Хоосон UnitCost: {null_count:,} ({null_count/total_records*100:.2f}%)")

# UnitCost = 0
zero_count = OpenDataSale.objects.filter(unitcost='0').count()
print(f"UnitCost = 0: {zero_count:,} ({zero_count/total_records*100:.2f}%)")

print("\n" + "=" * 100)
print("АГУУЛАХ ТУС БҮРЭЭР ДҮГНЭЛТ (WarehouseName)")
print("=" * 100)

# Агуулах тус бүрээр дүгнэлт
warehouses = OpenDataSale.objects.values('warehousename').annotate(
    unitcost_float=Cast('unitcost', FloatField())
).values('warehousename').annotate(
    total_records=Count('documentpkid'),
    zero_count=Count('documentpkid', filter=Q(unitcost='0')),
    null_count=Count('documentpkid', filter=Q(unitcost__isnull=True) | Q(unitcost='')),
    min_unitcost=Min('unitcost_float'),
    max_unitcost=Max('unitcost_float'),
    avg_unitcost=Avg('unitcost_float')
).order_by('warehousename')

for wh in warehouses:
    wh_name = wh['warehousename'] or 'Тодорхойгүй'
    print(f"\n📦 АГУУЛАХ: {wh_name}")
    print(f"   Нийт мөр: {wh['total_records']:,}")
    print(f"   NULL/Хоосон: {wh['null_count']:,} ({wh['null_count']/wh['total_records']*100:.2f}%)")
    print(f"   UnitCost = 0: {wh['zero_count']:,} ({wh['zero_count']/wh['total_records']*100:.2f}%)")
    print(f"   Хамгийн бага: {wh['min_unitcost']:.2f}" if wh['min_unitcost'] else "   Хамгийн бага: NULL")
    print(f"   Хамгийн их: {wh['max_unitcost']:.2f}" if wh['max_unitcost'] else "   Хамгийн их: NULL")
    print(f"   Дундаж: {wh['avg_unitcost']:.2f}" if wh['avg_unitcost'] else "   Дундаж: NULL")

# Sample өгөгдөл харах (UnitCost = 0 байгаа)
print("\n" + "=" * 100)
print("ЖИШЭЭ: UnitCost = 0 байгаа мөрүүд (эхний 10)")
print("=" * 100)

zero_samples = OpenDataSale.objects.filter(unitcost='0')[:10]
for i, record in enumerate(zero_samples, 1):
    print(f"\n{i}. Агуулах: {record.warehousename}")
    print(f"   Бараа: {record.itemname}")
    print(f"   Огноо: {record.documentdate}")
    print(f"   Тоо ширхэг: {record.qty}")
    print(f"   UnitCost: {record.unitcost}")
    print(f"   Үнэ: {record.price}")

# Sample өгөгдөл харах (UnitCost > 0 байгаа)
print("\n" + "=" * 100)
print("ЖИШЭЭ: UnitCost > 0 байгаа мөрүүд (эхний 10)")
print("=" * 100)

valid_samples = OpenDataSale.objects.exclude(Q(unitcost='0') | Q(unitcost__isnull=True) | Q(unitcost=''))[:10]
for i, record in enumerate(valid_samples, 1):
    print(f"\n{i}. Агуулах: {record.warehousename}")
    print(f"   Бараа: {record.itemname}")
    print(f"   Огноо: {record.documentdate}")
    print(f"   Тоо ширхэг: {record.qty}")
    print(f"   UnitCost: {record.unitcost}")
    print(f"   Үнэ: {record.price}")
    if record.unitcost and record.qty:
        try:
            cost = float(record.unitcost)
            qty = float(record.qty)
            total_cost = cost * qty
            print(f"   Нэгжийн өртөг × Тоо ширхэг = {cost:.2f} × {qty:.2f} = {total_cost:.2f}")
        except:
            pass

print("\n" + "=" * 100)
