import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale, OpenDataItem, OpenDataInventory, OpenDataPurchase, OpenDataLandedCost
from django.db.models import Count, Min, Max, Avg, Q
from django.db.models.functions import Cast
from django.db.models import FloatField

print("=" * 120)
print("UNITCOST ТАЛБАРЫН ЭХҮҮДИЙГ ШАЛГАХ")
print("=" * 120)

# 1. OpenDataItem - StandardUnitCost шалгах
print("\n1️⃣  OpenDataItem - StandardUnitCost (статик стандарт өртөг)")
print("-" * 120)

# Дүгнэлт хийх (тоо хэмжээ)
total_items = OpenDataItem.objects.count()

# Cast ашиглан хоосон утгуудыг хассаны дараа тооцоолно
items_stats = OpenDataItem.objects.annotate(
    cost_float=Cast('standardunitcost', FloatField())
).values('id', 'cost_float')

# Python-д тооцоолно
valid_costs = [item['cost_float'] for item in items_stats if item['cost_float'] is not None and item['cost_float'] > 0]
count_with_cost = len(valid_costs)
avg_cost = sum(valid_costs) / count_with_cost if count_with_cost > 0 else 0
min_cost = min(valid_costs) if valid_costs else 0
max_cost = max(valid_costs) if valid_costs else 0

print(f"Нийт бүтээгдэхүүн: {total_items:,}")
print(f"StandardUnitCost бүхий: {count_with_cost:,}")
print(f"Дундаж өртөг: {avg_cost:,.2f} ₮" if count_with_cost > 0 else "Дундаж өртөг: 0")
print(f"Хамгийн бага: {min_cost:,.2f} ₮" if count_with_cost > 0 else "Хамгийн бага: 0")
print(f"Хамгийн их: {max_cost:,.2f} ₮" if count_with_cost > 0 else "Хамгийн их: 0")

# 2. OpenDataSale - UnitCost (борлуулалтын үеийн өртөг)
print("\n\n2️⃣  OpenDataSale - UnitCost (борлуулалтын бичлэг дэх өртөг)")
print("-" * 120)
sale_samples = OpenDataSale.objects.exclude(
    Q(unitcost__isnull=True) | Q(unitcost='') | Q(unitcost='0')
).order_by('-documentdate')[:10]

print(f"{'Огноо':12} | {'Бараа':45} | {'UnitCost':>12} | {'Price':>12} | {'PayAmount':>15}")
print("-" * 120)
for sale in sale_samples:
    try:
        unitcost = float(sale.unitcost) if sale.unitcost else 0
        price = float(sale.price) if sale.price else 0
        payamount = float(sale.payamount) if sale.payamount else 0
        name = (sale.itemname[:42] + '...') if sale.itemname and len(sale.itemname) > 45 else (sale.itemname or 'N/A')
        print(f"{sale.documentdate[:10]:12} | {name:45} | {unitcost:>12,.2f} | {price:>12,.2f} | {payamount:>15,.2f}")
    except:
        pass

# 3. OpenDataInventory - UnitCost шалгах
print("\n\n3️⃣  OpenDataInventory - UnitCost (нөөцийн хөдөлгөөн дэх өртөг)")
print("-" * 120)
inventory_samples = OpenDataInventory.objects.exclude(
    Q(unitcost__isnull=True) | Q(unitcost='') | Q(unitcost='0')
).order_by('-documentdate')[:10]

print(f"{'Огноо':12} | {'Төрөл':20} | {'Бараа':40} | {'UnitCost':>12}")
print("-" * 120)
for inv in inventory_samples:
    try:
        unitcost = float(inv.unitcost) if inv.unitcost else 0
        name = (inv.itemname[:37] + '...') if inv.itemname and len(inv.itemname) > 40 else (inv.itemname or 'N/A')
        doctype = (inv.documenttype[:17] + '...') if inv.documenttype and len(inv.documenttype) > 20 else (inv.documenttype or 'N/A')
        print(f"{inv.documentdate[:10]:12} | {doctype:20} | {name:40} | {unitcost:>12,.2f}")
    except:
        pass

# 4. OpenDataPurchase - UnitCost шалгах
print("\n\n4️⃣  OpenDataPurchase - UnitCost (худалдан авалтын өртөг)")
print("-" * 120)
purchase_samples = OpenDataPurchase.objects.exclude(
    Q(unitcost__isnull=True) | Q(unitcost=0)
).order_by('-documentdate')[:10]

print(f"{'Огноо':12} | {'Нийлүүлэгч':30} | {'Бараа':35} | {'UnitCost':>12} | {'Amount':>15}")
print("-" * 120)
for purch in purchase_samples:
    vendor = (purch.vendorname[:27] + '...') if purch.vendorname and len(purch.vendorname) > 30 else (purch.vendorname or 'N/A')
    name = (purch.itemname[:32] + '...') if purch.itemname and len(purch.itemname) > 35 else (purch.itemname or 'N/A')
    print(f"{purch.documentdate:12} | {vendor:30} | {name:35} | {purch.unitcost or 0:>12,.2f} | {purch.amount or 0:>15,.2f}")

# 5. OpenDataLandedCost - UnitCost шалгах
print("\n\n5️⃣  OpenDataLandedCost - UnitCost (импортын өртөг + гаалийн хураамж + тээвэр)")
print("-" * 120)
landed_samples = OpenDataLandedCost.objects.exclude(
    Q(unitcost__isnull=True) | Q(unitcost='') | Q(unitcost='0')
).order_by('-documentdate')[:10]

