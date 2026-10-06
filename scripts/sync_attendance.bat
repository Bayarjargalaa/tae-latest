@echo off
REM Hurunii hee tanih toxooromjoos tsag burtgel tatah (python manage.py sync_attendance)
REM Windows Task Scheduler-r odort neg udaa (oroi) ajilluulna - scripts\setup_attendance_schedule.ps1
REM Tailbar: cmd.exe UTF-8 kirill tekstiig buruu unshdag tul ene failiin tailbaryg latinaar bichsen

cd /d "D:\Bayar\programming\python\tae"

set PYTHONIOENCODING=utf-8

if not exist logs mkdir logs

REM Tosliin venv baival tuugeer, ugui bol sistemiin python-oor
set PYTHON=python
if exist venv\Scripts\python.exe set PYTHON=venv\Scripts\python.exe

echo ===== %date% %time% ===== >> logs\attendance_sync.log
%PYTHON% manage.py sync_attendance >> logs\attendance_sync.log 2>&1
