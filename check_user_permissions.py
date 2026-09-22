"""
Check user permissions for nasaatelmen1024@gmail.com
Шинэ логик: Default False → Албан тушаалаар True болгоно
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataEmployee
from django.contrib.auth import get_user_model

User = get_user_model()

email = 'nasaatelmen1024@gmail.com'

print(f"\n{'='*80}")
print(f"ХЭРЭГЛЭГЧИЙН ЭРХИЙН ШАЛГАЛТ: {email}")
print(f"{'='*80}\n")

# 1. User model дээр шалгах
print("1️⃣  AUTHENTICATION (User model):")
try:
    user = User.objects.get(email=email)
    print(f"   ✅ Хэрэглэгч олдсон:")
    print(f"      - Username: {user.username}")
    print(f"      - Email: {user.email}")
    print(f"      - is_staff: {user.is_staff}")
    print(f"      - is_active: {user.is_active}")
except User.DoesNotExist:
    print(f"   ❌ User model дээр {email} олдсонгүй")
    user = None

# 2. OpenDataEmployee дээр шалгах
print(f"\n2️⃣  POSITION (OpenDataEmployee model):")
try:
    employee = OpenDataEmployee.objects.get(email=email)
    print(f"   ✅ Ажилтан олдсон:")
    print(f"      - Name: {employee.name}")
    print(f"      - Position: {employee.positionname}")
    print(f"      - Department: {employee.departmentname}")
    print(f"      - Email: {employee.email}")
except OpenDataEmployee.DoesNotExist:
    print(f"   ❌ OpenDataEmployee дээр {email} олдсонгүй")
    employee = None

# ========================================
# 3️⃣ ШИНЭ ЛОГИК (Default: бүгд False)
# ========================================
print(f"\n3️⃣  PERMISSIONS (ШИНЭ ЛОГИК - Default False):")

# Default: бүгд False
permissions = {
    'can_view_sales_report': False,
    'can_view_purchase_report': False,
    'can_view_delivery_report': False,
    'can_view_expense_report': False,
    'can_view_inventory': False,
    'can_edit_products': False,
    'can_manage_users': False,
}

if employee:
    position = employee.positionname
    print(f"   Албан тушаал: '{position}'")
    print(f"\n   IF/ELIF CHAIN:")
    
    matched = False
    
    # 1. Захирал, Ерөнхий нягтлан - БҮХ ЭРХ
    if position in ["Захирал", "Ерөнхий нягтлан"]:
        print(f"   ✅ IF #1: '{position}' БА ['Захирал', 'Ерөнхий нягтлан']")
        print(f"      → БҮХ ЭРХ ОЛГОНО (7/7)")
        permissions = {
            'can_view_sales_report': True,
            'can_view_purchase_report': True,
            'can_view_delivery_report': True,
            'can_view_expense_report': True,
            'can_view_inventory': True,
            'can_edit_products': True,
            'can_manage_users': True,
        }
        matched = True
    
    # 2. Гадаад харилцаа - Зөвхөн татан авалтын тайлан
    elif position == "Гадаад харилцаа":
        print(f"   ✅ ELIF #2: '{position}' == 'Гадаад харилцаа'")
        print(f"      → Зөвхөн татан авалтын тайлан (1/7)")
        permissions['can_view_purchase_report'] = True
        matched = True
    
    # 3. Нярав - Барааны үлдэгдэл + Түгээлтийн тайлан
    elif position == "Нярав":
        print(f"   ✅ ELIF #3: '{position}' == 'Нярав'")
        print(f"      → Үлдэгдэл + Түгээлт (2/7)")
        permissions['can_view_inventory'] = True
        permissions['can_view_delivery_report'] = True
        matched = True
    
    # 4. Түгээгч - Зөвхөн түгээлтийн тайлан
    elif position == "Түгээгч":
        print(f"   ✅ ELIF #4: '{position}' == 'Түгээгч'")
        print(f"      → Зөвхөн түгээлт (1/7)")
        permissions['can_view_delivery_report'] = True
        matched = True
    
    # 5. Ажилтан - Хязгаарлалттай эрх
    elif position == "Ажилтан":
        print(f"   ✅ ELIF #5: '{position}' == 'Ажилтан'")
        print(f"      → Эрхгүй (0/7)")
        matched = True
    
    # 6. Бусад албан тушаал - Default False хэвээр
    else:
        print(f"   ❌ Ямар ч нөхцөл тохирохгүй")
        print(f"   ➡️  ELSE: '{position}' → Default эрхгүй (0/7)")
        matched = False

else:
    print(f"   ⚠️  Employee олдоогүй - DEFAULT permissions (бүгд False)")

# Үр дүн харуулах
print(f"\n4️⃣  ЭЦСИЙН ҮР ДҮН:")
print(f"   Тайлангууд:")
print(f"      - Борлуулалтын тайлан: {'✅ ХАРНА' if permissions['can_view_sales_report'] else '❌ ХАРАХГҮЙ'}")
print(f"      - Татан авалтын тайлан: {'✅ ХАРНА' if permissions['can_view_purchase_report'] else '❌ ХАРАХГҮЙ'}")
print(f"      - Түгээлтийн тайлан: {'✅ ХАРНА' if permissions['can_view_delivery_report'] else '❌ ХАРАХГҮЙ'}")
print(f"      - Зардлын тооцоолол: {'✅ ХАРНА' if permissions['can_view_expense_report'] else '❌ ХАРАХГҮЙ'}")
print(f"      - Барааны үлдэгдэл: {'✅ ХАРНА' if permissions['can_view_inventory'] else '❌ ХАРАХГҮЙ'}")

# Нийт эрхийн тоо
total_perms = sum(permissions.values())
print(f"\n   📊 Нийт эрх: {total_perms}/7")

print(f"\n{'='*80}\n")

# ШИНЖИЛГЭЭ
print(f"🔍 ШИНЖИЛГЭЭ:")
if employee:
    print(f"\n   📋 SECURITY MODEL: Default Deny (аюулгүй)")
    print(f"      - Бүх эрх анхдаг False эхэлнэ")
    print(f"      - Албан тушаалаар тодорхой эрх олгоно")
    print(f"      - Санамсаргүй эрх олгохгүй")
    
    if employee.positionname in ["Захирал", "Ерөнхий нягтлан"]:
        print(f"\n   ✅ '{employee.positionname}' → Бүх эрхтэй (7/7)")
    elif employee.positionname in ["Гадаад харилцаа", "Нярав", "Түгээгч", "Ажилтан"]:
        print(f"\n   ⚠️  '{employee.positionname}' → Хязгаарлалттай эрх ({total_perms}/7)")
    else:
        print(f"\n   ❌ '{employee.positionname}' → Жагсаалтад байхгүй")
        print(f"      → Default эрхгүй (0/7)")
        print(f"\n   💡 САНАЛ:")
        print(f"      Хэрэв энэ албан тушаал эрхтэй байх ёстой бол:")
        print(f"      shop/context_processors.py файлд нэмнэ үү")

print(f"\n{'='*80}\n")
