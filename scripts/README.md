# Автомат MSSQL → PostgreSQL Синхрончлол

## Тохиргоо

### 1. Task Scheduler-д таск үүсгэх

PowerShell-г **Administrator** эрхээр нээгээд:

```powershell
cd D:\Bayar\programming\python\tae\scripts
.\setup_scheduled_task.ps1
```

### 2. Таск шалгах

```powershell
Get-ScheduledTask -TaskName "MSSQL_PostgreSQL_Sync"
```

### 3. Гараар ажиллуулах

```powershell
Start-ScheduledTask -TaskName "MSSQL_PostgreSQL_Sync"
```

### 4. Лог шалгах

```powershell
Get-Content ..\logs\sync.log -Tail 50
```

## Давтамж Өөрчлөх

Task Scheduler GUI-г нээгээд:
1. Win + R → `taskschd.msc`
2. "MSSQL_PostgreSQL_Sync" олох
3. Properties → Triggers → Edit
4. "Repeat task every" хэсгийг өөрчлөх

Эсвэл PowerShell-р:

```powershell
# 1 цаг тутам
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1)

# 30 минут тутам  
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 30)

# Trigger шинэчлэх
Set-ScheduledTask -TaskName "MSSQL_PostgreSQL_Sync" -Trigger $Trigger
```

## Таск Устгах

```powershell
Unregister-ScheduledTask -TaskName "MSSQL_PostgreSQL_Sync" -Confirm:$false
```

## Файлууд

- **sync_mssql_data.bat** - Sync ажиллуулах batch script
- **setup_scheduled_task.ps1** - Task Scheduler тохиргоо
- **../logs/sync.log** - Синхрончлолын логууд
