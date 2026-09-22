"""
Test expense transaction detail queries
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

# Test parameters
year = 2024
month = 1

print(f"\n{'='*60}")
print(f"Testing transaction queries for {year}/{month}")
print(f"{'='*60}\n")

# Test 1: Discount transactions (520101)
print("1. Хөнгөлөлт (AccountId=520101):")
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT 
            "DocumentDate",
            COALESCE("DocumentDesc", "DocumentNumber", '-') as description,
            "AccountId",
            "AccountName",
            CAST("DebitAmt" AS FLOAT) as amount
        FROM "OpenDataGeneralLedger"
        WHERE EXTRACT(year FROM "DocumentDate") = %s
          AND EXTRACT(month FROM "DocumentDate") = %s
          AND "AccountId" = %s
        ORDER BY "DocumentDate"
        LIMIT 5
    ''', [year, month, '520101'])
    
    rows = cursor.fetchall()
    print(f"   Олдсон: {len(rows)} гүйлгээ")
    for i, row in enumerate(rows[:3], 1):
        print(f"   {i}. {row[0]} - {row[1][:50] if row[1] else 'N/A'} ({row[2]}) - {row[4]:,.0f}₮")

# Test 2: Sales transactions
print("\n2. Борлуулалт (OpenDataSale):")
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT 
            "DocumentDate",
            "ItemName",
            "CustomerName",
            CAST("PayAmount" AS FLOAT) as amount
        FROM "OpenDataSale"
        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
          AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
        ORDER BY CAST("DocumentDate" AS DATE)
        LIMIT 5
    ''', [year, month])
    
    rows = cursor.fetchall()
    print(f"   Олдсон: {len(rows)} гүйлгээ")
    for i, row in enumerate(rows[:3], 1):
        item = row[1][:30] if row[1] else 'N/A'
        customer = row[2][:20] if row[2] else 'N/A'
        print(f"   {i}. {row[0]} - {item} ({customer}) - {row[3]:,.0f}₮")

# Test 3: Refund transactions
print("\n3. Буцаалт (OpenDataSaleRefund):")
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT 
            "DocumentDate",
            "ItemName",
            "CustomerName",
            CAST("PayAmount" AS FLOAT) as amount
        FROM "OpenDataSaleRefund"
        WHERE EXTRACT(year FROM "DocumentDate") = %s
          AND EXTRACT(month FROM "DocumentDate") = %s
        ORDER BY "DocumentDate"
        LIMIT 5
    ''', [year, month])
    
    rows = cursor.fetchall()
    print(f"   Олдсон: {len(rows)} гүйлгээ")
    for i, row in enumerate(rows[:3], 1):
        print(f"   {i}. {row[0]} - {row[1][:30]} ({row[2][:20]}) - {row[3]:,.0f}₮")

# Test 4: Expense accounts (7xxxxx)
print("\n4. Зардал (AccountId LIKE '7%'):")
with connection.cursor() as cursor:
    cursor.execute('''
        SELECT DISTINCT "AccountId", "AccountName"
        FROM "OpenDataGeneralLedger"
        WHERE "AccountId" LIKE '7%'
        ORDER BY "AccountId"
        LIMIT 5
    ''')
    
    accounts = cursor.fetchall()
    print(f"   Олдсон: {len(accounts)} зардлын данс")
    
    if accounts:
        test_account = accounts[0][0]
        print(f"\n   Жишээ: {test_account} - {accounts[0][1]}")
        
        cursor.execute('''
            SELECT 
                "DocumentDate",
                COALESCE("DocumentDesc", "DocumentNumber", '-') as description,
                CAST("DebitAmt" AS FLOAT) as amount
            FROM "OpenDataGeneralLedger"
            WHERE EXTRACT(year FROM "DocumentDate") = %s
              AND EXTRACT(month FROM "DocumentDate") = %s
              AND "AccountId" = %s
            ORDER BY "DocumentDate"
            LIMIT 3
        ''', [year, month, test_account])
        
        rows = cursor.fetchall()
        print(f"   {test_account} дансны гүйлгээ: {len(rows)}")
        for i, row in enumerate(rows, 1):
            print(f"   {i}. {row[0]} - {row[1][:50] if row[1] else 'N/A'} - {row[2]:,.0f}₮")

print(f"\n{'='*60}")
print("Test completed!")
print(f"{'='*60}\n")
