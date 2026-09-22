"""
Бүх хэрэглэгчдийг OpenDataEmployee-тай синхрчлох management command

Ашиглах:
    python manage.py sync_employee_users
    
Юу хийх вэ:
    1. Бүх User-үүдийг шалгана
    2. OpenDataEmployee-д байгаа имэйлтэй бол:
       - is_staff=True болгоно
       - Profile үүсгэнэ/шинэчилнэ
       - Ажилтны мэдээллийг синхрчлоно
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datamigration.models import OpenDataEmployee
from shop.models import UserProfile


class Command(BaseCommand):
    help = 'Бүх хэрэглэгчдийг OpenDataEmployee-тай синхрчлох'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Өөрчлөлтийг хийхгүй, зөвхөн харуулах',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('Syncing Users with OpenDataEmployee'))
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE - No changes will be made'))
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))

        # Статистик
        total_users = User.objects.count()
        total_employees = OpenDataEmployee.objects.exclude(email__isnull=True).exclude(email='').count()
        
        self.stdout.write(f'Total users in system: {total_users}')
        self.stdout.write(f'Total employees with email: {total_employees}\n')

        staff_granted = 0
        profile_created = 0
        profile_updated = 0
        already_synced = 0

        # Бүх хэрэглэгчдийг шалгах
        for user in User.objects.all():
            # OpenDataEmployee-с хайх (first() ашиглана - давхардсан имэйл байж болно)
            employee = OpenDataEmployee.objects.filter(email__iexact=user.email).first()
            
            if not employee:
                continue  # Ажилтан биш
            
            # Шинэчлэх шаардлагатай эсэхийг шалгах
            needs_update = False
            changes = []
            
            # Staff эрх шалгах
            if not user.is_staff:
                needs_update = True
                changes.append('Grant staff access')
                if not dry_run:
                    user.is_staff = True
            
            # Нэр шалгах
            if not user.first_name and employee.name:
                needs_update = True
                changes.append(f'Set name: {employee.name}')
                if not dry_run:
                    user.first_name = employee.name
            
            if needs_update and not dry_run:
                user.save()
                staff_granted += 1
            
            # Profile шалгах
            try:
                profile = UserProfile.objects.get(user=user)
                
                # Profile шинэчлэх шаардлагатай эсэх
                profile_needs_update = False
                
                if not profile.is_employee:
                    profile_needs_update = True
                    changes.append('Mark as employee')
                    if not dry_run:
                        profile.is_employee = True
                
                if not profile.employee_email:
                    profile_needs_update = True
                    changes.append('Link employee email')
                    if not dry_run:
                        profile.employee_email = employee.email
                
                if not profile.phone and employee.mobilenumber:
                    profile_needs_update = True
                    changes.append(f'Add phone: {employee.mobilenumber}')
                    if not dry_run:
                        profile.phone = employee.mobilenumber
                
                if profile_needs_update and not dry_run:
                    profile.save()
                    profile_updated += 1
                
                if not needs_update and not profile_needs_update:
                    already_synced += 1
                
            except UserProfile.DoesNotExist:
                changes.append('Create profile')
                if not dry_run:
                    UserProfile.objects.create(
                        user=user,
                        phone=employee.mobilenumber or '',
                        is_employee=True,
                        employee_email=employee.email
                    )
                    profile_created += 1
            
            # Өөрчлөлт байвал харуулах
            if changes:
                self.stdout.write(
                    self.style.WARNING(f'  {user.email}:') + 
                    f' {", ".join(changes)}'
                )

        # Дүгнэлт
        self.stdout.write(self.style.SUCCESS('\n' + '='*60))
        self.stdout.write(self.style.SUCCESS('Summary:'))
        self.stdout.write(self.style.SUCCESS('='*60))
        self.stdout.write(f'  Staff access granted: {staff_granted}')
        self.stdout.write(f'  Profiles created: {profile_created}')
        self.stdout.write(f'  Profiles updated: {profile_updated}')
        self.stdout.write(f'  Already synced: {already_synced}')
        
        total_synced = staff_granted + profile_created + profile_updated
        self.stdout.write(self.style.SUCCESS(f'\n  Total changes: {total_synced}'))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN - No actual changes were made'))
            self.stdout.write('Run without --dry-run to apply changes')
        
        self.stdout.write(self.style.SUCCESS('='*60 + '\n'))
