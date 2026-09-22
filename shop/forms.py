"""
Хэрэглэгчийн бүртгэлийн forms
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from datamigration.models import OpenDataEmployee, OpenDataItem
from shop.models import (
    UserProfile, Meal, MealIngredient, MealNumberAssignment,
    MealAttendance, MealAttendanceName, MealAttendanceIngredient,
)


class CustomUserCreationForm(UserCreationForm):
    """Өргөтгөсөн бүртгэлийн form - зөвхөн имэйлээр нэвтрэх"""
    email = forms.EmailField(required=True, label='Имэйл')
    phone = forms.CharField(max_length=20, required=True, label='Утас')
    first_name = forms.CharField(max_length=150, required=True, label='Нэр')
    
    class Meta:
        model = User
        fields = ('email', 'first_name', 'phone', 'password1', 'password2')
    
    def clean_email(self):
        """Имэйл давхардсан эсэхийг шалгах"""
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Энэ имэйл аль хэдийн бүртгэгдсэн байна.')
        return email
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['email']  # Username = имэйл
        user.first_name = self.cleaned_data['first_name']
        
        # OpenDataEmployee имэйл шалгах
        try:
            employee = OpenDataEmployee.objects.get(email__iexact=user.email)
            user.is_staff = True  # Ажилтан бол staff эрх
        except OpenDataEmployee.DoesNotExist:
            user.is_staff = False
        
        if commit:
            user.save()
            
            # Profile үүсгэх
            profile = UserProfile.objects.create(
                user=user,
                phone=self.cleaned_data['phone']
            )
            
            # Ажилтан бол холбох
            try:
                employee = OpenDataEmployee.objects.get(email__iexact=user.email)
                profile.is_employee = True
                profile.employee_email = employee.email
                profile.save()
            except OpenDataEmployee.DoesNotExist:
                pass
        
        return user


class MealForm(forms.ModelForm):
    """Хоол бүртгэх / засах"""
    class Meta:
        model = Meal
        fields = ['meal_type', 'name', 'description']
        widgets = {
            'meal_type': forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-lg px-4 py-2'}),
            'name': forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-lg px-4 py-2'}),
            'description': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded-lg px-4 py-2', 'rows': 3}),
        }


class MealNumberForm(forms.ModelForm):
    """Хоолыг холбох дугаар (1-10) - нэг хоол олон дугаартай байж болно"""
    number = forms.TypedChoiceField(
        label='Дугаар', coerce=int, empty_value=None,
        choices=[('', '---')] + [(n, n) for n in range(1, 11)],
        widget=forms.Select(attrs={'class': 'w-24 border border-gray-300 rounded-lg px-3 py-1.5'}),
    )

    class Meta:
        model = MealNumberAssignment
        fields = ['number']


MealNumberFormSet = forms.inlineformset_factory(
    Meal, MealNumberAssignment,
    form=MealNumberForm,
    extra=1, can_delete=True,
)


class IngredientItemChoiceField(forms.ModelChoiceField):
    """OpenDataItem-ийг 'код - нэр' хэлбэрээр select-д харуулж, цэвэр id (str) буцаана.

    MealIngredient.item_id нь plain CharField (OpenDataItem нь FK хийх боломжгүй
    view) тул select-ээс сонгосон OpenDataItem-ийг instance биш, зөвхөн pk-аар нь хадгална.
    """
    def label_from_instance(self, obj):
        return f"{obj.id} - {obj.name}"

    def clean(self, value):
        obj = super().clean(value)
        return obj.pk if obj else obj


class MealIngredientForm(forms.ModelForm):
    """Хоолны орц - зөвхөн '1502'-р эхэлсэн кодтой (материал) бараанаас сонгоно"""
    item_id = IngredientItemChoiceField(
        queryset=OpenDataItem.objects.filter(id__istartswith='1502').order_by('name'),
        label='Орц (бараа)',
        widget=forms.Select(attrs={'class': 'w-full border border-gray-300 rounded-lg px-3 py-1.5'}),
    )

    class Meta:
        model = MealIngredient
        fields = ['item_id', 'quantity', 'unit']
        widgets = {
            'quantity': forms.NumberInput(attrs={'class': 'w-24 border border-gray-300 rounded-lg px-3 py-1.5', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'w-24 border border-gray-300 rounded-lg px-3 py-1.5', 'placeholder': 'кг, ш...'}),
        }



MealIngredientFormSet = forms.inlineformset_factory(
    Meal, MealIngredient,
    form=MealIngredientForm,
    extra=1, can_delete=True,
)


class MealAttendanceForm(forms.ModelForm):
    """Хоол идэх нэрсийн бүртгэлийн огноо"""
    class Meta:
        model = MealAttendance
        fields = ['date', 'change_comment']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full border border-gray-300 rounded-lg px-4 py-2'}),
            'change_comment': forms.Textarea(attrs={'class': 'w-full border border-gray-300 rounded-lg px-4 py-2', 'rows': 2, 'placeholder': 'Орцонд өдрийн хазайлт орсон бол шалтгааныг энд бичнэ үү'}),
        }


class MealAttendanceIngredientForm(forms.ModelForm):
    """Тухайн өдрийн бодит орц - зөвхөн '1502'-р эхэлсэн кодтой (материал) бараанаас сонгоно.

    meal талбарыг далдаар (HiddenInput) дамжуулна - хэрэглэгч сонгохгүй, JS-ээр аль
    хоолны картад мөр нэмэгдэж буйгаас нь автоматаар тохируулна.
    """
    item_id = IngredientItemChoiceField(
        queryset=OpenDataItem.objects.filter(id__istartswith='1502').order_by('name'),
        label='Орц (бараа)',
        widget=forms.Select(attrs={'class': 'ingredient-item-select w-full border border-gray-300 rounded-lg px-3 py-1.5'}),
    )

    class Meta:
        model = MealAttendanceIngredient
        fields = ['meal', 'item_id', 'quantity', 'unit']
        widgets = {
            'meal': forms.HiddenInput(),
            'quantity': forms.NumberInput(attrs={'class': 'ingredient-qty-input w-20 border border-gray-300 rounded-lg px-2 py-1.5', 'step': '0.001'}),
            'unit': forms.TextInput(attrs={'class': 'w-16 border border-gray-300 rounded-lg px-2 py-1.5', 'placeholder': 'кг'}),
        }


class MealAttendanceNameForm(forms.ModelForm):
    """Хоол идэх нэг хүний нэр"""
    class Meta:
        model = MealAttendanceName
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'attendee-name-input w-full border border-gray-300 rounded-lg px-3 py-1.5', 'placeholder': 'Ажилтны нэр'}),
        }


MealAttendanceNameFormSet = forms.inlineformset_factory(
    MealAttendance, MealAttendanceName,
    form=MealAttendanceNameForm,
    extra=1, can_delete=True,
)

