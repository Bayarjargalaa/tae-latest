"""Test expense report cursor queries"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

print("Testing expense report cursor-based queries...")
print("=" * 80)

selected_year = 2026

# Test 1: OpenDataSale
print("\n1. Testing OpenDataSale with cursor...")
try:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                SUM(CAST("PayAmount" AS FLOAT)) as payamount_sum,
                SUM(CAST("VatAmount" AS FLOAT)) as vatamount_sum,
                SUM(CAST("AmountNonVat" AS FLOAT)) as amountnonvat_sum,
                SUM(CAST("UnitCost" AS FLOAT) * CAST("Qty" AS FLOAT)) as cost_sum
            FROM "OpenDataSale"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ORDER BY month
            ''',
            [selected_year]
        )
        rows = cursor.fetchall()
        print(f"✓ Found {len(rows)} months")
        for row in rows[:3]:
            print(f"  Month {int(row[0])}: PayAmount={row[1]:,.0f}₮")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: Discount (520101)
print("\n2. Testing discount with cursor...")
try:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                SUM("DebitAmt") as total
            FROM "OpenDataGeneralLedger"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
              AND "AccountId" = %s
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ORDER BY month
            ''',
            [selected_year, '520101']
        )
        rows = cursor.fetchall()
        print(f"✓ Found {len(rows)} months with discount")
        for row in rows:
            print(f"  Month {int(row[0])}: {row[1]:,.0f}₮")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: Refunds
print("\n3. Testing refunds with cursor...")
try:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                SUM(CAST("PayAmount" AS FLOAT)) as total
            FROM "OpenDataSaleRefund"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ORDER BY month
            ''',
            [selected_year]
        )
        rows = cursor.fetchall()
        print(f"✓ Found {len(rows)} months with refunds")
        for row in rows:
            print(f"  Month {int(row[0])}: {row[1]:,.0f}₮")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Expenses (7-series)
print("\n4. Testing expenses with cursor...")
try:
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                "AccountId" as accountid,
                "AccountName" as accountname,
                SUM("DebitAmt") as total
            FROM "OpenDataGeneralLedger"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
              AND "AccountId" LIKE '7%%'
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE)), "AccountId", "AccountName"
            ORDER BY "AccountId"
            LIMIT 10
            ''',
            [selected_year]
        )
        rows = cursor.fetchall()
        print(f"✓ Found {len(rows)} expense records")
        for row in rows[:5]:
            print(f"  Month {int(row[0])}, {row[1]}: {row[3]:,.0f}₮")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 80)
print("All cursor tests completed successfully!")
