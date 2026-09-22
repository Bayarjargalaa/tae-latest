# MSSQL -> PostgreSQL Data Migration Guide

## Бэлтгэл

### 1. MSSQL ODBC Driver Суулгах

**Windows:**
- [Microsoft ODBC Driver 17 for SQL Server](https://docs.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server) татаж суулгана

**Check installed drivers:**
```powershell
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}
```

### 2. Environment Variables Тохируулах

`.env` файл үүсгэж дараах мэдээллээ оруулна:

```env
# PostgreSQL
DB_NAME=tae_db
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432

# MSSQL
MSSQL_SERVER=your_mssql_server_ip_or_hostname
MSSQL_DATABASE=your_database_name
MSSQL_USERNAME=your_mssql_username
MSSQL_PASSWORD=your_mssql_password
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

### 3. Database Migration

```bash
# Virtual environment идэвхжүүлэх
venv\Scripts\Activate.ps1

# Django migrations ажиллуулах
python manage.py makemigrations
python manage.py migrate
```

## Өгөгдөл Импортлох

### Тусад нь импортлох

```bash
# 1. Бүтээгдэхүүн
python manage.py import_products

# 2. Харилцагчид
python manage.py import_customers

# 3. Ажилчид
python manage.py import_employees
```

### Бүгдийг нэг дор импортлох

```bash
python manage.py import_all
```

### Өмнөх өгөгдөл устгаад дахин импортлох

```bash
python manage.py import_all --clear
```

### Тодорхой хүснэгт зааж импортлох

```bash
python manage.py import_products --table=tblProducts
python manage.py import_customers --table=tblCustomers
python manage.py import_employees --table=tblEmployees
```

## Column Mapping

Commands нь дараах column нэрүүдийг автоматаар таньдаг:

### Products (Бүтээгдэхүүн)
- `ProductCode`, `Code` → code
- `ProductName`, `Name` → name
- `ProductNameEN`, `NameEN` → name_en
- `Description` → description
- `CostPrice` → cost_price
- `RetailPrice` → retail_price
- `WholesalePrice` → wholesale_price
- `Unit` → unit
- `Origin`, `Country` → origin_country
- `Manufacturer` → manufacturer
- `IsActive` → is_active
- `IsImported` → is_imported
- `ID`, `ProductID` → legacy_id

### Customers (Харилцагчид)
- `CustomerType`, `Type` → customer_type (B2C/B2B)
- `CustomerCode`, `Code` → code
- `CustomerName`, `Name` → name
- `Phone`, `Mobile` → phone
- `Email` → email
- `Address` → address
- `CompanyName` → company_name
- `TaxNumber`, `RegisterNumber` → tax_number
- `IsActive` → is_active
- `CreditLimit` → credit_limit
- `ID`, `CustomerID` → legacy_id

### Employees (Ажилчид)
- `EmployeeCode`, `Code` → code
- `FirstName`, `Name` → first_name
- `LastName`, `Surname` → last_name
- `Position` → position
- `Phone`, `Mobile` → phone
- `Email` → email
- `Salary` → salary
- `IsActive` → is_active
- `HireDate` → hire_date
- `TerminationDate` → termination_date
- `ID`, `EmployeeID` → legacy_id

## Санамж

1. **legacy_id** талбар нь MSSQL-ийн анхны ID-г хадгалж, давхардал үүсэхээс сэргийлнэ
2. Өгөгдөл дахин импортлох үед `legacy_id` ашиглан шинэчлэгдэнэ
3. Column нэрүүд таарахгүй бол command файлуудад өөрчлөлт хийнэ
4. Transaction ашигладаг учраас алдаа гарвал бүх өөрчлөлт буцаагдана

## Troubleshooting

### ODBC Driver олдохгүй
```
Install Microsoft ODBC Driver 17 for SQL Server
```

### Connection алдаа
- MSSQL server-ийн IP/hostname зөв эсэхийг шалгана
- Firewall 1433 порт нээлттэй эсэхийг шалгана
- Username/password зөв эсэхийг шалгана

### Column нэр таарахгүй
- `datamigration/management/commands/` дахь command файлуудад column mapping-ийг засна
