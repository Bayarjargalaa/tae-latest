#!/usr/bin/env python
"""Check if user exists"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth.models import User

# Check for specific email
email = 'o.bayarjargal10@gmail.com'
user = User.objects.filter(email=email).first()

if user:
    print(f'\n✅ Found user:')
    print(f'   Email: {user.email}')
    print(f'   Username: {user.username}')
    print(f'   Name: {user.first_name} {user.last_name}')
    print(f'   Staff: {user.is_staff}')
    print(f'   Registered: {user.date_joined}')
else:
    print(f'\n❌ User with email "{email}" not found')
    print(f'\nTotal users in database: {User.objects.count()}')
    
    # Show first 10 users
    users = User.objects.all()[:10]
    if users:
        print('\nFirst 10 users:')
        for i, u in enumerate(users, 1):
            print(f'   {i}. {u.email or "(no email)"} - {u.username}')
