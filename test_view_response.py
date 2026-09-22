import os
import django
from django.test import RequestFactory

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from shop.views import sales_report
from django.contrib.auth import get_user_model

User = get_user_model()

# Staff user үүсгэх (эсвэл авах)
try:
    user = User.objects.get(username='admin')
except User.DoesNotExist:
    user = User.objects.create_user(username='admin', is_staff=True)

# Request factory үүсгэх
factory = RequestFactory()

print("=" * 60)
print("TEST 1: Анхны ачаалалт (default summary tab)")
print("=" * 60)

request = factory.get('/dashboard/sales-report/')
request.user = user

response = sales_report(request)
content = response.content.decode('utf-8')

print(f'Status: {response.status_code}')
print(f'Content length: {len(content):,} bytes')

# HTML content шалгах
if 'active_tab' in content:
    print('✓ HTML-д active_tab гэсэн үг байна')

if 'Нэгтгэл' in content:
    print('✓ Summary tab харагдаж байна')

if 'product_sales' in content:
    print('⚠️ HTML-д product_sales variable байна (template debug?)')

print("\n" + "=" * 60)
print("TEST 2: by_product tab")
print("=" * 60)

request2 = factory.get('/dashboard/sales-report/?tab=by_product')
request2.user = user

response2 = sales_report(request2)
content2 = response2.content.decode('utf-8')

print(f'Status: {response2.status_code}')
print(f'Content length: {len(content2):,} bytes')

# Table rows тоолох
import re
tbody_rows = len(re.findall(r'<tr class="hover:bg-gray-50">', content2))
print(f'Table rows: {tbody_rows}')

# Empty message байгаа эсэхийг шалгах
if 'Сонгосон шүүлтээр өгөгдөл олдсонгүй' in content2:
    print('\n❌ HTML-д "өгөгдөл олдсонгүй" гэсэн мессеж байна!')
    print('Энэ нь product_sales хоосон эсвэл context-д байхгүй байна гэсэн үг')
elif 'Барааны нэр' in content2 and tbody_rows > 0:
    print(f'\n✅ HTML-д {tbody_rows} мөр table data байна - table зөв ачаалагдсан')
    
    # Эхний мөрийн өгөгдөл авах
    first_row_match = re.search(r'<tr class="hover:bg-gray-50">.*?<td class="px-6 py-4 text-sm text-gray-900">(.*?)</td>', content2, re.DOTALL)
    if first_row_match:
        print(f'  Эхний мөр: {first_row_match.group(1)[:50]}')
else:
    print(f'\n⚠️ Table header байна ({tbody_rows} rows found)')
    if tbody_rows == 0:
        print('❌ Table rows ХООСОН - өгөгдөл байхгүй!')
