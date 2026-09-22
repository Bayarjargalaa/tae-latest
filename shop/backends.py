"""
Custom authentication backend - имэйлээр нэвтрэх
OpenDataEmployee-тай автомат синхрчлох
"""
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model

User = get_user_model()


class EmailBackend(ModelBackend):
    """
    Имэйлээр нэвтрэх + OpenDataEmployee-тай автомат синхрчлох
    
    Нэвтрэх бүрт:
    1. OpenDataEmployee-д байгаа эсэхийг шалгана
    2. Байвал is_staff=True, Profile автоматаар үүснэ/шинэчлэгдэнэ
    3. Ажилтны эрх автоматаар олгогдоно
    """
    
    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or not password:
            return None
        
        try:
            # Имэйлээр хайх (case-insensitive)
            user = User.objects.get(email__iexact=username)
        except User.DoesNotExist:
            return None
        
        # Нууц үг шалгах
        if user.check_password(password) and self.user_can_authenticate(user):
            # Нэвтрэх бүрт ажилтны статусыг шалгаж шинэчлэх
            self._sync_employee_status(user)
            return user
        
        return None
    
    def _sync_employee_status(self, user):
        """
        User-ийг OpenDataEmployee-тай синхрчлох
        Ажилтан бол автоматаар is_staff=True, Profile үүсгэнэ
        """
        from datamigration.models import OpenDataEmployee
        from shop.models import UserProfile
        
        # OpenDataEmployee-д байгаа эсэхийг шалгах (first() ашиглана - давхардсан имэйл байж болно)
        employee = OpenDataEmployee.objects.filter(email__iexact=user.email).first()
        
        if employee:
            
            # Staff эрх шинэчлэх
            updated = False
            if not user.is_staff:
                user.is_staff = True
                updated = True
            
            # Нэр шинэчлэх (хоосон бол)
            if not user.first_name and employee.name:
                user.first_name = employee.name
                updated = True
            
            if updated:
                user.save()
            
            # Profile үүсгэх/шинэчлэх
            profile, created = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    'phone': employee.mobilenumber or '',
                    'is_employee': True,
                    'employee_email': employee.email
                }
            )
            
            # Profile шинэчлэх (үүссэн биш бол)
            if not created:
                profile_updated = False
                if not profile.is_employee:
                    profile.is_employee = True
                    profile_updated = True
                
                if not profile.employee_email:
                    profile.employee_email = employee.email
                    profile_updated = True
                
                if not profile.phone and employee.mobilenumber:
                    profile.phone = employee.mobilenumber
                    profile_updated = True
                
                if profile_updated:
                    profile.save()
        else:
            # Ажилтан биш - staff эрхийг хасах
            if user.is_staff and not user.is_superuser:
                # Superuser биш, гэхдээ ажилтан бас биш бол эрх хасах
                user.is_staff = False
                user.save()
