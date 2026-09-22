"""Test expense report raw SQL queries"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale, OpenDataGeneralLedger, OpenDataSaleRefund
from django.db import connection

print("Testing expense report raw SQL queries...")
print("=" * 80)

# Get the latest year
with connection.cursor() as cursor:
    cursor.execute(
        "SELECT EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE)) as year FROM \"OpenDataSale\" ORDER BY year DESC LIMIT 1"
    )
    row = cursor.fetchone()
    selected_year = int(row[0]) if row else 2026

print(f"\nTesting with year: {selected_year}")
print("=" * 80)

# Test 1: OpenDataSale monthly aggregation
print("\n1. Testing OpenDataSale monthly aggregation (raw SQL)...")
try:
    sales_data = []
    for row in OpenDataSale.objects.raw(
        '''
        SELECT 
            EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
            SUM(CAST("PayAmount" AS FLOAT)) as payamount_sum,
            SUM(CAST("VatAmount" AS FLOAT)) as vatamount_sum,
            SUM(CAST("AmountNonVat" AS FLOAT)) as amountnonvat_sum,
            SUM(CAST("UnitCost" AS FLOAT) * CAST("Qty" AS FLOAT)) as cost_sum,
            0 as "DocumentPkId"
        FROM "OpenDataSale"
        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
        GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
        ORDER BY month
        ''',
        [selected_year]
    ):
        month = int(row.month) if row.month else 0
        print(f"  Month {month}: PayAmount={row.payamount_sum:,.0f}₮")
        sales_data.append(row)
    
    print(f"✓ Found {len(sales_data)} months with sales data")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 2: OpenDataGeneralLedger discount
print("\n2. Testing OpenDataGeneralLedger discount (raw SQL)...")
try:
    discount_data = []
    for row in OpenDataGeneralLedger.objects.raw(
        '''
        SELECT 
            EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
            SUM("DebitAmt") as total,
            "DocumentPkId"
        FROM "OpenDataGeneralLedger"
        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
          AND "AccountId" = '520101'
        GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
        ORDER BY month
        ''',
        [selected_year]
    ):
        month = int(row.month) if row.month else 0
        print(f"  Month {month}: Discount={row.total:,.0f}₮")
        discount_data.append(row)
    
    print(f"✓ Found {len(discount_data)} months with discount data")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 3: OpenDataSaleRefund
print("\n3. Testing OpenDataSaleRefund (raw SQL)...")
try:
    refund_data = []
    for row in OpenDataSaleRefund.objects.raw(
        '''
        SELECT 
            EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
            SUM("PayAmount") as total,
            "DocumentPkId"
        FROM "OpenDataSaleRefund"
        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
        GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
        ORDER BY month
        ''',
        [selected_year]
    ):
        month = int(row.month) if row.month else 0
        print(f"  Month {month}: Refund={row.total:,.0f}₮")
        refund_data.append(row)
    
    print(f"✓ Found {len(refund_data)} months with refund data")
except Exception as e:
    print(f"✗ Error: {e}")

# Test 4: Expense accounts (7-series) with cursor
print("\n4. Testing expense accounts with cursor...")
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
            LIMIT 5
            ''',
            [selected_year]
        )
        expenses = cursor.fetchall()
        
        for row in expenses:
            month, accountid, accountname, total = row
            print(f"  Month {int(month)}, {accountid} ({accountname}): {total:,.0f}₮")
        
        print(f"✓ Found {len(expenses)} expense records")
except Exception as e:
    print(f"✗ Error: {e}")

print("\n" + "=" * 80)
print("All tests completed!")
