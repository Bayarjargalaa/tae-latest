"""
Test expense account detail view
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from shop.views import expense_transaction_detail
from django.contrib.auth import get_user_model

User = get_user_model()

factory = RequestFactory()

# Test зардлын данс: 700101 (Цалингийн зардал)
url = '/dashboard/expense-transaction-detail/?year=2024&month=1&type=expense&account_id=700101'

print(f"\n{'='*80}")
print(f"Testing: {url}")
print(f"{'='*80}\n")

request = factory.get(url)
user = User.objects.filter(is_staff=True).first()
request.user = user

response = expense_transaction_detail(request)

print(f"\nResponse status: {response.status_code}")

content = response.content.decode('utf-8')
row_count = content.count('<tr class="hover:bg-gray-50">')
print(f"Transaction rows: {row_count}")

# Check for key phrases
if '310201' in content or 'Цалингийн өглөг' in content:
    print("✅ FOUND: Цалингийн өглөг (correct credit account)")
else:
    print("❌ NOT FOUND: Цалингийн өглөг")

if '100102' in content or 'Касс' in content:
    print("✅ FOUND: Касс дахь мөнгө (correct)")
else:
    print("⚠️  NOT FOUND: Касс")

print(f"\n{'='*80}\n")
