"""Test expense report query logic"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from datamigration.models import OpenDataSale, OpenDataGeneralLedger, OpenDataSaleRefund
from django.db.models import Sum, FloatField, ExpressionWrapper
from django.db.models.functions import Cast, ExtractYear, ExtractMonth

print("Testing expense report queries...")
print("-" * 80)

# Test 1: Get available years from OpenDataSale
try:
    print("\n1. Getting available years from OpenDataSale...")
    available_years = OpenDataSale.objects.extra(
        select={'year': "EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE))"}
    ).values_list('year', flat=True).distinct().order_by('-year')
    available_years = [int(y) for y in available_years if y][:5]  # First 5 years
    print(f"✓ Available years: {available_years}")
except Exception as e:
    print(f"✗ Error: {e}")

# Test with first year if available
if available_years:
    selected_year = available_years[0]
    print(f"\nTesting with year: {selected_year}")
    print("-" * 80)
    
    # Test 2: Sales by month with new syntax
    try:
        print("\n2. Testing OpenDataSale query (sales by month)...")
        sales_by_month = OpenDataSale.objects.extra(
            select={'month': "EXTRACT(month FROM CAST(\"DocumentDate\" AS DATE))"},
            where=["EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE)) = %s"],
            params=[selected_year]
        ).values('month').annotate(
            payamount_sum=Sum(Cast('payamount', FloatField())),
        )[:3]  # First 3 months
        
        for row in sales_by_month:
            print(f"  Month {row['month']}: {row['payamount_sum']:,.0f}₮")
        print("✓ OpenDataSale query successful")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 3: Discount by month from GeneralLedger
    try:
        print("\n3. Testing OpenDataGeneralLedger query (discount)...")
        discount_by_month = OpenDataGeneralLedger.objects.extra(
            select={'month': "EXTRACT(month FROM CAST(\"DocumentDate\" AS DATE))"},
            where=["EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE)) = %s"],
            params=[selected_year]
        ).filter(
            accountid='520101'
        ).values('month').annotate(
            total=Sum('debitamt')
        )[:3]
        
        count = discount_by_month.count()
        print(f"✓ Found {count} months with discount data")
        for row in discount_by_month:
            print(f"  Month {row['month']}: {row['total']:,.0f}₮")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 4: Refund by month
    try:
        print("\n4. Testing OpenDataSaleRefund query...")
        refund_by_month = OpenDataSaleRefund.objects.extra(
            select={'month': "EXTRACT(month FROM CAST(\"DocumentDate\" AS DATE))"},
            where=["EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE)) = %s"],
            params=[selected_year]
        ).values('month').annotate(
            total=Sum('payamount')
        )[:3]
        
        count = refund_by_month.count()
        print(f"✓ Found {count} months with refund data")
        for row in refund_by_month:
            print(f"  Month {row['month']}: {row['total']:,.0f}₮")
    except Exception as e:
        print(f"✗ Error: {e}")
    
    # Test 5: Expense accounts (7-series)
    try:
        print("\n5. Testing expense accounts (7-series)...")
        expenses_by_month = OpenDataGeneralLedger.objects.extra(
            select={'month': "EXTRACT(month FROM CAST(\"DocumentDate\" AS DATE))"},
            where=["EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE)) = %s"],
            params=[selected_year]
        ).filter(
            accountid__startswith='7'
        ).values('accountid', 'accountname').distinct()[:5]
        
        print(f"✓ Found {len(list(expenses_by_month))} expense accounts")
        for row in expenses_by_month:
            print(f"  {row['accountid']}: {row['accountname']}")
    except Exception as e:
        print(f"✗ Error: {e}")

print("\n" + "=" * 80)
print("All tests completed!")
