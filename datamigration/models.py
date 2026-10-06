"""
MSSQL Views моделууд (PostgreSQL хүснэгтүүдээс автоматаар үүссэн)
"""
from django.db import models


class OpenDataItem(models.Model):
    """Бүтээгдэхүүний мэдээлэл (OpenDataItem view)"""
    id = models.TextField(db_column='Id', primary_key=True)
    pkid = models.BigIntegerField(db_column='PkId', blank=True, null=True)
    barcode = models.TextField(db_column='Barcode', blank=True, null=True)
    name = models.TextField(db_column='Name', blank=True, null=True)
    qtyinpackage = models.FloatField(db_column='QtyInPackage', blank=True, null=True)
    baseprice = models.FloatField(db_column='BasePrice', blank=True, null=True)
    saleprice = models.FloatField(db_column='SalePrice', blank=True, null=True)
    standardunitcost = models.FloatField(db_column='StandardUnitCost', blank=True, null=True)
    itemcategoryname = models.TextField(db_column='ItemCategoryName', blank=True, null=True)
    measurename = models.TextField(db_column='MeasureName', blank=True, null=True)
    manufacturername = models.TextField(db_column='ManufacturerName', blank=True, null=True)
    brandname = models.TextField(db_column='BrandName', blank=True, null=True)
    activestatus = models.TextField(db_column='ActiveStatus', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataItem'
        verbose_name = 'Бүтээгдэхүүн'
        verbose_name_plural = 'Бүтээгдэхүүнүүд'

    def __str__(self):
        return self.name or f"Item {self.pkid}"


class OpenDataItemPriceChannel(models.Model):
    """Үнийн жагсаалт/суваг (OpenDataItemPriceChannel view) - жиш: '001' = Үндсэн үнэ"""
    pkid = models.BigIntegerField(db_column='PkId', primary_key=True)
    code = models.TextField(db_column='Id', blank=True, null=True)
    name = models.TextField(db_column='Name', blank=True, null=True)
    parentpkid = models.TextField(db_column='ParentPkId', blank=True, null=True)
    copypkid = models.FloatField(db_column='CopyPkId', blank=True, null=True)
    factor = models.FloatField(db_column='Factor', blank=True, null=True)
    smartorderchannelid = models.TextField(db_column='SmartOrderChannelId', blank=True, null=True)
    notusediscount = models.TextField(db_column='NotUseDiscount', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataItemPriceChannel'
        verbose_name = 'Үнийн жагсаалт'
        verbose_name_plural = 'Үнийн жагсаалтууд'

    def __str__(self):
        return f"{self.code} - {self.name}"


class OpenDataItemPrice(models.Model):
    """Барааны үнийн түүх - огноо, суваг тус бүрээр (OpenDataItemPrice view).

    View-д цор ганц unique багана байхгүй тул itempkid-г primary key болгосон
    (зөвхөн filter/aggregate query-д ашиглана, .get(pk=...) ашиглахгүй).
    """
    itempkid = models.BigIntegerField(db_column='ItemPkId', primary_key=True)
    pricedate = models.DateField(db_column='PriceDate', blank=True, null=True)
    customerpkid = models.FloatField(db_column='CustomerPkId', blank=True, null=True)
    pricechannelpkid = models.BigIntegerField(db_column='PriceChannelPkId', blank=True, null=True)
    measurepkid = models.BigIntegerField(db_column='MeasurePkId', blank=True, null=True)
    purchaseprice = models.FloatField(db_column='PurchasePrice', blank=True, null=True)
    baseprice = models.FloatField(db_column='BasePrice', blank=True, null=True)
    discountpercent = models.FloatField(db_column='DiscountPercent', blank=True, null=True)
    price = models.FloatField(db_column='Price', blank=True, null=True)
    wholeprice = models.FloatField(db_column='WholePrice', blank=True, null=True)
    wholeqty = models.FloatField(db_column='WholeQty', blank=True, null=True)
    wholepriceactivestatus = models.TextField(db_column='WholePriceActiveStatus', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataItemPrice'
        verbose_name = 'Барааны үнэ'
        verbose_name_plural = 'Барааны үнийн түүх'

    def __str__(self):
        return f"{self.itempkid} - {self.pricechannelpkid} - {self.pricedate}"


class OpenDataCustomer(models.Model):
    """Харилцагчийн мэдээлэл (OpenDataCustomer view)"""
    id = models.TextField(db_column='Id', primary_key=True)
    pkid = models.BigIntegerField(db_column='PkId', blank=True, null=True)
    name = models.TextField(db_column='Name', blank=True, null=True)
    registrynumber = models.TextField(db_column='RegistryNumber', blank=True, null=True)
    distributionchannelname = models.TextField(db_column='DistributionChannelName', blank=True, null=True)
    customerlevel = models.TextField(db_column='CustomerLevel', blank=True, null=True)
    latitude = models.FloatField(db_column='Latitude', blank=True, null=True)
    longitude = models.FloatField(db_column='Longitude', blank=True, null=True)
    paymenttype = models.TextField(db_column='PaymentType', blank=True, null=True)
    regionname = models.TextField(db_column='RegionName', blank=True, null=True)
    loanlimit = models.FloatField(db_column='LoanLimit', blank=True, null=True)
    activestatus = models.TextField(db_column='ActiveStatus', blank=True, null=True)
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataCustomer'
        verbose_name = 'Харилцагч'
        verbose_name_plural = 'Харилцагчид'

    def __str__(self):
        return self.name or f"Customer {self.pkid}"


class OpenDataEmployee(models.Model):
    """Ажилчдын мэдээлэл (OpenDataEmployee view)"""
    id = models.TextField(db_column='Id', primary_key=True)
    pkid = models.BigIntegerField(db_column='PkId', blank=True, null=True)
    name = models.TextField(db_column='Name', blank=True, null=True)
    registrynumber = models.TextField(db_column='RegistryNumber', blank=True, null=True)
    departmentname = models.TextField(db_column='DepartmentName', blank=True, null=True)
    positionname = models.TextField(db_column='PositionName', blank=True, null=True)
    mobilenumber = models.TextField(db_column='MobileNumber', blank=True, null=True)
    email = models.TextField(db_column='Email', blank=True, null=True)
    hiredate = models.DateField(db_column='HireDate', blank=True, null=True)
    basesalary = models.FloatField(db_column='BaseSalary', blank=True, null=True)
    isreclusion = models.TextField(db_column='IsReclusion', blank=True, null=True)
    # Цалин бодолтод ашиглах нэмэлт утгууд (эх системийн D-баганууд)
    insuredtypeid = models.TextField('НДШ-ийн код (даатгуулагчийн төрөл)', db_column='InsuredTypeId', blank=True, null=True)
    insuredtypename = models.TextField('Даатгуулагчийн төрөл', db_column='InsuredTypeName', blank=True, null=True)
    d4 = models.FloatField('Удаан жилийн нэмэгдэл', db_column='D4', blank=True, null=True)
    d5 = models.FloatField('Хадгаламж', db_column='D5', blank=True, null=True)
    d6 = models.FloatField('Эрсдэлийн сан', db_column='D6', blank=True, null=True)
    d7 = models.FloatField('Хуримтлал', db_column='D7', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataEmployee'
        verbose_name = 'Ажилчин'
        verbose_name_plural = 'Ажилчид'

    def __str__(self):
        return self.name or f"Employee {self.pkid}"


class OpenDataSale(models.Model):
    """Борлуулалтын мэдээлэл (OpenDataSale view)"""
    # View-д id column байхгүй учраас documentpkid-г primary key болгоно
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdate = models.TextField(db_column='DocumentDate', blank=True, null=True)  # TEXT field
    warehousename = models.TextField(db_column='WarehouseName', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    brandname = models.TextField(db_column='BrandName', blank=True, null=True)
    sellername = models.TextField(db_column='SellerName', blank=True, null=True)
    customername = models.TextField(db_column='CustomerName', blank=True, null=True)
    distributionchannelname = models.TextField(db_column='DistributionChannelName', blank=True, null=True)
    qty = models.TextField(db_column='Qty', blank=True, null=True)  # TEXT field
    price = models.TextField(db_column='Price', blank=True, null=True)  # TEXT field
    vatamount = models.TextField(db_column='VatAmount', blank=True, null=True)  # TEXT field
    amountnonvat = models.TextField(db_column='AmountNonVat', blank=True, null=True)  # TEXT field - НӨАТ-гүй дүн
    discountamount = models.TextField(db_column='DiscountAmount', blank=True, null=True)  # TEXT field
    payamount = models.TextField(db_column='PayAmount', blank=True, null=True)  # TEXT field
    unitcost = models.TextField(db_column='UnitCost', blank=True, null=True)  # TEXT field
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataSale'
        verbose_name = 'Борлуулалт'
        verbose_name_plural = 'Борлуулалтууд'

    def __str__(self):
        return f"{self.documentnumber} - {self.documentdate}"


class OpenDataPurchase(models.Model):
    """Худалдан авалтын мэдээлэл (OpenDataPurchase view)"""
    id = models.BigAutoField(primary_key=True)
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', blank=True, null=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdate = models.DateField(db_column='DocumentDate', blank=True, null=True)
    vendorname = models.TextField(db_column='VendorName', blank=True, null=True)
    warehousename = models.TextField(db_column='WarehouseName', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    qty = models.FloatField(db_column='Qty', blank=True, null=True)
    unitcost = models.FloatField(db_column='UnitCost', blank=True, null=True)
    amount = models.FloatField(db_column='Amount', blank=True, null=True)
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataPurchase'
        verbose_name = 'Худалдан авалт'
        verbose_name_plural = 'Худалдан авалтууд'

    def __str__(self):
        return f"{self.documentnumber} - {self.documentdate}"


class OpenDataInventory(models.Model):
    """Нөөцийн хөдөлгөөн (OpenDataInventory view)"""
    # View-д id column байхгүй учраас documentpkid-г primary key болгоно
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentdate = models.TextField(db_column='DocumentDate', blank=True, null=True)  # TEXT field
    documenttype = models.TextField(db_column='DocumentType', blank=True, null=True)
    warehousename = models.TextField(db_column='WarehouseName', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    brandname = models.TextField(db_column='BrandName', blank=True, null=True)
    inqty = models.TextField(db_column='InQty', blank=True, null=True)  # TEXT field
    outqty = models.TextField(db_column='OutQty', blank=True, null=True)  # TEXT field
    endqty = models.TextField(db_column='EndQty', blank=True, null=True)  # TEXT field
    unitcost = models.TextField(db_column='UnitCost', blank=True, null=True)  # TEXT field
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataInventory'
        verbose_name = 'Нөөцийн хөдөлгөөн'
        verbose_name_plural = 'Нөөцийн хөдөлгөөнүүд'

    def __str__(self):
        return f"{self.itemname} - {self.documentdate}"


class OpenDataLandedCost(models.Model):
    """Татан авалтын өртөг (LandedCost - импортын зардал)"""
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdate = models.DateField(db_column='DocumentDate', blank=True, null=True)
    vendorname = models.TextField(db_column='VendorName', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    qty = models.TextField(db_column='Qty', blank=True, null=True)  # TEXT in DB
    price = models.TextField(db_column='Price', blank=True, null=True)  # TEXT in DB
    itemamountfc = models.TextField(db_column='ItemAmountFc', blank=True, null=True)  # TEXT in DB
    unitcost = models.TextField(db_column='UnitCost', blank=True, null=True)  # TEXT in DB
    customsfee = models.TextField(db_column='CustomAmount', blank=True, null=True)  # TEXT in DB
    transportcost = models.TextField(db_column='OtherExpenseAmount', blank=True, null=True)  # TEXT in DB
    totalcost = models.TextField(db_column='TotalExpenseAmount', blank=True, null=True)  # TEXT in DB
    amount = models.TextField(db_column='Amount', blank=True, null=True)  # TEXT in DB
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataLandedCost'
        verbose_name = 'Татан авалтын өртөг'
        verbose_name_plural = 'Татан авалтын өртгүүд'

    def __str__(self):
        return f"{self.documentnumber} - {self.documentdate}"


class OpenDataSaleHeader(models.Model):
    """Борлуулалтын толгой мэдээлэл (SaleHeader - түгээлтийн мэдээлэл)"""
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentdate = models.DateField(db_column='DocumentDate', blank=True, null=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdesc = models.TextField(db_column='DocumentDesc', blank=True, null=True)
    distributorid = models.TextField(db_column='DistributorId', blank=True, null=True)
    distributorname = models.TextField(db_column='DistributorName', blank=True, null=True)
    sellerid = models.TextField(db_column='SellerId', blank=True, null=True)
    sellername = models.TextField(db_column='SellerName', blank=True, null=True)
    customerid = models.TextField(db_column='CustomerId', blank=True, null=True)
    customername = models.TextField(db_column='CustomerName', blank=True, null=True)
    itemid = models.TextField(db_column='ItemId', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    saleorderqty = models.FloatField(db_column='SaleOrderQty', blank=True, null=True)
    shippingqty = models.FloatField(db_column='ShippingQty', blank=True, null=True)
    deliveryqty = models.FloatField(db_column='DeliveryQty', blank=True, null=True)
    measureid = models.TextField(db_column='MeasureId', blank=True, null=True)
    measurename = models.TextField(db_column='MeasureName', blank=True, null=True)
    price = models.FloatField(db_column='Price', blank=True, null=True)
    discountpercent = models.FloatField(db_column='DiscountPercent', blank=True, null=True)
    discountamount = models.FloatField(db_column='DiscountAmount', blank=True, null=True)
    promotionamount = models.FloatField(db_column='PromotionAmount', blank=True, null=True)
    itempromotionamount = models.FloatField(db_column='ItemPromotionAmount', blank=True, null=True)
    manualdiscountamount = models.FloatField(db_column='ManualDiscountAmount', blank=True, null=True)
    vatamount = models.FloatField(db_column='VatAmount', blank=True, null=True)
    amountnonvat = models.FloatField(db_column='AmountNonVat', blank=True, null=True)
    amount = models.FloatField(db_column='Amount', blank=True, null=True)
    payamount = models.FloatField(db_column='PayAmount', blank=True, null=True)
    modifieddate = models.DateTimeField(db_column='ModifiedDate', blank=True, null=True)
    createddate = models.DateTimeField(db_column='CreatedDate', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'OpenDataSaleHeader'
        verbose_name = 'Түгээлтийн мэдээлэл'
        verbose_name_plural = 'Түгээлтийн мэдээлэл'

    def __str__(self):
        return f"{self.documentnumber} - {self.documentdate}"


class OpenDataGeneralLedger(models.Model):
    """Ерөнхий дэвтэр - Accounting General Ledger"""
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdate = models.DateField(db_column='DocumentDate', blank=True, null=True)
    documentdesc = models.TextField(db_column='DocumentDesc', blank=True, null=True)
    documenttypename = models.TextField(db_column='DocumentTypeName', blank=True, null=True)
    accountid = models.TextField(db_column='AccountId', blank=True, null=True)  # 520101 гэх мэт
    accountname = models.TextField(db_column='AccountName', blank=True, null=True)
    accounttypename = models.TextField(db_column='AccountTypeName', blank=True, null=True)
    accountgroupid = models.TextField(db_column='AccountGroupId', blank=True, null=True)
    accountgroupname = models.TextField(db_column='AccountGroupName', blank=True, null=True)
    branchid = models.TextField(db_column='BranchId', blank=True, null=True)
    branchname = models.TextField(db_column='BranchName', blank=True, null=True)
    costcenterid = models.TextField(db_column='CostCenterId', blank=True, null=True)
    costcenter = models.TextField(db_column='CostCenter', blank=True, null=True)
    expenseid = models.TextField(db_column='ExpenseId', blank=True, null=True)
    expensename = models.TextField(db_column='ExpenseName', blank=True, null=True)
    debitamt = models.FloatField(db_column='DebitAmt', blank=True, null=True)
    creditamt = models.FloatField(db_column='CreditAmt', blank=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'OpenDataGeneralLedger'
        verbose_name = 'Ерөнхий дэвтэр'
        verbose_name_plural = 'Ерөнхий дэвтэр'
    
    def __str__(self):
        return f"{self.documentnumber} - {self.accountid}"


class OpenDataSaleRefund(models.Model):
    """Борлуулалтын буцаалт"""
    documentpkid = models.BigIntegerField(db_column='DocumentPkId', primary_key=True)
    documentdate = models.DateField(db_column='DocumentDate', blank=True, null=True)
    documentnumber = models.TextField(db_column='DocumentNumber', blank=True, null=True)
    documentdesc = models.TextField(db_column='DocumentDesc', blank=True, null=True)
    paymenttype = models.TextField(db_column='PaymentType', blank=True, null=True)
    customerid = models.TextField(db_column='CustomerId', blank=True, null=True)
    customername = models.TextField(db_column='CustomerName', blank=True, null=True)
    sellerid = models.TextField(db_column='SellerId', blank=True, null=True)
    sellername = models.TextField(db_column='SellerName', blank=True, null=True)
    distributorid = models.TextField(db_column='DistributorId', blank=True, null=True)
    distributorname = models.TextField(db_column='DistributorName', blank=True, null=True)
    warehouseid = models.TextField(db_column='WarehouseId', blank=True, null=True)
    warehousename = models.TextField(db_column='WarehouseName', blank=True, null=True)
    itemid = models.TextField(db_column='ItemId', blank=True, null=True)
    itemname = models.TextField(db_column='ItemName', blank=True, null=True)
    qty = models.FloatField(db_column='Qty', blank=True, null=True)
    price = models.FloatField(db_column='Price', blank=True, null=True)
    discountamount = models.FloatField(db_column='DiscountAmount', blank=True, null=True)
    vatamount = models.FloatField(db_column='VatAmount', blank=True, null=True)
    amountnonvat = models.FloatField(db_column='AmountNonVat', blank=True, null=True)
    amount = models.FloatField(db_column='Amount', blank=True, null=True)
    payamount = models.FloatField(db_column='PayAmount', blank=True, null=True)
    
    class Meta:
        managed = False
        db_table = 'OpenDataSaleRefund'
        verbose_name = 'Борлуулалтын буцаалт'
        verbose_name_plural = 'Борлуулалтын буцаалт'
    
    def __str__(self):
        return f"{self.documentnumber} - {self.documentdate}"

