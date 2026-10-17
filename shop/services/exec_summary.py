"""
Удирдлагын нэгтгэл (/dashboard/) - сонгосон хугацааны байгууллагын үзүүлэлтүүд бүлэг бүлгээр.

Бүлэг бүрийг тусад нь (идэвхтэй tab) тооцож, OpenData хүснэгтийн хувилбараар кэшлэнэ (report_cache).

Хугацаа: энэ сар (анхдагч, өнөөдрийг хүртэл), өмнөх сар, энэ улирал, энэ он, сонгосон огноо.
Харьцуулалт: өмнөх ижил хугацаа (сар/улирал/оныг календарийн дагуу ижил өдөр хүртэл - "MTD vs өмнөх MTD"),
өнгөрсөн оны мөн үе, эсвэл харьцуулахгүй.

Эх сурвалж:
- Борлуулалт: OpenDataSale (орлого = PayAmount, НӨАТ-гүй = AmountNonVat, өртөг = Qty x UnitCost),
  буцаалт: OpenDataSaleRefund, суваг: OpenDataDistributionChannel, бүртгэлтэй харилцагч: OpenDataCustomer,
  төлөвлөгөө: SalesPlan / SalesPlanItem.
- Бараа материал: хөдөлгөөн (тоо, өртөг) - OpenDataInventory; эхний/эцсийн үлдэгдлийн үнэ - ерөнхий журналын
  1501 (Бараа материал-Агуулах) данс. Хоёулаа хугацааны хөдөлгөөнөөр таардаг ч түүхэн эхний үлдэгдэл зөрдөг тул
  үлдэгдлийг журналаас авна; хөдөлгөөнөөр тайлбарлагдаагүй зөрүүг "Бусад / тохируулга" гэж харуулна.
- Авлага / өглөг: shop.services.recpay_report (OpenDataRecPay) - насжилтыг баримтын огнооноос (ихэнх баримтын
  төлөх огноо нь баримтын огноотой ижил тул "төлөх огнооноос" бол бараг бүгд хэтэрсэн мэт гарна).
  DSO-г зөвхөн худалдааны авлагаар (1201 - Дансны авлага) тооцно; ажилчид, хувь хүний авлагыг дансаар задалж харуулна.
- Мөнгөн хөрөнгө: ерөнхий журналын 10xx (касс), 11xx (банк) данс. Нэг баримтад мөнгөн хөрөнгийн данс дебит,
  кредит хоёуланд орсон бол данс хоорондын шилжүүлэг - орлого/зарлагаас хасна.
"""
import calendar
import re
from datetime import date, timedelta
from decimal import Decimal

from django.db import connection

from shop.services.report_cache import cached

PERIODS = [
    ('this_month', 'Энэ сар'),
    ('last_month', 'Өмнөх сар'),
    ('this_quarter', 'Энэ улирал'),
    ('this_year', 'Энэ он'),
    ('custom', 'Огноо сонгох'),
]
COMPARES = [
    ('prev', 'Өмнөх ижил хугацаа'),
    ('yoy', 'Өнгөрсөн оны мөн үе'),
    ('none', 'Харьцуулахгүй'),
]
SECTIONS = [
    ('sales', 'Борлуулалт', '💰'),
    ('inventory', 'Бараа материал', '📦'),
    ('receivable', 'Авлага', '📥'),
    ('payable', 'Өглөг', '📤'),
    ('cash', 'Мөнгөн хөрөнгө', '🏦'),
    ('hr', 'Хүний нөөц', '👥'),
    ('fleet', 'Тээврийн хэрэгсэл', '🚚'),
]
COMING_SOON = {'fleet'}

HT_PREFIX = 'ХТ'
# Кэшийн түлхүүрийн хувилбар - тооцооны бүтэц өөрчлөгдөхөд нэмэгдүүлнэ (хуучин кэш хэрэглэгдэхгүй)
CACHE_VERSION = 5
INVENTORY_ACCOUNT = '1501%'
CASH_ACCOUNTS = ('10%', '11%')


