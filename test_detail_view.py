"""
Test expense transaction detail view directly
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import RequestFactory
from shop.views import expense_transaction_detail
from django.contrib.auth import get_user_model

User = get_user_model()

# Create request factory
factory = RequestFactory()

# Test URL with parameters
url = '/dashboard/expense-transaction-detail/?year=2024&month=1&type=refund'

print(f"\n{'='*60}")
print(f"Testing view: {url}")
print(f"{'='*60}\n")

# Create fake request
request = factory.get(url)

# Get or create staff user
try:
    user = User.objects.filter(is_staff=True).first()
    if not user:
        print("WARNING: No staff user found. Creating test user...")
        user = User.objects.create_user(
            username='test_staff',
            password='test123',
            is_staff=True
        )
    request.user = user
    print(f"User: {user.username} (is_staff={user.is_staff})\n")
    
    # Call view
    response = expense_transaction_detail(request)
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response type: {type(response)}")
    
    if hasattr(response, 'context_data'):
        print(f"\nContext data:")
        for key, value in response.context_data.items():
            if key == 'transactions':
                print(f"  {key}: {len(value)} items")
            else:
                print(f"  {key}: {value}")
    
    # Check content
    content = response.content.decode('utf-8')
    print(f"\nContent length: {len(content)} bytes")
    
    # Check for key elements
    if 'Гүйлгээ олдсонгүй' in content:
        print("⚠️  WARNING: 'Гүйлгээ олдсонгүй' found in content!")
    
    if '<tr class="hover:bg-gray-50">' in content or '<td class="px-4 py-3 text-sm text-gray-600">' in content:
        print("✅ Transaction rows found in HTML")
    
    # Count table rows
    row_count = content.count('<tr class="hover:bg-gray-50">')
    print(f"✅ Transaction rows in HTML: {row_count}")
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print(f"\n{'='*60}\n")
