# MSSQL Views импортлох - Хурдан Гарын Авлага

## 🚀 Богино Заавар

### 1. Environment тохируулах
```bash
# .env файл үүсгэх
copy .env.example .env
```

`.env` файлд дараах мэдээллээ оруулна:
```env
# PostgreSQL
DB_NAME=tae_db
DB_USER=postgres
DB_PASSWORD=<postgres нууц үг>
DB_HOST=localhost
DB_PORT=5432

# MSSQL - TugsAminErdene Системүүд
MSSQL_SERVER=25.11.54.181,1399
MSSQL_DATABASE=TugsAminErdeneAccounting
MSSQL_DATABASE2=TugsAminErdeneDistribution
MSSQL_USERNAME=openDataUser1108
MSSQL_PASSWORD=fiKzBSBRMb&h
MSSQL_DRIVER=ODBC Driver 17 for SQL Server
```

### 2. PostgreSQL Database үүсгэх
```bash
# PostgreSQL-д нэвтрэх
psql -U postgres

# Database үүсгэх
CREATE DATABASE tae_db;
\q
```

### 3. Django Migration
```bash
# Virtual environment идэвхжүүлэх
venv\Scripts\Activate.ps1

# Migrations
python manage.py makemigrations
python manage.py migrate
```

### 4. Views импортлох
```bash
# 1. Эхлээд views-ийн жагсаалт харах
python manage.py import_views --list

# 2. Хүснэгтүүд үүсгэх + Өгөгдөл импортлох
python manage.py import_views --create-tables
```

## 📊 Гарах Үр Дүн

Command ажиллуулахад:
```
======================================================================
MSSQL Views → PostgreSQL Импортлолт
======================================================================

📊 Боловсруулах databases: TugsAminErdeneAccounting, TugsAminErdeneDistribution

🗄️  Database: TugsAminErdeneAccounting
----------------------------------------------------------------------
  42 views олдлоо

  📋 View: dbo.CustomerList
    Columns: 15
    ✓ Хүснэгт үүсгэгдлээ: view_tugsaminerdeneaccounting_dbo_customerlist
    ✓ 1,234 мөр хадгалагдлаа

  📋 View: dbo.ProductInventory
    Columns: 8
    ✓ Хүснэгт үүсгэгдлээ: view_tugsaminerdeneaccounting_dbo_productinventory
    ✓ 567 мөр хадгалагдлаа

...

======================================================================
📊 ДҮГНЭЛТ
======================================================================
Нийт views: 84
Амжилттай: 84
Нийт мөр: 15,678
======================================================================
```

## 🔍 PostgreSQL дээр шалгах

```bash
# Django shell ашиглах
python manage.py dbshell
```

```sql
-- Импортлогдсон хүснэгтүүдийн жагсаалт
SELECT table_name 
FROM information_schema.tables 
WHERE table_name LIKE 'view_%' 
ORDER BY table_name;

-- Тодорхой хүснэгтийн өгөгдөл харах
SELECT * FROM view_tugsaminerdeneaccounting_dbo_customerlist LIMIT 10;

-- Бүх хүснэгтүүдийн мөрийн тоо
SELECT 
    schemaname,
    tablename,
    n_live_tup as row_count
FROM pg_stat_user_tables
WHERE tablename LIKE 'view_%'
ORDER BY n_live_tup DESC;

-- Хүснэгтийн хэмжээ
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size(quote_ident(table_name))) as size
FROM information_schema.tables 
WHERE table_name LIKE 'view_%'
ORDER BY pg_total_relation_size(quote_ident(table_name)) DESC;
```

## ⚙️ Нэмэлт Команд Сонголтууд

```bash
# Тодорхой database-ийн views
python manage.py import_views --database=TugsAminErdeneAccounting

# Тодорхой view импортлох
python manage.py import_views --database=TugsAminErdeneAccounting --view=dbo.CustomerList

# Тест (анхны 100 мөр татах)
python manage.py import_views --limit=100

# Зөвхөн жагсаалт харах (импортлохгүй)
python manage.py import_views --list

# Хүснэгт үүсгэхгүй (зөвхөн өгөгдөл шинэчлэх)
python manage.py import_views  # --create-tables-ийг заагаагүй
```

## 🎯 Системийн Онцлог

### Автомат Column Mapping
- MSSQL data type → PostgreSQL type автомат хөрвүүлэлт
- VARCHAR, INT, DECIMAL, DATETIME, UNIQUEIDENTIFIER гэх мэт

### Хүснэгтийн Нэрийн Формат
```
view_<database>_<schema>_<viewname>
```

Жишээ:
- `TugsAminErdeneAccounting` → `view_tugsaminerdeneaccounting_...`
- `dbo.CustomerList` → `...._dbo_customerlist`

### Transaction Safety
- Алдаа гарвал өөрчлөлт автоматаар буцаагдана
- Бүх view бие даан боловсруулагдана

## ⚠️ Анхаарах Зүйлс

1. **ODBC Driver**: 
   ```powershell
   # Суулгасан эсэхийг шалгах
   Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}
   ```
   Суулгаагүй бол: https://aka.ms/downloadmsodbcsql

2. **Network холболт**: 
   - MSSQL server (25.11.54.181:1399) хандах боломжтой байх
   - Firewall нээлттэй эсэхийг шалгах

3. **Эрх**: 
   - MSSQL user нь views унших эрхтэй байх
   - PostgreSQL user нь хүснэгт үүсгэх эрхтэй байх

4. **Хурд**: 
   - Том views (100,000+ мөр) удаан ажиллаж болно
   - `--limit` ашиглаж эхлээд тест хийх зүйтэй

## 🔄 Давтан Импортлох

Views-ийн өгөгдөл шинэчлэгдсэн үед:

```bash
# Хуучин өгөгдлийг арилгаж, шинэ өгөгдөл импортлох
python manage.py import_views --create-tables
```

`--create-tables` нь:
1. Хуучин хүснэгтийг устгана (DROP TABLE)
2. Шинэ хүснэгт үүсгэнэ
3. Өгөгдөл импортлоно

## 📞 Тусламж

Асуудал гарвал:
- `docs/VIEWS_IMPORT.md` - Дэлгэрэнгүй заавар
- `docs/DATA_MIGRATION.md` - Өгөгдлийн шилжүүлэлт
- `.github/copilot-instructions.md` - Төслийн заавар
