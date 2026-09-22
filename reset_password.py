#!/usr/bin/env python
"""Reset user password"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

# Email and new password
email = 'o.bayarjargal10@gmail.com'
new_password = 'TaeShop2026!'  # Temporary password

user = User.objects.filter(email=email).first()

if user:
    user.set_password(new_password)
    user.save()
    print(f'\n✅ Password updated successfully!')
    print(f'\n   Email: {email}')
    print(f'   New Password: {new_password}')
    print(f'\n⚠️  Please login and change this password immediately.')
else:
    print(f'\n❌ User with email "{email}" not found')
