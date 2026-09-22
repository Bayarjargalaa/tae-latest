import os
import django
from django.test import RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from shop.views import sales_report
from django.contrib.auth import get_user_model
import re

User = get_user_model()

try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_user(username='admin', is_staff=True)

factory = RequestFactory()

print("=" * 70)
print("ТЕСТ: Шүүлтээр илэрсэн бараа/харилцагч dropdown-д")
print("=" * 70)

# ТЕСТ 1: Огноо сонгоогүй - БҮХ өгөгдөл
print("\n1. Огноо сонгоогүй (БҮХ өгөгдөл):")
request1 = factory.get('/dashboard/sales-report/?tab=by_product')
request1.user = user

response1 = sales_report(request1)
content1 = response1.content.decode('utf-8')

products_options1 = re.findall(r'<option value="([^"]*)"[^>]*>(?:.*?)</option>', 
                                re.search(r'<select id="product-select".*?</select>', content1, re.DOTALL).group(0) if re.search(r'<select id="product-select".*?</select>', content1, re.DOTALL) else '')
customers_options1 = re.findall(r'<option value="([^"]*)"[^>]*>', 
                                 re.search(r'<select id="customer-select".*?</select>', content1, re.DOTALL).group(0) if re.search(r'<select id="customer-select".*?</select>', content1, re.DOTALL) else '')

products_count1 = len([p for p in products_options1 if p])  # Хоосон биш
customers_count1 = len([c for c in customers_options1 if c])

print(f'   Бараа dropdown: {products_count1} бараа')
print(f'   Харилцагч dropdown: {customers_count1} харилцагч')

# ТЕСТ 2: 2024 оны өгөгдөл
print("\n2. 2024 оны өгөгдөл:")
request2 = factory.get('/dashboard/sales-report/?tab=by_product&date_from=2024-01-01&date_to=2024-12-31')
request2.user = user

response2 = sales_report(request2)
content2 = response2.content.decode('utf-8')

products_options2 = re.findall(r'<option value="([^"]*)"[^>]*>', 
                                re.search(r'<select id="product-select".*?</select>', content2, re.DOTALL).group(0) if re.search(r'<select id="product-select".*?</select>', content2, re.DOTALL) else '')
customers_options2 = re.findall(r'<option value="([^"]*)"[^>]*>', 
                                 re.search(r'<select id="customer-select".*?</select>', content2, re.DOTALL).group(0) if re.search(r'<select id="customer-select".*?</select>', content2, re.DOTALL) else '')

products_count2 = len([p for p in products_options2 if p])
customers_count2 = len([c for c in customers_options2 if c])

print(f'   Бараа dropdown: {products_count2} бараа')
print(f'   Харилцагч dropdown: {customers_count2} харилцагч')

# ТЕСТ 3: 2026-02 (сүүлийн сар)
print("\n3. 2026-02 сар:")
request3 = factory.get('/dashboard/sales-report/?tab=by_product&date_from=2026-02-01&date_to=2026-02-12')
request3.user = user

response3 = sales_report(request3)
content3 = response3.content.decode('utf-8')

products_options3 = re.findall(r'<option value="([^"]*)"[^>]*>', 
                                re.search(r'<select id="product-select".*?</select>', content3, re.DOTALL).group(0) if re.search(r'<select id="product-select".*?</select>', content3, re.DOTALL) else '')
customers_options3 = re.findall(r'<option value="([^"]*)"[^>]*>', 
                                 re.search(r'<select id="customer-select".*?</select>', content3, re.DOTALL).group(0) if re.search(r'<select id="customer-select".*?</select>', content3, re.DOTALL) else '')

products_count3 = len([p for p in products_options3 if p])
customers_count3 = len([c for c in customers_options3 if c])

print(f'   Бараа dropdown: {products_count3} бараа')
print(f'   Харилцагч dropdown: {customers_count3} харилцагч')

# Эхний 5 бараа харуулах (ТЕСТ 3)
print(f'\n   Эхний 5 бараа (2026-02):')
for i, product in enumerate([p for p in products_options3 if p][:5], 1):
    print(f'     {i}. {product[:60]}')

print("\n" + "=" * 70)
print("ДҮГНЭЛТ:")
print("=" * 70)

if products_count1 > products_count2 > products_count3:
    print("✅ Dropdown жагсаалт шүүлтээр БАГАСЧ байна")
    print(f"   БҮХ өгөгдөл ({products_count1}) > 2024 ({products_count2}) > 2026-02 ({products_count3})")
    print("   Энэ нь зөв - зөвхөн тухайн хугацаанд борлуулалттай бараанууд гарч байна")
else:
    print("⚠️ Шүүлт нөлөөлөхгүй эсвэл буруу:")
    print(f"   БҮХ: {products_count1}, 2024: {products_count2}, 2026-02: {products_count3}")
