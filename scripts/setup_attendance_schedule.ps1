# Windows Task Scheduler дээр өдөр бүр оройн цагаар хурууны төхөөрөмжөөс цаг бүртгэл татах task үүсгэх
# Admin эрхтэйгээр PowerShell дээр ажиллуулах:
#   powershell -ExecutionPolicy Bypass -File scripts\setup_attendance_schedule.ps1
# Цагийг өөрчлөх бол: ... -File scripts\setup_attendance_schedule.ps1 -At "21:30"

param(
    [string]$At = "20:00"
)

$ProjectPath = "D:\Bayar\programming\python\tae"
$ScriptPath = Join-Path $ProjectPath "scripts\sync_attendance.bat"

$TaskName = "TAE_Attendance_Sync"
$TaskDescription = "Daily fingerprint device attendance sync for TAE (python manage.py sync_attendance)"

# Trigger: өдөр бүр заасан цагт
$Trigger = New-ScheduledTaskTrigger -Daily -At $At

# Action: Batch script ажиллуулах
$Action = New-ScheduledTaskAction -Execute $ScriptPath -WorkingDirectory $ProjectPath

# Settings: компьютер тэр үед унтарсан/унтсан байвал асмагц ажиллана, 30 минутаас удвал зогсооно
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30)

Register-ScheduledTask -TaskName $TaskName `
    -Description $TaskDescription `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Force | Out-Null

Write-Host "Scheduled Task uuslee: $TaskName" -ForegroundColor Green
Write-Host "   Odor bur $At-d $ScriptPath ajillana" -ForegroundColor Cyan
Write-Host "   Log: $ProjectPath\logs\attendance_sync.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "Task udirdah:" -ForegroundColor Yellow
Write-Host "  Harah:      Get-ScheduledTaskInfo -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "  Odoo ajilluulah: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "  Ustgah:     Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Gray
