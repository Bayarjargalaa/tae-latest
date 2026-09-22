# Барааны үлдэгдэл Snapshot System

## Ерөнхий мэдээлэл

Барааны үлдэгдлийн мэдээллийг **2 цаг тутамд автоматаар шинэчилж**, `inventory_snapshot` хүснэгтэд хадгална. Энэ нь хэрэглэгчид барааны үлдэгдэл хуудсыг харахад маш хурдан ажиллахад тусална (866,491 бичлэг бүхий OpenDataInventory-с шууд уншихын оронд).

## Хэрхэн ажилладаг

1. **InventorySnapshot Model** (`shop/models_inventory.py`):
   - Бараа бүрийн 3 агуулахын (Толгойт, жижиг, алтжин) үлдэгдлийг хадгална
   - Нийт үлдэгдэл, дундаж өртөг, сүүлийн огноонуудыг агуулна
   
2. **Management Command** (`shop/management/commands/update_inventory_snapshot.py`):
   - OpenDataInventory-с сүүлийн үлдэгдлийг тооцоолно
   - InventorySnapshot-ыг үүсгэх/шинэчилнэ
   
3. **View** (`shop/views.py` - `inventory_report`):
   - Snapshot хүснэгтээс өгөгдөл унших (их хурдан!)
   - Pagination, шүүлт, эрэмбэлэлт
   
4. **Scheduled Task**:
   - Windows Task Scheduler ашиглан 2 цаг тутамд автоматаар ажиллана

## Анхны тохиргоо

### 1. Migration ажиллуулах
```bash
python manage.py makemigrations shop
python manage.py migrate shop
```

### 2. Анхны snapshot үүсгэх
```bash
python manage.py update_inventory_snapshot
```
⏱ Удаж болно (~5-10 минут 282+ барааны хувьд)

### 3. Scheduled Task тохируулах (автоматаар 2 цаг тутамд)

#### Windows Task Scheduler ашиглах:

**Арга 1: PowerShell script (Админ эрхтэй)**
```powershell
# Admin эрхтэй PowerShell нээгээд:
cd D:\Bayar\programming\python\tae\scripts
.\setup_inventory_schedule.ps1
```

**Арга 2: Гараар тохируулах**
1. Task Scheduler нээх (`taskschd.msc`)
2. "Create Basic Task..." сонгох
3. Name: `TAE_Inventory_Snapshot_Update`
4. Trigger: Daily, Repeat every 2 hours
5. Action: Start a program
   - Program: `D:\Bayar\programming\python\tae\scripts\update_inventory.bat`
6. Finish

## Гараар ажиллуулах

### Command ашиглах:
```bash
python manage.py update_inventory_snapshot
```

### Options:
```bash
# Хуучин snapshot устгаж шинээр үүсгэх
python manage.py update_inventory_snapshot --clear
```

## Logs

Scheduled task-ийн log-ууд:
- `logs/inventory_snapshot.log` - Command output
- `logs/inventory_snapshot_schedule.log` - Schedule timestamps

## Техникийн дэлгэрэнгүй

### Performance давуу тал:
- ❌ **Өмнө**: 866,491 бичлэгээс query (удаан)
- ✅ **Одоо**: ~282 бичлэгтэй snapshot хүснэгтээс унших (хурдан!)

### Database structure:
```sql
CREATE TABLE inventory_snapshot (
    id INTEGER PRIMARY KEY,
    itemname VARCHAR(500) UNIQUE NOT NULL,
    brandname VARCHAR(200),
    tolgoit_qty DECIMAL(15,2),
    jijig_qty DECIMAL(15,2),
    altjin_qty DECIMAL(15,2),
    total_qty DECIMAL(15,2),
    avg_unitcost DECIMAL(15,2),
    tolgoit_date DATE,
    jijig_date DATE,
    altjin_date DATE,
    updated_at TIMESTAMP,
    created_at TIMESTAMP
);
```

### Indexes (Query optimization):
- `itemname` - Бараагаар хайлт
- `brandname` - Брэндээр хайлт
- `total_qty DESC` - Үлдэгдлээр эрэмбэлэлт
- `updated_at` - Шинэчлэлтийн огноо

## Асуудал шийдвэрлэлт

### Snapshot хуучирсан (2 цагаас илүү)
```bash
# Гараар шинэчилж болно:
python manage.py update_inventory_snapshot
```

### Scheduled task ажиллахгүй байна
```powershell
# Task-ийн төлөв шалгах:
Get-ScheduledTask -TaskName "TAE_Inventory_Snapshot_Update"

# Гараар ажиллуулж үзэх:
Start-ScheduledTask -TaskName "TAE_Inventory_Snapshot_Update"
```

### Өгөгдөл буруу харагдаж байна
```bash
# Snapshot-ыг устгаж шинээр үүсгэх:
python manage.py update_inventory_snapshot --clear
```

## Хөгжүүлэгчдэд

### Admin interface
InventorySnapshot model-ийг admin дээр бүртгэхгүй (read-only computed data).

### Custom management command
`shop/management/commands/update_inventory_snapshot.py` файлыг өөрчлөх хэрэгтэй бол:
- Агуулахын жагсаалт: `target_warehouses`
- Progress output: `self.stdout.write()`
- Error handling: `try/except` блокууд

---
**Хамгийн сүүлд шинэчилсэн**: 2026-02-12
