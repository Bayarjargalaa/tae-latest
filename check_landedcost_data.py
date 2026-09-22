import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataLandedCost

# Эхний 5 мөрийг шалгах
records = OpenDataLandedCost.objects.all()[:5]

print(f"Total records: {OpenDataLandedCost.objects.count()}")
print("\nFirst 5 records:")
print("-" * 100)

for record in records:
    print(f"Vendor: {record.vendorname}")
    print(f"Item: {record.itemname}")
    print(f"Date: {record.documentdate} (type: {type(record.documentdate)})")
    if record.documentdate:
        if isinstance(record.documentdate, str):
            print(f"  WARNING: Date is STRING!")
            try:
                from datetime import datetime
                date_obj = datetime.strptime(record.documentdate, '%Y-%m-%d').date()
                print(f"  Parsed - Year: {date_obj.year}, Month: {date_obj.month}, Day: {date_obj.day}")
            except:
                print(f"  ERROR: Cannot parse date")
        else:
            print(f"  Year: {record.documentdate.year}")
            print(f"  Month: {record.documentdate.month}")
            print(f"  Day: {record.documentdate.day}")
    print(f"Qty: {record.qty} (type: {type(record.qty)})")
    print(f"Price: {record.price} (type: {type(record.price)})")
    print(f"Amount FC: {record.itemamountfc} (type: {type(record.itemamountfc)})")
    print("-" * 100)

# Тодорхой vendor/item/year комбинацыг шалгах
print("\nChecking specific vendor/item combination:")
test_records = OpenDataLandedCost.objects.filter(
    vendorname__icontains='ammerland',
    itemname__icontains='cream cheese'
).order_by('documentdate')[:10]

print(f"Found {test_records.count()} records")
for rec in test_records:
    if rec.documentdate:
        print(f"{rec.vendorname} | {rec.itemname} | {rec.documentdate} | Year: {rec.documentdate.year} | Month: {rec.documentdate.month}")
