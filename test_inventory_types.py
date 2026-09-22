"""Test OpenDataInventory field types"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataInventory

# Get a sample record
sample = OpenDataInventory.objects.first()
if sample:
    print(f"Sample record:")
    print(f"  endqty: {sample.endqty!r} (type: {type(sample.endqty).__name__})")
    print(f"  unitcost: {sample.unitcost!r} (type: {type(sample.unitcost).__name__})")
    print(f"  inqty: {sample.inqty!r} (type: {type(sample.inqty).__name__})")
    print(f"  outqty: {sample.outqty!r} (type: {type(sample.outqty).__name__})")
else:
    print("No records found")
