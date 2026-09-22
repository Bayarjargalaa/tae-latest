from django.contrib import admin
from .models import (
    ProductExtension, UserProfile, MenuPermission, MenuGroupAssignment, Meal, MealIngredient,
    MealNumberAssignment, MealCycleSettings, MealAttendance, MealAttendanceName,
)


@admin.register(MenuPermission)
class MenuPermissionAdmin(admin.ModelAdmin):
    list_display = ['position_name', 'menu_key', 'is_visible']
    list_filter = ['is_visible', 'position_name']
    search_fields = ['position_name', 'menu_key']


@admin.register(MenuGroupAssignment)
class MenuGroupAssignmentAdmin(admin.ModelAdmin):
    list_display = ['menu_key', 'group_key']
    search_fields = ['menu_key', 'group_key']


class MealIngredientInline(admin.TabularInline):
    model = MealIngredient
    extra = 1


class MealNumberInline(admin.TabularInline):
    model = MealNumberAssignment
    extra = 1


@admin.register(Meal)
class MealAdmin(admin.ModelAdmin):
    list_display = ['meal_type', 'numbers_display', 'name', 'created_at']
    list_filter = ['meal_type']
    search_fields = ['name']
    inlines = [MealNumberInline, MealIngredientInline]

    def numbers_display(self, obj):
        return obj.number_display or '-'
    numbers_display.short_description = 'Дугаарууд'


@admin.register(MealCycleSettings)
class MealCycleSettingsAdmin(admin.ModelAdmin):
    list_display = ['anchor_date']

    def has_add_permission(self, request):
        # Ганцхан мөр байх ёстой (singleton тохиргоо)
        return not MealCycleSettings.objects.exists()


class MealAttendanceNameInline(admin.TabularInline):
    model = MealAttendanceName
    extra = 1


@admin.register(MealAttendance)
class MealAttendanceAdmin(admin.ModelAdmin):
    list_display = ['date', 'menu_number', 'name_count']
    inlines = [MealAttendanceNameInline]

    def name_count(self, obj):
        return obj.names.count()
    name_count.short_description = 'Хүний тоо'


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'phone', 'is_employee', 'employee_email', 'distributor_id']
    list_filter = ['is_employee']
    search_fields = ['user__username', 'user__email', 'phone', 'employee_email', 'distributor_id']
    
    fieldsets = (
        ('Хэрэглэгч', {
            'fields': ('user',)
        }),
        ('Холбоо барих', {
            'fields': ('phone',)
        }),
        ('Ажилтны мэдээлэл', {
            'fields': ('is_employee', 'employee_email', 'distributor_id')
        }),
    )


@admin.register(ProductExtension)
class ProductExtensionAdmin(admin.ModelAdmin):
    list_display = ['item_id', 'name_mn', 'country_of_origin', 'qty_per_box', 'supplier', 'has_image']
    list_filter = ['country_of_origin', 'supplier']
    search_fields = ['item_id', 'name_mn', 'supplier']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Холбоос', {
            'fields': ('item_id',)
        }),
        ('Үндсэн мэдээлэл', {
            'fields': ('name_mn', 'country_of_origin', 'qty_per_box', 'supplier')
        }),
        ('Зургууд', {
            'fields': ('image_main', 'image_2', 'image_3')
        }),
        ('Огноо', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def has_image(self, obj):
        return bool(obj.image_main)
    has_image.boolean = True
    has_image.short_description = 'Зураgtай'

