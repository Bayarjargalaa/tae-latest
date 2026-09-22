import os
import django
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from shop.models_inventory import InventorySnapshot

print("=" * 70)
print("БАРААНЫ ҮЛДЭГДЛИЙН SNAPSHOT - Статус шалгалт")
print("=" * 70)

# Snapshot-ын тоо
total_items = InventorySnapshot.objects.count()
print(f"\n📦 Snapshot-д хадгалагдсан барааны тоо: {total_items}")

# Сүүлд шинэчилсэн
if total_items > 0:
    latest = InventorySnapshot.objects.order_by('-updated_at').first()
    print(f"🕒 Сүүлд шинэчилсэн: {latest.updated_at}")
    
    # Одоогоос хэчнээн цагийн өмнө
    now = datetime.now(latest.updated_at.tzinfo)
    diff = now - latest.updated_at
    hours = diff.total_seconds() / 3600
    print(f"   ({hours:.1f} цагийн өмнө)")
    
    # Хамгийн их үлдэгдэлтэй 5 бараа
    print("\n📊 Хамгийн их үлдэгдэлтэй 5 бараа:")
    top_items = InventorySnapshot.objects.filter(total_qty__gt=0).order_by('-total_qty')[:5]
    for i, item in enumerate(top_items, 1):
        print(f"   {i}. {item.itemname[:50]}: {item.total_qty:,.0f}")
else:
    print("\n❌ Snapshot хоосон байна!")
    print("   Дараах командыг ажиллуулна уу:")
    print("   python manage.py update_inventory_snapshot")

print("\n" + "=" * 70)
print("WINDOWS TASK SCHEDULER - Статус")
print("=" * 70)

import subprocess

try:
    result = subprocess.run(
        ['powershell', '-Command', 
         "Get-ScheduledTask -TaskName '*inventory*' -ErrorAction SilentlyContinue | Select-Object TaskName, State, LastRunTime, NextRunTime"],
        capture_output=True,
        text=True,
        timeout=5
    )
    
    if result.stdout.strip():
        print("\n✅ Scheduled Task олдлоо:")
        print(result.stdout)
    else:
        print("\n❌ Scheduled Task олдсонгүй!")
        print("\n📝 Task үүсгэх заавар:")
        print("   1. PowerShell-г Administrator эрхээр нээх")
        print("   2. Дараах командыг ажиллуулах:")
        print("      cd D:\\Bayar\\programming\\python\\tae\\scripts")
        print("      .\\setup_inventory_schedule.ps1")
        
except Exception as e:
    print(f"\n⚠️ PowerShell шалгалт амжилтгүй: {e}")

print("\n" + "=" * 70)
print("💡 ГАРААР ШИНЭЧЛЭХ:")
print("   python manage.py update_inventory_snapshot")
print("=" * 70)
