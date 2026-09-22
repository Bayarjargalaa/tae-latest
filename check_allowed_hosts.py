import os
import django

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.conf import settings

print("=" * 60)
print("ALLOWED_HOSTS шалгалт")
print("=" * 60)
print(f"\nALLOWED_HOSTS: {settings.ALLOWED_HOSTS}")
print(f"\nДэлгэрэнгүй:")
for i, host in enumerate(settings.ALLOWED_HOSTS, 1):
    print(f"  {i}. '{host}'")

print("\n" + "=" * 60)
print("www.tae.mn байгаа эсэх:", 'www.tae.mn' in settings.ALLOWED_HOSTS)
print("tae.mn байгаа эсэх:", 'tae.mn' in settings.ALLOWED_HOSTS)
print("=" * 60)
