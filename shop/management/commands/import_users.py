"""
users_backup.json-оос хэрэглэгчдийг импортлох management command
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datamigration.models import OpenDataEmployee
from shop.models import UserProfile
import json


class Command(BaseCommand):
    help = 'users_backup.json-оос хэрэглэгчдийг импортлох'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='users_backup.json',
            help='JSON файлын зам'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            self.stdout.write(self.style.ERROR(f'File not found: {file_path}'))
            return
        
        imported = 0
        skipped = 0
        updated_staff = 0
        
        for item in data:
            if item['model'] != 'auth.user':
                continue
            
            fields = item['fields']
            username = fields['username']
            email = fields['email']
            
            # User байгаа эсэх шалгах
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    'email': email,
                    'password': fields['password'],
                    'first_name': fields.get('first_name', ''),
                    'last_name': fields.get('last_name', ''),
                    'is_staff': fields.get('is_staff', False),
                    'is_active': fields.get('is_active', True),
                    'is_superuser': fields.get('is_superuser', False),
                    'date_joined': fields.get('date_joined'),
                    'last_login': fields.get('last_login'),
                }
            )
            
            if created:
                imported += 1
                self.stdout.write(f'  Created: {username} ({email})')
                
                # OpenDataEmployee-р staff эрх шалгах
                if email:
                    try:
                        employee = OpenDataEmployee.objects.get(email__iexact=email)
                        user.is_staff = True
                        user.save()
                        updated_staff += 1
                        self.stdout.write(self.style.SUCCESS(f'    -> Staff access granted (found in OpenDataEmployee)'))
                        
                        # UserProfile үүсгэх
                        UserProfile.objects.get_or_create(
                            user=user,
                            defaults={
                                'is_employee': True,
                                'employee_email': employee.email
                            }
                        )
                    except OpenDataEmployee.DoesNotExist:
                        # Profile үүсгэх (ажилтан биш)
                        UserProfile.objects.get_or_create(user=user)
                else:
                    # Profile үүсгэх
                    UserProfile.objects.get_or_create(user=user)
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(f'  Skipped: {username} (already exists)'))
        
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(f'Total users: {len([i for i in data if i["model"] == "auth.user"])}')
        self.stdout.write(f'Imported: {imported}')
        self.stdout.write(f'Skipped: {skipped}')
        self.stdout.write(f'Staff access granted: {updated_staff}')
        self.stdout.write('='*70)
