"""
Нэме: delivery_report view
"""

@login_required
def delivery_report(request):
    """Түгээлтийн тайлан - OpenDataSaleHeader өгөгдлөөс"""
    from collections import defaultdict
    
    # Огноо фильтр
    date_from_str = request.GET.get('date_from', '')
    date_to_str = request.GET.get('date_to', '')
    seller_filter = request.GET.get('seller', '')
    year_filter = request.GET.get('year', '')
    month_filter = request.GET.get('month', '')
    
    date_from = None
    date_to = None
    
    if date_from_str and date_from_str.strip():
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if date_to_str and date_to_str.strip():
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    # OpenDataSaleHeader QuerySet
    delivery_qs = OpenDataSaleHeader.objects.all()
    
    # Огноогоор шүүх
    if date_from:
        delivery_qs = delivery_qs.filter(documentdate__gte=date_from)
    
    if date_to:
        delivery_qs = delivery_qs.filter(documentdate__lte=date_to)
    
    # Жолоочоор шүүх
    if seller_filter:
        delivery_qs = delivery_qs.filter(sellername__icontains=seller_filter)
    
    # Өдрөөр бүлэглэх - Он-Сар-Өдөр-Жолооч
    daily_data = delivery_qs.extra(
        select={
            'year': "EXTRACT(year FROM \"DocumentDate\")",
            'month': "EXTRACT(month FROM \"DocumentDate\")",
            'day': "EXTRACT(day FROM \"DocumentDate\")"
        }
    ).values('year', 'month', 'day', 'sellername').annotate(
        total_amount=Sum('payamount'),
        total_qty=Sum('deliveryqty'),
        total_orders=Count('documentpkid', distinct=True)
    ).order_by('-year', '-month', '-day', 'sellername')
    
    # Pivot бүтэц: {year: {month: {day: {seller: {...}}}}}
    pivot = defaultdict(lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(dict))))
    
    for row in daily_data:
        year = int(row['year']) if row['year'] else 0
        month = int(row['month']) if row['month'] else 0
        day = int(row['day']) if row['day'] else 0
        seller = row['sellername'] or 'Тодорхойгүй'
        
        if year and month and day:
            pivot[year][month][day][seller] = {
                'amount': row['total_amount'] or 0,
                'qty': row['total_qty'] or 0,
                'orders': row['total_orders'] or 0
            }
            
            # Өдрийн нийлбэр
            if 'day_total' not in pivot[year][month][day]:
                pivot[year][month][day]['day_total'] = {'amount': 0, 'qty': 0, 'orders': 0}
            
            pivot[year][month][day]['day_total']['amount'] += row['total_amount'] or 0
            pivot[year][month][day]['day_total']['qty'] += row['total_qty'] or 0
            pivot[year][month][day]['day_total']['orders'] += row['total_orders'] or 0
    
    # Sorted pivot
    sorted_pivot = {year: dict(sorted(months.items(), reverse=True)) 
                    for year, months in sorted(pivot.items(), reverse=True)}
    
    for year in sorted_pivot:
        for month in sorted_pivot[year]:
            sorted_pivot[year][month] = dict(sorted(sorted_pivot[year][month].items(), reverse=True))
    
    # Жолоочдын жагсаалт
    sellers_list = OpenDataSaleHeader.objects.values_list(
        'sellername', flat=True
    ).distinct().exclude(sellername__isnull=True).exclude(sellername='').order_by('sellername')
    
    # Боломжит жилүүд
    years = delivery_qs.extra(
        select={'year': "EXTRACT(year FROM \"DocumentDate\")"}
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    # Статистик
    stats = delivery_qs.aggregate(
        total_amount=Sum('payamount'),
        total_qty=Sum('deliveryqty'),
        total_orders=Count('documentpkid', distinct=True),
        total_sellers=Count('sellername', distinct=True)
    )
    
    context = {
        'pivot_data': sorted_pivot,
        'sellers': list(sellers_list),
        'years': [int(y) for y in years if y],
        'stats': stats,
        'date_from': date_from_str or '',
        'date_to': date_to_str or '',
        'selected_seller': seller_filter,
        'selected_year': year_filter,
        'selected_month': month_filter,
        'total_records': delivery_qs.count(),
    }
    
    return render(request, 'shop/delivery_report.html', context)
