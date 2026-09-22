# MSSQL Views Import Guide

## Тохиргоо

### 1. .env файл үүсгэх
```bash
copy .env.example .env
```

### 2. MSSQL мэдээлэл оруулах
```.env
# PostgreSQL
DB_NAME=tae_db
DB_USER=postgres
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# MSSQL
MSSQL_SERVER=25.11.54.181,1399
MSSQL_DATABASE=TugsAminErdeneAccounting
MSSQL_DATABASE2=TugsAminErdeneDistribution
MSSQL_USERNAME=openDataUser1108
MSSQL_PASSWORD=fiKzBSBRMb&h
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

## Commands

### 1. Views-ийн жагсаалт харах
```bash
# Бүх database-ийн views
python manage.py import_views --list

# Тодорхой database
python manage.py import_views --database=TugsAminErdeneAccounting --list
```

### 2. Хүснэгтүүд үүсгэх
```bash
# Бүх views-д хүснэгт үүсгэх
python manage.py import_views --create-tables

# Тодорхой database
python manage.py import_views --database=TugsAminErdeneAccounting --create-tables
```

### 3. Өгөгдөл импортлох
```bash
# Бүх views-ийн өгөгдөл
python manage.py import_views

# Тодорхой database
python manage.py import_views --database=TugsAminErdeneAccounting

# Тодорхой view
python manage.py import_views --database=TugsAminErdeneAccounting --view=dbo.ViewName

# Тест (анхны 1000 мөр)
python manage.py import_views --limit=1000
```

### 4. Хүснэгт үүсгэж, өгөгдөл импортлох
```bash
python manage.py import_views --create-tables
```

## Хүснэгтийн Нэрийн Дүрэм

Views нь дараах форматаар хүснэгт үүснэ:
```
view_<database>_<schema>_<viewname>
```

**Жишээ:**
- Database: `TugsAminErdeneAccounting`
- View: `dbo.CustomerList`
- PostgreSQL хүснэгт: `view_tugsaminerdeneaccounting_dbo_customerlist`

## Data Type Mapping

| MSSQL Type | PostgreSQL Type |
|------------|----------------|
| VARCHAR/NVARCHAR | VARCHAR/TEXT |
| INT | INTEGER |
| BIGINT | BIGINT |
| DECIMAL/MONEY | DECIMAL(18,2) |
| BIT | BOOLEAN |
| DATETIME | TIMESTAMP |
| UNIQUEIDENTIFIER | UUID |

## Жишээ Ажлын Урсгал

```bash
# 1. Views-ийн жагсаалт харах
python manage.py import_views --list

# 2. Хүснэгтүүд үүсгэх
python manage.py import_views --create-tables

# 3. Өгөгдөл импортлох
python manage.py import_views

# 4. Үр дүн шалгах
python manage.py dbshell
SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'view_%';
```

## Санамж

1. **ODBC Driver**: Microsoft ODBC Driver 17 for SQL Server суулгасан байх
2. **Network**: MSSQL server-тэй холбогдох боломжтой байх (firewall шалгах)
3. **Эрх**: Views-ийг унших эрх байх
4. **Хурд**: Том views-үүд удаан ажиллаж болно (--limit ашиглаж тест хийх)
5. **Хадгалалт**: `--create-tables` заагаагүй бол хүснэгт үүсгэхгүй (зөвхөн өгөгдөл хадгална)

## Troubleshooting

### ODBC Driver олдохгүй
```bash
# Суулгасан driver-уудыг шалгах
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}

# Суулгаагүй бол: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
```

### Connection timeout
```python
# view_extractor.py дээр timeout-ыг нэмэгдүүлнэ:
self.connection = pyodbc.connect(connection_string, timeout=60)
```

### Memory error (том views)
```bash
# Жижиг batch-аар татах
python manage.py import_views --limit=10000
```

## Query Examples

```sql
-- Импортлогдсон хүснэгтүүд
SELECT table_name, pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) AS size
FROM information_schema.tables 
WHERE table_name LIKE 'view_%'
ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;

-- Тодорхой хүснэгтийн мөрийн тоо
SELECT COUNT(*) FROM view_tugsaminerdeneaccounting_dbo_customerlist;

-- Бүх импортлогдсон хүснэгтүүдийн мөрийн тоо
SELECT 
    table_name,
    (xpath('/row/cnt/text()', query_to_xml(
        format('SELECT COUNT(*) AS cnt FROM %I', table_name), 
        false, true, ''
    )))[1]::text::int AS row_count
FROM information_schema.tables 
WHERE table_name LIKE 'view_%'
ORDER BY table_name;
```
