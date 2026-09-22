"""
Check OpenDataGeneralLedger structure for debit/credit pairs
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.db import connection

print(f"\n{'='*80}")
print("GENERAL LEDGER STRUCTURE TEST")
print(f"{'='*80}\n")

# Test: Цалингийн зардлын данс (700101)
account_id = '700101'
year = 2024
month = 1

with connection.cursor() as cursor:
    # Жишээ гүйлгээ авах
    cursor.execute('''
        SELECT 
            "DocumentPkId",
            "DocumentNumber",
            CAST("DocumentDate" AS DATE) as date,
            "DocumentDesc",
            "AccountId",
            "AccountName",
            CAST("DebitAmt" AS FLOAT) as debit,
            CAST("CreditAmt" AS FLOAT) as credit
        FROM "OpenDataGeneralLedger"
        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
          AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
          AND "AccountId" = %s
        ORDER BY "DocumentPkId"
        LIMIT 3
    ''', [year, month, account_id])
    
    rows = cursor.fetchall()
    print(f"Found {len(rows)} records for account {account_id} in {year}/{month}\n")
    
    for row in rows:
        doc_pk, doc_num, date, desc, acc_id, acc_name, debit, credit = row
        print(f"DocumentPkId: {doc_pk}")
        print(f"  Date: {date}")
        print(f"  Number: {doc_num}")
        print(f"  Description: {desc[:60] if desc else 'N/A'}")
        print(f"  This line - Account: {acc_id} ({acc_name})")
        print(f"  This line - Debit: {debit:,.0f}  Credit: {credit:,.0f}")
        
        # Find the corresponding line (same DocumentPkId, different AccountId)
        cursor.execute('''
            SELECT 
                "AccountId",
                "AccountName",
                CAST("DebitAmt" AS FLOAT) as debit,
                CAST("CreditAmt" AS FLOAT) as credit
            FROM "OpenDataGeneralLedger"
            WHERE "DocumentPkId" = %s
              AND "AccountId" != %s
        ''', [doc_pk, account_id])
        
        other_rows = cursor.fetchall()
        if other_rows:
            print(f"  Paired lines ({len(other_rows)}):")
            for other_acc_id, other_acc_name, other_debit, other_credit in other_rows:
                print(f"    - Account: {other_acc_id} ({other_acc_name})")
                print(f"      Debit: {other_debit:,.0f}  Credit: {other_credit:,.0f}")
        else:
            print(f"  ⚠️  No paired line found!")
        print()

print(f"{'='*80}\n")
