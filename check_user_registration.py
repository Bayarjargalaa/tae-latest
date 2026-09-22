"""Check if user already registered with this email"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from shop.models import UserProfile

email = 'ochko.buya@gmail.com'

print(f"Checking if {email} is already registered:")
print("-" * 60)

# Check User table
user = User.objects.filter(email__iexact=email).first()
if user:
    print(f"✅ User exists:")
    print(f"  Username: {user.username}")
    print(f"  Email: {user.email}")
    print(f"  First name: {user.first_name}")
    print(f"  Is staff: {user.is_staff}")
    print(f"  Is active: {user.is_active}")
    print(f"  Date joined: {user.date_joined}")
    
    # Check profile
    try:
        profile = UserProfile.objects.get(user=user)
        print(f"\n  Profile:")
        print(f"    Phone: {profile.phone}")
        print(f"    Is employee: {profile.is_employee}")
        print(f"    Employee email: {profile.employee_email}")
    except UserProfile.DoesNotExist:
        print(f"\n  ⚠️ No profile found")
else:
    print(f"❌ User not registered yet")
    print(f"\nThis email belongs to employee 'Очгэрэл //' in OpenDataEmployee")
    print(f"When registered, will automatically get staff privileges.")