print(f"{'Огноо':12} | {'Бараа':40} | {'UnitCost':>12} | {'CustomsFee':>12} | {'Transport':>12} | {'TotalCost':>12}")
print("-" * 120)
for landed in landed_samples:
    try:
        unitcost = float(landed.unitcost) if landed.unitcost else 0
        customs = float(landed.customsfee) if landed.customsfee else 0
        transport = float(landed.transportcost) if landed.transportcost else 0
        totalcost = float(landed.totalcost) if landed.totalcost else 0
        name = (landed.itemname[:37] + '...') if landed.itemname and len(landed.itemname) > 40 else (landed.itemname or 'N/A')
        print(f"{landed.documentdate:12} | {name:40} | {unitcost:>12,.2f} | {customs:>12,.2f} | {transport:>12,.2f} | {totalcost:>12,.2f}")
    except:
        pass

# 6. НЭГЖ БАРААНЫ ӨРТГИЙН ХАРЬЦУУЛАЛТ
print("\n\n6️⃣  НЭГ БАРАА - ӨӨР ӨӨР ХҮСНЭГТҮҮДЭД ӨРТӨГ ЯАЖ БАЙНА?")
print("=" * 120)

# Борлуулалтаас хамгийн их борлуулагдсан бараа авах
top_items = OpenDataSale.objects.values('itemname').annotate(
    total_qty=Count('documentpkid')
).order_by('-total_qty')[:5]

for rank, item_data in enumerate(top_items, 1):
    item_name = item_data['itemname']
    if not item_name:
        continue
    
    print(f"\n🔍 TOP {rank}: {item_name}")
    print("-" * 120)
    
    # OpenDataItem - StandardUnitCost (Cast ашиглана)
    item_info = OpenDataItem.objects.filter(name=item_name).annotate(
        std_cost=Cast('standardunitcost', FloatField())
    ).first()
    if item_info and item_info.std_cost:
        print(f"   📦 OpenDataItem.StandardUnitCost: {item_info.std_cost:,.2f} ₮")
    else:
        print(f"   📦 OpenDataItem.StandardUnitCost: NULL/Хоосон")
    
    # OpenDataSale - UnitCost (дундаж)
    sale_avg = OpenDataSale.objects.filter(itemname=item_name).exclude(
        Q(unitcost__isnull=True) | Q(unitcost='')
    ).aggregate(avg_cost=Avg(Cast('unitcost', FloatField())))
    if sale_avg['avg_cost']:
        print(f"   💰 OpenDataSale.UnitCost (дундаж): {sale_avg['avg_cost']:,.2f} ₮")
    else:
        print(f"   💰 OpenDataSale.UnitCost: NULL/Хоосон")
    
    # OpenDataPurchase - UnitCost (дундаж)
    purch_avg = OpenDataPurchase.objects.filter(itemname=item_name).exclude(
        Q(unitcost__isnull=True)
    ).aggregate(avg_cost=Avg('unitcost'))
    if purch_avg['avg_cost']:
        print(f"   🛒 OpenDataPurchase.UnitCost (дундаж): {purch_avg['avg_cost']:,.2f} ₮")
    else:
        print(f"   🛒 OpenDataPurchase.UnitCost: NULL/Хоосон")
    
    # OpenDataLandedCost - UnitCost (дундаж)
    landed_avg = OpenDataLandedCost.objects.filter(itemname=item_name).exclude(
        Q(unitcost__isnull=True) | Q(unitcost='')
    ).aggregate(avg_cost=Avg(Cast('unitcost', FloatField())))
    if landed_avg['avg_cost']:
        print(f"   🚢 OpenDataLandedCost.UnitCost (дундаж): {landed_avg['avg_cost']:,.2f} ₮")
    else:
        print(f"   🚢 OpenDataLandedCost.UnitCost: NULL/Хоосон")

print("\n\n" + "=" * 120)
print("📋 ДҮГНЭЛТ")
print("=" * 120)
print("""
🔴 САНХҮҮГИЙН ПРОГРАММААС АСУУХ АСУУЛТУУД:

1️⃣  OpenDataSale VIEW-ны UnitCost талбар ямар эхээс (table/column) авагдаж байна вэ?
    - OpenDataItem.StandardUnitCost ашигладаг уу?
    - OpenDataInventory.UnitCost (борлуулалтын үеийн агуулахын өртөг) ашигладаг уу?
    - Өөр тооцооллын логик байгаа юу?

2️⃣  UnitCost өөрчлөгддөг үү цаг хугацааны явцад?
    - Moving Average ашигладаг уу?
    - FIFO (First In First Out) ашигладаг уу?
    - LIFO (Last In First Out) ашигладаг уу?
    - Fixed Standard Cost ашигладаг уу?

3️⃣  OpenDataSale VIEW-н CREATE script-ийг өгч чадах уу?
    - Бид UnitCost талбарын эх үүсвэрийг нягтлах шаардлагатай

4️⃣  Импортын бараанд (LandedCost):
    - Гаалийн хураамж болон тээврийн зардал UnitCost-д нэмэгддэг үү?
    - Эсвэл тусдаа тооцоологддог уу?

5️⃣  Борлуулалтын ашгийн тайланд:
    - Gross Profit (Орлого - COGS) тооцоологддог уу?
    - Net Profit (Gross Profit - Үйл ажиллагааны зардал) тооцоологддог уу?
    - Ямар зардлууд тооцоологддог вэ?
""")
