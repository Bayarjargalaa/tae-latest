"""
Shop app views - E-commerce frontend
"""
from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.urls import reverse
from django.db.models import Sum, Count, Avg, Q, FloatField, DateField, Min, Max, F, ExpressionWrapper
from django.db.models.functions import Cast, TruncDate, ExtractYear, ExtractMonth, ExtractDay
from django.utils import timezone
from datetime import timedelta, datetime
from datamigration.models import OpenDataItem, OpenDataCustomer, OpenDataEmployee, OpenDataSale, OpenDataSaleHeader
from shop.models import ProductExtension
from shop.forms import CustomUserCreationForm


def _attach_base_channel_prices(products):
    """Бүтээгдэхүүн бүрт '001' (Үндсэн үнэ) сувгийн хамгийн сүүлийн огнооны
    үнийг saleprice/baseprice дээр нь бичиж өгнө. Тухайн барааны энэ сувагт
    үнэ бүртгэгдээгүй бол OpenDataItem дээрх анхны утгыг хэвээр үлдээнэ.
    """
    from datamigration.models import OpenDataItemPrice, OpenDataItemPriceChannel

    products = list(products)
    pkids = [p.pkid for p in products if p.pkid]
    if not pkids:
        return products

    base_channel = OpenDataItemPriceChannel.objects.filter(code='001').first()
    if not base_channel:
        return products

    latest_prices = (
        OpenDataItemPrice.objects
        .filter(customerpkid__isnull=True, pricechannelpkid=base_channel.pkid, itempkid__in=pkids)
        .order_by('itempkid', '-pricedate')
        .distinct('itempkid')
    )
    price_map = {p.itempkid: p for p in latest_prices}

    for product in products:
        entry = price_map.get(product.pkid)
        if entry:
            if entry.price is not None:
                product.saleprice = entry.price
            if entry.baseprice is not None:
                product.baseprice = entry.baseprice

    return products


def home(request):
    """Нүүр хуудас - Featured бүтээгдэхүүнүүд"""
    # Ажилтан нэвтэрсэн бол шууд хувийн мэдээлэл рүү нь чиглүүлнэ
    if request.user.is_authenticated and request.user.is_staff:
        return redirect('shop:profile')
    
    # Идэвхтэй бүтээгдэхүүнүүд (эхний 12)
    products = OpenDataItem.objects.filter(activestatus='Y').order_by('-pkid')[:12]
    products = _attach_base_channel_prices(products)

    # ProductExtension холбох
    product_ids = [p.id for p in products]
    extensions = {ext.item_id: ext for ext in ProductExtension.objects.filter(item_id__in=product_ids)}
    
    # Extension нэмэх
    for product in products:
        product.extension = extensions.get(product.id)
    
    # Категориуд (unique)
    categories = OpenDataItem.objects.filter(activestatus='Y').values_list('itemcategoryname', flat=True).distinct()[:12]
    
    context = {
        'products': products,
        'categories': [cat for cat in categories if cat],
    }
    
    return render(request, 'shop/home.html', context)


