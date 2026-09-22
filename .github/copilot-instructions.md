# Copilot Instructions

## Төслийн Тойм (Project Overview)

**European Food Import E-commerce & ERP System**

Django-д суурилсан Full-Stack систем - Европоос хүнсний бүтээгдэхүүн импортлох, B2C/B2B борлуулах, дотоод санхүү/нөөц удирдах.

### Үндсэн Технологи
- **Backend**: Django (Python), Django REST Framework
- **Database**: PostgreSQL
- **Frontend**: Modern, minimalist design (Цагаан/Хар + Ногоон/Цэнхэр)
- **Target**: Аюулгүй, тогтвортой, хурдтай систем

## Архитектурын Гол Бүрэлдэхүүн

### 1. Хэрэглэгчийн Бүлгүүд (User Roles)
```python
# Гурван үндсэн бүлэг
- B2C: Хувь хүмүүс (сүлжээ дэлгүүр, худалдааны төв)
- B2B: Бизнес түншүүд (ресторан, дэлгүүр) - тусгай үнэ, бөөнөөр захиалга
- STAFF: Ажилчид (нярав, нягтлан, менежер) - эрх хязгаарлалттай ERP
```

### 2. Үндсэн Django Apps Бүтэц
```
products/       # Бүтээгдэхүүний каталог, category, pricing
orders/         # B2C/B2B захиалга, cart, checkout
purchase/       # Гадаад захиалга (PurchaseOrder), COGS тооцоолол
inventory/      # Нөөцийн удирдлага (stock_quantity, movements)
accounts/       # Авлагын удирдлага (B2B receivables)
finance/        # Тайлан (борлуулалт, ашиг, цалин)
users/          # Эрхийн удирдлага, role-based permissions
```

## Санхүү/ERP Онцлог Шинж Чанарууд

### PurchaseOrder Загвар
```python
# Гадаад захиалга бүртгэх үед дараах зардлуудыг нэмнэ:
- Гаалийн хураамж
- Тээврийн зардал
- Нэгжийн өртөг (COGS) автоматаар тооцоологдоно
```

### Эрхийн Удирдлага
```python
# Role-based access control (RBAC)
- Гадаадын харилцаа менежер: PurchaseOrder бүртгэх
- Нярав: stock_quantity хянах, нөөц хөдөлгөөн
- Авлагын нягтлан: Авлагын үлдэгдэл, B2B төлбөр
- Захирал/Ерөнхий нягтлан: Бүх тайлан үзэх
```

## Хөгжүүлэлтийн Зарчим

### Code Style
- PEP 8 дагаж Python код бичих
- Django naming conventions: models (CamelCase), views (snake_case)
- Монгол болон англи хэлний comments хэрэглэж болно

### Database Conventions
- PostgreSQL-ийг үндсэн database-аар ашиглах
- Migration files бүгдийг version control-д хадгалах
- Санхүүгийн өгөгдөлд `DecimalField` ашиглах (FloatField биш!)

### Security Practices
```python
# Санхүү/эрхийн мэдрэг өгөгдөлтэй ажиллах учраас:
- Django permissions + custom decorators ашиглах
- Staff-only views-д @staff_member_required
- B2B portals-д тусгай authentication
- Авлагын мэдээлэл зөвхөн эрх бүхий хэрэглэгчид
```

### Frontend Design
- Европын чанар, цэвэр байдлыг илэрхийлэх орчин үеийн UI
- Color scheme: Цагаан/Хар (үндсэн) + Ногоон/Цэнхэр (онцлох)
- Responsive design - desktop болон mobile

## Ажлын Урсгал (Workflows)

### Development Setup
```bash
# Virtual environment үүсгэх
python -m venv venv
venv\Scripts\Activate.ps1

# Dependencies суулгах
pip install -r requirements.txt

# Database migration
python manage.py makemigrations
python manage.py migrate

# Development server
python manage.py runserver
```

### Testing
- Unit tests бүх app-д бичих
- Санхүүгийн тооцооллын tests заавал шаардлагатай (COGS, pricing)
- `python manage.py test` ажиллуулах

## Анхаарах Зүйлс

1. **COGS Тооцоолол**: PurchaseOrder-д зардал нэмэхэд бүх хамааралтай бүтээгдэхүүний нэгжийн өртөг шинэчлэгдэх ёстой
2. **B2B vs B2C Pricing**: Бизнес түншүүдэд тусгай/бөөний үнэ, хувь хүмүүст жижиглэнгийн үнэ
3. **Stock Management**: Борлуулалт болон буцаалт бүр `stock_quantity`-г автоматаар шинэчилнэ
4. **Multilingual Support**: Монгол болон англи хэлийг дэмжих (Django i18n)

---

*Төслийн хөгжилтэй хамт энэхүү заавар шинэчлэгдэнэ.*
