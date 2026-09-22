@echo off
REM Барааны үлдэгдлийн snapshot шинэчлэх batch script
REM 2 цаг тутамд Windows Task Scheduler-р ажиллуулна

cd /d "D:\Bayar\programming\python\tae"

REM Python environment санах ойруулах (хэрэв venv ашиглаж байвал)
REM call venv\Scripts\activate.bat

REM UTF-8 encoding тохируулах
set PYTHONIOENCODING=utf-8

REM Snapshot шинэчлэх
python manage.py update_inventory_snapshot >> logs\inventory_snapshot.log 2>&1

echo Snapshot updated at %date% %time% >> logs\inventory_snapshot_schedule.log
