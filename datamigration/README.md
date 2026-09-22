# Data Migration App

MSSQL-ээс PostgreSQL-руу өгөгдөл шилжүүлэх Django app.

## Management Commands

### 1. Бүтээгдэхүүн импортлох
```bash
python manage.py import_products
python manage.py import_products --table=Products --clear
```

### 2. Харилцагчид импортлох
```bash
python manage.py import_customers
python manage.py import_customers --table=Customers --clear
```

### 3. Ажилчид импортлох
```bash
python manage.py import_employees
python manage.py import_employees --table=Employees --clear
```

### 4. Бүх өгөгдөл импортлох
```bash
python manage.py import_all
python manage.py import_all --clear
```

## Тохиргоо

`.env` файлд MSSQL холболтын мэдээллээ оруулна:

```
MSSQL_SERVER=your_server
MSSQL_DATABASE=your_database
MSSQL_USERNAME=your_username
MSSQL_PASSWORD=your_password
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

## Онцлог Шинж Чанарууд

- **legacy_id** field ашиглан давхардал зайлсхийнэ
- Transaction ашиглан аюулгүй өгөгдөл шилжүүлнэ
- Алдааны дэлгэрэнгүй log хөтлөнө
- Column нэрүүд автоматаар тааруулагдана
