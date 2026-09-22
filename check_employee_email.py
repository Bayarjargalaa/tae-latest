"""Test if email exists in OpenDataEmployee"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataEmployee

# Search for the email
email = 'ochko.buya@gmail.com'

print(f"Searching for: {email}")
print("-" * 60)

# Case-insensitive search
employees = OpenDataEmployee.objects.filter(email__iexact=email)
print(f"\nExact match (case-insensitive): {employees.count()} found")

if employees.exists():
    for emp in employees:
        print(f"  Found: {emp.name} - {emp.email}")
else:
    print("  ❌ Not found")

# Search for similar emails (partial match)
print(f"\nSearching for similar emails containing 'ochko' or 'buya':")
similar = OpenDataEmployee.objects.filter(
    email__icontains='ochko'
) | OpenDataEmployee.objects.filter(
    email__icontains='buya'
)

print(f"Found {similar.count()} similar emails:")
for emp in similar[:10]:
    print(f"  - {emp.name}: {emp.email}")

# Show all employees with email
print(f"\n\nTotal employees with email: {OpenDataEmployee.objects.exclude(email__isnull=True).exclude(email='').count()}")
print("\nFirst 10 employee emails:")
for emp in OpenDataEmployee.objects.exclude(email__isnull=True).exclude(email='')[:10]:
    print(f"  - {emp.name}: {emp.email}")
