import os
import django
from django.test import RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from shop.views import sales_report
from django.contrib.auth import get_user_model

User = get_user_model()

# Staff user
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_user(username='admin', is_staff=True)

factory = RequestFactory()

print("=" * 70)
print("ТЕСТ: Хоосон болон 'None' параметрүүд")
print("=" * 70)

# ТЕСТ 1: product=None&customer=None (literal "None" string)
print("\n1. product=None&customer=None параметр:")
request1 = factory.get('/dashboard/sales-report/?tab=by_product&product=None&customer=None')
request1.user = user

response1 = sales_report(request1)
content1 = response1.content.decode('utf-8')

print(f'   Status: {response1.status_code}')

import re
tbody_rows1 = len(re.findall(r'<tr class="hover:bg-gray-50">', content1))
print(f'   Table rows: {tbody_rows1}')

if 'өгөгдөл олдсонгүй' in content1:
    print('   ❌ "өгөгдөл олдсонгүй" мессеж байна')
else:
    print(f'   ✅ Өгөгдөл зөв гарсан ({tbody_rows1} мөр)')

# ТЕСТ 2: date_from=&date_to= (хоосон string)
print("\n2. date_from=&date_to= (хоосон огноо):")
request2 = factory.get('/dashboard/sales-report/?tab=by_product&date_from=&date_to=')
request2.user = user

response2 = sales_report(request2)
content2 = response2.content.decode('utf-8')

print(f'   Status: {response2.status_code}')

tbody_rows2 = len(re.findall(r'<tr class="hover:bg-gray-50">', content2))
print(f'   Table rows: {tbody_rows2}')

if 'өгөгдөл олдсонгүй' in content2:
    print('   ❌ "өгөгдөл олдсонгүй" мессеж байна')
else:
    print(f'   ✅ Өгөгдөл зөв гарсан ({tbody_rows2} мөр)')

# ТЕСТ 3: Бодит огноо + product=None
print("\n3. Бодит огноо + product=None:")
request3 = factory.get('/dashboard/sales-report/?tab=by_product&date_from=2026-02-01&date_to=2026-02-12&product=None&customer=None')
request3.user = user

response3 = sales_report(request3)
content3 = response3.content.decode('utf-8')

print(f'   Status: {response3.status_code}')

tbody_rows3 = len(re.findall(r'<tr class="hover:bg-gray-50">', content3))
print(f'   Table rows: {tbody_rows3}')

if 'өгөгдөл олдсонгүй' in content3:
    print('   ❌ "өгөгдөл олдсонгүй" мессеж байна')
else:
    print(f'   ✅ Өгөгдөл зөв гарсан ({tbody_rows3} мөр)')

print("\n" + "=" * 70)
print("ДҮГНЭЛТ:")
print("=" * 70)

if tbody_rows1 > 0 and tbody_rows2 > 0 and tbody_rows3 > 0:
    print("✅ БҮХ тест амжилттай! 'None' болон хоосон параметрүүд зөв цэвэрлэгдлээ.")
else:
    print("❌ Зарим тест бүтэлгүйтсэн:")
    if tbody_rows1 == 0:
        print("   - product=None параметр асуудал үүсгэж байна")
    if tbody_rows2 == 0:
        print("   - Хоосон огноо параметр асуудал үүсгэж байна")
    if tbody_rows3 == 0:
        print("   - Бодит огноо + None параметр асуудал үүсгэж байна")
