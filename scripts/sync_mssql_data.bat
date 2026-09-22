@echo off
REM MSSQL -> PostgreSQL automated sync
REM Runs every 2 hours

cd /d "D:\Bayar\programming\python\tae"

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Sync all views from both databases (redirect to log file)
echo [%date% %time%] Sync started >> logs\sync.log

python manage.py import_views --database=TugsAminErdeneAccounting --create-tables 2>&1 | findstr /V "SUCCESS WARNING" >> logs\sync.log
python manage.py import_views --database=TugsAminErdeneDistribution --create-tables 2>&1 | findstr /V "SUCCESS WARNING" >> logs\sync.log

echo [%date% %time%] Sync completed >> logs\sync.log
echo. >> logs\sync.log

deactivate
