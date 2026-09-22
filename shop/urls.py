"""
Shop app URLs
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

app_name = 'shop'

urlpatterns = [
    path('', views.home, name='home'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/sales-report/', views.sales_report, name='sales_report'),
    path('dashboard/purchase-report/', views.purchase_report, name='purchase_report'),
    path('dashboard/delivery-report/', views.delivery_report, name='delivery_report'),
    path('dashboard/expense-report/', views.expense_report, name='expense_report'),
    path('dashboard/expense-report-by-year/', views.expense_report_by_year, name='expense_report_by_year'),
    path('dashboard/expense-transaction-detail/', views.expense_transaction_detail, name='expense_transaction_detail'),
    path('dashboard/inventory/', views.inventory_report, name='inventory_report'),
    path('dashboard/item-prices/', views.item_prices, name='item_prices'),
    path('dashboard/item-prices/export/', views.item_prices_export, name='item_prices_export'),
    path('dashboard/meals/', views.meal_list, name='meal_list'),
    path('dashboard/meals/new/', views.meal_edit, name='meal_create'),
    path('dashboard/meals/<int:pk>/edit/', views.meal_edit, name='meal_edit'),
    path('dashboard/meals/<int:pk>/delete/', views.meal_delete, name='meal_delete'),
    path('dashboard/meals/cycle-settings/', views.meal_cycle_settings_update, name='meal_cycle_settings_update'),
    path('dashboard/meals/material-calc/', views.meal_material_calc, name='meal_material_calc'),
    path('dashboard/meal-attendance/', views.meal_attendance_list, name='meal_attendance_list'),
    path('dashboard/meal-attendance/summary/', views.meal_attendance_summary, name='meal_attendance_summary'),
    path('dashboard/meal-attendance/new/', views.meal_attendance_form, name='meal_attendance_create'),
    path('dashboard/meal-attendance/<int:pk>/edit/', views.meal_attendance_form, name='meal_attendance_edit'),
    path('dashboard/meal-attendance/<int:pk>/delete/', views.meal_attendance_delete, name='meal_attendance_delete'),
    path('dashboard/hr/attendance/', views.attendance_calc, name='attendance_calc'),
    path('dashboard/hr/attendance/sync/', views.attendance_sync, name='attendance_sync'),
    path('dashboard/hr/attendance/sync-merchandiser/', views.attendance_sync_merchandiser, name='attendance_sync_merchandiser'),
    path('dashboard/hr/attendance/save/', views.attendance_save, name='attendance_save'),
    path('dashboard/hr/attendance/position-settings/', views.attendance_position_settings, name='attendance_position_settings'),
    path('dashboard/hr/employee-fingerprint/', views.employee_fingerprint, name='employee_fingerprint'),
    path('profile/', views.profile, name='profile'),
    path('settings/menu-permissions/', views.menu_permission_config, name='menu_permission_config'),
    path('api/ai-chat/', views.ai_chat_message, name='ai_chat_message'),
    path('api/product-stock/', views.product_stock_lookup, name='product_stock_lookup'),
    path('products/', views.product_list, name='products'),
    path('products/<str:pk>/', views.product_detail, name='product_detail'),
    path('products/<str:pk>/edit/', views.product_edit, name='product_edit'),
    
    # Auth
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='shop/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    
    # Password Reset
    path('password-reset/', 
         auth_views.PasswordResetView.as_view(
             template_name='shop/password_reset.html',
             email_template_name='shop/password_reset_email.txt',
             html_email_template_name='shop/password_reset_email.html',
             subject_template_name='shop/password_reset_subject.txt',
             success_url='/password-reset/done/'
         ), 
         name='password_reset'),
    path('password-reset/done/', 
         auth_views.PasswordResetDoneView.as_view(template_name='shop/password_reset_done.html'), 
         name='password_reset_done'),
    path('password-reset-confirm/<uidb64>/<token>/', 
         auth_views.PasswordResetConfirmView.as_view(
             template_name='shop/password_reset_confirm.html',
             success_url='/password-reset-complete/'
         ), 
         name='password_reset_confirm'),
    path('password-reset-complete/', 
         auth_views.PasswordResetCompleteView.as_view(template_name='shop/password_reset_complete.html'), 
         name='password_reset_complete'),
]

