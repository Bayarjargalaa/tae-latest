# TAE - European Food Import E-commerce & ERP System

Django-д суурилсан Full-Stack систем - Европоос хүнсний бүтээгдэхүүн импортлох, B2C/B2B борлуулах, дотоод санхүү/нөөц удирдах.

## Онцлог Шинж Чанарууд

### Хэрэглэгчийн Бүлгүүд
- **B2C**: Хувь хүмүүс - Жижиглэнгийн худалдаа
- **B2B**: Бизнес түншүүд - Тусгай үнэ, бөөнөөр захиалга
- **Staff**: Ажилчид - ERP функцууд (нярав, нягтлан, менежер)

### Үндсэн Модулиуд
- `products/` - Бүтээгдэхүүний каталог
- `orders/` - B2C/B2B захиалга
- `purchase/` - Гадаад захиалга, COGS тооцоолол
- `inventory/` - Нөөцийн удирдлага
- `accounts/` - Авлагын удирдлага
- `finance/` - Санхүүгийн тайлан
- `users/` - Эрхийн удирдлага

## Суулгах Заавар

### 1. Repository-г татах
```bash
git clone <repository-url>
cd tae
```

### 2. Virtual Environment үүсгэх
```bash
python -m venv venv
venv\Scripts\Activate.ps1  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Dependencies суулгах
```bash
pip install -r requirements.txt
```

### 4. Environment variables тохируулах
```bash
# .env.example файлыг .env болгож хуулж, утгуудыг тохируулах
copy .env.example .env  # Windows
# cp .env.example .env  # Linux/Mac
```

### 5. PostgreSQL Database үүсгэх
```sql
CREATE DATABASE tae_db;
CREATE USER postgres WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE tae_db TO postgres;
```

### 6. Migration ажиллуулах
```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Superuser үүсгэх
```bash
python manage.py createsuperuser
```

### 8. Development Server эхлүүлэх
```bash
python manage.py runserver
```

Вэб хөтөч дээр `http://localhost:8000` хаяг руу орно.

## Төслийн Бүтэц

```
tae/
├── core/                 # Үндсэн Django тохиргоо
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
├── products/             # Бүтээгдэхүүний app
├── orders/               # Захиалгын app
├── purchase/             # Гадаад худалдан авалтын app
├── inventory/            # Нөөцийн app
├── accounts/             # Авлагын app
├── finance/              # Санхүүгийн app
├── users/                # Хэрэглэгчийн app
├── static/               # Static файлууд
├── media/                # Upload файлууд
├── .github/              # GitHub тохиргоо
│   └── copilot-instructions.md
├── manage.py
├── requirements.txt
├── .env.example
└── .gitignore
```

## Хөгжүүлэлтийн Зарчим

- PEP 8 Python code style
- Django naming conventions
- PostgreSQL үндсэн database
- Санхүүгийн өгөгдөлд `DecimalField` ашиглах
- Role-based access control (RBAC)
- REST API дэмжлэг

## Өгөгдөл Импортлох

### MSSQL Views → PostgreSQL
```bash
# Views-ийн жагсаалт
python manage.py import_views --list

# Хүснэгтүүд үүсгэж, өгөгдөл импортлох
python manage.py import_views --create-tables

# Дэлгэрэнгүй: docs/VIEWS_IMPORT.md
```

### MSSQL Tables → PostgreSQL
```bash
# Бүтээгдэхүүн
python manage.py import_products

# Харилцагчид
python manage.py import_customers

# Ажилчид
python manage.py import_employees

# Бүгдийг нэгэн зэрэг
python manage.py import_all

# Дэлгэрэнгүй: docs/DATA_MIGRATION.md
```

## Холбоо Барих

Дэлгэрэнгүй мэдээлэл `.github/copilot-instructions.md` файлд байна.

---

*Төслийг Монгол Улсад Европын чанартай хүнсийг хүргэх зорилготой.*
