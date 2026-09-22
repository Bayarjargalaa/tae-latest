import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale
from django.db.models import Sum, Count, Avg, ExpressionWrapper, FloatField
from django.db.models.functions import Cast, ExtractYear
from django.db.models import DateField

print("=" * 100)
print("АШГИЙН ТООЦООЛЛЫН ШАЛГАЛТ")
print("=" * 100)

# Жил бүрээр ашиг тооцоолох (sales_report кодын дагуу)
yearly_data = OpenDataSale.objects.extra(
    select={'year': "EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE))"}
).values('year').annotate(
    revenue=Sum(Cast('payamount', FloatField())),
    total_cost=Sum(
        ExpressionWrapper(
            Cast('unitcost', FloatField()) * Cast('qty', FloatField()),
            output_field=FloatField()
        )
    ),
    total_qty=Sum(Cast('qty', FloatField())),
    avg_price=Avg(Cast('price', FloatField())),
    avg_unitcost=Avg(Cast('unitcost', FloatField())),
    total_records=Count('documentpkid')
).order_by('year')

print("\nЖИЛ БҮРИЙН АШГИЙН ТООЦООЛОЛ:")
print("-" * 100)
print(f"{'Жил':>6} | {'Орлого (₮)':>20} | {'Өртөг (₮)':>20} | {'Ашиг (₮)':>20} | {'Ашиг %':>10} | {'Мөр':>10}")
print("-" * 100)

for row in yearly_data:
    year = int(row['year']) if row['year'] else 0
    revenue = row['revenue'] or 0
    cost = row['total_cost'] or 0
    profit = revenue - cost
    profit_pct = (profit / revenue * 100) if revenue > 0 else 0
    
    print(f"{year:>6} | {revenue:>20,.2f} | {cost:>20,.2f} | {profit:>20,.2f} | {profit_pct:>9.2f}% | {row['total_records']:>10,}")

print("\n" + "=" * 100)
print("ЖИШЭЭ ӨГӨГДӨЛ ШАЛГАЛТ (PayAmount vs Price × Qty)")
print("=" * 100)

# 10 мөр жишээ авах
samples = OpenDataSale.objects.exclude(
    qty__isnull=True
).exclude(
    price__isnull=True
).exclude(
    payamount__isnull=True
).exclude(
    unitcost__isnull=True
)[:20]

print(f"\n{'№':>3} | {'Огноо':>12} | {'Qty':>10} | {'Price':>12} | {'PayAmount':>15} | {'Calc (P×Q)':>15} | {'Зөрүү':>15}")
print("-" * 100)

mismatches = 0
for i, record in enumerate(samples, 1):
    try:
        qty = float(record.qty)
        price = float(record.price)
        payamount = float(record.payamount)
        calculated = price * qty
        diff = payamount - calculated
        diff_pct = (diff / payamount * 100) if payamount != 0 else 0
        
        # 1% -аас их зөрүү байвал тэмдэглэх
        mark = "⚠️" if abs(diff_pct) > 1 else "✓"
        if abs(diff_pct) > 1:
            mismatches += 1
        
        print(f"{i:>3} | {record.documentdate[:10]:>12} | {qty:>10,.2f} | {price:>12,.2f} | {payamount:>15,.2f} | {calculated:>15,.2f} | {diff:>14,.2f} {mark}")
    except (ValueError, TypeError):
        print(f"{i:>3} | ERROR converting values")

print(f"\nPayAmount ≠ Price × Qty (1% дээш зөрүү): {mismatches}/{i}")

print("\n" + "=" * 100)
print("ӨРТӨГ vs ОРЛОГЫН ХАРЬЦАА ШАЛГАЛТ")
print("=" * 100)

# 20 мөр өртөг/орлогын харьцааг харах
cost_samples = OpenDataSale.objects.exclude(
    qty__isnull=True
).exclude(
    unitcost__isnull=True
).exclude(
    payamount__isnull=True
)[:20]

print(f"\n{'№':>3} | {'Бараа':>40} | {'UnitCost':>12} | {'Price':>12} | {'Markup%':>10} | {'TotalCost':>15} | {'Revenue':>15} | {'Profit':>15}")
print("-" * 130)

negative_margins = 0
for i, record in enumerate(cost_samples, 1):
    try:
        qty = float(record.qty) if record.qty else 0
        unitcost = float(record.unitcost) if record.unitcost else 0
        price = float(record.price) if record.price else 0
        payamount = float(record.payamount) if record.payamount else 0
        
        markup = ((price - unitcost) / unitcost * 100) if unitcost > 0 else 0
        total_cost = unitcost * qty
        profit = payamount - total_cost
        
        mark = "⚠️" if markup < 0 else "✓"
        if markup < 0:
            negative_margins += 1
        
        item_name = (record.itemname[:37] + '...') if record.itemname and len(record.itemname) > 40 else (record.itemname or 'N/A')
        
        print(f"{i:>3} | {item_name:>40} | {unitcost:>12,.2f} | {price:>12,.2f} | {markup:>9.2f}% | {total_cost:>15,.2f} | {payamount:>15,.2f} | {profit:>14,.2f} {mark}")
    except (ValueError, TypeError) as e:
        print(f"{i:>3} | ERROR: {e}")

print(f"\nӨртөг > Үнэ (сөрөг markup): {negative_margins}/{i}")

print("\n" + "=" * 100)
print("ДҮГНЭЛТ")
print("=" * 100)