def product_list(request):
    """Бүтээгдэхүүний жагсаалт (pagination, filter)"""
    products = OpenDataItem.objects.filter(activestatus='Y')
    
    # Id баганаас 8 болон 9-р эхэлсэн бараануудыг харуулах
    from django.db.models import Q
    products = products.filter(
        Q(id__istartswith='8') | Q(id__istartswith='9')
    )
    
    # Агуулах жижигт 10+ үлдэгдэлтэй бараа шүүлт
    # Нэвтрээгүй хэрэглэгчдэд default-оор идэвхтэй
    if request.user.is_authenticated:
        jijig_min_qty = request.GET.get('jijig_min', 'false')
    else:
        jijig_min_qty = request.GET.get('jijig_min', 'true')  # Нэвтрээгүй бол 10+ л харуулах
    
    if jijig_min_qty == 'true':
        from shop.models_inventory import InventorySnapshot
        # InventorySnapshot-с jijig_qty >= 10 байгаа барааны нэрүүдийг авах
        eligible_items = InventorySnapshot.objects.filter(jijig_qty__gte=10).values_list('itemname', flat=True)
        products = products.filter(name__in=eligible_items)
    
    # Category шүүлт
    category = request.GET.get('category')
    if category:
        products = products.filter(itemcategoryname=category)
    
    # Хайлт
    search_query = request.GET.get('q')
    if search_query:
        products = products.filter(name__icontains=search_query)
    
    # Brand шүүлт
    brand = request.GET.get('brand')
    if brand:
        products = products.filter(brandname=brand)
    
    # Pagination
    paginator = Paginator(products, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    page_obj.object_list = _attach_base_channel_prices(page_obj.object_list)

    # ProductExtension холбох
    product_ids = [p.id for p in page_obj]
    extensions = {ext.item_id: ext for ext in ProductExtension.objects.filter(item_id__in=product_ids)}
    
    for product in page_obj:
        product.extension = extensions.get(product.id)
    
    # Filters
    categories = OpenDataItem.objects.filter(activestatus='Y').values_list('itemcategoryname', flat=True).distinct()
    brands = OpenDataItem.objects.filter(activestatus='Y').values_list('brandname', flat=True).distinct()
    
    context = {
        'page_obj': page_obj,
        'categories': [cat for cat in categories if cat],
        'brands': [brand for brand in brands if brand],
        'current_category': category,
        'current_brand': brand,
        'search_query': search_query,
        'jijig_min_qty': jijig_min_qty,
    }
    
    return render(request, 'shop/products.html', context)


def product_detail(request, pk):
    """Бүтээгдэхүүний дэлгэрэнгүй"""
    from django.shortcuts import get_object_or_404
    
    product = get_object_or_404(OpenDataItem, pk=pk)
    _attach_base_channel_prices([product])

    # Extension холбох
    try:
        extension = ProductExtension.objects.get(item_id=product.id)
    except ProductExtension.DoesNotExist:
        extension = None

    product.extension = extension

    # Төстэй бүтээгдэхүүнүүд
    related = OpenDataItem.objects.filter(
        itemcategoryname=product.itemcategoryname,
        activestatus='Y'
    ).exclude(pk=pk)[:4]
    related = _attach_base_channel_prices(related)

    context = {
        'product': product,
        'related_products': related,
    }
    
    return render(request, 'shop/product_detail.html', context)


def product_edit(request, pk):
    """Бүтээгдэхүүний нэмэлт мэдээлэл засах (staff only)"""
    from django.shortcuts import get_object_or_404, redirect
    from django.contrib.admin.views.decorators import staff_member_required
    
    # Staff эрх шалгах
    if not request.user.is_staff:
        return redirect('shop:products')
    
    product = get_object_or_404(OpenDataItem, pk=pk)
    
    # Extension авах эсвэл үүсгэх
    extension, created = ProductExtension.objects.get_or_create(item_id=product.id)
    
    if request.method == 'POST':
        # Form өгөгдөл хадгалах
        extension.name_mn = request.POST.get('name_mn', '').strip()
        extension.country_of_origin = request.POST.get('country_of_origin', '').strip()
        extension.supplier = request.POST.get('supplier', '').strip()
        
        qty = request.POST.get('qty_per_box', '').strip()
        extension.qty_per_box = int(qty) if qty else None
        
        # Зураг хадгалах
        if 'image_main' in request.FILES:
            extension.image_main = request.FILES['image_main']
        
        extension.save()
        
        return redirect('shop:products')
    
    context = {
        'product': product,
        'extension': extension,
    }
    
    return render(request, 'shop/product_edit.html', context)


def register(request):
    """Бүртгүүлэх - OpenDataEmployee имэйл шалгана"""
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            
            # Ажилтан эсэхийг мэдэгдэх
            if user.is_staff:
                from django.contrib import messages
                messages.success(request, f'Тавтай морилно уу, {user.username}! Та ажилтны эрхтэй нэвтэрлээ.')
            else:
                from django.contrib import messages
                messages.info(request, f'Амжилттай бүртгүүллээ, {user.username}!')
            
            return redirect('shop:home')
    else:
        form = CustomUserCreationForm()
    
    return render(request, 'shop/register.html', {'form': form})


@login_required
def dashboard(request):
    """Ажилтны хяналтын самбар (staff only)"""
    # Зөвхөн ажилтанд зөвшөөрөх
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')
    
    # Статистик - "15"-аар эхэлсэн код нь орцны түүхий эд тул жинхэнэ
    # бүтээгдэхүүний тооноос хасна
    from shop.models_inventory import InventorySnapshot

    products_qs = OpenDataItem.objects.exclude(id__istartswith='15')
    total_products = products_qs.count()
    active_products = products_qs.filter(activestatus='Y').count()
    in_stock_products = InventorySnapshot.objects.filter(total_qty__gt=0).count()
    total_customers = OpenDataCustomer.objects.count()
    total_employees = OpenDataEmployee.objects.count()

    context = {
        'total_products': total_products,
        'active_products': active_products,
        'in_stock_products': in_stock_products,
        'total_customers': total_customers,
        'total_employees': total_employees,
    }

    return render(request, 'shop/dashboard.html', context)


@login_required
def sales_report(request):
    """Борлуулалтын тайлан - OpenDataSale өгөгдлөөс"""
    # Зөвхөн ажилтанд зөвшөөрөх
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')
    
    # Tab сонголт (summary, by_product, by_customer, by_date)
    active_tab = request.GET.get('tab', 'summary')
    
    # Шүүлтийн параметрүүд
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    product_filter = request.GET.get('product')
    category_filter = request.GET.get('category')
    customer_filter = request.GET.get('customer')
    brand_filter = request.GET.get('brand')
    year_filter = request.GET.get('year')
    
    # "None" string болон хоосон утгуудыг цэвэрлэх
    def clean_param(value):
        if not value or value.strip() == '' or value.strip().lower() == 'none':
            return None
        return value.strip()
    
    product_filter = clean_param(product_filter)
    category_filter = clean_param(category_filter)
    customer_filter = clean_param(customer_filter)
    brand_filter = clean_param(brand_filter)
    year_filter = clean_param(year_filter)
    
    # Огнооны шүүлт (optional - зааагүй бол БҮХ өгөгдөл)
    date_from = None
    date_to = None
    
    if date_from_str and date_from_str.strip():
        try:
            date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # Буруу формат бол ignore
    
    if date_to_str and date_to_str.strip():
        try:
            date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
        except ValueError:
            pass  # Буруу формат бол ignore
    
    # OpenDataSale QuerySet - БҮХ өгөгдлөөс эхэлнэ
    sales_qs = OpenDataSale.objects.all()
    
    # Огноогоор шүүх (зааасан бол)
    if date_from or date_to:
        sales_qs = sales_qs.annotate(
            date_field=Cast('documentdate', DateField())
        )
        
        if date_from:
            sales_qs = sales_qs.filter(date_field__gte=date_from)
        
        if date_to:
            sales_qs = sales_qs.filter(date_field__lte=date_to)
    
    # =========== TAB-AAR ӨӨРЧЛӨГДӨХ ӨГӨГДӨЛ ===========
    context = {
        'active_tab': active_tab,
        'date_from': date_from_str or '',
        'date_to': date_to_str or '',
        'selected_product': product_filter,
        'selected_category': category_filter,
        'selected_customer': customer_filter,
        'selected_brand': brand_filter,
        'selected_year': year_filter,
    }
    
    if active_tab == 'summary':
        # НЭГТГЭЛ - Pivot хүснэгт (Он-Сар)
        # Summary tab-д зөвхөн огноо/жилээр шүүнэ, бараа/харилцагчаар ШҮҮХГҮЙ
        summary_qs = sales_qs  # Огноогоор шүүлсэн QuerySet ашиглана
        pivot_result = _get_pivot_summary(summary_qs, year_filter)
        context.update({
            'pivot_data': pivot_result['data'],
            'grand_total': pivot_result['grand_total'],
            'available_years': _get_available_years(summary_qs),
        })
        
        # Статистик summary tab-ын QuerySet-ээр
        stats = summary_qs.aggregate(
            total_revenue=Sum(Cast('payamount', FloatField())),
            total_qty=Sum(Cast('qty', FloatField())),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = summary_qs.count()
        
    elif active_tab == 'by_product':
        # БАРААГААР - Барааны дэлгэрэнгүй
        # Энэ tab-д л бараа/харилцагчаар шүүнэ
        product_qs = sales_qs
        
        if product_filter:
            product_qs = product_qs.filter(itemname__icontains=product_filter)
        
        if category_filter:
            category_items = OpenDataItem.objects.filter(
                itemcategoryname=category_filter
            ).values_list('name', flat=True)
            product_qs = product_qs.filter(itemname__in=category_items)
        
        if customer_filter:
            product_qs = product_qs.filter(customername__icontains=customer_filter)
        
        if brand_filter:
            product_qs = product_qs.filter(brandname__icontains=brand_filter)
        
        product_sales = _get_product_analysis(product_qs, product_filter)
        
        # Dropdown lists - Шүүлсэн QuerySet-ээс авна
        # Зөвхөн тухайн огнооны хүрээнд борлуулалттай бараа/харилцагчид
        products_list = sales_qs.values_list(
            'itemname', flat=True
        ).distinct().exclude(itemname__isnull=True).exclude(itemname='').order_by('itemname')
        
        customers_list = sales_qs.values_list(
            'customername', flat=True
        ).distinct().exclude(customername__isnull=True).exclude(customername='').order_by('customername')
        
        context.update({
            'product_sales': product_sales,
            'products': [{'name': p} for p in products_list],  # Template-д product.name ашиглахын тулд dict
            'customers': list(customers_list),
        })
        
        # Статистик тухайн tab-ын шүүлсэн QuerySet-ээр
        stats = product_qs.aggregate(
            total_revenue=Sum(Cast('payamount', FloatField())),
            total_qty=Sum(Cast('qty', FloatField())),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = product_qs.count()
        
    elif active_tab == 'by_customer':
        # ХАРИЛЦАГЧААР - Харилцагчийн дэлгэрэнгүй
        # Энэ tab-д харилцагч/бараагаар шүүнэ
        customer_qs = sales_qs
        
        if customer_filter:
            customer_qs = customer_qs.filter(customername__icontains=customer_filter)
        
        if product_filter:
            customer_qs = customer_qs.filter(itemname__icontains=product_filter)
        
        customer_sales = _get_customer_analysis(customer_qs, customer_filter)
        
        # Dropdown lists - Шүүлсэн QuerySet-ээс авна
        customers_list = sales_qs.values_list(
            'customername', flat=True
        ).distinct().exclude(customername__isnull=True).exclude(customername='').order_by('customername')
        
        products_list = sales_qs.values_list(
            'itemname', flat=True
        ).distinct().exclude(itemname__isnull=True).exclude(itemname='').order_by('itemname')
        
        context.update({
            'customer_sales': customer_sales,
            'customers': list(customers_list),
            'products': [{'name': p} for p in products_list],  # Template-д product.name ашиглахын тулд dict
        })
        
        # Статистик тухайн tab-ын шүүлсэн QuerySet-ээр
        stats = customer_qs.aggregate(
            total_revenue=Sum(Cast('payamount', FloatField())),
            total_qty=Sum(Cast('qty', FloatField())),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = customer_qs.count()
        
    elif active_tab == 'by_date':
        # ОГНООГООР - Өдрийн дэлгэрэнгүй
        # Энэ tab-д зөвхөн огноогоор шүүнэ (нэмэлт шүүлт байхгүй)
        date_qs = sales_qs
        daily_sales = _get_daily_analysis(date_qs)
        context.update({
            'daily_sales': daily_sales,
        })
        
        # Статистик тухайн tab-ын QuerySet-ээр
        stats = date_qs.aggregate(
            total_revenue=Sum(Cast('payamount', FloatField())),
            total_qty=Sum(Cast('qty', FloatField())),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = date_qs.count()
    
    # Хэрэв stats байхгүй бол (буруу tab утга) үндсэн статистик оруулах
    if 'stats' not in context:
        stats = sales_qs.aggregate(
            total_revenue=Sum(Cast('payamount', FloatField())),
            total_qty=Sum(Cast('qty', FloatField())),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = sales_qs.count()
    
    # БҮХ датаны огнооны хүрээ (summary tab-д харуулах)
    all_data = OpenDataSale.objects.all()
    date_range = all_data.aggregate(
        earliest=Min(Cast('documentdate', DateField())),
        latest=Max(Cast('documentdate', DateField())),
    )
    context['earliest_date'] = date_range.get('earliest')
    context['latest_date'] = date_range.get('latest')
    context['all_records_count'] = all_data.count()
    
    return render(request, 'shop/sales_report.html', context)


def _get_pivot_summary(sales_qs, selected_year=None):
    """Он-Сараар нэгтгэсэн pivot хүснэгт"""
    from collections import defaultdict
    
    # Он-Сар бүрээр group хийх
    monthly_data = sales_qs.extra(
        select={'year': "EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE))",
                'month': "EXTRACT(month FROM CAST(\"DocumentDate\" AS DATE))"}
    ).values('year', 'month').annotate(
        revenue=Sum(Cast('payamount', FloatField())),  # Орлого - PayAmount
        amountnonvat_sum=Sum(Cast('amountnonvat', FloatField())),  # НӨАТ-гүй дүн
        total_cost=Sum(
            ExpressionWrapper(
                Cast('unitcost', FloatField()) * Cast('qty', FloatField()),
                output_field=FloatField()
            )
        ),
        orders=Count('documentpkid', distinct=True),
        customers=Count('customername', distinct=True),
        qty=Sum(Cast('qty', FloatField()))
    ).order_by('-year', 'month')
    
    # Жилүүдээр бүлэглэх
    pivot = defaultdict(lambda: {'months': {}, 'total': 0, 'total_orders': 0, 'total_qty': 0, 'total_cost': 0, 'total_profit': 0, 'total_customers': 0})
    
    for row in monthly_data:
        year = int(row['year']) if row['year'] else 0
        month = int(row['month']) if row['month'] else 0
        revenue = row['revenue'] or 0
        amountnonvat = row['amountnonvat_sum'] or 0
        cost = row['total_cost'] or 0
        profit = amountnonvat - cost  # Ашиг = AmountNonVat - (UnitCost × Qty)
        orders = row['orders'] or 0
        customers = row['customers'] or 0
        qty = row['qty'] or 0
        
        if year and month:
            pivot[year]['months'][month] = {
                'revenue': revenue,
                'cost': cost,
                'profit': profit,
                'orders': orders,
                'customers': customers,
                'qty': qty,
            }
            pivot[year]['total'] += revenue
            pivot[year]['total_orders'] += orders
            pivot[year]['total_qty'] += qty
            pivot[year]['total_cost'] += cost
            pivot[year]['total_profit'] += profit
    
    # Sorted by year ASCENDING (2021 -> 2026) and months 1-12
    sorted_pivot = dict(sorted(pivot.items(), reverse=False))
    
    # Сар бүрийг эрэмбэлэх (1-12)
    for year_data in sorted_pivot.values():
        year_data['months'] = dict(sorted(year_data['months'].items()))
    
    # Жил бүрийн давхардаагүй харилцагчийн тоог тооцоолох
    for year in sorted_pivot.keys():
        # Жил бүрт тусдаа query хийж давхардаагүй харилцагчийг тооцоолно
        year_start = f"{year}-01-01"
        year_end = f"{year}-12-31"
        year_customers = sales_qs.annotate(
            date_field=Cast('documentdate', DateField())
        ).filter(
            date_field__gte=year_start,
            date_field__lte=year_end
        ).aggregate(
            customers=Count('customername', distinct=True)
        )['customers'] or 0
        sorted_pivot[year]['total_customers'] = year_customers
    
    # Grand Total тооцоолох (бүх жилүүдийн нийлбэр)
    # Харилцагчийн тоо - бүх датаны давхардаагүй харилцагч
    all_customers = sales_qs.aggregate(total_customers=Count('customername', distinct=True))['total_customers'] or 0
    
    grand_total = {
        'revenue': sum(y['total'] for y in sorted_pivot.values()),
        'cost': sum(y['total_cost'] for y in sorted_pivot.values()),
        'profit': sum(y['total_profit'] for y in sorted_pivot.values()),
        'orders': sum(y['total_orders'] for y in sorted_pivot.values()),
        'customers': all_customers,
        'qty': sum(y['total_qty'] for y in sorted_pivot.values()),
    }
    
    # Filter by selected year
    if selected_year:
        try:
            year_int = int(selected_year)
            if year_int in sorted_pivot:
                sorted_pivot = {year_int: sorted_pivot[year_int]}
                # Нэг жил сонгосон бол grand total тэр жилийн дүн
                grand_total = {
                    'revenue': sorted_pivot[year_int]['total'],
                    'cost': sorted_pivot[year_int]['total_cost'],
                    'profit': sorted_pivot[year_int]['total_profit'],
                    'orders': sorted_pivot[year_int]['total_orders'],
                    'customers': sorted_pivot[year_int]['total_customers'],
                    'qty': sorted_pivot[year_int]['total_qty'],
                }
            else:
                sorted_pivot = {}
                grand_total = {'revenue': 0, 'cost': 0, 'profit': 0, 'orders': 0, 'customers': 0, 'qty': 0}
        except ValueError:
            pass
    
    return {'data': sorted_pivot, 'grand_total': grand_total}


def _get_available_years(sales_qs):
    """Боломжит жилүүдийг авах"""
    years = sales_qs.extra(
        select={'year': "EXTRACT(year FROM CAST(\"DocumentDate\" AS DATE))"}
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    return [int(y) for y in years if y]


def _get_product_analysis(sales_qs, product_name=None):
    """Барааны дэлгэрэнгүй шинжилгээ"""
    if product_name:
        sales_qs = sales_qs.filter(itemname__icontains=product_name)
    
    product_stats = sales_qs.values('itemname', 'brandname').annotate(
        revenue=Sum(Cast('payamount', FloatField())),
        qty=Sum(Cast('qty', FloatField())),
        orders=Count('documentpkid', distinct=True),
        customers=Count('customername', distinct=True)
    ).order_by('-revenue')
    
    return product_stats


def _get_customer_analysis(sales_qs, customer_name=None):
    """Харилцагчийн дэлгэрэнгүй шинжилгээ"""
    if customer_name:
        sales_qs = sales_qs.filter(customername__icontains=customer_name)
    
    customer_stats = sales_qs.values('customername').annotate(
        revenue=Sum(Cast('payamount', FloatField())),
        qty=Sum(Cast('qty', FloatField())),
        orders=Count('documentpkid', distinct=True),
        products=Count('itemname', distinct=True)
    ).order_by('-revenue')
    
    return customer_stats


def _get_daily_analysis(sales_qs):
    """Өдрийн дэлгэрэнгүй шинжилгээ"""
    daily_stats = sales_qs.values('documentdate').annotate(
        revenue=Sum(Cast('payamount', FloatField())),
        orders=Count('documentpkid', distinct=True),
        qty=Sum(Cast('qty', FloatField()))
    ).order_by('-documentdate')[:60]
    
    return daily_stats
    
    # =========== СТАТИСТИК ТООЦООЛОЛ ===========
    # Cast text fields to numeric for aggregation
    stats = sales_qs.aggregate(
        total_revenue=Sum(Cast('payamount', FloatField())),
        total_qty=Sum(Cast('qty', FloatField())),
        total_orders=Count('documentpkid', distinct=True),
        avg_order_value=Avg(Cast('payamount', FloatField()))
    )
    
    # Өдөр тутмын борлуулалт (сүүлийн 7 хоног)
    daily_sales = sales_qs.values('documentdate').annotate(
        revenue=Sum(Cast('payamount', FloatField())),
        orders=Count('documentpkid', distinct=True)
    ).order_by('-documentdate')[:7]
    
    # Шилдэг бүтээгдэхүүн (top 10)
    top_products = sales_qs.values('itemname', 'brandname').annotate(
        quantity=Sum(Cast('qty', FloatField())),
        revenue=Sum(Cast('payamount', FloatField()))
    ).order_by('-revenue')[:10]
    
    # Шилдэг харилцагчид (top 10)
    top_customers = sales_qs.values('customername').annotate(
        orders=Count('documentpkid', distinct=True),
        revenue=Sum(Cast('payamount', FloatField()))
    ).order_by('-revenue')[:10]
    
    # Сүүлийн борлуулалтууд (дэлгэрэнгүй жагсаалт - pagination)
    recent_sales = sales_qs.order_by('-documentdate', '-createddate')
    paginator = Paginator(recent_sales, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Шүүлтүүдэд зориулсан жагсаалтууд
    products = OpenDataItem.objects.filter(activestatus='Y').order_by('name')[:200]
    categories = OpenDataItem.objects.filter(activestatus='Y').values_list('itemcategoryname', flat=True).distinct()
    brands = sales_qs.values_list('brandname', flat=True).distinct()[:50]
    customers = sales_qs.values_list('customername', flat=True).distinct()[:50]
    
    # Дата бэлтгэх
    sales_data = {
        'total_revenue': stats['total_revenue'] or 0,
        'total_orders': stats['total_orders'] or 0,
        'total_items_sold': stats['total_qty'] or 0,
        'avg_order_value': stats['avg_order_value'] or 0,
        'top_products': top_products,
        'top_customers': top_customers,
        'daily_sales': list(reversed(daily_sales)),  # Эхнээс нь харуулах
    }
    
    context = {
        'date_from': date_from_str,
        'date_to': date_to_str,
        'products': products,
        'categories': [cat for cat in categories if cat],
        'brands': [brand for brand in brands if brand],
        'customers': [cust for cust in customers if cust],
        'selected_product': product_filter,
        'selected_category': category_filter,
        'selected_customer': customer_filter,
        'selected_brand': brand_filter,
        'sales_data': sales_data,
        'page_obj': page_obj,
        'is_demo': False,  # Бодит өгөгдөл
        'total_records': sales_qs.count(),
    }
    
    return render(request, 'shop/sales_report.html', context)


def inventory_report(request):
    """Барааны үлдэгдэл - InventorySnapshot хүснэгтээс (2 цаг тутамд шинэчлэгддэг)"""
    # Зөвхөн ажилтанд зөвшөөрөх
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')
    
    from shop.models_inventory import InventorySnapshot
    from django.db.models import Q
    from django.core.paginator import Paginator
    
    # Шүүлтийн параметрүүд
    warehouse_filter = request.GET.get('warehouse')
    product_filter = request.GET.get('product')
    brand_filter = request.GET.get('brand')
    show_stock_only = request.GET.get('stock_only', 'true')  # Default: үлдэгдэлтэй л харуулах
    jijig_min_qty = request.GET.get('jijig_min', 'false')  # Агуулах жижигт 10+ үлдэгдэлтэй
    
    # "None" болон хоосон утгуудыг цэвэрлэх
    def clean_param(value):
        if not value or value.strip() == '' or value.strip().lower() == 'none':
            return None
        return value.strip()
    
    warehouse_filter = clean_param(warehouse_filter)
    product_filter = clean_param(product_filter)
    brand_filter = clean_param(brand_filter)
    
    # Snapshot-с өгөгдөл авах (их хурдан!)
    inventory_qs = InventorySnapshot.objects.all()
    
    # Үлдэгдэлтэй барааг л харуулах эсэх
    if show_stock_only == 'true':
        inventory_qs = inventory_qs.filter(total_qty__gt=0)
    
    # Агуулах жижигт 10+ үлдэгдэлтэй шүүлт
    if jijig_min_qty == 'true':
        inventory_qs = inventory_qs.filter(jijig_qty__gte=10)
    
    # Шүүлт хэрэглэх
    if product_filter:
        inventory_qs = inventory_qs.filter(itemname__icontains=product_filter)
    
    if brand_filter:
        inventory_qs = inventory_qs.filter(brandname__icontains=brand_filter)
    
    # Нэрээр эрэмбэлэх (A → Z)
    inventory_qs = inventory_qs.order_by('itemname')
    
    # Агуулахаар шүүх (үлдэгдэлтэй агуулахаар)
    if warehouse_filter:
        if warehouse_filter == 'Агуулах Толгойт':
            inventory_qs = inventory_qs.filter(tolgoit_qty__gt=0)
        elif warehouse_filter == 'Агуулах жижиг':
            inventory_qs = inventory_qs.filter(jijig_qty__gt=0)
        elif warehouse_filter == 'Агуулах алтжин':
            inventory_qs = inventory_qs.filter(altjin_qty__gt=0)
    
    # Pagination (50 items per page)
    paginator = Paginator(inventory_qs, 50)
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)
    
    # Dropdown жагсаалтууд
    target_warehouses = ['Агуулах Толгойт', 'Агуулах жижиг', 'Агуулах алтжин']
    
    # Dropdown-д хэт олон зүйл ачаалахгүйн тулд limit
    all_snapshots = InventorySnapshot.objects.all()
    if product_filter:
        all_snapshots = all_snapshots.filter(itemname__icontains=product_filter)
    if brand_filter:
        all_snapshots = all_snapshots.filter(brandname__icontains=brand_filter)
    
    products_list = all_snapshots.values_list('itemname', flat=True).distinct().order_by('itemname')[:500]
    brands_list = all_snapshots.values_list('brandname', flat=True).distinct().exclude(
        brandname__isnull=True
    ).exclude(brandname='').order_by('brandname')[:100]
    
    # Template-д илгээх өгөгдлийг бэлтгэх
    inventory_data = []
    for snapshot in page_obj:
        inventory_data.append({
            'itemname': snapshot.itemname,
            'brandname': snapshot.brandname or '-',
            'warehouses': {
                'Агуулах Толгойт': {
                    'endqty': float(snapshot.tolgoit_qty),
                    'date': snapshot.tolgoit_date
                },
                'Агуулах жижиг': {
                    'endqty': float(snapshot.jijig_qty),
                    'date': snapshot.jijig_date
                },
                'Агуулах алтжин': {
                    'endqty': float(snapshot.altjin_qty),
                    'date': snapshot.altjin_date
                }
            },
            'total_qty': float(snapshot.total_qty)
        })
    
    # Сүүлийн шинэчлэлтийн огноо
    latest_update = InventorySnapshot.objects.order_by('-updated_at').first()
    last_updated = latest_update.updated_at if latest_update else None
    
    context = {
        'inventory_data': inventory_data,
        'page_obj': page_obj,
        'target_warehouses': target_warehouses,
        'warehouses_list': target_warehouses,
        'products_list': [{'name': p} for p in products_list],
        'brands_list': list(brands_list),
        'selected_warehouse': warehouse_filter,
        'selected_product': product_filter,
        'selected_brand': brand_filter,
        'show_stock_only': show_stock_only,  # Үлдэгдэлтэй барааг л харуулах эсэх
        'jijig_min_qty': jijig_min_qty,  # Агуулах жижигт 10+ үлдэгдэл
        'total_items': inventory_qs.count(),
        'last_updated': last_updated,  # Сүүлийн шинэчлэлт
    }
    
    return render(request, 'shop/inventory.html', context)


def _get_item_price_data(request):
    """Барааны үнийн хуудасны шүүлт/тооцооллыг хийнэ. HTML харагдац болон Excel
    экспорт хоёулаа энэ функцийг ашиглаж, ижил дүрмээр өгөгдлөө бэлдэнэ."""
    from datamigration.models import OpenDataItem, OpenDataItemPrice, OpenDataItemPriceChannel

    search_query = request.GET.get('q', '').strip()
    stock_only = request.GET.get('stock_only') == 'true'
    below_base_only = request.GET.get('below_base_only') == 'true'
    show_all = request.GET.get('show_all') == 'true'
    selected_channel_pkids = [c for c in request.GET.getlist('channel') if c]

    # Суваг тус бүрийг кодоор нь эрэмбэлж авна (жиш: '001' = Үндсэн үнэ эхэнд орно)
    all_channels = list(OpenDataItemPriceChannel.objects.all().order_by('code'))
    if selected_channel_pkids:
        channels = [c for c in all_channels if str(c.pkid) in selected_channel_pkids]
    else:
        channels = all_channels
    channel_pkids = [c.pkid for c in channels]

    base_channel = next((c for c in all_channels if c.code == '001'), None)

    # Item+суваг хослол бүрийн хамгийн сүүлийн огнооны үнийг нэг query-ээр авна
    # (Postgres-ийн DISTINCT ON). Хэрэглэгч тусгайлсан үнэ (customerpkid) биш,
    # ерөнхий сувгийн үнийг л авна. Зөвхөн сонгосон (эсвэл бүх) сувгаар шүүнэ.
    latest_prices = (
        OpenDataItemPrice.objects
        .filter(customerpkid__isnull=True, pricechannelpkid__in=channel_pkids)
        .order_by('itempkid', 'pricechannelpkid', '-pricedate')
        .distinct('itempkid', 'pricechannelpkid')
    )

    price_map = {}
    item_pks_with_price = set()
    for p in latest_prices:
        price_map.setdefault(p.itempkid, {})[p.pricechannelpkid] = p.price
        item_pks_with_price.add(p.itempkid)

    # 001 (Үндсэн үнэ) сувгийн үнийг харьцуулалтад ашиглах зорилгоор, тухайн
    # суваг харагдаж буй баганад ороогүй ч гэсэн тусад нь авна
    base_price_map = {}
    if base_channel:
        base_prices_qs = (
            OpenDataItemPrice.objects
            .filter(customerpkid__isnull=True, pricechannelpkid=base_channel.pkid)
            .order_by('itempkid', '-pricedate')
            .distinct('itempkid')
        )
        base_price_map = {p.itempkid: p.price for p in base_prices_qs}

    def is_cell_below_base(ch, value, base_price):
        return (
            base_price is not None and value is not None
            and (not base_channel or ch.pkid != base_channel.pkid)
            and value < base_price
        )

    # Аль барааны ядаж нэг сувагт үнэ нь үндсэн үнээс доогуур болохыг тодорхойлно
    below_base_item_pks = set()
    for itempkid, channel_prices in price_map.items():
        base_price = base_price_map.get(itempkid)
        if base_price is None:
            continue
        for ch in channels:
            if is_cell_below_base(ch, channel_prices.get(ch.pkid), base_price):
                below_base_item_pks.add(itempkid)
                break

    items_qs = OpenDataItem.objects.filter(pkid__in=item_pks_with_price)
    if search_query:
        items_qs = items_qs.filter(name__icontains=search_query)
    if stock_only:
        from shop.models_inventory import InventorySnapshot
        in_stock_names = InventorySnapshot.objects.filter(total_qty__gt=0).values_list('itemname', flat=True)
        items_qs = items_qs.filter(name__in=in_stock_names)
    if below_base_only:
        items_qs = items_qs.filter(pkid__in=below_base_item_pks)
    items_qs = items_qs.order_by('name')

    def build_rows(items_iterable):
        rows = []
        for item in items_iterable:
            item_prices_by_channel = price_map.get(item.pkid, {})
            base_price = base_price_map.get(item.pkid)
            cells = []
            for ch in channels:
                value = item_prices_by_channel.get(ch.pkid)
                cells.append({'value': value, 'is_below_base': is_cell_below_base(ch, value, base_price)})
            rows.append({'item': item, 'cells': cells, 'base_price': base_price})
        return rows

    return {
        'search_query': search_query,
        'stock_only': stock_only,
        'below_base_only': below_base_only,
        'show_all': show_all,
        'selected_channel_pkids': selected_channel_pkids,
        'all_channels': all_channels,
        'channels': channels,
        'items_qs': items_qs,
        'build_rows': build_rows,
    }


def item_prices(request):
    """Барааны үнэ - OpenDataItemPrice + OpenDataItemPriceChannel-ээс.

    Мөр = бараа, багана = үнийн жагсаалт/суваг (кодоор эрэмбэлсэн), утга =
    тухайн бараа/сувгийн хамгийн сүүлийн огнооны үнэ.
    """
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    data = _get_item_price_data(request)
    items_qs = data['items_qs']

    page_obj = None
    if data['show_all']:
        display_items = items_qs
    else:
        from django.core.paginator import Paginator
        paginator = Paginator(items_qs, 50)
        page_obj = paginator.get_page(request.GET.get('page', 1))
        display_items = page_obj

    rows = data['build_rows'](display_items)

    querystring = request.GET.copy()
    querystring.pop('page', None)

    context = {
        'all_channels': data['all_channels'],
        'channels': data['channels'],
        'selected_channel_pkids': data['selected_channel_pkids'],
        'stock_only': data['stock_only'],
        'below_base_only': data['below_base_only'],
        'show_all': data['show_all'],
        'rows': rows,
        'page_obj': page_obj,
        'search_query': data['search_query'],
        'total_items': items_qs.count(),
        'querystring': querystring.urlencode(),
    }
    return render(request, 'shop/item_prices.html', context)


def item_prices_export(request):
    """Барааны үнийн хуудасны идэвхтэй шүүлтийг Excel (.xlsx) файлаар татаж авна.
    Үндсэн үнээс доогуур мөрүүдийг улаанаар тэмдэглэнэ."""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from django.http import HttpResponse

    data = _get_item_price_data(request)
    channels = data['channels']
    rows = data['build_rows'](data['items_qs'])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Барааны үнэ'

    header_font = Font(bold=True)
    red_fill = PatternFill(start_color='FFCDD2', end_color='FFCDD2', fill_type='solid')

    ws.cell(row=1, column=1, value='Бараа').font = header_font
    for col_idx, ch in enumerate(channels, start=2):
        cell = ws.cell(row=1, column=col_idx, value=f"{ch.code} - {ch.name}")
        cell.font = header_font
        cell.alignment = Alignment(horizontal='right', wrap_text=True)

    for row_idx, row in enumerate(rows, start=2):
        ws.cell(row=row_idx, column=1, value=row['item'].name)
        for col_idx, cell_data in enumerate(row['cells'], start=2):
            cell = ws.cell(row=row_idx, column=col_idx, value=cell_data['value'])
            if cell_data['is_below_base']:
                cell.fill = red_fill

    ws.column_dimensions['A'].width = 42
    for col_idx in range(2, len(channels) + 2):
        ws.column_dimensions[get_column_letter(col_idx)].width = 14
    ws.freeze_panes = 'B2'

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = 'attachment; filename="item_prices.xlsx"'
    return response


def purchase_report(request):
    """Татан авалтын тайлан - OpenDataLandedCost өгөгдлөөс (Pivot: Он-Сар-Харилцагч-Бараа-Өдөр)"""
    # Зөвхөн ажилтанд зөвшөөрөх
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')
    
    from datamigration.models import OpenDataLandedCost
    
    # Tab сонголт (summary, by_vendor, by_item, by_date)
    active_tab = request.GET.get('tab', 'summary')
    
    # Шүүлтийн параметрүүд
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    vendor_filter = request.GET.get('vendor')
    item_filter = request.GET.get('item')
    brand_filter = request.GET.get('brand')
    year_filter = request.GET.get('year')
    
    # "None" string болон хоосон утгуудыг цэвэрлэх
    def clean_param(value):
        if not value or value.strip() == '' or value.strip().lower() == 'none':
            return None
        return value.strip()
    
    vendor_filter = clean_param(vendor_filter)
    item_filter = clean_param(item_filter)
    brand_filter = clean_param(brand_filter)
    year_filter = clean_param(year_filter)
    
    # Огнооны шүүлт
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
    
    # OpenDataLandedCost QuerySet - БҮХ өгөгдлөөс эхэлнэ
    purchase_qs = OpenDataLandedCost.objects.all()
    
    # Огноогоор шүүх
    if date_from:
        purchase_qs = purchase_qs.filter(documentdate__gte=date_from)
    
    if date_to:
        purchase_qs = purchase_qs.filter(documentdate__lte=date_to)
    
    context = {
        'active_tab': active_tab,
        'date_from': date_from_str or '',
        'date_to': date_to_str or '',
        'selected_vendor': vendor_filter,
        'selected_item': item_filter,
        'selected_brand': brand_filter,
        'selected_year': year_filter,
    }
    
    if active_tab == 'summary':
        # НЭГТГЭЛ - Pivot хүснэгт (Харилцагч->Бараа->Он->Сар->Өдөр)
        summary_qs = purchase_qs
        pivot_result = _get_purchase_pivot_summary(summary_qs, year_filter)
        context.update({
            'pivot_data': pivot_result['data'],
            'grand_total': pivot_result['grand_total'],
        })
        
        # Статистик - TEXT талбаруудыг CAST хийж тооцоолох
        from django.db.models.functions import Cast
        from django.db.models import FloatField
        
        stats = summary_qs.annotate(
            qty_float=Cast('qty', FloatField()),
            price_float=Cast('price', FloatField()),
            amount_float=Cast('itemamountfc', FloatField())
        ).aggregate(
            total_qty=Sum('qty_float'),
            total_price=Avg('price_float'),
            total_amount=Sum('amount_float'),
            total_orders=Count('documentpkid', distinct=True),
            total_vendors=Count('vendorname', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = summary_qs.count()
        
    elif active_tab == 'by_vendor':
        # ХАРИЛЦАГЧААР (Vendor)
        vendor_qs = purchase_qs
        
        if vendor_filter:
            vendor_qs = vendor_qs.filter(vendorname__icontains=vendor_filter)
        
        if item_filter:
            vendor_qs = vendor_qs.filter(itemname__icontains=item_filter)
        
        vendor_analysis = _get_vendor_analysis(vendor_qs)
        
        # Dropdown lists
        vendors_list = purchase_qs.values_list(
            'vendorname', flat=True
        ).distinct().exclude(vendorname__isnull=True).exclude(vendorname='').order_by('vendorname')
        
        items_list = purchase_qs.values_list(
            'itemname', flat=True
        ).distinct().exclude(itemname__isnull=True).exclude(itemname='').order_by('itemname')
        
        context.update({
            'vendor_analysis': vendor_analysis,
            'vendors': list(vendors_list),
            'items': [{'name': i} for i in items_list],
        })
        
        # Статистик
        stats = vendor_qs.aggregate(
            total_qty=Sum('qty'),
            total_price=Avg('price'),
            total_amount=Sum('itemamountfc'),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = vendor_qs.count()
        
    elif active_tab == 'by_item':
        # БАРААГААР
        item_qs = purchase_qs
        
        if item_filter:
            item_qs = item_qs.filter(itemname__icontains=item_filter)
        
        if vendor_filter:
            item_qs = item_qs.filter(vendorname__icontains=vendor_filter)
        
        item_analysis = _get_item_analysis(item_qs)
        
        # Dropdown lists
        items_list = purchase_qs.values_list(
            'itemname', flat=True
        ).distinct().exclude(itemname__isnull=True).exclude(itemname='').order_by('itemname')
        
        vendors_list = purchase_qs.values_list(
            'vendorname', flat=True
        ).distinct().exclude(vendorname__isnull=True).exclude(vendorname='').order_by('vendorname')
        
        context.update({
            'item_analysis': item_analysis,
            'items': [{'name': i} for i in items_list],
            'vendors': list(vendors_list),
        })
        
        # Статистик
        stats = item_qs.aggregate(
            total_qty=Sum('qty'),
            total_price=Avg('price'),
            total_amount=Sum('itemamountfc'),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = item_qs.count()
        
    elif active_tab == 'by_date':
        # ӨДРӨӨР
        date_qs = purchase_qs
        
        date_analysis = _get_purchase_date_analysis(date_qs)
        
        # Статистик
        stats = date_qs.aggregate(
            total_qty=Sum('qty'),
            total_price=Avg('price'),
            total_amount=Sum('itemamountfc'),
            total_orders=Count('documentpkid', distinct=True),
        )
        context['stats'] = stats
        context['total_records'] = date_qs.count()
        
        context['date_analysis'] = date_analysis
    
    return render(request, 'shop/purchase_report.html', context)


# ========== HELPER FUNCTIONS - Purchase Report ==========

def _get_purchase_pivot_summary(purchase_qs, selected_year=None):
    """Харилцагч->Бараа->Он->Сар->Өдөр бүтэцтэй pivot хүснэгт"""
    from collections import defaultdict
    from datetime import datetime
    
    # БҮХ өгөгдлийг авах (зөвхөн шаардлагатай талбаруудыг)
    all_data = purchase_qs.values(
        'vendorname', 'itemname', 'documentdate', 
        'qty', 'price', 'itemamountfc', 'documentpkid'
    ).order_by('vendorname', 'itemname', 'documentdate')
    
    # Nested dictionary бүтэц: vendor -> item -> year -> month -> day
    pivot = defaultdict(lambda: {
        'items': defaultdict(lambda: {
            'years': defaultdict(lambda: {
                'months': defaultdict(lambda: {
                    'days': defaultdict(lambda: {
                        'qty': 0,
                        'price': 0,
                        'amount': 0,
                        'orders': set()
                    }),
                    'total_qty': 0,
                    'total_price': 0,
                    'total_amount': 0,
                    'total_orders': 0
                }),
                'total_qty': 0,
                'total_price': 0,
                'total_amount': 0,
                'total_orders': 0
            }),
            'total_qty': 0,
            'total_price': 0,
            'total_amount': 0,
            'total_orders': 0
        }),
        'total_qty': 0,
        'total_price': 0,
        'total_amount': 0,
        'total_orders': 0
    })
    
    # Өгөгдлийг бүлэглэх
    for row in all_data:
        vendor = row['vendorname'] or 'Тодорхойгүй'
        item = row['itemname'] or 'Тодорхойгүй'
        date = row['documentdate']
        
        # Type conversion - датабазаас string ирж магадгүй
        try:
            qty = float(row['qty']) if row['qty'] else 0
        except (ValueError, TypeError):
            qty = 0
            
        try:
            price = float(row['price']) if row['price'] else 0
        except (ValueError, TypeError):
            price = 0
            
        try:
            amount = float(row['itemamountfc']) if row['itemamountfc'] else 0
        except (ValueError, TypeError):
            amount = 0
            
        order_id = row['documentpkid']
        
        if not date:
            continue
        
        # Хэрэв date string бол date object болгох
        if isinstance(date, str):
            try:
                date = datetime.strptime(date, '%Y-%m-%d').date()
            except:
                continue
        
        year = date.year
        month = date.month
        day = date.day
        
        # Харилцагчийн items доторх item
        item_data = pivot[vendor]['items'][item]
        year_data = item_data['years'][year]
        month_data = year_data['months'][month]
        day_data = month_data['days'][day]
        
        # Өдрийн өгөгдөл
        day_data['qty'] += qty
        day_data['price'] = price  # Хамгийн сүүлийн үнэ
        day_data['amount'] += amount
        day_data['orders'].add(order_id)
        
        # Сарын нийлбэр
        month_data['total_qty'] += qty
        month_data['total_price'] = price  # Хамгийн сүүлийн үнэ
        month_data['total_amount'] += amount
        if order_id:
            month_data['total_orders'] = len([d['orders'] for d in month_data['days'].values()])
        
        # Оны нийлбэр
        year_data['total_qty'] += qty
        year_data['total_price'] = price
        year_data['total_amount'] += amount
        
        # Барааны нийлбэр
        item_data['total_qty'] += qty
        item_data['total_price'] = price
        item_data['total_amount'] += amount
        
        # Харилцагчийн нийлбэр
        pivot[vendor]['total_qty'] += qty
        pivot[vendor]['total_price'] = price
        pivot[vendor]['total_amount'] += amount
    
    # Dict-рүү хөрвүүлэх
    result = {}
    for vendor, vendor_data in sorted(pivot.items()):
        result[vendor] = {
            'total_qty': vendor_data['total_qty'],
            'total_price': vendor_data['total_price'],
            'total_amount': vendor_data['total_amount'],
            'items': {}
        }
        
        for item, item_data in sorted(vendor_data['items'].items()):
            result[vendor]['items'][item] = {
                'total_qty': item_data['total_qty'],
                'total_price': item_data['total_price'],
                'total_amount': item_data['total_amount'],
                'years': {}
            }
            
            for year, year_data in sorted(item_data['years'].items(), reverse=True):
                result[vendor]['items'][item]['years'][year] = {
                    'total_qty': year_data['total_qty'],
                    'total_price': year_data['total_price'],
                    'total_amount': year_data['total_amount'],
                    'months': {}
                }
                
                for month, month_data in sorted(year_data['months'].items()):
                    result[vendor]['items'][item]['years'][year]['months'][month] = {
                        'total_qty': month_data['total_qty'],
                        'total_price': month_data['total_price'],
                        'total_amount': month_data['total_amount'],
                        'days': dict(sorted(month_data['days'].items()))
                    }
                    
                    # Өдрийн orders set-ийг тоо болгох
                    for day, day_data in result[vendor]['items'][item]['years'][year]['months'][month]['days'].items():
                        day_data['orders'] = len(day_data['orders']) if day_data['orders'] else 0
    
    # Grand total
    grand_total = {
        'total_qty': sum(v['total_qty'] for v in result.values()),
        'total_price': sum(v['total_price'] for v in result.values()) / len(result) if result else 0,  # Дундаж үнэ
        'total_amount': sum(v['total_amount'] for v in result.values()),
    }
    
    return {'data': result, 'grand_total': grand_total}


def _get_purchase_available_years(purchase_qs):
    """Боломжит жилүүдийг авах"""
    years = purchase_qs.extra(
        select={'year': "EXTRACT(year FROM \"DocumentDate\")"}
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    return [int(y) for y in years if y]


def _get_vendor_analysis(purchase_qs):
    """Харилцагчийн (vendor) дэлгэрэнгүй шинжилгээ"""
    from django.db.models.functions import Cast
    from django.db.models import FloatField
    
    vendor_stats = purchase_qs.annotate(
        qty_float=Cast('qty', FloatField()),
        price_float=Cast('price', FloatField()),
        amount_float=Cast('itemamountfc', FloatField())
    ).values('vendorname').annotate(
        total_qty=Sum('qty_float'),
        total_price=Avg('price_float'),
        total_amount=Sum('amount_float'),
        orders=Count('documentpkid', distinct=True),
        items=Count('itemname', distinct=True)
    ).order_by('-total_amount')
    
    return vendor_stats


def _get_item_analysis(purchase_qs):
    """Барааны дэлгэрэнгүй шинжилгээ"""
    from django.db.models.functions import Cast
    from django.db.models import FloatField
    
    item_stats = purchase_qs.annotate(
        qty_float=Cast('qty', FloatField()),
        price_float=Cast('price', FloatField()),
        amount_float=Cast('itemamountfc', FloatField())
    ).values('itemname').annotate(
        total_qty=Sum('qty_float'),
        total_price=Avg('price_float'),
        total_amount=Sum('amount_float'),
        orders=Count('documentpkid', distinct=True),
        vendors=Count('vendorname', distinct=True)
    ).order_by('-total_amount')
    
    return item_stats


def _get_purchase_date_analysis(purchase_qs):
    """Өдрөөр дэлгэрэнгүй шинжилгээ"""
    from django.db.models.functions import Cast
    from django.db.models import FloatField
    
    date_stats = purchase_qs.annotate(
        qty_float=Cast('qty', FloatField()),
        price_float=Cast('price', FloatField()),
        amount_float=Cast('itemamountfc', FloatField())
    ).values('documentdate').annotate(
        total_qty=Sum('qty_float'),
        total_price=Avg('price_float'),
        total_amount=Sum('amount_float'),
        orders=Count('documentpkid', distinct=True),
        vendors=Count('vendorname', distinct=True)
    ).order_by('-documentdate')
    
    return date_stats


"""
Нэме: delivery_report view
"""

@login_required
def delivery_report(request):
    """Түгээлтийн тайлан - OpenDataSaleHeader өгөгдлөөс"""
    from collections import defaultdict
    
    # Эрхийн удирдлага - нэвтэрсэн хэрэглэгчийн email шалгах
    logged_in_email = request.user.email
    is_admin = False
    user_distributor_id = None
    
    # Employee мэдээлэл олох
    try:
        employee = OpenDataEmployee.objects.get(email=logged_in_email)
        # Захирал эсвэл Ерөнхий нягтлан бол бүгдийг харуулна
        if employee.positionname in ["Захирал", "Ерөнхий нягтлан"]:
            is_admin = True
        else:
            # Жирийн ажилтны хувьд UserProfile-с DistributorId олох
            try:
                profile = request.user.profile
                user_distributor_id = profile.distributor_id
                
                # Хэрэв UserProfile-д distributor_id байхгүй бол Employee-ийн pkid-г ашиглах
                # (Түгээгч ажилтан өөрийн түгээлтийг харах)
                if not user_distributor_id:
                    user_distributor_id = employee.id
            except:
                # UserProfile байхгүй бол Employee-ийн pkid-г ашиглах
                user_distributor_id = employee.id
    except OpenDataEmployee.DoesNotExist:
        # Employee бүртгэлгүй бол UserProfile-с distributor_id-г шалгах
        try:
            profile = request.user.profile
            user_distributor_id = profile.distributor_id
        except:
            pass
    
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
    
    # Эрхийн шүүлт - админ биш бол зөвхөн өөрийн түгээгчийн өгөгдлийг харуулна
    if not is_admin and user_distributor_id:
        delivery_qs = delivery_qs.filter(distributorid=user_distributor_id)
    elif not is_admin and not user_distributor_id:
        # Эрхгүй хэрэглэгч - хоосон өгөгдол
        delivery_qs = delivery_qs.none()
    
    # DocumentDate нь TEXT учраас эхлээд Cast хийнэ
    delivery_qs = delivery_qs.annotate(
        date_field_filter=Cast('documentdate', DateField())
    )
    
    # Огноогийн автомат шүүлт - сүүлийн 1 жил
    one_year_ago = timezone.now() - timedelta(days=365)
    
    # Сүүлийн 1 жилийн өгөгдөл
    delivery_qs = delivery_qs.filter(date_field_filter__gte=one_year_ago.date())
    
    # Огноогоор шүүх (хэрэглэгчийн оруулсан)
    if date_from:
        delivery_qs = delivery_qs.filter(date_field_filter__gte=date_from)
    
    if date_to:
        delivery_qs = delivery_qs.filter(date_field_filter__lte=date_to)
    
    # Жолоочоор шүүх
    if seller_filter:
        delivery_qs = delivery_qs.filter(distributorname__icontains=seller_filter)
    
    # Хүснэгтийн баганы толгойн шүүлт
    filter_year = request.GET.get('filter_year', '').strip()
    filter_month = request.GET.get('filter_month', '').strip()
    filter_day = request.GET.get('filter_day', '').strip()
    filter_seller = request.GET.get('filter_seller', '').strip()
    
    # Өдрөөр бүлэглэх - Он-Сар-Өдөр-Жолооч
    daily_data = delivery_qs.annotate(
        date_field=Cast('documentdate', DateField()),
        year=ExtractYear('date_field'),
        month=ExtractMonth('date_field'),
        day=ExtractDay('date_field'),
        payamount_float=Cast('payamount', FloatField()),
        deliveryqty_float=Cast('deliveryqty', FloatField())
    )
    
    # Хүснэгтийн баганы толгойн шүүлт (annotate хийсний дараа)
    if filter_year:
        daily_data = daily_data.filter(year=int(filter_year))
    if filter_month:
        daily_data = daily_data.filter(month=int(filter_month))
    if filter_day:
        daily_data = daily_data.filter(day=int(filter_day))
    if filter_seller:
        daily_data = daily_data.filter(distributorname__icontains=filter_seller)
    
    # Бүлэглэх
    daily_data = daily_data.values('year', 'month', 'day', 'distributorname').annotate(
        total_amount=Sum('payamount_float'),
        total_qty=Sum('deliveryqty_float'),
        total_orders=Count('documentpkid', distinct=True)
    ).order_by('-year', '-month', '-day', 'distributorname')
    
    # Статистик - шүүлтийн дараах нийлбэр (Python дээр тооцоолох)
    daily_data_list = list(daily_data)
    stats = {
        'total_amount': sum(row['total_amount'] or 0 for row in daily_data_list),
        'total_qty': sum(row['total_qty'] or 0 for row in daily_data_list),
        'total_orders': sum(row['total_orders'] or 0 for row in daily_data_list),
        'total_sellers': len(set(row['distributorname'] for row in daily_data_list if row['distributorname']))
    }
    
    # Жолоочдын жагсаалт
    sellers_list = OpenDataSaleHeader.objects.values_list(
        'distributorname', flat=True
    ).distinct().exclude(distributorname__isnull=True).exclude(distributorname='').order_by('distributorname')
    
    # Боломжит жилүүд
    years = delivery_qs.annotate(
        year=ExtractYear('date_field_filter')
    ).values_list('year', flat=True).distinct().order_by('-year')
    
    context = {
        'daily_data': daily_data_list,
        'sellers': list(sellers_list),
        'years': [int(y) for y in years if y],
        'stats': stats,
        'date_from': date_from_str or '',
        'date_to': date_to_str or '',
        'selected_seller': seller_filter,
        'selected_year': year_filter,
        'selected_month': month_filter,
        'total_records': len(daily_data_list),
    }
    
    return render(request, 'shop/delivery_report.html', context)


@login_required
def expense_report(request):
    """Зардлын тооцоолол - Expense Calculation Report"""
    # Зөвхөн ажилтанд зөвшөөрөх
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')
    
    from datamigration.models import OpenDataSale
    from django.db import connection
    from collections import defaultdict
    
    # Сонгосон он (default - сүүлийн он)
    selected_year_str = request.GET.get('year', '').replace(',', '')  # Мянгачлалыг арилгах
    
    # OpenDataSale-с жилүүдийг авах
    available_years = _get_available_years(OpenDataSale.objects.all())
    
    # Хэрэв available_years хоосон бол сүүлийн 5 жилийг үүсгэх
    if not available_years:
        current_year = timezone.now().year
        available_years = list(range(current_year, current_year - 5, -1))
    
    # Default он - хамгийн сүүлийн он
    if not selected_year_str and available_years:
        selected_year = available_years[0]
    elif selected_year_str:
        selected_year = int(selected_year_str)
    else:
        selected_year = timezone.now().year
    
    # Сараар өгөгдөл цуглуулах (1-12 сар)
    monthly_data = {i: {} for i in range(1, 13)}
    
    # 1. OpenDataSale - PayAmount (Борлуулалтын дүн)
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
            ''',
            [selected_year]
        )
        for row in cursor.fetchall():
            month = int(row[0]) if row[0] else 0
            if 1 <= month <= 12:
                monthly_data[month]['payamount'] = row[1] or 0
                monthly_data[month]['vatamount'] = row[2] or 0
                monthly_data[month]['amountnonvat'] = row[3] or 0
                monthly_data[month]['cost'] = row[4] or 0
    
    # 2. OpenDataGeneralLedger - 520101 Борлуулалтын хөнгөлөлт
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                SUM(CAST("DebitAmt" AS FLOAT)) as total
            FROM "OpenDataGeneralLedger"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
              AND "AccountId" = %s
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ''',
            [selected_year, '520101']
        )
        for row in cursor.fetchall():
            month = int(row[0]) if row[0] else 0
            if 1 <= month <= 12:
                monthly_data[month]['discount'] = row[1] or 0
    
    # 3. OpenDataSaleRefund - Буцаалтын дүн
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                SUM(CAST("PayAmount" AS FLOAT)) as total
            FROM "OpenDataSaleRefund"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ''',
            [selected_year]
        )
        for row in cursor.fetchall():
            month = int(row[0]) if row[0] else 0
            if 1 <= month <= 12:
                monthly_data[month]['refund'] = row[1] or 0
    
    # 4. Бохир ашиг = AmountNonVat - Өртөг
    # 5. Хөнгөлөлт, буцаалт хассан зардлын өмнөх ашиг = AmountNonVat - Хөнгөлөлт - Буцаалт - Өртөг
    for month in range(1, 13):
        amountnonvat = monthly_data[month].get('amountnonvat', 0)
        discount = monthly_data[month].get('discount', 0)
        refund = monthly_data[month].get('refund', 0)
        cost = monthly_data[month].get('cost', 0)
        
        # Бохир ашиг (зөвхөн өртөг хассан)
        monthly_data[month]['gross_profit'] = amountnonvat - cost
        
        # Хөнгөлөлт, буцаалт хассан зардлын өмнөх ашиг
        monthly_data[month]['gross_profit_after_discount'] = amountnonvat - discount - refund - cost
    
    # 5. OpenDataGeneralLedger - 7-р эхэлсэн зардлууд (дансны дугаараар бүлэглэх)
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT 
                EXTRACT(month FROM CAST("DocumentDate" AS DATE)) as month,
                "AccountId" as accountid,
                "AccountName" as accountname,
                SUM(CAST("DebitAmt" AS FLOAT)) as total
            FROM "OpenDataGeneralLedger"
            WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
              AND "AccountId" LIKE '7%%'
            GROUP BY EXTRACT(month FROM CAST("DocumentDate" AS DATE)), "AccountId", "AccountName"
            ORDER BY "AccountId", EXTRACT(month FROM CAST("DocumentDate" AS DATE))
            ''',
            [selected_year]
        )
        expenses_by_month = cursor.fetchall()
    
    # Зардлын дансуудыг цуглуулах
    expense_accounts = {}
    for row in expenses_by_month:
        month = int(row[0]) if row[0] else 0  # month
        account_id = row[1] or 'Unknown'  # accountid
        account_name = row[2] or 'Тодорхойгүй'  # accountname
        total = row[3] or 0  # total
        
        if account_id not in expense_accounts:
            expense_accounts[account_id] = {
                'name': account_name,
                'monthly': {i: 0 for i in range(1, 13)}
            }
        
        if 1 <= month <= 12:
            expense_accounts[account_id]['monthly'][month] = total
    
    # Нийт зардал сараар
    total_expenses_monthly = {i: 0 for i in range(1, 13)}
    for account_data in expense_accounts.values():
        for month in range(1, 13):
            total_expenses_monthly[month] += account_data['monthly'][month]
    
    # 6. Цэвэр ашиг = Хөнгөлөлт, буцаалт хассан зардлын өмнөх ашиг - Нийт зардал
    for month in range(1, 13):
        gross_profit_after_discount = monthly_data[month].get('gross_profit_after_discount', 0)
        total_expense = total_expenses_monthly[month]
        monthly_data[month]['net_profit'] = gross_profit_after_discount - total_expense
    
    # Жилийн нийлбэр тооцоолох
    yearly_totals = {
        'payamount': sum(monthly_data[m].get('payamount', 0) for m in range(1, 13)),
        'vatamount': sum(monthly_data[m].get('vatamount', 0) for m in range(1, 13)),
        'amountnonvat': sum(monthly_data[m].get('amountnonvat', 0) for m in range(1, 13)),
        'discount': sum(monthly_data[m].get('discount', 0) for m in range(1, 13)),
        'refund': sum(monthly_data[m].get('refund', 0) for m in range(1, 13)),
        'cost': sum(monthly_data[m].get('cost', 0) for m in range(1, 13)),
        'gross_profit': sum(monthly_data[m].get('gross_profit', 0) for m in range(1, 13)),
        'gross_profit_after_discount': sum(monthly_data[m].get('gross_profit_after_discount', 0) for m in range(1, 13)),
        'total_expense': sum(total_expenses_monthly.values()),
        'net_profit': sum(monthly_data[m].get('net_profit', 0) for m in range(1, 13)),
    }
    
    # Зардлын дансны жилийн дүн
    for account_id in expense_accounts:
        expense_accounts[account_id]['yearly_total'] = sum(
            expense_accounts[account_id]['monthly'].values()
        )
    
    context = {
        'selected_year': selected_year,
        'available_years': available_years,
        'monthly_data': monthly_data,
        'expense_accounts': dict(sorted(expense_accounts.items())),
        'total_expenses_monthly': total_expenses_monthly,
        'yearly_totals': yearly_totals,
        'months': range(1, 13),
    }
    
    return render(request, 'shop/expense_report.html', context)


@staff_member_required
def expense_report_by_year(request):
    """Зардлын тооцоолол жилээр - Expense Report by Year (Columns = Years)"""
    from datamigration.models import OpenDataSale
    from django.db import connection
    from collections import defaultdict
    
    # OpenDataSale-с жилүүдийг авах
    available_years = _get_available_years(OpenDataSale.objects.all())
    
    # Хэрэв available_years хоосон бол сүүлийн 5 жилийг үүсгэх
    if not available_years:
        current_year = timezone.now().year
        available_years = list(range(current_year, current_year - 5, -1))
    
    # Жил бүрийн өгөгдөл
    yearly_data = {year: {} for year in available_years}
    
    # 1. OpenDataSale - Борлуулалт, НӨАТ, өртөг
    for year in available_years:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT 
                    SUM(CAST("PayAmount" AS FLOAT)) as payamount_sum,
                    SUM(CAST("VatAmount" AS FLOAT)) as vatamount_sum,
                    SUM(CAST("AmountNonVat" AS FLOAT)) as amountnonvat_sum,
                    SUM(CAST("UnitCost" AS FLOAT) * CAST("Qty" AS FLOAT)) as cost_sum
                FROM "OpenDataSale"
                WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                ''',
                [year]
            )
            row = cursor.fetchone()
            if row:
                yearly_data[year]['payamount'] = row[0] or 0
                yearly_data[year]['vatamount'] = row[1] or 0
                yearly_data[year]['amountnonvat'] = row[2] or 0
                yearly_data[year]['cost'] = row[3] or 0
    
    # 2. Борлуулалтын хөнгөлөлт (520101)
    for year in available_years:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT SUM(CAST("DebitAmt" AS FLOAT)) as total
                FROM "OpenDataGeneralLedger"
                WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                  AND "AccountId" = %s
                ''',
                [year, '520101']
            )
            row = cursor.fetchone()
            yearly_data[year]['discount'] = (row[0] or 0) if row else 0
    
    # 3. Буцаалт
    for year in available_years:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT SUM(CAST("PayAmount" AS FLOAT)) as total
                FROM "OpenDataSaleRefund"
                WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                ''',
                [year]
            )
            row = cursor.fetchone()
            yearly_data[year]['refund'] = (row[0] or 0) if row else 0
    
    # 4. Бохир ашиг болон хөнгөлөлт/буцаалт хассан ашиг
    for year in available_years:
        amountnonvat = yearly_data[year].get('amountnonvat', 0)
        cost = yearly_data[year].get('cost', 0)
        discount = yearly_data[year].get('discount', 0)
        refund = yearly_data[year].get('refund', 0)
        
        yearly_data[year]['gross_profit'] = amountnonvat - cost
        yearly_data[year]['gross_profit_after_discount'] = amountnonvat - cost - discount - refund
    
    # 5. Зардлууд (7-р данс) - дансаар бүлэглэх
    expense_accounts = {}
    for year in available_years:
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                SELECT 
                    "AccountId" as accountid,
                    "AccountName" as accountname,
                    SUM(CAST("DebitAmt" AS FLOAT)) as total
                FROM "OpenDataGeneralLedger"
                WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                  AND "AccountId" LIKE '7%%'
                GROUP BY "AccountId", "AccountName"
                ORDER BY "AccountId"
                ''',
                [year]
            )
            for row in cursor.fetchall():
                account_id = row[0] or 'Unknown'
                account_name = row[1] or 'Тодорхойгүй'
                total = row[2] or 0
                
                if account_id not in expense_accounts:
                    expense_accounts[account_id] = {
                        'name': account_name,
                        'yearly': {y: 0 for y in available_years}
                    }
                
                expense_accounts[account_id]['yearly'][year] = total
    
    # Нийт зардал жил бүрээр
    total_expenses_yearly = {year: 0 for year in available_years}
    for account_data in expense_accounts.values():
        for year in available_years:
            total_expenses_yearly[year] += account_data['yearly'][year]
    
    # 6. Цэвэр ашиг
    for year in available_years:
        gross_profit_after_discount = yearly_data[year].get('gross_profit_after_discount', 0)
        total_expense = total_expenses_yearly[year]
        yearly_data[year]['total_expense'] = total_expense
        yearly_data[year]['net_profit'] = gross_profit_after_discount - total_expense
    
    context = {
        'available_years': available_years,
        'yearly_data': yearly_data,
        'expense_accounts': dict(sorted(expense_accounts.items())),
        'total_expenses_yearly': total_expenses_yearly,
    }
    
    return render(request, 'shop/expense_report_by_year.html', context)


@staff_member_required
def expense_transaction_detail(request):
    """Зардлын гүйлгээний дэлгэрэнгүй"""
    from django.db import connection
    import logging
    logger = logging.getLogger(__name__)
    
    year = request.GET.get('year')
    month = request.GET.get('month')
    account_id = request.GET.get('account_id')
    transaction_type = request.GET.get('type')  # 'discount', 'sale', 'refund', 'expense'
    
    logger.info(f"Transaction detail requested: year={year}, month={month}, type={transaction_type}, account={account_id}")
    
    if not year or not month:
        # Параметр дутуу бол error template үзүүлэх
        context = {
            'title': 'Алдаа - Параметр дутуу',
            'year': year or 'N/A',
            'month': month or 'N/A',
            'transactions': [],
            'total_amount': 0,
            'transaction_count': 0,
            'error_message': f'Он эсвэл сар дутуу байна. Year={year}, Month={month}',
        }
        return render(request, 'shop/expense_transaction_detail.html', context)
    
    transactions = []
    title = ""
    
    try:
        with connection.cursor() as cursor:
            if transaction_type == 'discount' or account_id == '520101':
                # Борлуулалтын хөнгөлөлт (520101)
                title = f"{year} оны {month}-р сар - Борлуулалтын хөнгөлөлт (520101)"
                cursor.execute('''
                    WITH main_line AS (
                        SELECT 
                            "DocumentPkId",
                            CAST("DocumentDate" AS DATE) as date,
                            COALESCE("DocumentDesc", "DocumentNumber", '-') as description,
                            "AccountId" || ' - ' || "AccountName" as main_account,
                            CAST("DebitAmt" AS FLOAT) as main_debit,
                            CAST("CreditAmt" AS FLOAT) as main_credit
                        FROM "OpenDataGeneralLedger"
                        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                          AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
                          AND "AccountId" = %s
                    ),
                    paired_lines AS (
                        SELECT 
                            gl."DocumentPkId",
                            STRING_AGG(gl."AccountId" || ' - ' || gl."AccountName", ', ' ORDER BY gl."AccountId") as other_accounts
                        FROM "OpenDataGeneralLedger" gl
                        INNER JOIN main_line ml ON gl."DocumentPkId" = ml."DocumentPkId"
                        WHERE gl."AccountId" != %s
                        GROUP BY gl."DocumentPkId"
                    )
                    SELECT 
                        ml.date,
                        ml.description,
                        ml.main_account as debit_account,
                        COALESCE(pl.other_accounts, '-') as credit_account,
                        CASE WHEN ml.main_debit > 0 THEN ml.main_debit ELSE ml.main_credit END as amount
                    FROM main_line ml
                    LEFT JOIN paired_lines pl ON ml."DocumentPkId" = pl."DocumentPkId"
                    ORDER BY ml.date
                ''', [year, month, '520101', '520101'])
                logger.info(f"Discount query executed")
                
            elif transaction_type == 'sale':
                # Борлуулалт (OpenDataSale)
                title = f"{year} оны {month}-р сар - Борлуулалт"
                cursor.execute('''
                    SELECT 
                        CAST("DocumentDate" AS DATE) as date,
                        "ItemName" || ' (' || "CustomerName" || ')' as description,
                        'Барааны борлуулалт' as debit_account,
                        'Орлого' as credit_account,
                        CAST("PayAmount" AS FLOAT) as amount
                    FROM "OpenDataSale"
                    WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                      AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
                    ORDER BY CAST("DocumentDate" AS DATE), "DocumentPkId"
                ''', [year, month])
                logger.info(f"Sale query executed")
                
            elif transaction_type == 'refund':
                # Буцаалт
                title = f"{year} оны {month}-р сар - Буцаалт"
                cursor.execute('''
                    SELECT 
                        "DocumentDate" as date,
                        "ItemName" || ' (' || "CustomerName" || ')' as description,
                        'Буцаалт' as debit_account,
                        'Орлого' as credit_account,
                        CAST("PayAmount" AS FLOAT) as amount
                    FROM "OpenDataSaleRefund"
                    WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                      AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
                    ORDER BY CAST("DocumentDate" AS DATE)
                ''', [year, month])
                logger.info(f"Refund query executed")
                
            elif account_id and account_id.startswith('7'):
                # 7-р зардлын данс
                cursor.execute('''
                    SELECT 
                        "AccountName"
                    FROM "OpenDataGeneralLedger"
                    WHERE "AccountId" = %s
                    LIMIT 1
                ''', [account_id])
                account_row = cursor.fetchone()
                account_name = account_row[0] if account_row else 'Тодорхойгүй данс'
                
                title = f"{year} оны {month}-р сар - {account_id} ({account_name})"
                cursor.execute('''
                    WITH main_line AS (
                        SELECT 
                            "DocumentPkId",
                            CAST("DocumentDate" AS DATE) as date,
                            COALESCE("DocumentDesc", "DocumentNumber", '-') as description,
                            "AccountId" || ' - ' || "AccountName" as main_account,
                            CAST("DebitAmt" AS FLOAT) as main_debit,
                            CAST("CreditAmt" AS FLOAT) as main_credit
                        FROM "OpenDataGeneralLedger"
                        WHERE EXTRACT(year FROM CAST("DocumentDate" AS DATE)) = %s
                          AND EXTRACT(month FROM CAST("DocumentDate" AS DATE)) = %s
                          AND "AccountId" = %s
                    ),
                    paired_lines AS (
                        SELECT 
                            gl."DocumentPkId",
                            STRING_AGG(gl."AccountId" || ' - ' || gl."AccountName", ', ' ORDER BY gl."AccountId") as other_accounts
                        FROM "OpenDataGeneralLedger" gl
                        INNER JOIN main_line ml ON gl."DocumentPkId" = ml."DocumentPkId"
                        WHERE gl."AccountId" != %s
                        GROUP BY gl."DocumentPkId"
                    )
                    SELECT 
                        ml.date,
                        ml.description,
                        ml.main_account as debit_account,
                        COALESCE(pl.other_accounts, '-') as credit_account,
                        CASE WHEN ml.main_debit > 0 THEN ml.main_debit ELSE ml.main_credit END as amount
                    FROM main_line ml
                    LEFT JOIN paired_lines pl ON ml."DocumentPkId" = pl."DocumentPkId"
                    ORDER BY ml.date
                ''', [year, month, account_id, account_id])
                logger.info(f"Expense account query executed for {account_id}")
            
            else:
                # Гүйлгээний төрөл тодорхойгүй
                logger.warning(f"Invalid transaction type: {transaction_type}")
                context = {
                    'title': 'Алдаа - Гүйлгээний төрөл тодорхойгүй',
                    'year': year,
                    'month': month,
                    'transactions': [],
                    'total_amount': 0,
                    'transaction_count': 0,
                    'error_message': f'Гүйлгээний төрөл тодорхойгүй: type={transaction_type}, account_id={account_id}',
                }
                return render(request, 'shop/expense_transaction_detail.html', context)
            
            # Гүйлгээнүүдийг цуглуулах
            for row in cursor.fetchall():
                transactions.append({
                    'date': row[0],
                    'description': row[1] or '-',
                    'debit_account': row[2] or '-',
                    'credit_account': row[3] or '-',
                    'amount': row[4] or 0
                })
            
            logger.info(f"Found {len(transactions)} transactions")
    
    except Exception as e:
        logger.error(f"Error in expense_transaction_detail: {str(e)}", exc_info=True)
        context = {
            'title': 'Алдаа гарлаа',
            'year': year,
            'month': month,
            'transactions': [],
            'total_amount': 0,
            'transaction_count': 0,
            'error_message': f'Өгөгдлийн сангаас мэдээлэл авахад алдаа гарлаа: {str(e)}',
        }
        return render(request, 'shop/expense_transaction_detail.html', context)
    
    # Нийт дүн
    total_amount = sum(t['amount'] for t in transactions)
    
    logger.info(f"Rendering template with {len(transactions)} transactions, total: {total_amount}")
    
    context = {
        'title': title,
        'year': year,
        'month': month,
        'transactions': transactions,
        'total_amount': total_amount,
        'transaction_count': len(transactions),
    }
    
    return render(request, 'shop/expense_transaction_detail.html', context)


@login_required
def profile(request):
    """Хувийн мэдээлэл - OpenDataEmployee + UserProfile"""
    from django.contrib import messages
    from shop.models import UserProfile

    employee = None
    if request.user.email:
        employee = OpenDataEmployee.objects.filter(email__iexact=request.user.email).first()

    user_profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        user_profile.phone = request.POST.get('phone', '').strip()
        user_profile.save()
        messages.success(request, 'Мэдээлэл амжилттай хадгалагдлаа.')
        return redirect('shop:profile')

    context = {
        'employee': employee,
        'user_profile': user_profile,
    }
    return render(request, 'shop/profile.html', context)


@login_required
def menu_permission_config(request):
    """Sidebar цэсийг албан тушаал тус бүрээр харуулах эсэх, мөн бүлэглэлтийг тохируулах хуудас (зөвхөн superuser).

    Албан тушаал нэг нэгээр сонгож эрхийг нь тохируулдаг тул цэс хэдий чинээ
    олон болсон ч зөвхөн мөр нэмэгдэнэ, баганаар өсдөг матриц болохгүй.
    """
    from django.contrib import messages
    from shop.models import MenuPermission, MenuGroupAssignment
    from shop.menuconfig import ALWAYS_ALL_MENU_POSITIONS, get_configurable_menu_items, get_group_choices, get_effective_menu_groups

    if not request.user.is_superuser:
        messages.warning(request, 'Энэ хуудас зөвхөн админд зориулагдсан.')
        return redirect('shop:dashboard')

    positions = list(
        OpenDataEmployee.objects.exclude(positionname__isnull=True)
        .exclude(positionname='')
        .values_list('positionname', flat=True)
        .distinct()
        .order_by('positionname')
    )
    menu_items = get_configurable_menu_items()
    group_choices = get_group_choices()

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'groups':
            for item in menu_items:
                group_key = request.POST.get(f"group__{item['key']}")
                if group_key:
                    MenuGroupAssignment.objects.update_or_create(
                        menu_key=item['key'],
                        defaults={'group_key': group_key},
                    )
            messages.success(request, 'Цэсний бүлэглэлт амжилттай хадгалагдлаа.')
            return redirect('shop:menu_permission_config')

        if action == 'permissions':
            position = request.POST.get('position', '')
            if position in ALWAYS_ALL_MENU_POSITIONS:
                messages.info(request, f'"{position}" албан тушаал бүх цэсийг автоматаар харах тул тохиргоо хийх шаардлагагүй.')
            elif position in positions:
                for item in menu_items:
                    field_name = f"visible__{item['key']}"
                    MenuPermission.objects.update_or_create(
                        position_name=position,
                        menu_key=item['key'],
                        defaults={'is_visible': field_name in request.POST},
                    )
                messages.success(request, f'"{position}" албан тушаалын цэсний эрх хадгалагдлаа.')
            return redirect(f"{request.path}?position={position}")

    # Идэвхтэй албан тушаал: query param эсвэл жагсаалтын эхнийх
    selected_position = request.GET.get('position') or (positions[0] if positions else '')
    is_always_all_position = selected_position in ALWAYS_ALL_MENU_POSITIONS

    existing_for_position = dict(
        MenuPermission.objects.filter(position_name=selected_position).values_list('menu_key', 'is_visible')
    )

    # Групээр бүлэглэсэн checkbox жагсаалт - шинэ цэс нэмэгдэхэд зөвхөн мөр нэмэгдэнэ, багана биш
    permission_groups = []
    for group in get_effective_menu_groups():
        rows = []
        for item in group['items']:
            if item.get('always_visible'):
                continue
            rows.append({
                'key': item['key'],
                'label': item['label'],
                'icon': item['icon'],
                'field_name': f"visible__{item['key']}",
                # Ерөнхий нягтлан шинэ цэсийг ч оролцуулаад бүгдийг үргэлж харна;
                # бусад албан тушаалд тохиргоогүй цэс default-аар нуугдана (opt-in)
                'is_visible': True if is_always_all_position else existing_for_position.get(item['key'], False),
            })
        if rows:
            permission_groups.append({'label': group['label'] or group['key'], 'rows': rows})

    group_overrides = dict(MenuGroupAssignment.objects.values_list('menu_key', 'group_key'))
    group_rows = [
        {
            'key': item['key'],
            'label': item['label'],
            'icon': item['icon'],
            'field_name': f"group__{item['key']}",
            'current_group_key': group_overrides.get(item['key'], item['group_key']),
        }
        for item in menu_items
    ]

    context = {
        'positions': positions,
        'selected_position': selected_position,
        'is_always_all_position': is_always_all_position,
        'always_all_positions': ALWAYS_ALL_MENU_POSITIONS,
        'permission_groups': permission_groups,
        'group_choices': group_choices,
        'group_rows': group_rows,
    }
    return render(request, 'shop/menu_permission_config.html', context)




@login_required
def meal_list(request):
    """Хоолны бүртгэлийн жагсаалт"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from shop.models import Meal, MealCycleSettings, get_menu_number_for_date
    meals = (
        Meal.objects.prefetch_related('ingredients', 'numbers')
        .annotate(min_number=Min('numbers__number'))
        .order_by('min_number', 'meal_type', 'name')
    )
    today = timezone.localdate()
    cycle_effective_from = MealCycleSettings.get_effective_from()
    context = {
        'meals': meals,
        'cycle_effective_from': cycle_effective_from,
        'cycle_effective_number': get_menu_number_for_date(cycle_effective_from) if cycle_effective_from else None,
        'today': today,
        'today_menu_number': get_menu_number_for_date(today),
        'number_choices': range(1, 11),
    }
    return render(request, 'shop/meal_list.html', context)


@login_required
def meal_cycle_settings_update(request):
    """Сонгосон огноог өгсөн хоолны дугаартай тохируулж, циклийг шинэчилнэ.

    Тохируулсан огнооноос хойшхи бүх ажлын өдрүүдэд шинэ дараалал (тухайн
    дугаараас цааш 1-10 хүртэл эргэлдэх) хүчинтэй болно.
    """
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from shop.models import MealCycleSettings

    if request.method == 'POST':
        date_str = request.POST.get('date')
        number_str = request.POST.get('number')
        try:
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            number = int(number_str)
            if target_date.weekday() >= 5:
                raise ValueError('weekend')
            if not (1 <= number <= 10):
                raise ValueError('number out of range')
        except (TypeError, ValueError):
            messages.error(request, 'Огноо, дугаарыг зөв сонгоно уу (амралтын өдөр байж болохгүй, дугаар 1-10 хооронд байна).')
            return redirect('shop:meal_list')

        MealCycleSettings.set_number_for_date(target_date, number)
        messages.success(
            request,
            f'{target_date} өдрийг {number} дугаартай болгож циклийг шинэчиллээ. '
            f'Энэ өдрөөс хойшхи бүх ажлын өдрүүдэд дараалал үргэлжилнэ.'
        )

    return redirect('shop:meal_list')


@login_required
def meal_material_calc(request):
    """Сонгосон хугацаанд ажилтнуудад хэрэгтэй орцны материалын нийт хэмжээг тооцоолно.

    Тухайн хугацаанд ажлын өдөр бүрийн хоолны дугаар хэд удаа давтагдахыг тоолж,
    орц тус бүрийн (нэг хүнд хэмжээ × давтагдсан тоо × хүний тоо)-г нэгтгэнэ.
    """
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from collections import Counter
    from shop.models import Meal, get_menu_number_for_date

    today = timezone.localdate()
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    headcount_str = request.GET.get('headcount')

    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else today
    except ValueError:
        date_from = today
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today + timedelta(days=29)
    except ValueError:
        date_to = today + timedelta(days=29)
    if date_to < date_from:
        date_from, date_to = date_to, date_from

    try:
        headcount = int(headcount_str)
        if headcount < 0:
            headcount = 0
    except (TypeError, ValueError):
        headcount = 0

    # Тухайн хугацаанд ажлын өдөр бүрийн хоолны дугаарыг тоолно (амралтын өдөр/
    # тохируулаагүй өдөр None буцаах тул тоологдохгүй)
    number_counts = Counter()
    d = date_from
    while d <= date_to:
        n = get_menu_number_for_date(d)
        if n:
            number_counts[n] += 1
        d += timedelta(days=1)

    # Тухайн хугацаанд давтагдсан хоолнуудыг төрлөөр нь (1-р/2-р хоол, хачир)
    # тусдаа хүснэгт болгож нэрээр нь харуулна. Нэг хоол 2 өөр дугаартай байсан ч
    # нэр нь ижил тул давхардуулахгүй, тоог нь нэгтгэж нэг мөр болгоно.
    meals = list(
        Meal.objects.filter(numbers__number__in=number_counts.keys())
        .prefetch_related('ingredients', 'numbers')
        .distinct()
        .order_by('meal_type', 'name')
    ) if number_counts else []

    repetition_by_type = {'1': [], '2': [], '3': []}
    for meal in meals:
        occurrence_count = sum(number_counts.get(n, 0) for n in meal.number_list)
        if occurrence_count == 0:
            continue
        repetition_by_type.setdefault(meal.meal_type, []).append({
            'name': meal.name, 'count': occurrence_count,
        })
    for rows in repetition_by_type.values():
        rows.sort(key=lambda r: (-r['count'], r['name']))

    detail_rows = []
    summary = {}

    if headcount > 0 and number_counts:
        for meal in meals:
            occurrence_count = sum(number_counts.get(n, 0) for n in meal.number_list)
            if occurrence_count == 0:
                continue
            for ing in meal.ingredients.all():
                per_person = ing.quantity or 0
                total = float(per_person) * occurrence_count * headcount
                ingredient_name = ing.item.name if ing.item else ing.item_id
                detail_rows.append({
                    'meal_type': meal.get_meal_type_display(),
                    'meal_name': meal.name,
                    'ingredient': ingredient_name,
                    'per_person': per_person,
                    'unit': ing.unit,
                    'occurrence_count': occurrence_count,
                    'total': total,
                })
                key = ing.item_id
                if key not in summary:
                    summary[key] = {'label': ingredient_name, 'unit': ing.unit, 'total': 0.0}
                summary[key]['total'] += total

    summary_rows = []
    for key, data in sorted(summary.items(), key=lambda kv: kv[1]['label']):
        unit = (data['unit'] or '').strip().lower()
        converted = None
        converted_unit = None
        if unit in ('гр', 'г'):
            converted = data['total'] / 1000
            converted_unit = 'кг'
        elif unit == 'мл':
            converted = data['total'] / 1000
            converted_unit = 'л'
        summary_rows.append({
            'label': data['label'],
            'unit': data['unit'],
            'total': data['total'],
            'converted': converted,
            'converted_unit': converted_unit,
        })

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'headcount': headcount,
        'repetition_1': repetition_by_type.get('1', []),
        'repetition_2': repetition_by_type.get('2', []),
        'repetition_3': repetition_by_type.get('3', []),
        'has_repetitions': any(repetition_by_type.values()),
        'detail_rows': detail_rows,
        'summary_rows': summary_rows,
    }
    return render(request, 'shop/meal_material_calc.html', context)


@login_required
def meal_edit(request, pk=None):
    """Хоол бүртгэх / засах (орцын хамт)"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from shop.models import Meal, MealNumberAssignment
    from shop.forms import MealForm, MealIngredientFormSet, MealNumberFormSet

    meal = get_object_or_404(Meal, pk=pk) if pk else Meal()

    if request.method == 'POST':
        form = MealForm(request.POST, instance=meal)
        formset = MealIngredientFormSet(request.POST, instance=meal)
        number_formset = MealNumberFormSet(request.POST, instance=meal)
        if form.is_valid() and formset.is_valid() and number_formset.is_valid():
            meal_type = form.cleaned_data['meal_type']
            conflict = False
            for number_form in number_formset.forms:
                if not number_form.cleaned_data or number_form.cleaned_data.get('DELETE'):
                    continue
                number = number_form.cleaned_data.get('number')
                if number is None:
                    continue
                clash = MealNumberAssignment.objects.filter(meal__meal_type=meal_type, number=number)
                if meal.pk:
                    clash = clash.exclude(meal=meal)
                other_meal = clash.select_related('meal').first()
                if other_meal:
                    number_form.add_error('number', f'{number} дугаарыг "{other_meal.meal.name}" хоол аль хэдийн эзэлсэн байна.')
                    conflict = True

            if not conflict:
                meal = form.save()
                formset.instance = meal
                formset.save()
                number_formset.instance = meal
                number_formset.save()

                messages.success(request, 'Хоол амжилттай хадгалагдлаа.')
                return redirect('shop:meal_list')
    else:
        form = MealForm(instance=meal)
        formset = MealIngredientFormSet(instance=meal)
        number_formset = MealNumberFormSet(instance=meal)

    context = {
        'form': form,
        'formset': formset,
        'number_formset': number_formset,
        'meal': meal if meal.pk else None,
    }
    return render(request, 'shop/meal_form.html', context)


@login_required
def meal_delete(request, pk):
    """Хоол устгах"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from shop.models import Meal

    meal = get_object_or_404(Meal, pk=pk)
    if request.method == 'POST':
        meal.delete()
        messages.success(request, 'Хоол устгагдлаа.')
        return redirect('shop:meal_list')

    context = {'meal': meal}
    return render(request, 'shop/meal_confirm_delete.html', context)


@login_required
def meal_attendance_list(request):
    """Хоол идэх нэрсийн бүртгэлийн жагсаалт"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from shop.models import MealAttendance

    attendances = MealAttendance.objects.prefetch_related('names').order_by('-date')
    context = {'attendances': attendances}
    return render(request, 'shop/meal_attendance_list.html', context)


@login_required
def meal_attendance_summary(request):
    """Сонгосон огнооны хооронд хоол идсэн хүмүүс/орцын нэгтгэл (огноогоор багана болгосон хүснэгт)"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from shop.models import MealAttendance

    view_mode = request.GET.get('view', 'ingredients')
    if view_mode not in ('ingredients', 'people'):
        view_mode = 'ingredients'

    today = timezone.localdate()
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else today - timedelta(days=6)
    except ValueError:
        date_from = today - timedelta(days=6)
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today
    except ValueError:
        date_to = today

    attendances = list(
        MealAttendance.objects.filter(date__gte=date_from, date__lte=date_to)
        .prefetch_related('names')
        .order_by('date')
    )
    dates = [a.date for a in attendances]

    row_order = []
    row_labels = {}
    row_units = {}
    cell_values = {}

    for attendance in attendances:
        headcount = len(attendance.names.all())
        if view_mode == 'people':
            for person in attendance.names.all():
                name = person.name.strip()
                if not name:
                    continue
                if name not in row_labels:
                    row_labels[name] = name
                    row_units[name] = ''
                    row_order.append(name)
                    cell_values[name] = {}
                cell_values[name][attendance.date] = cell_values[name].get(attendance.date, 0) + 1
        else:
            for meal in attendance.meals:
                for ingredient in meal.ingredients.all():
                    key = ingredient.item_id
                    if key not in row_labels:
                        item = ingredient.item
                        row_labels[key] = item.name if item else ingredient.item_id
                        row_units[key] = ingredient.unit
                        row_order.append(key)
                        cell_values[key] = {}
                    qty = float(ingredient.quantity or 0) * headcount
                    cell_values[key][attendance.date] = cell_values[key].get(attendance.date, 0) + qty

    row_order.sort(key=lambda k: row_labels[k])

    column_totals = {d: 0 for d in dates}
    rows = []
    for key in row_order:
        cells = []
        row_total = 0
        for d in dates:
            value = cell_values[key].get(d)
            cells.append(value)
            if value:
                row_total += value
                column_totals[d] += value
        rows.append({
            'label': row_labels[key],
            'unit': row_units.get(key, ''),
            'cells': cells,
            'total': row_total,
        })

    context = {
        'view_mode': view_mode,
        'date_from': date_from,
        'date_to': date_to,
        'dates': dates,
        'rows': rows,
        'column_totals': [column_totals[d] for d in dates],
        'grand_total': sum(column_totals.values()),
    }
    return render(request, 'shop/meal_attendance_summary.html', context)


@login_required
def meal_attendance_form(request, pk=None):
    """Хоол идэх нэрсийн бүртгэл - огноо сонгоход тухайн өдрийн хоол/орц автоматаар харагдаж, хүмүүсийн нэрсийг бүртгэнэ"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from django.forms import inlineformset_factory
    from shop.models import MealAttendance, MealAttendanceName, MealAttendanceIngredient
    from shop.forms import (
        MealAttendanceForm, MealAttendanceNameFormSet, MealAttendanceNameForm,
        MealAttendanceIngredientForm,
    )

    IngredientFormSet = inlineformset_factory(
        MealAttendance, MealAttendanceIngredient,
        form=MealAttendanceIngredientForm, extra=0, can_delete=True,
    )

    attendance = get_object_or_404(MealAttendance, pk=pk) if pk else None

    if request.method == 'POST':
        if not attendance:
            posted_date = request.POST.get('date')
            try:
                posted_date = datetime.strptime(posted_date, '%Y-%m-%d').date()
            except (TypeError, ValueError):
                messages.error(request, 'Огноо буруу байна.')
                return redirect('shop:meal_attendance_list')
            attendance, _ = MealAttendance.objects.get_or_create(date=posted_date)

        form = MealAttendanceForm(request.POST, instance=attendance)
        formset = MealAttendanceNameFormSet(request.POST, instance=attendance)
        ingredient_formset = IngredientFormSet(request.POST, instance=attendance)

        if form.is_valid() and formset.is_valid() and ingredient_formset.is_valid():
            meals_before_save = list(attendance.meals)

            attendance = form.save()
            formset.instance = attendance
            formset.save()
            ingredient_formset.instance = attendance
            ingredient_formset.save()

            after_snapshot = {
                (o.meal_id, o.item_id, o.quantity, o.unit)
                for o in attendance.ingredient_overrides.all()
            }
            template_snapshot = {
                (m.pk, ing.item_id, ing.quantity, ing.unit)
                for m in meals_before_save for ing in m.ingredients.all()
            }
            changed = after_snapshot != template_snapshot
            if changed != attendance.ingredients_changed:
                attendance.ingredients_changed = changed
                attendance.save(update_fields=['ingredients_changed'])

            messages.success(request, 'Хоол идэх нэрсийн бүртгэл хадгалагдлаа.')
            return redirect('shop:meal_attendance_edit', pk=attendance.pk)
    else:
        if not attendance:
            date_param = request.GET.get('date')
            try:
                selected_date = datetime.strptime(date_param, '%Y-%m-%d').date() if date_param else timezone.localdate()
            except ValueError:
                selected_date = timezone.localdate()

            existing = MealAttendance.objects.filter(date=selected_date).first()
            if existing:
                return redirect('shop:meal_attendance_edit', pk=existing.pk)
            attendance = MealAttendance(date=selected_date)

            # Шинэ бүртгэл нээхэд өмнөх хамгийн сүүлийн өдрийн нэрсийг урьдчилан бөглөнө -
            # тэндээсээ засах/нэмэх/хасах хийхэд хялбар байх зорилготой
            previous = (
                MealAttendance.objects.filter(date__lt=selected_date)
                .prefetch_related('names')
                .order_by('-date')
                .first()
            )
            initial_names = [{'name': n.name} for n in previous.names.all()] if previous else []

            NameFormSet = inlineformset_factory(
                MealAttendance, MealAttendanceName,
                form=MealAttendanceNameForm, extra=len(initial_names) + 1, can_delete=True,
            )
            formset = NameFormSet(instance=attendance, initial=initial_names)
        else:
            formset = MealAttendanceNameFormSet(instance=attendance)

        form = MealAttendanceForm(instance=attendance)

        # Орцны formset - тухайн өдөрт хадгалагдсан хувилбар байвал түүнийг, үгүй бол
        # стандарт жороос (Meal.ingredients) урьдчилан бөглөж харуулна
        meals = list(attendance.meals) if attendance.date else []
        existing_override_meal_ids = set(
            MealAttendanceIngredient.objects.filter(attendance=attendance).values_list('meal_id', flat=True)
        ) if attendance.pk else set()

        initial_ingredients = []
        for meal in meals:
            if meal.pk in existing_override_meal_ids:
                continue
            for ing in meal.ingredients.all():
                initial_ingredients.append({
                    'meal': meal.pk, 'item_id': ing.item_id, 'quantity': ing.quantity, 'unit': ing.unit,
                })

        ExtraIngredientFormSet = inlineformset_factory(
            MealAttendance, MealAttendanceIngredient,
            form=MealAttendanceIngredientForm, extra=len(initial_ingredients), can_delete=True,
        )
        ingredient_formset = ExtraIngredientFormSet(
            instance=attendance if attendance.pk else None, initial=initial_ingredients,
        )

        # Байгаа орцонд зөвхөн нэрийг нь текстээр харуулна (сонголтыг зөвхөн шинэ
        # орц нэмэхэд ашиглана) - нэрийг энд урьдчилан тооцоолж form дээр наана
        from datamigration.models import OpenDataItem
        item_ids = {
            (f.instance.item_id if f.instance.pk else f.initial.get('item_id'))
            for f in ingredient_formset.forms
        }
        item_ids.discard(None)
        item_names = dict(OpenDataItem.objects.filter(pk__in=item_ids).values_list('id', 'name'))
        for ing_form in ingredient_formset.forms:
            current_item_id = ing_form.instance.item_id if ing_form.instance.pk else ing_form.initial.get('item_id')
            ing_form.display_name = item_names.get(current_item_id, current_item_id)

    # Орцны form-уудыг хоол тус бүрээр нь бүлэглэж, загварт харуулахад бэлтгэнэ
    meals_for_context = list(attendance.meals) if attendance.date else []
    forms_by_meal = {}
    for ing_form in ingredient_formset.forms:
        meal_id = ing_form.instance.meal_id or ing_form.initial.get('meal')
        forms_by_meal.setdefault(meal_id, []).append(ing_form)
    meal_ingredient_groups = [(meal, forms_by_meal.get(meal.pk, [])) for meal in meals_for_context]

    context = {
        'form': form,
        'formset': formset,
        'ingredient_formset': ingredient_formset,
        'meal_ingredient_groups': meal_ingredient_groups,
        'attendance': attendance if attendance.pk else None,
        'selected_date': attendance.date,
        'menu_number': attendance.menu_number,
        'meals': meals_for_context,
        'is_weekend': attendance.date.weekday() >= 5,
    }
    return render(request, 'shop/meal_attendance_form.html', context)


@login_required
def meal_attendance_delete(request, pk):
    """Хоол идэх нэрсийн бүртгэл устгах"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from django.shortcuts import get_object_or_404
    from shop.models import MealAttendance

    attendance = get_object_or_404(MealAttendance, pk=pk)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, 'Бүртгэл устгагдлаа.')
        return redirect('shop:meal_attendance_list')

    context = {'attendance': attendance}
    return render(request, 'shop/meal_attendance_confirm_delete.html', context)


def _lookup_product_stock(query):
    """Чөлөөт текстээс утга бүхий үгсийг гаргаж аваад InventorySnapshot-с тохирох
    эхний 5 барааг үлдэгдлийн хамт буцаана. AI чат болон public JSON endpoint хоёулаа
    ашиглана.
    """
    import re
    from shop.models_inventory import InventorySnapshot
    from django.db.models import Q

    query = (query or "").strip()
    if not query:
        return []

    # 3-с дээш тэмдэгттэй үгсийг л ашиглана (богино холбогч үгсийг үл тооцно)
    words = [w for w in re.split(r"\s+", query) if len(w) >= 3][:8]
    if not words:
        return []

    q_filter = Q()
    for word in words:
        q_filter |= Q(itemname__icontains=word)

    snapshots = InventorySnapshot.objects.filter(q_filter).order_by("-total_qty")[:5]

    return [
        {
            "name": s.itemname,
            "brand": s.brandname or "",
            "qty": float(s.total_qty),
            "in_stock": s.total_qty > 0,
        }
        for s in snapshots
    ]


AI_CHAT_SYSTEM_PROMPT = (
    "Чи бол Төгс Амин Эрдэнэ ХХК компанийн вэбсайт дээрх AI туслах. Энэ компани нь Европын "
    "(Итали, Франц, Герман, Испани, Грек гэх мэт) шилдэг брэндүүдийн хүнсний бүтээгдэхүүнийг "
    "Монгол улс руу импортолж, хувь хүн (B2C) болон ресторан/дэлгүүр зэрэг бизнес түншүүдэд "
    "(B2B) борлуулдаг. Чиний цорын ганц үүрэг бол ЗӨВХӨН энэ компани болон түүний "
    "бүтээгдэхүүний талаарх асуултад хариулах. Хэрэв хэрэглэгч компани эсвэл бүтээгдэхүүнтэй "
    "огт холбоогүй өөр сэдвээр асуувал, өөр ямар ч мэдээлэл өгөлгүй, зөвхөн дараах хариултыг "
    "эелдэгээр өг: 'Уучлаарай, би зөвхөн манай байгууллага болон бүтээгдэхүүний талаарх таны "
    "сонирхсон асуултад хариулах боломжтой.' Хэрэв хэрэглэгч тодорхой барааны нөөц/үлдэгдлийн "
    "талаар асуувал, доор өгөгдсөн Барааны нөөцийн систем-ийн мэдээллийг ҮНДЭСЛЭН тухайн бараа "
    "НӨӨЦТЭЙ эсвэл НӨӨЦГҮЙ гэдгийг л тодорхой хэлээрэй, тоо ширхэгийг хэзээ ч бүү дурьд, өөрөө "
    "таамаглаж бүү хариул. Хэрэв тохирох бараа олдоогүй бол уучлалт хүсээд тодорхой барааны "
    "нэрийг лавлаарай. Хэрэглэгч заримдаа Монгол үгээ Латин үсгээр галиглаж бичдэг (жишээ нь: "
    "'sain bnu', 'unetei bhuu', 'ta yamar unaa hudaldj bgaa' гэх мэт) - ийм тохиолдолд бичсэн "
    "үгийн Монгол хэл дээрх утгыг ойлгож, хариултаа энгийн монгол (кирилл) хэлээр өгнө үү. "
    "Хариултаа товч, эелдэг, монгол хэлээр өгнө үү."
)


def ai_chat_message(request):
    """AI чат - Anthropic Claude API-г Django-с шууд дуудна (n8n дундын шат ашигладаггүй)."""
    if request.method != "POST":
        return JsonResponse({"error": "POST хүсэлт байх ёстой"}, status=405)

    import json
    import logging
    import requests
    from django.conf import settings

    logger = logging.getLogger(__name__)

    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Буруу бус JSON"}, status=400)

    message = (payload.get("message") or "").strip()
    if not message:
        return JsonResponse({"error": "Зурвас хоосон байна"}, status=400)

    stock_results = _lookup_product_stock(message)
    if stock_results:
        lines = [
            f"- {r['name']}: {'НӨӨЦТЭЙ' if r['in_stock'] else 'НӨӨЦГҮЙ'}"
            for r in stock_results
        ]
        stock_context = (
            "Барааны нөөцийн систем (эх сурвалж, найдвартай) дараах тохирох бараануудыг олсон:\n"
            + "\n".join(lines)
        )
    else:
        stock_context = "Барааны нөөцийн системээс энэ асуултад тохирох бараа олдсонгүй."

    body = {
        "model": "claude-sonnet-5",
        "max_tokens": 1024,
        "system": AI_CHAT_SYSTEM_PROMPT,
        "messages": [
            {"role": "user", "content": f"{stock_context}\n\nХэрэглэгчийн асуулт: {message}"}
        ],
    }
    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    # Anthropic талд заримдаа тохиолддог түр зуурын сүлжээний алдааг даван туулахын тулд нэг удаа дахин оролдоно
    data = None
    last_error = None
    for attempt in range(2):
        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                json=body,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
            response.encoding = "utf-8"
            data = response.json()
            break
        except (requests.RequestException, ValueError) as exc:
            last_error = exc

    if data is None:
        logger.exception("Anthropic API руу хүсэлт 2 оролдлогоор ч амжилтгүй боллоо", exc_info=last_error)
        return JsonResponse({"error": "AI чат үйлчилгээ түр боломжгүй байна"}, status=502)

    reply = next(
        (c.get("text", "") for c in data.get("content", []) if c.get("type") == "text"),
        "",
    )
    return JsonResponse({"reply": reply})


def product_stock_lookup(request):
    """AI чат (n8n)-с барааны үлдэгдэл асуухад ашиглах public JSON endpoint.

    ?q= параметрт ирсэн чөлөөт текстээс утга бүхий үгсийг гаргаж аваад,
    InventorySnapshot-с тохирох эхний 5 барааг үлдэгдлийн хамт буцаана.
    """
    query = request.GET.get("q") or ""
    return JsonResponse({"results": _lookup_product_stock(query)})


@login_required
def attendance_calc(request):
    """Цаг бүртгэлийн тооцоо - төхөөрөмжийн ирц болон Ажилтны хурууны мэдээллийг (EmployeeFingerprint)
    нэгтгэж, сонгосон огнооны мужид харуулна. Хадгалсан засвар байвал тооцооллыг тэрээр орлуулна."""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from shop.models import EmployeeFingerprint
    from shop.services.attendance import build_attendance_rows

    today = timezone.localdate()
    date_from_str = request.GET.get('date_from')
    date_to_str = request.GET.get('date_to')
    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date() if date_from_str else today.replace(day=1)
    except ValueError:
        date_from = today.replace(day=1)
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date() if date_to_str else today
    except ValueError:
        date_to = today

    rows = build_attendance_rows(date_from, date_to)
    error = None
    if not EmployeeFingerprint.objects.exclude(device_user_id='').exists():
        error = 'Ажилтны хурууны мэдээлэл бүртгэгдээгүй байна. "Ажилтны хурууны мэдээлэл" хуудаснаас ажилтан бүрийн төхөөрөмжийн кодыг тохируулна уу.'

    context = {
        'date_from': date_from,
        'date_to': date_to,
        'rows': rows,
        'error': error,
    }
    return render(request, 'shop/attendance_calc.html', context)


@login_required
def attendance_sync(request):
    """Хурууны хээ таних төхөөрөмжөөс шинэ ирцийн бүртгэлийг татаж AttendanceRawLog-д хадгална"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ үйлдэл зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    if request.method != 'POST':
        return redirect('shop:attendance_calc')

    from django.contrib import messages
    from shop.services.attendance import sync_from_device

    try:
        fetched, created = sync_from_device()
        messages.success(request, f'Төхөөрөмжөөс {fetched} бүртгэл татагдлаа, шинээр {created} мөр хадгалагдлаа.')
    except Exception as e:
        messages.error(request, f'Төхөөрөмжтэй холбогдоход алдаа гарлаа: {e}')

    url = reverse('shop:attendance_calc')
    date_from = request.POST.get('date_from')
    date_to = request.POST.get('date_to')
    qs = []
    if date_from:
        qs.append(f'date_from={date_from}')
    if date_to:
        qs.append(f'date_to={date_to}')
    if qs:
        url += '?' + '&'.join(qs)
    return redirect(url)


@login_required
def attendance_sync_merchandiser(request):
    """Түгээлтийн программаас экспортолсон Excel файлыг (сонгож upload хийсэн) уншиж, худалдааны
    төлөөлөгч/мерчандайзерийн зочилсон (зураг илгээсэн) бүртгэлийг MerchandiserVisitLog-д импортолно"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ үйлдэл зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    if request.method != 'POST':
        return redirect('shop:attendance_calc')

    from django.contrib import messages
    from shop.services.attendance import import_merchandiser_visits

    uploaded_file = request.FILES.get('document_file')
    if not uploaded_file:
        messages.error(request, 'Эхлээд Excel файлаа сонгоно уу.')
    else:
        try:
            fetched, created = import_merchandiser_visits(file_obj=uploaded_file)
            messages.success(request, f'{uploaded_file.name}-с {fetched} бүртгэл уншигдлаа, шинээр {created} мөр хадгалагдлаа.')
        except ValueError as e:
            messages.error(request, f'Файлын бүтэц таарахгүй байна: {e}')
        except Exception as e:
            messages.error(request, f'Файл уншихад алдаа гарлаа: {e}')

    url = reverse('shop:attendance_calc')
    date_from = request.POST.get('date_from')
    date_to = request.POST.get('date_to')
    qs = []
    if date_from:
        qs.append(f'date_from={date_from}')
    if date_to:
        qs.append(f'date_to={date_to}')
    if qs:
        url += '?' + '&'.join(qs)
    return redirect(url)


@login_required
def attendance_position_settings(request):
    """Албан тушаал тус бүрийн ажил эхлэх цагийг тохируулах хуудас (Цаг бүртгэлийн тооцоонд ашиглана).

    Цаг хоосон үлдвэл тухайн албан тушаал 'бусад' дүрмээр (ирсэн цагаас хойш 8 цаг ажиллах ёстой,
    дутсан минутыг хоцролтоор тооцно) тооцоологдоно."""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from shop.models import AttendancePositionRule

    if request.method == 'POST':
        position_names = request.POST.getlist('position_name')
        start_times = request.POST.getlist('start_time')
        for position_name, start_time_str in zip(position_names, start_times):
            start_time_str = (start_time_str or '').strip()
            if start_time_str:
                try:
                    start_time = datetime.strptime(start_time_str, '%H:%M').time()
                except ValueError:
                    continue
                AttendancePositionRule.objects.update_or_create(
                    position_name=position_name,
                    defaults={'start_time': start_time},
                )
            else:
                AttendancePositionRule.objects.filter(position_name=position_name).delete()

        messages.success(request, 'Албан тушаалын ажлын цагийн тохиргоо хадгалагдлаа.')
        return redirect('shop:attendance_position_settings')

    position_names = set(
        OpenDataEmployee.objects.exclude(positionname__isnull=True)
        .exclude(positionname='')
        .values_list('positionname', flat=True)
        .distinct()
    )
    existing_rules = {r.position_name: r.start_time for r in AttendancePositionRule.objects.all()}
    position_names.update(existing_rules.keys())

    rows = [
        {
            'position_name': name,
            'start_time': existing_rules.get(name).strftime('%H:%M') if existing_rules.get(name) else '',
        }
        for name in sorted(position_names)
    ]

    return render(request, 'shop/attendance_position_settings.html', {'rows': rows})


@login_required
def employee_fingerprint(request):
    """Идэвхтэй ажилчдын нэрсийг OpenDataEmployee-ээс харуулж, тус бүрийн хурууны хээ таних
    төхөөрөмж дээрх кодыг (EmployeeFingerprint) засаж хадгалах боломжтой хуудас.

    Цаг бүртгэлийн тооцоо энд хадгалсан кодоор төхөөрөмжийн түүхий бүртгэлийг ажилтантай
    холбодог (data/users.xlsx файлыг орлож байгаа)."""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ хуудас зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    from django.contrib import messages
    from shop.models import EmployeeFingerprint

    if request.method == 'POST':
        employee_codes = request.POST.getlist('employee_code')
        device_user_ids = request.POST.getlist('device_user_id')
        saved = 0
        for employee_code, device_user_id in zip(employee_codes, device_user_ids):
            device_user_id = (device_user_id or '').strip()
            if device_user_id:
                EmployeeFingerprint.objects.update_or_create(
                    employee_code=employee_code,
                    defaults={'device_user_id': device_user_id, 'updated_by': request.user},
                )
                saved += 1
            else:
                EmployeeFingerprint.objects.filter(employee_code=employee_code).delete()

        messages.success(request, f'{saved} ажилтны хурууны код хадгалагдлаа.')
        return redirect('shop:employee_fingerprint')

    employees = list(
        OpenDataEmployee.objects.filter(isreclusion='N')
        .exclude(id__isnull=True).exclude(id='')
        .order_by('name')
    )
    codes = {e.id for e in employees}
    device_codes = dict(
        EmployeeFingerprint.objects.filter(employee_code__in=codes).values_list('employee_code', 'device_user_id')
    )

    rows = [
        {
            'employee_code': e.id,
            'name': e.name,
            'positionname': e.positionname,
            'device_user_id': device_codes.get(e.id, ''),
        }
        for e in employees
    ]

    return render(request, 'shop/employee_fingerprint.html', {'rows': rows})


@login_required
def attendance_save(request):
    """Цаг бүртгэлийн хүснэгтэд хийсэн засварыг тусдаа жагсаалт (AttendanceRecord) болгож хадгална"""
    if not request.user.is_staff:
        from django.contrib import messages
        messages.warning(request, 'Энэ үйлдэл зөвхөн ажилтанд зориулагдсан.')
        return redirect('shop:home')

    if request.method != 'POST':
        return redirect('shop:attendance_calc')

    from django.contrib import messages
    from shop.services.attendance import save_attendance_row

    field_names = [
        'employee_code', 'device_user_id', 'name', 'date', 'weekday',
        'arrived_time', 'left_time', 'late_1_10', 'late_11_20', 'late_20_plus', 'customer_name',
    ]
    lists = [request.POST.getlist(f) for f in field_names]

    saved_count = 0
    errors = []
    for values in zip(*lists):
        row = dict(zip(field_names, values))
        if not row.get('employee_code') or not row.get('date'):
            continue
        try:
            row['date'] = datetime.strptime(row['date'], '%Y-%m-%d').date()
        except ValueError:
            continue
        try:
            save_attendance_row(row, request.user)
            saved_count += 1
        except ValueError as e:
            errors.append(f"{row.get('name') or row['employee_code']} ({row['date']}): {e}")

    if saved_count:
        messages.success(request, f'{saved_count} мөр хадгалагдлаа.')
    if errors:
        # Хэт олон алдаа зэрэг гарвал мессежийг эвдэхгүйн тулд эхний хэдийг л харуулна
        shown = errors[:10]
        more = f' (мөн {len(errors) - 10} мөр)' if len(errors) > 10 else ''
        messages.error(request, 'Дараах мөрүүд буруу утгатай тул хадгалагдсангүй: ' + '; '.join(shown) + more)

    url = reverse('shop:attendance_calc')
    date_from = request.POST.get('date_from')
    date_to = request.POST.get('date_to')
    qs = []
    if date_from:
        qs.append(f'date_from={date_from}')
    if date_to:
        qs.append(f'date_to={date_to}')
    if qs:
        url += '?' + '&'.join(qs)
    return redirect(url)
