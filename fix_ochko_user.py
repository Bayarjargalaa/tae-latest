"""Fix ochko.buya@gmail.com user - add staff privileges and profile"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User
from shop.models import UserProfile
from datamigration.models import OpenDataEmployee

email = 'ochko.buya@gmail.com'

print(f"Fixing user: {email}")
print("-" * 60)

try:
    # Get user
    user = User.objects.get(email__iexact=email)
    print(f"Found user: {user.username}")
    
    # Get employee info
    employee = OpenDataEmployee.objects.get(email__iexact=email)
    print(f"Found employee: {employee.name}")
    
    # Update user
    print("\nUpdating user:")
    user.is_staff = True
    user.first_name = employee.name or "Очгэрэл"
    user.save()
    print(f"  ✅ Set is_staff=True")
    print(f"  ✅ Set first_name={user.first_name}")
    
    # Create or update profile
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'phone': employee.mobilenumber or '',
            'is_employee': True,
            'employee_email': employee.email
        }
    )
    
    if created:
        print(f"\n  ✅ Created UserProfile")
    else:
        profile.is_employee = True
        profile.employee_email = employee.email
        if employee.mobilenumber:
            profile.phone = employee.mobilenumber
        profile.save()
        print(f"\n  ✅ Updated UserProfile")
    
    print(f"\n{'='*60}")
    print(f"SUCCESS! {email} is now:")
    print(f"  - Staff member (can access dashboard)")
    print(f"  - Has profile linked to employee data")
    print(f"  - Name: {user.first_name}")
    print(f"  - Phone: {profile.phone}")
    print(f"{'='*60}\n")
    
except User.DoesNotExist:
    print(f"❌ User not found")
except OpenDataEmployee.DoesNotExist:
    print(f"❌ Employee not found")
except Exception as e:
    print(f"❌ Error: {e}")
