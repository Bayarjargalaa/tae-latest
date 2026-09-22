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
print("ТЕСТ: Dropdown lists (бараа, харилцагч)")
print("=" * 70)

request = factory.get('/dashboard/sales-report/?tab=by_product')
request.user = user

response = sales_report(request)
content = response.content.decode('utf-8')

print(f'Status: {response.status_code}')
print(f'Content size: {len(content):,} bytes')

# Datalist elements шалгах
products_datalist = re.search(r'<datalist id="products-list">(.*?)</datalist>', content, re.DOTALL)
customers_datalist = re.search(r'<datalist id="customers-list">(.*?)</datalist>', content, re.DOTALL)

print("\n1. БАРАА DROPDOWN (products-list):")
if products_datalist:
    options = re.findall(r'<option value="(.*?)">', products_datalist.group(1))
    print(f'   ✓ Datalist олдлоо')
    print(f'   Options тоо: {len(options)}')
    if len(options) > 0:
        print(f'   Эхний 5 option:')
        for i, opt in enumerate(options[:5], 1):
            print(f'     {i}. {opt[:60]}')
    else:
        print('   ❌ ХООСОН - options байхгүй!')
else:
    print('   ❌ products-list datalist HTML-д байхгүй!')

print("\n2. ХАРИЛЦАГЧ DROPDOWN (customers-list):")
if customers_datalist:
    options = re.findall(r'<option value="(.*?)">', customers_datalist.group(1))
    print(f'   ✓ Datalist олдлоо')
    print(f'   Options тоо: {len(options)}')
    if len(options) > 0:
        print(f'   Эхний 5 option:')
        for i, opt in enumerate(options[:5], 1):
            print(f'     {i}. {opt[:60]}')
    else:
        print('   ❌ ХООСОН - options байхгүй!')
else:
    print('   ❌ customers-list datalist HTML-д байхгүй!')

# Template variable шууд шалгах
print("\n3. TEMPLATE VARIABLES:")
if '{% for product in products %}' in content:
    print('   ✓ Template loop: {% for product in products %}')
if '{% for customer in customers %}' in content:
    print('   ✓ Template loop: {% for customer in customers %}')

# Context debug (хэрэв template-д {{ products }} байвал)
products_count_match = re.search(r'<!--DEBUG: products count: (\d+)-->', content)
if products_count_match:
    print(f'   Debug info: {products_count_match.group(1)} products')

print("\n" + "=" * 70)
