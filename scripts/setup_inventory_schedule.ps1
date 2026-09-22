# Windows Task Scheduler дээр 2 цаг тутамд ажиллах task үүсгэх
# Admin эрхтэйгээр PowerShell дээр ажиллуулах

# Төслийн зам
$ProjectPath = "D:\Bayar\programming\python\tae"
$ScriptPath = Join-Path $ProjectPath "scripts\update_inventory.bat"

# Task үүсгэх
$TaskName = "TAE_Inventory_Snapshot_Update"
$TaskDescription = "Updates inventory snapshot every 2 hours for TAE E-commerce system"

# Trigger: 2 цаг тутамд
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 2)

# Action: Batch script ажиллуулах
$Action = New-ScheduledTaskAction -Execute $ScriptPath

# Settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Task бүртгэх
Register-ScheduledTask -TaskName $TaskName `
    -Description $TaskDescription `
    -Trigger $Trigger `
    -Action $Action `
    -Settings $Settings `
    -Force

Write-Host "✅ Scheduled Task үүслээ: $TaskName" -ForegroundColor Green
Write-Host "   2 цаг тутамд $ScriptPath ажиллана" -ForegroundColor Cyan
Write-Host ""
Write-Host "Task удирдах:" -ForegroundColor Yellow
Write-Host "  Харах:  Get-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "  Идэвхжүүлэх: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "  Устгах: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor Gray
