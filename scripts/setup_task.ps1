# Windows Task Scheduler setup for MSSQL->PostgreSQL sync
# Runs every 2 hours

$TaskName = "MSSQL_PostgreSQL_Sync"
$ScriptPath = "D:\Bayar\programming\python\tae\scripts\sync_mssql_data.bat"
$LogPath = "D:\Bayar\programming\python\tae\logs"

# Create logs folder
if (!(Test-Path $LogPath)) {
    New-Item -ItemType Directory -Path $LogPath -Force | Out-Null
    Write-Host "Created logs folder: $LogPath" -ForegroundColor Green
}

# Remove old task if exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Removed existing task" -ForegroundColor Yellow
}

# Create task
$Action = New-ScheduledTaskAction -Execute $ScriptPath
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 2)
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "MSSQL to PostgreSQL sync every 2 hours" | Out-Null

Write-Host ""
Write-Host "Task created successfully!" -ForegroundColor Green
Write-Host "Name:       $TaskName"
Write-Host "Frequency:  Every 2 hours"
Write-Host "Script:     $ScriptPath"
Write-Host "Logs:       $LogPath\sync.log"
Write-Host ""
Write-Host "Commands:"
Write-Host "  View:   Get-ScheduledTask -TaskName $TaskName"
Write-Host "  Run:    Start-ScheduledTask -TaskName $TaskName"
Write-Host "  Delete: Unregister-ScheduledTask -TaskName $TaskName"
Write-Host ""
