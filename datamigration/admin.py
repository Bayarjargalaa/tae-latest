"""
DataMigration admin үүсэх
"""
from django.contrib import admin
from .models import (
    OpenDataItem,
    OpenDataCustomer,
    OpenDataEmployee,
    OpenDataSale,
    OpenDataPurchase,
    OpenDataInventory
)


@admin.register(OpenDataItem)
class OpenDataItemAdmin(admin.ModelAdmin):
    list_display = ('pkid', 'name', 'barcode', 'brandname', 'saleprice', 'standardunitcost', 'activestatus')
    list_filter = ('activestatus', 'brandname', 'itemcategoryname')
    search_fields = ('name', 'barcode', 'brandname')
    list_per_page = 50


@admin.register(OpenDataCustomer)
class OpenDataCustomerAdmin(admin.ModelAdmin):
    list_display = ('pkid', 'name', 'registrynumber', 'customerlevel', 'regionname', 'activestatus', 'createddate')
    list_filter = ('activestatus', 'customerlevel', 'regionname')
    search_fields = ('name', 'registrynumber')
    list_per_page = 50


@admin.register(OpenDataEmployee)
class OpenDataEmployeeAdmin(admin.ModelAdmin):
    list_display = ('pkid', 'name', 'registrynumber', 'departmentname', 'positionname', 'hiredate', 'basesalary')
    list_filter = ('departmentname', 'positionname', 'isreclusion')
    search_fields = ('name', 'registrynumber', 'mobilenumber')
    list_per_page = 50


@admin.register(OpenDataSale)
class OpenDataSaleAdmin(admin.ModelAdmin):
    list_display = ('documentnumber', 'documentdate', 'customername', 'itemname', 'qty', 'price', 'payamount', 'createddate')
    list_filter = ('distributionchannelname', 'brandname')
    search_fields = ('documentnumber', 'customername', 'itemname', 'documentdate')
    date_hierarchy = 'createddate'  # documentdate одоо TextField учраас createddate ашиглана
    list_per_page = 50


@admin.register(OpenDataPurchase)
class OpenDataPurchaseAdmin(admin.ModelAdmin):
    list_display = ('documentnumber', 'documentdate', 'vendorname', 'itemname', 'qty', 'unitcost', 'amount', 'createddate')
    list_filter = ('documentdate', 'vendorname')
    search_fields = ('documentnumber', 'vendorname', 'itemname')
    date_hierarchy = 'documentdate'
    list_per_page = 50


@admin.register(OpenDataInventory)
class OpenDataInventoryAdmin(admin.ModelAdmin):
    list_display = ('documentdate', 'documenttype', 'warehousename', 'itemname', 'inqty', 'outqty', 'endqty', 'createddate')
    list_filter = ('documenttype', 'warehousename', 'brandname')
    search_fields = ('itemname', 'warehousename', 'documentdate')
    date_hierarchy = 'createddate'  # documentdate одоо TextField учраас createddate ашиглана
    list_per_page = 50