def _fetch(sql, params=()):
    with connection.cursor() as cursor:
        cursor.execute(sql, list(params))
        columns = [c.name for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _f(value):
    return float(value or 0)


def _pct(part, whole):
    return part / whole * 100 if whole else None


def _change(cur, prev):
    """Өөрчлөлтийн хувь (харьцуулах утга 0/байхгүй бол None)."""
    if prev is None or not prev:
        return None
    return (cur - prev) / abs(prev) * 100


# ---------------------------------------------------------------------------------------------------------
# Хугацаа
# ---------------------------------------------------------------------------------------------------------

def _shift_months(d, months):
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def _parse_date(value):
    try:
        return date.fromisoformat((value or '').strip())
    except ValueError:
        return None


def parse_period(params, today=None):
    """GET параметрээс хугацаа, харьцуулах хугацааг тодорхойлно."""
    today = today or date.today()
    period = params.get('period', 'this_month')
    period = period if period in dict(PERIODS) else 'this_month'
    compare = params.get('compare', 'prev')
    compare = compare if compare in dict(COMPARES) else 'prev'

    months = 1  # календарийн шилжилт (өмнөх ижил хугацаа)
    if period == 'last_month':
        start = _shift_months(today.replace(day=1), -1)
        end = date(start.year, start.month, calendar.monthrange(start.year, start.month)[1])
    elif period == 'this_quarter':
        start, end, months = date(today.year, (today.month - 1) // 3 * 3 + 1, 1), today, 3
    elif period == 'this_year':
        start, end, months = date(today.year, 1, 1), today, 12
    elif period == 'custom':
        start = _parse_date(params.get('date_from')) or today.replace(day=1)
        end = _parse_date(params.get('date_to')) or today
        if start > end:
            start, end = end, start
        months = None
    else:
        start, end = today.replace(day=1), today

    if compare == 'yoy':
        cmp_from, cmp_to = _shift_months(start, -12), _shift_months(end, -12)
    elif compare == 'prev':
        if months:
            cmp_from = _shift_months(start, -months)
            # Сарын сүүлийн өдөр бол өмнөх үеийн мөн сарын сүүлийн өдөр хүртэл (9/30 -> 8/31)
            last_day = end.day == calendar.monthrange(end.year, end.month)[1]
            cmp_to = _shift_months(end, -months)
            if last_day:
                cmp_to = date(cmp_to.year, cmp_to.month, calendar.monthrange(cmp_to.year, cmp_to.month)[1])
        else:
            length = (end - start).days + 1
            cmp_to = start - timedelta(days=1)
            cmp_from = cmp_to - timedelta(days=length - 1)
    else:
        cmp_from = cmp_to = None

    days = (end - start).days + 1
    single_month = start.year == end.year and start.month == end.month
    month_days = calendar.monthrange(start.year, start.month)[1] if single_month else None
    return {
        'period': period, 'compare': compare, 'date_from': start, 'date_to': end,
        'cmp_from': cmp_from, 'cmp_to': cmp_to, 'days': days,
        'single_month': single_month, 'month_days': month_days,
        # Сар дуусаагүй (өнөөдрийг агуулсан) бол сарын эцсийн таамаг гаргана
        'in_progress': single_month and start <= today <= date(start.year, start.month, month_days) and end >= today,
        'today': today,
    }


def _period_payload(p):
    return {k: p[k] for k in ('date_from', 'date_to', 'cmp_from', 'cmp_to')}


# ---------------------------------------------------------------------------------------------------------
# Борлуулалт
# ---------------------------------------------------------------------------------------------------------

SALE = '"OpenDataSale"'
SALES_TABLES = ['OpenDataSale', 'OpenDataSaleRefund', 'OpenDataCustomer', 'OpenDataDistributionChannel', 'OpenDataItem']


def _sales_kpis(d_from, d_to):
    rows = _fetch(f'''
        SELECT COALESCE(SUM("PayAmount"), 0) AS revenue, COALESCE(SUM("AmountNonVat"), 0) AS net,
               COALESCE(SUM("Qty" * "UnitCost"), 0) AS cost, COUNT(DISTINCT "DocumentPkId") AS orders,
               COUNT(DISTINCT NULLIF("CustomerId", '')) AS customers, COUNT(DISTINCT "ItemId") AS skus,
               COALESCE(SUM("Qty"), 0) AS qty, COALESCE(SUM("DiscountAmount"), 0) AS discount
        FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s''', [d_from, d_to])[0]
    refund = _fetch('SELECT COALESCE(SUM("PayAmount"), 0) AS v FROM "OpenDataSaleRefund" WHERE "DocumentDate" BETWEEN %s AND %s',
                    [d_from, d_to])[0]['v']
    k = {key: _f(v) for key, v in rows.items()}
    k['refund'] = _f(refund)
    k['profit'] = k['net'] - k['cost']
    k['margin'] = _pct(k['profit'], k['net'])
    k['aov'] = k['revenue'] / k['orders'] if k['orders'] else 0
    k['refund_rate'] = _pct(k['refund'], k['revenue'])
    return k


def _daily(d_from, d_to):
    return {r['d']: _f(r['v']) for r in _fetch(
        f'SELECT "DocumentDate" AS d, SUM("PayAmount") AS v FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1',
        [d_from, d_to])}


def _channels(d_from, d_to):
    """Суваг бүрийн үзүүлэлт + бүртгэлтэй (идэвхтэй) харилцагчийн тоо."""
    rows = _fetch(f'''
        SELECT COALESCE(s."DistributionChannelId", '') AS id, MAX(COALESCE(dc."Name", '')) AS name,
               SUM(s."PayAmount") AS revenue, SUM(s."AmountNonVat") AS net, SUM(s."Qty" * s."UnitCost") AS cost,
               COUNT(DISTINCT s."DocumentPkId") AS orders, COUNT(DISTINCT NULLIF(s."CustomerId", '')) AS customers,
               COUNT(DISTINCT s."ItemId") AS skus,
               COUNT(DISTINCT (NULLIF(s."CustomerId", ''), s."ItemId")) AS customer_items
        FROM {SALE} s LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = s."DistributionChannelId"
        WHERE s."DocumentDate" BETWEEN %s AND %s GROUP BY 1''', [d_from, d_to])
    registered = {r['id']: r['n'] for r in _fetch(
        'SELECT "DistributionChannelId" AS id, COUNT(*) AS n FROM "OpenDataCustomer" '
        'WHERE "ActiveStatus" = \'Y\' GROUP BY 1')}
    names = {r['Id']: r['Name'] for r in _fetch('SELECT "Id", "Name" FROM "OpenDataDistributionChannel"')}
    result = []
    for r in rows:
        net, cost, customers = _f(r['net']), _f(r['cost']), r['customers']
        result.append({
            'id': r['id'], 'name': r['name'] or names.get(r['id']) or '(суваггүй)',
            'is_ht': (r['name'] or '').startswith(HT_PREFIX),
            'revenue': _f(r['revenue']), 'net': net, 'profit': net - cost, 'margin': _pct(net - cost, net),
            'orders': r['orders'], 'customers': customers, 'skus': r['skus'],
            'aov': _f(r['revenue']) / r['orders'] if r['orders'] else 0,
            'registered': registered.get(r['id'], 0),
            'coverage': _pct(customers, registered.get(r['id'], 0)),
            # Нэг харилцагч дунджаар хэдэн нэр төрлийн бараа авсан (ассортиментийн гүн)
            'depth': r['customer_items'] / customers if customers else 0,
        })
    result.sort(key=lambda r: -r['revenue'])
    return result


def _ht_group_coverage(d_from, d_to):
    """ХТ x барааны бүлэг: тухайн ХТ-ийн худалдан авсан харилцагчдын хэдэн % нь энэ бүлгээс авсан."""
    rows = _fetch(f'''
        SELECT s."DistributionChannelId" AS ch, COALESCE(NULLIF(ig."ItemGroupId", ''), '(бүлэггүй)') AS grp,
               COUNT(DISTINCT s."CustomerId") AS n, SUM(s."PayAmount") AS revenue
        FROM {SALE} s
        JOIN "OpenDataDistributionChannel" dc ON dc."Id" = s."DistributionChannelId"
        LEFT JOIN "OpenDataItem" ig ON ig."Id" = s."ItemId"
        WHERE s."DocumentDate" BETWEEN %s AND %s AND dc."Name" LIKE %s AND COALESCE(s."CustomerId", '') <> ''
        GROUP BY 1, 2''', [d_from, d_to, HT_PREFIX + '%'])
    group_revenue = {}
    for r in rows:
        group_revenue[r['grp']] = group_revenue.get(r['grp'], 0) + _f(r['revenue'])
    groups = [g for g, _ in sorted(group_revenue.items(), key=lambda kv: -kv[1])][:12]
    return {'groups': groups, 'cells': {(r['ch'], r['grp']): r['n'] for r in rows if r['grp'] in groups}}


def _top(d_from, d_to, key, name, limit=10):
    return _fetch(f'''
        SELECT {key} AS id, MAX({name}) AS name, SUM("PayAmount") AS revenue, SUM("Qty") AS qty,
               SUM("AmountNonVat" - "Qty" * "UnitCost") AS profit
        FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s AND COALESCE({key}, '') <> ''
        GROUP BY 1 ORDER BY 3 DESC LIMIT {int(limit)}''', [d_from, d_to])


def _revenue_by(d_from, d_to, key, ids):
    if not d_from or not ids:
        return {}
    return {r['id']: _f(r['v']) for r in _fetch(
        f'SELECT {key} AS id, SUM("PayAmount") AS v FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s '
        f'AND {key} = ANY(%s) GROUP BY 1', [d_from, d_to, list(ids)])}


def _refund_reasons(d_from, d_to):
    return _fetch('''
        SELECT COALESCE(NULLIF("SaleRefundReasonName", ''), '(шалтгаангүй)') AS name, SUM("PayAmount") AS amount,
               COUNT(DISTINCT "DocumentPkId") AS docs
        FROM "OpenDataSaleRefund" WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1 ORDER BY 2 DESC LIMIT 6''',
                  [d_from, d_to])


def _sales_data(p):
    d_from, d_to, c_from, c_to = p['date_from'], p['date_to'], p['cmp_from'], p['cmp_to']
    cur = _sales_kpis(d_from, d_to)
    cmp = _sales_kpis(c_from, c_to) if c_from else None
    channels = _channels(d_from, d_to)
    cmp_channels = {c['id']: c for c in _channels(c_from, c_to)} if c_from else {}
    for c in channels:
        prev = cmp_channels.get(c['id'])
        c['revenue_change'] = _change(c['revenue'], prev['revenue']) if prev else None
        c['coverage_prev'] = prev['coverage'] if prev else None
        c['share'] = _pct(c['revenue'], cur['revenue'])

    top_items = _top(d_from, d_to, '"ItemId"', '"ItemName"')
    top_customers = _top(d_from, d_to, '"CustomerId"', '"CustomerName"')
    prev_items = _revenue_by(c_from, c_to, '"ItemId"', [r['id'] for r in top_items])
    prev_customers = _revenue_by(c_from, c_to, '"CustomerId"', [r['id'] for r in top_customers])
    for rows, prev in ((top_items, prev_items), (top_customers, prev_customers)):
        for r in rows:
            r['revenue'], r['qty'], r['profit'] = _f(r['revenue']), _f(r['qty']), _f(r['profit'])
            r['change'] = _change(r['revenue'], prev.get(r['id'])) if c_from else None
            r['share'] = _pct(r['revenue'], cur['revenue'])

    daily = _daily(d_from, d_to)
    cmp_daily = _daily(c_from, c_to) if c_from else {}
    return {
        'kpis': cur, 'cmp': cmp, 'channels': channels,
        'coverage': _ht_group_coverage(d_from, d_to),
        'top_items': top_items, 'top_customers': top_customers,
        'refund_reasons': [{'name': r['name'], 'amount': _f(r['amount']), 'docs': r['docs']} for r in _refund_reasons(d_from, d_to)],
        'daily': [(d.isoformat(), v) for d, v in sorted(daily.items())],
        'cmp_daily': [(d.isoformat(), v) for d, v in sorted(cmp_daily.items())],
    }


def _cumulative(start, end, daily):
    """Өдөр бүрийн хуримтлагдсан дүн (start..end, борлуулалтгүй өдөр ч орно)."""
    values, total, d = [], 0.0, start
    while d <= end:
        total += daily.get(d.isoformat(), 0)
        values.append(round(total))
        d += timedelta(days=1)
    return values


def _plans(p, channels):
    """Сувгийн төлөвлөгөөний биелэлт ба төлөвлөгөөт барааны биелэлт (хугацаанд орсон сарууд)."""
    from shop.models import SalesPlan, SalesPlanItem
    from shop.services.product_files import item_names

    months = []
    m = p['date_from'].replace(day=1)
    while m <= p['date_to']:
        months.append(m)
        m = _shift_months(m, 1)
    plans = {}
    for plan in SalesPlan.objects.filter(month__in=months):
        plans[plan.channel_id] = plans.get(plan.channel_id, 0) + float(plan.amount)

    # Сар дуусаагүй бол өнөөдрийг хүртэлх "байх ёстой" дүн (төлөвлөгөө x өнгөрсөн хоног / сарын хоног)
    pace = (p['date_to'].day / p['month_days']) if p['in_progress'] else 1
    channel_rows = []
    for c in channels:
        target = plans.get(c['id'])
        if not target and not c['is_ht']:
            continue
        forecast = c['revenue'] / pace if p['in_progress'] and pace else c['revenue']
        channel_rows.append({
            'id': c['id'], 'name': c['name'], 'target': target, 'actual': c['revenue'],
            'pct': _pct(c['revenue'], target), 'pace_pct': _pct(c['revenue'], (target or 0) * pace),
            'forecast': forecast, 'forecast_pct': _pct(forecast, target),
        })
    for cid, target in plans.items():
        if not any(r['id'] == cid for r in channel_rows):
            channel_rows.append({'id': cid, 'name': cid, 'target': target, 'actual': 0, 'pct': 0, 'pace_pct': 0,
                                 'forecast': 0, 'forecast_pct': 0})

    items = list(SalesPlanItem.objects.filter(month__in=months).values('item_id', 'channel_id', 'target_qty'))
    focus = {}
    if items:
        item_ids = sorted({i['item_id'] for i in items})
        sold = {(r['item'], r['ch']): r for r in _fetch(f'''
            SELECT "ItemId" AS item, COALESCE("DistributionChannelId", '') AS ch, SUM("Qty") AS qty,
                   COUNT(DISTINCT NULLIF("CustomerId", '')) AS customers
            FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s AND "ItemId" = ANY(%s) GROUP BY 1, 2''',
                                                         [p['date_from'], p['date_to'], item_ids])}
        names = item_names(item_ids)
        targets = {}
        for i in items:
            key = (i['item_id'], i['channel_id'])
            targets[key] = targets.get(key, 0) + float(i['target_qty'])
        channel_names = {c['id']: c['name'] for c in channels}
        customers = {c['id']: c['customers'] for c in channels}
        for (item_id, ch), target in targets.items():
            s = sold.get((item_id, ch), {})
            row = focus.setdefault(ch, {'channel': channel_names.get(ch, ch), 'items': [], 'target': 0, 'sold': 0, 'done': 0})
            qty = _f(s.get('qty'))
            row['items'].append({'id': item_id, 'name': names.get(item_id, item_id), 'target': target, 'sold': qty,
                                 'pct': _pct(qty, target), 'customers': s.get('customers', 0),
                                 'reach': _pct(s.get('customers', 0), customers.get(ch, 0))})
            row['target'] += target
            row['sold'] += min(qty, target)  # илүү биелэлт бусад барааны дутууг нөхөхгүй
            row['done'] += qty >= target > 0
        for row in focus.values():
            row['items'].sort(key=lambda r: (r['pct'] or 0))
            row['pct'] = _pct(row['sold'], row['target'])
            row['count'] = len(row['items'])
    return {
        'channels': sorted(channel_rows, key=lambda r: -(r['actual'] or 0)),
        'has_plan': bool(plans), 'pace': pace, 'pace_pct': pace * 100,
        'focus': sorted(focus.values(), key=lambda r: r['channel']),
        'months': months,
    }


def sales(p):
    data = cached(f'exec_sales_v{CACHE_VERSION}', SALES_TABLES, _period_payload(p), lambda: _sales_data(p))
    k, c = data['kpis'], data['cmp']
    # Хувь үзүүлэлтийн (ашгийн хувь, буцаалтын хувь) өөрчлөлтийг пунктээр, бусдыг хувиар
    points = ('margin', 'refund_rate')
    data['kpi_changes'] = {
        key: None if not c else ((k[key] - c[key]) if k[key] is not None and c[key] is not None else None)
        if key in points else _change(k[key], c[key]) for key in k}
    daily = dict(data['daily'])
    data['chart'] = {
        'labels': [(p['date_from'] + timedelta(days=i)).isoformat() for i in range(p['days'])],
        'current': _cumulative(p['date_from'], p['date_to'], daily),
        'compare': _cumulative(p['cmp_from'], p['cmp_from'] + timedelta(days=p['days'] - 1), dict(data['cmp_daily']))
        if p['cmp_from'] else [],
    }
    data['forecast'] = (k['revenue'] / p['date_to'].day * p['month_days']) if p['in_progress'] and p['date_to'].day else None
    data['plans'] = _plans(p, data['channels'])
    total_target = sum(r['target'] or 0 for r in data['plans']['channels'])
    data['plan_total'] = {'target': total_target, 'actual': sum(r['actual'] for r in data['plans']['channels'] if r['target']),
                          } if total_target else None
    if data['plan_total']:
        data['plan_total']['pct'] = _pct(data['plan_total']['actual'], total_target)
    data['forecast_pct'] = _pct(data['forecast'], total_target) if data['forecast'] and total_target else None
    # Нэг сарын хугацаанд төлөвлөгөөг өдөрт жигд хуваасан хуримтлагдсан шугам
    if total_target and p['single_month'] and p['date_from'].day == 1:
        data['chart']['plan'] = [round(total_target * (i + 1) / p['month_days']) for i in range(p['days'])]
    cov = data['coverage']
    ht = [ch for ch in data['channels'] if ch['is_ht']]
    # Нүдний өнгө: нэг өнгийн (цэнхэр) дараалсан шатлал, 20%-иар 6 түвшин
    data['heatmap'] = {
        'groups': cov['groups'],
        'rows': [{'name': ch['name'], 'customers': ch['customers'],
                  'cells': [{'v': v, 'lvl': min(5, int((v or 0) // 20)) if v else -1, 'n': cov['cells'].get((ch['id'], g), 0)}
                            for g in cov['groups']
                            for v in [_pct(cov['cells'].get((ch['id'], g), 0), ch['customers'])]]}
                 for ch in ht],
    }
    return data


# ---------------------------------------------------------------------------------------------------------
# Бараа материал
# ---------------------------------------------------------------------------------------------------------

INVENTORY_TABLES = ['OpenDataInventory', 'OpenDataGeneralLedger', 'OpenDataSale']

# Баримтын төрөл -> ангилал. Дотоод хөдөлгөөн (агуулах хооронд) ба эхний үлдэгдлийг тооцохгүй.
MOVE_TYPES = {
    'Татан авалт': 'purchase', 'Худалдан авалт': 'purchase', 'Худалдан авалтын буцаалт': 'purchase',
    'Бараа материалын орлого': 'other_in', 'Агуулахын нярвын орлого': 'other_in',
    'Түгээлтийн хүргэлт': 'sales', 'Түгээлтийн борлуулалт': 'sales', 'Дэлгүүрийн борлуулалт': 'sales',
    'Бараа материал борлуулалт': 'sales',
    'Түгээлтийн буцаалт': 'returns', 'Дэлгүүрийн борлуулалтын буцаалт': 'returns', 'Борлуулалтын буцаалт': 'returns',
    'Бараа материал зарлага': 'expense', 'Агуулахын нярвын зарлага': 'expense', 'Түгээлтийн нярвын зарлага': 'expense',
    'Хангамж тавьж олгох': 'expense',
    'Бараа материалын тооллого': 'count', 'Бараа материалын хөрвүүлэлт': 'conversion',
}
MOVE_LABELS = {
    'purchase': ('Татан авалт', '🚢'), 'other_in': ('Бусад орлого', '➕'), 'sales': ('Борлуулалт', '🛒'),
    'returns': ('Борлуулалтын буцаалт', '↩️'), 'expense': ('Зарлага', '📤'), 'count': ('Тооллогын зөрүү', '🧮'),
    'conversion': ('Хөрвүүлэлт', '🔁'),
}
# Зарлагын шалтгааныг баримтын тайлбараас (DocumentDesc) ангилна - эхнийх нь тааруулбал түүгээр
EXPENSE_REASONS = [
    ('act', 'Акт (устгал, гэмтэл)', r'акт|устга|гэмт|хугацаа\s*дуус|муудс|задарс'),
    ('tasting', 'Амталгаа, дээж', r'амтал|амтлаг|дээж|сурталч|промо'),
    ('lab', 'Шинжилгээ', r'шинжилгээ'),
    ('customs', 'Гааль', r'гааль'),
    ('internal', 'Дотоод хэрэгцээ (гал тогоо, хангамж)', r'гал\s*тог|хангамж|ажилчид|оффис|менежер'),
]
EXPENSE_OTHER = ('other', 'Бусад зарлага')


def expense_reason(desc):
    text = (desc or '').lower()
    for key, label, pattern in EXPENSE_REASONS:
        if re.search(pattern, text):
            return key
    return EXPENSE_OTHER[0]


def _gl_balance(accounts, before):
    """Журналын дансны (LIKE загвар) үлдэгдэл - тухайн огнооноос өмнөх бүх гүйлгээ."""
    where = ' OR '.join('"AccountId" LIKE %s' for _ in accounts)
    return _f(_fetch(f'SELECT SUM("DebitAmt" - "CreditAmt") AS v FROM "OpenDataGeneralLedger" '
                     f'WHERE ({where}) AND "DocumentDate" < %s', [*accounts, before])[0]['v'])


def _inventory_data(p):
    d_from, d_to = p['date_from'], p['date_to']
    types = list(MOVE_TYPES)
    rows = _fetch('''
        SELECT "DocumentType" AS t, COALESCE("DocumentDesc", '') AS descr,
               SUM("InQty") AS in_qty, SUM("OutQty") AS out_qty, SUM("InAmt") AS in_amt, SUM("OutAmt") AS out_amt
        FROM "OpenDataInventory" WHERE "DocumentDate" BETWEEN %s AND %s AND "DocumentType" = ANY(%s)
        GROUP BY 1, 2''', [d_from, d_to, types])
    cats = {key: {'key': key, 'label': label, 'icon': icon, 'in_qty': 0, 'out_qty': 0, 'in_amt': 0, 'out_amt': 0}
            for key, (label, icon) in MOVE_LABELS.items()}
    reasons = {key: {'key': key, 'label': label, 'qty': 0, 'amount': 0}
               for key, label, _ in EXPENSE_REASONS + [EXPENSE_OTHER + (None,)]}
    for r in rows:
        cat = cats[MOVE_TYPES[r['t']]]
        for f in ('in_qty', 'out_qty', 'in_amt', 'out_amt'):
            cat[f] += _f(r[f])
        if MOVE_TYPES[r['t']] == 'expense':
            reason = reasons[expense_reason(r['descr'])]
            reason['qty'] += _f(r['out_qty']) - _f(r['in_qty'])
            reason['amount'] += _f(r['out_amt']) - _f(r['in_amt'])

    revenue = _fetch(f'SELECT SUM("PayAmount") AS revenue, SUM("AmountNonVat") AS net FROM {SALE} '
                     f'WHERE "DocumentDate" BETWEEN %s AND %s', [d_from, d_to])[0]
    opening = _gl_balance([INVENTORY_ACCOUNT], d_from)
    closing = _gl_balance([INVENTORY_ACCOUNT], d_to + timedelta(days=1))

    # Актласан бараа (зарлагын тайлбараар) - үнээр эхний 10
    expense_items = _fetch('''
        SELECT "ItemName" AS name, COALESCE("DocumentDesc", '') AS descr, SUM("OutQty" - "InQty") AS qty,
               SUM("OutAmt" - "InAmt") AS amount
        FROM "OpenDataInventory" WHERE "DocumentDate" BETWEEN %s AND %s
          AND "DocumentType" IN ('Бараа материал зарлага', 'Агуулахын нярвын зарлага', 'Түгээлтийн нярвын зарлага')
        GROUP BY 1, 2''', [d_from, d_to])
    act_items = {}
    for r in expense_items:
        if expense_reason(r['descr']) == 'act':
            item = act_items.setdefault(r['name'], {'name': r['name'], 'qty': 0, 'amount': 0})
            item['qty'] += _f(r['qty'])
            item['amount'] += _f(r['amount'])

    # Хугацаанд борлуулалтгүй ч үлдэгдэлтэй бараа (удаан эргэлттэй)
    slow = _fetch(f'''
        SELECT s.itemname AS name, s.total_qty AS qty, s.avg_unitcost AS cost, s.total_qty * s.avg_unitcost AS value
        FROM inventory_snapshot s
        WHERE s.total_qty > 0 AND NOT EXISTS (
            SELECT 1 FROM {SALE} x WHERE x."ItemName" = s.itemname AND x."DocumentDate" BETWEEN %s AND %s)
        ORDER BY 4 DESC''', [d_from, d_to])
    return {
        'cats': cats, 'reasons': reasons, 'opening': opening, 'closing': closing,
        'revenue': _f(revenue['revenue']), 'net': _f(revenue['net']),
        'act_items': sorted(act_items.values(), key=lambda r: -r['amount'])[:10],
        'slow': [{'name': r['name'], 'qty': _f(r['qty']), 'value': _f(r['value'])} for r in slow],
    }


def inventory(p):
    data = cached(f'exec_inventory_v{CACHE_VERSION}', INVENTORY_TABLES, _period_payload(p), lambda: _inventory_data(p))
    c = data['cats']
    cogs = c['sales']['out_amt'] - c['sales']['in_amt']
    returns = c['returns']['in_amt'] - c['returns']['out_amt']
    purchase = c['purchase']['in_amt'] - c['purchase']['out_amt']
    other_in = c['other_in']['in_amt'] - c['other_in']['out_amt']
    expense = c['expense']['out_amt'] - c['expense']['in_amt']
    count = c['count']['in_amt'] - c['count']['out_amt']
    conversion = c['conversion']['in_amt'] - c['conversion']['out_amt']
    explained = data['opening'] + purchase + other_in + returns - cogs - expense + count + conversion
    adjustment = data['closing'] - explained
    steps = [('Эхний үлдэгдэл', data['opening'], 'total'), ('Татан авалт', purchase, 'up'), ('Бусад орлого', other_in, 'up'),
             ('Буцаалт', returns, 'up'), ('Борлуулалтын өртөг', -cogs, 'down'), ('Зарлага', -expense, 'down'),
             ('Тооллого', count, 'delta'), ('Хөрвүүлэлт', conversion, 'delta'), ('Бусад / тохируулга', adjustment, 'delta'),
             ('Эцсийн үлдэгдэл', data['closing'], 'total')]
    data['waterfall'] = [{'label': label, 'value': v, 'kind': kind} for label, v, kind in steps
                         if kind == 'total' or abs(v) >= 1]
    avg_inv = (data['opening'] + data['closing']) / 2
    sales_qty = c['sales']['out_qty'] - c['sales']['in_qty']
    data['kpis'] = {
        'closing': data['closing'], 'change': _change(data['closing'], data['opening']),
        'purchase': purchase, 'purchase_qty': c['purchase']['in_qty'] - c['purchase']['out_qty'],
        'cogs': cogs, 'sales_qty': sales_qty, 'revenue': data['revenue'],
        'gross_profit': data['net'] - cogs, 'margin': _pct(data['net'] - cogs, data['net']),
        'expense': expense, 'expense_qty': c['expense']['out_qty'] - c['expense']['in_qty'],
        'act': data['reasons']['act']['amount'],
        # Бараа материалын эргэлтийн хоног (DIO) = дундаж үлдэгдэл / борлуулалтын өртөг x хоног
        'dio': avg_inv / cogs * p['days'] if cogs > 0 else None,
        'turnover': cogs / avg_inv * (365 / p['days']) if avg_inv > 0 else None,
        'slow_count': len(data['slow']), 'slow_value': sum(r['value'] for r in data['slow']),
        'returns': returns,
    }
    data['rows'] = [{**cat, 'net_amt': cat['in_amt'] - cat['out_amt'], 'net_qty': cat['in_qty'] - cat['out_qty']}
                    for cat in c.values() if cat['in_qty'] or cat['out_qty'] or cat['in_amt'] or cat['out_amt']]
    data['reason_rows'] = sorted([r for r in data['reasons'].values() if r['qty'] or r['amount']], key=lambda r: -r['amount'])
    data['slow_top'] = data['slow'][:10]
    return data


# ---------------------------------------------------------------------------------------------------------
# Авлага, өглөг
# ---------------------------------------------------------------------------------------------------------

RECPAY_TABLES = ['OpenDataRecPay', 'OpenDataSale', 'OpenDataInventory']
TRADE_RECEIVABLE = '1201'  # Дансны авлага (худалдааны)


def _recpay_data(kind, p):
    from shop.services import recpay_report as rr
    filters = {'date_from': p['date_from'], 'date_to': p['date_to'], 'aging_basis': 'doc', 'balance': 'nonzero',
               'group_by': 'customer'}
    report = rr.build_report(kind, filters)
    result = {'kpis': report['kpis'], 'aging': report['aging'], 'top': report['top'], 'trend': report['trend']}
    by_account = rr.build_report(kind, {**filters, 'group_by': 'account'})['rows']
    result['accounts'] = sorted(by_account, key=lambda r: -abs(r['closing']))[:10]
    result['trade'] = sum(r['closing'] for r in by_account if r['key'].startswith(TRADE_RECEIVABLE))
    if p['cmp_to']:
        prev = rr.build_report(kind, {**filters, 'date_from': p['cmp_from'], 'date_to': p['cmp_to']})['kpis']
        result['cmp'] = {k: prev[k] for k in ('closing', 'positive', 'risk', 'risk_share', 'increase', 'decrease')}
    else:
        result['cmp'] = None
    return result


def recpay(kind, p):
    data = cached(f'exec_{kind}_v{CACHE_VERSION}', RECPAY_TABLES, _period_payload(p), lambda: _recpay_data(kind, p))
    k = data['kpis']
    if kind == 'receivable':
        base = _f(_fetch(f'SELECT SUM("PayAmount") AS v FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s',
                         [p['date_from'], p['date_to']])[0]['v'])
    else:
        base = _f(_fetch('''SELECT SUM("OutAmt" - "InAmt") AS v FROM "OpenDataInventory" WHERE "DocumentDate" BETWEEN %s AND %s
                            AND "DocumentType" IN ('Түгээлтийн борлуулалт', 'Дэлгүүрийн борлуулалт', 'Бараа материал борлуулалт')''',
                         [p['date_from'], p['date_to']])[0]['v'])
    # DSO / DPO - үлдэгдэл хэдэн хоногийн борлуулалт (өртөг)-тэй тэнцэх вэ. DSO-д зөвхөн худалдааны авлага
    k['trade'] = data['trade'] if kind == 'receivable' else k['positive']
    k['days'] = k['trade'] / base * p['days'] if base > 0 else None
    k['base'] = base
    # Цуглуулалт / төлөлтийн хувь = төлөгдсөн / (эхний үлдэгдэл + нэмэгдсэн)
    k['collection'] = _pct(k['decrease'], k['opening'] + k['increase'])
    cmp = data['cmp']
    data['changes'] = {key: _change(k[key], cmp[key]) for key in ('closing', 'risk', 'increase', 'decrease')} if cmp else {}
    data['risk_share_delta'] = (k['risk_share'] - cmp['risk_share']) if cmp else None
    return data


# ---------------------------------------------------------------------------------------------------------
# Мөнгөн хөрөнгө
# ---------------------------------------------------------------------------------------------------------

CASH_TABLES = ['OpenDataGeneralLedger']
CURRENCY_RE = re.compile(r'/\s*(USD|EUR|RUS|RUB|CNY|GBP|JPY)\s*/', re.I)


def _cash_data(p):
    d_from, d_to = p['date_from'], p['date_to']
    acc = '("AccountId" LIKE %s OR "AccountId" LIKE %s)'
    # Нэг баримтад мөнгөн хөрөнгийн данс дебит, кредит хоёуланд орсон бол - данс хоорондын шилжүүлэг
    transfer_cte = f'''
        WITH t AS (
            SELECT "DocumentPkId" FROM "OpenDataGeneralLedger"
            WHERE {acc} AND "DocumentDate" BETWEEN %s AND %s GROUP BY 1
            HAVING BOOL_OR("DebitAmt" > 0) AND BOOL_OR("CreditAmt" > 0)
        )'''
    base_params = [*CASH_ACCOUNTS, d_from, d_to]
    accounts = _fetch(f'''
        SELECT "AccountId" AS id, MAX("AccountName") AS name,
               SUM(CASE WHEN "DocumentDate" < %s THEN "DebitAmt" - "CreditAmt" ELSE 0 END) AS opening,
               SUM(CASE WHEN "DocumentDate" >= %s THEN "DebitAmt" ELSE 0 END) AS debit,
               SUM(CASE WHEN "DocumentDate" >= %s THEN "CreditAmt" ELSE 0 END) AS credit,
               SUM("DebitAmt" - "CreditAmt") AS closing
        FROM "OpenDataGeneralLedger" WHERE {acc} AND "DocumentDate" <= %s GROUP BY 1 ORDER BY 1''',
                      [d_from, d_from, d_from, *CASH_ACCOUNTS, d_to])
    flows = _fetch(f'''{transfer_cte}
        SELECT CASE WHEN g."DocumentPkId" IN (SELECT "DocumentPkId" FROM t) THEN '__transfer__'
                    ELSE COALESCE(NULLIF(g."CashFlowPropertyName", ''), '(ангилаагүй)') END AS cat,
               SUM(g."DebitAmt") AS inflow, SUM(g."CreditAmt") AS outflow
        FROM "OpenDataGeneralLedger" g
        WHERE {acc.replace('"AccountId"', 'g."AccountId"')} AND g."DocumentDate" BETWEEN %s AND %s
        GROUP BY 1''', [*base_params, *CASH_ACCOUNTS, d_from, d_to])
    daily = _fetch(f'''
        SELECT "DocumentDate" AS d, SUM("DebitAmt" - "CreditAmt") AS net
        FROM "OpenDataGeneralLedger" WHERE {acc} AND "DocumentDate" BETWEEN %s AND %s GROUP BY 1 ORDER BY 1''',
                   base_params)
    # Сүүлийн 3 бүтэн сарын гадагшлах урсгал (шилжүүлэггүй) - мөнгөний хүрэлцээг тооцоход
    m3_to = d_to.replace(day=1) - timedelta(days=1)
    m3_from = _shift_months(m3_to.replace(day=1), -2)
    burn = _fetch(f'''
        WITH t AS (
            SELECT "DocumentPkId" FROM "OpenDataGeneralLedger"
            WHERE {acc} AND "DocumentDate" BETWEEN %s AND %s GROUP BY 1
            HAVING BOOL_OR("DebitAmt" > 0) AND BOOL_OR("CreditAmt" > 0)
        )
        SELECT SUM("CreditAmt") AS outflow, SUM("DebitAmt") AS inflow FROM "OpenDataGeneralLedger"
        WHERE {acc} AND "DocumentDate" BETWEEN %s AND %s AND "DocumentPkId" NOT IN (SELECT "DocumentPkId" FROM t)''',
                  [*CASH_ACCOUNTS, m3_from, m3_to, *CASH_ACCOUNTS, m3_from, m3_to])[0]
    return {
        'accounts': [{**r, **{k: _f(r[k]) for k in ('opening', 'debit', 'credit', 'closing')}} for r in accounts],
        'flows': [{'cat': r['cat'], 'inflow': _f(r['inflow']), 'outflow': _f(r['outflow'])} for r in flows],
        'daily': [(r['d'].isoformat(), _f(r['net'])) for r in daily],
        'burn': {'outflow': _f(burn['outflow']) / 3, 'inflow': _f(burn['inflow']) / 3,
                 'from': m3_from.isoformat(), 'to': m3_to.isoformat()},
    }


def cash(p):
    data = cached(f'exec_cash_v{CACHE_VERSION}', CASH_TABLES, _period_payload(p), lambda: _cash_data(p))
    accounts = data['accounts']
    for a in accounts:
        m = CURRENCY_RE.search(a['name'] or '')
        a['currency'] = (m.group(1).upper().replace('RUS', 'RUB') if m else 'MNT')
        a['kind'] = 'Касс' if a['id'].startswith('10') else 'Банк'
    opening = sum(a['opening'] for a in accounts)
    closing = sum(a['closing'] for a in accounts)
    transfer = next((f for f in data['flows'] if f['cat'] == '__transfer__'), {'inflow': 0, 'outflow': 0})
    external = [f for f in data['flows'] if f['cat'] != '__transfer__']
    inflow = sum(f['inflow'] for f in external)
    outflow = sum(f['outflow'] for f in external)
    running, series, d = opening, [], p['date_from']
    daily = dict(data['daily'])
    while d <= p['date_to']:
        running += daily.get(d.isoformat(), 0)
        series.append(round(running))
        d += timedelta(days=1)
    burn = data['burn']
    data['kpis'] = {
        'opening': opening, 'closing': closing, 'inflow': inflow, 'outflow': outflow, 'net': inflow - outflow,
        'transfer': transfer['inflow'], 'change': _change(closing, opening),
        'mnt': sum(a['closing'] for a in accounts if a['currency'] == 'MNT'),
        'fx': sum(a['closing'] for a in accounts if a['currency'] != 'MNT'),
        'bank': sum(a['closing'] for a in accounts if a['kind'] == 'Банк'),
        'cashbox': sum(a['closing'] for a in accounts if a['kind'] == 'Касс'),
        'burn': burn['outflow'], 'burn_net': burn['outflow'] - burn['inflow'],
        # Мөнгөний хүрэлцээ - одоогийн үлдэгдэл сарын дундаж зарлагыг хэдэн сар даах вэ
        'runway': closing / burn['outflow'] if burn['outflow'] > 0 else None,
    }
    data['in_cats'] = sorted([f for f in external if f['inflow'] >= 1], key=lambda f: -f['inflow'])[:8]
    data['out_cats'] = sorted([f for f in external if f['outflow'] >= 1], key=lambda f: -f['outflow'])[:8]
    data['chart'] = {'labels': [(p['date_from'] + timedelta(days=i)).isoformat() for i in range(p['days'])], 'balance': series}
    data['accounts'] = sorted([a for a in accounts if abs(a['closing']) >= 1 or a['debit'] or a['credit']],
                              key=lambda a: -a['closing'])
    return data


BUILDERS = {'sales': sales, 'inventory': inventory, 'cash': cash,
            'receivable': lambda p: recpay('receivable', p), 'payable': lambda p: recpay('payable', p)}


# ---------------------------------------------------------------------------------------------------------
# Хүний нөөц
# ---------------------------------------------------------------------------------------------------------
# Ажилтны тоо, шилжилт хөдөлгөөн - OpenDataEmployee (HireDate, IsReclusion/ReclusionDate). Тухайн өдрийн ажилтан =
#   ажилд орсон <= өдөр ба (гараагүй эсвэл гарсан огноо > өдөр). Огноогүй ч гарсан (IsReclusion='Y') ажилтныг тоолохгүй.
# Цалин - payroll_snapshot.payroll_facts (хаагдсан сард хадгалсан хувилбар, бусад сард шууд бодолт; карт + бэлэн).
#   Дуусаагүй сарын цалин нь өнөөдрийг хүртэлх ирцээрх урьдчилсан бодолт.
# Ирц - timesheet.build_timesheet: ажилласан / ажиллавал зохих хоног (дуусаагүй сард хурууны хээний сүүлийн бүртгэлийн
#   өдөр хүртэлх ажлын өдрөөр хувьтгана), хоцролт (минут), чөлөө, тайлбаргүй тасалсан хоног.
# Цалин, ирцийг энэ системд анх цалин бодсон сараас (PayrollEntry / PayrollMonthClose) хойш л тооцно - өмнөх
#   саруудын бодолт бүрэн бус өгөгдөлтэй тул. Ажилтны тоо, эргэлт нь ажилтны бүртгэлээс бүх хугацаагаар.
# Хувь хүний цалинг харуулахгүй - зөвхөн нэгтгэл.

HR_TABLES = ['OpenDataEmployee', 'OpenDataSale', 'shop_payroll_entry', 'shop_payroll_month_close',
             'shop_attendance_record', 'shop_attendance_raw_log', 'shop_timesheet_entry', 'shop_employee_pay_profile']


def _hr_start():
    """Цалин, ирцийн тооцоо эхэлсэн сар (он, сар) - системд анх цалин бодсон/хаасан сар."""
    from shop.models import PayrollEntry, PayrollMonthClose
    found = [(r['year'], r['month']) for model in (PayrollEntry, PayrollMonthClose)
             for r in model.objects.order_by('year', 'month').values('year', 'month')[:1]]
    return min(found) if found else None


def _attendance_through(today):
    """Хурууны хээний сүүлийн бүртгэлийн өдөр (ирээдүйн огноотой алдаатай бүртгэлийг тооцохгүй)."""
    from django.utils import timezone
    from shop.models import AttendanceRawLog
    last = (AttendanceRawLog.objects.filter(timestamp__lte=timezone.now()).order_by('-timestamp')
            .values_list('timestamp', flat=True).first())
    return min(timezone.localtime(last).date(), today) if last else today


def _months_in(d_from, d_to):
    months, m = [], d_from.replace(day=1)
    while m <= d_to:
        months.append((m.year, m.month))
        m = _shift_months(m, 1)
    return months


def _employees():
    return _fetch('''
        SELECT "Id" AS code, "Name" AS name, COALESCE(NULLIF("DepartmentName", ''), 'Тодорхойгүй') AS department,
               COALESCE(NULLIF("PositionName", ''), 'Тодорхойгүй') AS position, "Gender" AS gender,
               "BirthDate" AS birth, "HireDate" AS hired, "IsReclusion" AS left_flag, "ReclusionDate" AS left_on
        FROM "OpenDataEmployee" WHERE COALESCE("Id", '') <> '' ''')


def _active_on(e, day):
    if not e['hired'] or e['hired'] > day:
        return False
    if e['left_on']:
        return e['left_on'] > day
    return e['left_flag'] != 'Y'


def _years(start, on):
    if not start:
        return None
    return on.year - start.year - ((on.month, on.day) < (start.month, start.day))


def _band_label(value, bands):
    from shop.services.payroll_snapshot import UNKNOWN
    if value is None:
        return UNKNOWN
    for limit, label in bands:
        if limit is None or value < limit:
            return label
    return UNKNOWN


def _counts(items, key, order=None):
    result = {}
    for item in items:
        result[item[key]] = result.get(item[key], 0) + 1
    rows = [{'label': k, 'count': v} for k, v in result.items()]
    if order:
        rows.sort(key=lambda r: order.get(r['label'], 99))
    else:
        rows.sort(key=lambda r: (-r['count'], r['label']))
    return rows


def _payroll(months):
    from shop.services.payroll_snapshot import payroll_facts
    facts, status = payroll_facts(months, ['card', 'cash'])
    keys = ('gross', 'ndsh_employer', 'ndsh_employee', 'pit', 'net_pay', 'employer_cost', 'sales_bonus', 'deductions')
    total = {k: float(sum((f[k] for f in facts), Decimal(0))) for k in keys}
    by_dept = {}
    for f in facts:
        d = by_dept.setdefault(f['department'] or 'Тодорхойгүй', {'label': f['department'] or 'Тодорхойгүй', 'cost': 0.0,
                                                                   'gross': 0.0, 'people': set(), 'months': set()})
        d['cost'] += float(f['employer_cost'])
        d['gross'] += float(f['gross'])
        d['people'].add(f['employee_code'])
        d['months'].add((f['employee_code'], f['year'], f['month']))
    depts = []
    for d in by_dept.values():
        employee_months = len(d.pop('months'))
        d['people'] = len(d['people'])
        d['avg_gross'] = d['gross'] / employee_months if employee_months else 0
        depts.append(d)
    depts.sort(key=lambda d: -d['cost'])
    employee_months = len({(f['employee_code'], f['year'], f['month']) for f in facts})
    total['avg_gross'] = total['gross'] / employee_months if employee_months else 0
    total['people'] = len({f['employee_code'] for f in facts})
    sheet_labels = {'card': 'карт', 'cash': 'бэлэн'}
    closed = sorted(f'{y}.{m:02d} {sheet_labels[sheet]}' for (y, m, sheet), close in status.items() if close)
    return {'total': total, 'departments': depts, 'closed': closed,
            'open': sorted(f'{y}.{m:02d} {sheet_labels[sheet]}' for (y, m, sheet), close in status.items() if not close)}


def _attendance(months, through, employees):
    from shop.services.timesheet import build_timesheet
    dept_of = {e['code']: e['department'] for e in employees}
    keys = ('required_days', 'worked_days', 'leave_days', 'late_1_10', 'late_11_20', 'late_21_30', 'unexplained_days')
    total = {k: 0.0 for k in keys}
    by_dept = {}
    late_people = {}
    pending = set()  # дуусаагүй сард бүртгэл нь хараахан ороогүй ажилтан
    for year, month in months:
        days, _, rows, _, _ = build_timesheet(year, month)
        workdays = [d for d in days if not d['is_sunday'] and not d['is_holiday']]
        # Дуусаагүй сард ажиллавал зохих хоногийг өнгөрсөн ажлын өдрийн хувиар
        ratio = 1.0
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        if through < month_end and workdays:
            ratio = sum(1 for d in workdays if d['date'] <= through) / len(workdays)
        for r in rows:
            if not r.get('is_main', True):
                continue
            # ХТ-ийн айлчлал (Document.xlsx), худалдагчийн хоног сарын эцэст ордог тул дуусаагүй сард бүртгэлгүй
            # ажилтныг тасалсан гэж тооцохгүй
            if ratio < 1 and not r.get('worked_days'):
                pending.add(r['name'])
                continue
            dept = dept_of.get(r['employee_code'], 'Тодорхойгүй')
            d = by_dept.setdefault(dept, {'label': dept, **{k: 0.0 for k in keys}})
            values = {k: float(r.get(k) or 0) for k in keys}
            values['required_days'] *= ratio
            # Цаг бүртгүүлдэггүй албан тушаалд ажилласан хоног = сарын зохих хоног тул хувьтгасан хэмжээнээс хэтрүүлэхгүй
            values['worked_days'] = min(values['worked_days'], values['required_days'])
            values['unexplained_days'] = max(values['unexplained_days'], 0)
            for k in keys:
                total[k] += values[k]
                d[k] += values[k]
            late = values['late_1_10'] + values['late_11_20'] + values['late_21_30']
            if late:
                p = late_people.setdefault(r['employee_code'], {'name': r['name'], 'position': r['positionname'] or '', 'minutes': 0})
                p['minutes'] += late
    for row in [total, *by_dept.values()]:
        row['rate'] = min(_pct(row['worked_days'], row['required_days']) or 0, 100) if row['required_days'] else None
        row['late'] = row['late_1_10'] + row['late_11_20'] + row['late_21_30']
    return {'total': total, 'departments': sorted(by_dept.values(), key=lambda d: (d['rate'] is None, d['rate'] or 0)),
            'late_top': sorted(late_people.values(), key=lambda p: -p['minutes'])[:8], 'pending': sorted(pending)}


def _hr_data(p):
    from shop.services.payroll_snapshot import AGE_BANDS, GENDER_LABELS, TENURE_BANDS
    d_from, d_to, today = p['date_from'], p['date_to'], p['today']
    employees = _employees()
    start_day = d_from - timedelta(days=1)
    active = [e for e in employees if _active_on(e, d_to)]
    active_start = [e for e in employees if _active_on(e, start_day)]
    hires = [e for e in employees if e['hired'] and d_from <= e['hired'] <= d_to]
    leavers = [e for e in employees if e['left_on'] and d_from <= e['left_on'] <= d_to]
    avg_headcount = (len(active) + len(active_start)) / 2

    # Сүүлийн 12 сарын ажилтны тоо (сарын эцэст), орсон, гарсан
    trend, m = [], _shift_months(d_to.replace(day=1), -11)
    while m <= d_to:
        end = min(date(m.year, m.month, calendar.monthrange(m.year, m.month)[1]), d_to)
        trend.append({
            'label': f'{m.year}.{m.month:02d}',
            'headcount': sum(1 for e in employees if _active_on(e, end)),
            'hires': sum(1 for e in employees if e['hired'] and m <= e['hired'] <= end),
            'leavers': sum(1 for e in employees if e['left_on'] and m <= e['left_on'] <= end),
        })
        m = _shift_months(m, 1)

    for e in active:
        e['age_band'] = _band_label(_years(e['birth'], d_to), AGE_BANDS)
        e['tenure_band'] = _band_label(_years(e['hired'], d_to), TENURE_BANDS)
        e['gender_label'] = GENDER_LABELS.get(e['gender'], 'Тодорхойгүй')
    age_order = {label: i for i, (_, label) in enumerate(AGE_BANDS)}
    tenure_order = {label: i for i, (_, label) in enumerate(TENURE_BANDS)}
    tenures = [_years(e['hired'], d_to) for e in active if e['hired']]
    ages = [_years(e['birth'], d_to) for e in active if e['birth']]

    start = _hr_start()
    months = [m for m in _months_in(d_from, d_to) if start and m >= start]
    skipped = [f'{y}.{m:02d}' for y, m in _months_in(d_from, d_to) if not start or (y, m) < start]
    payroll = _payroll(months) if months else None
    cmp = None
    if p['cmp_from']:
        cmp = {'headcount': sum(1 for e in employees if _active_on(e, p['cmp_to'])), 'cost': None, 'avg_gross': None}
        cmp_months = _months_in(p['cmp_from'], p['cmp_to'])
        # Харьцуулах хугацааны бүх сар цалингийн тооцоотой үед л цалинг харьцуулна
        if start and cmp_months[0] >= start:
            cmp_payroll = _payroll(cmp_months)['total']
            cmp.update(cost=cmp_payroll['employer_cost'], avg_gross=cmp_payroll['avg_gross'])
    revenue = _f(_fetch(f'SELECT SUM("PayAmount") AS v FROM {SALE} WHERE "DocumentDate" BETWEEN %s AND %s',
                        [d_from, d_to])[0]['v'])

    def person(e, field):
        return {'name': e['name'], 'position': e['position'], 'department': e['department'], 'date': e[field].isoformat()}

    # Энэ болон дараагийн 30 хоногт төрсөн өдөр, ойтой ажилтан (сэтгэл ханамж)
    upcoming = []
    for e in active:
        for kind, base in (('birthday', e['birth']), ('anniversary', e['hired'])):
            if not base:
                continue
            try:
                nxt = base.replace(year=today.year)
            except ValueError:  # 2-р сарын 29
                nxt = date(today.year, 3, 1)
            if nxt < today:
                nxt = nxt.replace(year=today.year + 1) if not (nxt.month == 2 and nxt.day == 29) else date(today.year + 1, 3, 1)
            if (nxt - today).days <= 30:
                years = nxt.year - base.year
                if kind == 'anniversary' and years < 1:
                    continue
                upcoming.append({'kind': kind, 'name': e['name'], 'position': e['position'], 'date': nxt.isoformat(),
                                 'days': (nxt - today).days, 'years': years})
    upcoming.sort(key=lambda u: u['days'])

    return {
        'headcount': len(active), 'headcount_start': len(active_start), 'hires': len(hires), 'leavers': len(leavers),
        'turnover': _pct(len(leavers), avg_headcount),
        # Жилд шилжүүлсэн эргэлт = хугацааны эргэлт x 365 / хоног
        'turnover_annual': (_pct(len(leavers), avg_headcount) or 0) * 365 / p['days'] if avg_headcount else None,
        'hire_list': [person(e, 'hired') for e in sorted(hires, key=lambda e: e['hired'], reverse=True)],
        'leaver_list': [person(e, 'left_on') for e in sorted(leavers, key=lambda e: e['left_on'], reverse=True)],
        'trend': trend,
        'departments': _counts(active, 'department'),
        'genders': _counts(active, 'gender_label'),
        'ages': _counts(active, 'age_band', age_order),
        'tenures': _counts(active, 'tenure_band', tenure_order),
        'avg_tenure': sum(tenures) / len(tenures) if tenures else None,
        'avg_age': sum(ages) / len(ages) if ages else None,
        'payroll': payroll, 'cmp': cmp, 'revenue': revenue,
        'attendance': _attendance(months, _attendance_through(today), employees) if months else None,
        'attendance_through': _attendance_through(today).isoformat(),
        'hr_start': f'{start[0]}.{start[1]:02d}' if start else None, 'skipped_months': skipped,
        'upcoming': upcoming[:10],
    }


def hr(p):
    data = cached(f'exec_hr_v{CACHE_VERSION}', HR_TABLES, {**_period_payload(p), 'today': p['today']}, lambda: _hr_data(p))
    pay = data['payroll']['total'] if data['payroll'] else None
    cmp = data['cmp']
    # Цалин сараар бодогддог тул дуусаагүй сарын урьдчилсан цалинг өмнөх үеийн бүтэн сартай харьцуулахгүй
    pay_cmp = cmp if cmp and not p['in_progress'] else None
    data['kpis'] = {
        'headcount': data['headcount'],
        'headcount_change': (data['headcount'] - cmp['headcount']) if cmp else None,
        'cost': pay['employer_cost'] if pay else None,
        'cost_change': _change(pay['employer_cost'], pay_cmp['cost']) if pay and pay_cmp and pay_cmp['cost'] else None,
        'avg_gross': pay['avg_gross'] if pay else None,
        'avg_gross_change': _change(pay['avg_gross'], pay_cmp['avg_gross']) if pay and pay_cmp and pay_cmp['avg_gross'] else None,
        # Цалингийн зардал борлуулалтын хэдэн хувь (цалингийн тооцоотой сарын борлуулалттай харьцуулна)
        'cost_ratio': _pct(pay['employer_cost'], data['revenue']) if pay and not data['skipped_months'] else None,
        'revenue_per_head': data['revenue'] / data['headcount'] if data['headcount'] else None,
        'attendance': data['attendance']['total']['rate'] if data['attendance'] else None,
    }
    if pay:
        data['payroll_parts'] = [
            ('Гарт олгох', pay['net_pay']), ('ХХОАТ', pay['pit']), ('НДШ ажилтан', pay['ndsh_employee']),
            ('Суутгал', pay['deductions']), ('НДШ байгууллага', pay['ndsh_employer']),
        ]
    data['payroll_in_progress'] = bool(pay) and bool(data['payroll']['open']) and p['in_progress']
    return data


BUILDERS['hr'] = hr
