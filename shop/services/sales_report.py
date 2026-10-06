"""
Борлуулалтын тайлан (/dashboard/sales-report/) - OpenDataSale хүснэгтээс.

Хурдны шийдэл:
- Баганын бодит төрлөөр (DocumentDate = date, дүн = double) шууд SQL - Cast хийхгүй тул индекс ашиглагдана
  (индекс: datamigration.opendata_indexes, синк бүрийн дараа сэргээгдэнэ).
- Нэгтгэлийн бүх түвшинг (сар, жил, нийт - давхардаагүй харилцагчтай) GROUPING SETS-ээр нэг query-д.
- Үр дүнг хүснэгтийн "хувилбар"-аар (pg_class OID + өөрчлөлтийн тоолуур) кэшлэнэ: синк хүснэгтийг дахин
  үүсгэхэд OID солигдох тул кэш автоматаар хүчингүй болно.

Үзүүлэлт: орлого = PayAmount, НӨАТ-гүй = AmountNonVat, өртөг = UnitCost x Qty, ашиг = НӨАТ-гүй - өртөг,
захиалга = давхардаагүй баримт (DocumentPkId).
"""
from datetime import date, timedelta

from django.db import connection

TABLE = '"OpenDataSale"'

# Барааны бүлэг: OpenDataItem.ItemGroupId (борлуулалтын ItemCategoryName/BrandName хоосон байдаг тул)
ITEM_GROUP_JOIN = 'LEFT JOIN "OpenDataItem" ig ON ig."Id" = "OpenDataSale"."ItemId"'
ITEM_GROUP = 'COALESCE(NULLIF(ig."ItemGroupId", \'\'), \'(бүлэггүй)\')'

# Олон сонголттой шүүлт: параметр -> багана
MULTI_FILTERS = {
    'channel': '"DistributionChannelName"',
    'group': '"ItemId" IN (SELECT "Id" FROM "OpenDataItem" WHERE "ItemGroupId" = ANY(%s))',
    'warehouse': '"WarehouseName"',
    'seller': '"SellerName"',
    'item': '"ItemId"',
    'customer': '"CustomerId"',
}

# Задаргааны tab: түлхүүр -> (бүлэглэх ID, нэр, нэмэлт багана {нэр: SQL})
DIMENSIONS = {
    'product': {
        'name_label': 'Бараа', 'label': 'Бараагаар', 'icon': '📦', 'id': '"ItemId"', 'name': 'MAX("ItemName")',
        'extra': {'group': f'MAX({ITEM_GROUP})'}, 'join': ITEM_GROUP_JOIN,
        'count_label': 'Харилцагч', 'count': 'COUNT(DISTINCT "CustomerId")',
    },
    'customer': {
        'name_label': 'Харилцагч', 'label': 'Харилцагчаар', 'icon': '👥', 'id': '"CustomerId"', 'name': 'MAX("CustomerName")',
        'extra': {'channel': 'MAX("DistributionChannelName")', 'last_date': 'MAX("DocumentDate")'},
        'count_label': 'Бараа', 'count': 'COUNT(DISTINCT "ItemId")',
    },
    'channel': {
        'name_label': 'Суваг', 'label': 'Сувгаар', 'icon': '🛣️', 'id': 'COALESCE("DistributionChannelName", \'(суваггүй)\')',
        'name': 'COALESCE(MAX("DistributionChannelName"), \'(суваггүй)\')', 'extra': {},
        'count_label': 'Харилцагч', 'count': 'COUNT(DISTINCT "CustomerId")',
    },
    'group': {
        'name_label': 'Барааны бүлэг', 'label': 'Барааны бүлгээр', 'icon': '🏷️', 'id': ITEM_GROUP, 'name': f'MAX({ITEM_GROUP})', 'extra': {},
        'join': ITEM_GROUP_JOIN, 'count_label': 'Бараа', 'count': 'COUNT(DISTINCT "ItemId")',
    },
    'warehouse': {
        'name_label': 'Агуулах', 'label': 'Агуулахаар', 'icon': '🏬', 'id': 'COALESCE("WarehouseName", \'(тодорхойгүй)\')',
        'name': 'COALESCE(MAX("WarehouseName"), \'(тодорхойгүй)\')', 'extra': {},
        'count_label': 'Бараа', 'count': 'COUNT(DISTINCT "ItemId")',
    },
    'seller': {
        'name_label': 'Борлуулагч', 'label': 'Борлуулагчаар', 'icon': '🧑‍💼', 'id': 'COALESCE("SellerName", \'(тодорхойгүй)\')',
        'name': 'COALESCE(MAX("SellerName"), \'(тодорхойгүй)\')', 'extra': {},
        'count_label': 'Харилцагч', 'count': 'COUNT(DISTINCT "CustomerId")',
    },
}

METRICS_SQL = '''
    COALESCE(SUM("PayAmount"), 0) AS revenue,
    COALESCE(SUM("AmountNonVat"), 0) AS nonvat,
    COALESCE(SUM("UnitCost" * "Qty"), 0) AS cost,
    COALESCE(SUM("Qty"), 0) AS qty,
    COUNT(DISTINCT "DocumentPkId") AS orders,
    COUNT(DISTINCT "CustomerId") AS customers
'''


SOURCE_TABLES = ['OpenDataSale', 'OpenDataItem']


def cached(name, payload, builder):
    """builder()-ийн үр дүнг хүснэгтийн хувилбар + параметрээр кэшлэнэ (shop.services.report_cache)."""
    from shop.services.report_cache import cached as report_cached
    return report_cached(f'sales_report:{name}', SOURCE_TABLES, payload, builder)


def _fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        cols = [c.name for c in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def where_clause(filters, date_from=None, date_to=None):
    """Шүүлтийн WHERE ба параметрүүд. date_from/date_to-г дарж өгвөл (өмнөх хугацаатай харьцуулахад) тэдгээрийг."""
    parts, params = ['TRUE'], []
    d_from = date_from if date_from is not None else filters.get('date_from')
    d_to = date_to if date_to is not None else filters.get('date_to')
    if d_from:
        parts.append('"DocumentDate" >= %s')
        params.append(d_from)
    if d_to:
        parts.append('"DocumentDate" <= %s')
        params.append(d_to)
    for key, column in MULTI_FILTERS.items():
        values = filters.get(key) or []
        if values:
            parts.append(column if '%s' in column else f'{column} = ANY(%s)')
            params.append(list(values))
    return ' AND '.join(parts), params


def _metrics(row):
    revenue, nonvat, cost = float(row['revenue']), float(row['nonvat']), float(row['cost'])
    orders = row['orders'] or 0
    profit = nonvat - cost
    return {
        'revenue': revenue, 'nonvat': nonvat, 'cost': cost, 'profit': profit,
        'margin': (profit / nonvat * 100) if nonvat else 0,
        'qty': float(row['qty']), 'orders': orders, 'customers': row['customers'] or 0,
        'avg_order': revenue / orders if orders else 0,
    }


def kpis(filters):
    """Үндсэн үзүүлэлт + өмнөх ижил урттай хугацаатай харьцуулалт (огноо заасан бол)."""
    def build():
        where, params = where_clause(filters)
        current = _metrics(_fetch(f'SELECT {METRICS_SQL}, MIN("DocumentDate") AS first, MAX("DocumentDate") AS last '
                                  f'FROM {TABLE} WHERE {where}', params)[0])
        previous = None
        d_from, d_to = filters.get('date_from'), filters.get('date_to')
        if d_from and d_to:
            span = (d_to - d_from).days + 1
            p_to = d_from - timedelta(days=1)
            p_from = p_to - timedelta(days=span - 1)
            where_p, params_p = where_clause(filters, p_from, p_to)
            previous = _metrics(_fetch(f'SELECT {METRICS_SQL} FROM {TABLE} WHERE {where_p}', params_p)[0])
            previous['period'] = f'{p_from:%Y.%m.%d} – {p_to:%Y.%m.%d}'
        return {'current': current, 'previous': previous}
    return cached('kpis', filters, build)


def summary(filters):
    """Он-сарын нэгтгэл: сар, жил, нийт түвшин (давхардаагүй харилцагчийг түвшин бүрт зөв) - нэг query."""
    def build():
        where, params = where_clause(filters)
        rows = _fetch(
            f'''
            SELECT EXTRACT(YEAR FROM "DocumentDate")::int AS y, EXTRACT(MONTH FROM "DocumentDate")::int AS m,
                   GROUPING(EXTRACT(YEAR FROM "DocumentDate")::int) AS gy,
                   GROUPING(EXTRACT(MONTH FROM "DocumentDate")::int) AS gm,
                   {METRICS_SQL}
            FROM {TABLE} WHERE {where}
            GROUP BY GROUPING SETS (
                (EXTRACT(YEAR FROM "DocumentDate")::int, EXTRACT(MONTH FROM "DocumentDate")::int),
                (EXTRACT(YEAR FROM "DocumentDate")::int), ()
            )
            ''', params)
        years, total = {}, None
        for r in rows:
            metrics = _metrics(r)
            if r['gy']:
                total = metrics
            elif r['gm']:
                years.setdefault(r['y'], {'months': []})['total'] = metrics
            else:
                years.setdefault(r['y'], {'months': []})['months'].append({'month': r['m'], **metrics})
        result = []
        for y in sorted(years):
            months = sorted(years[y]['months'], key=lambda x: x['month'])
            result.append({'year': y, 'total': years[y].get('total'), 'months': months})
        return {'years': result, 'total': total}
    return cached('summary', filters, build)


def breakdown(filters, dim):
    """Задаргаа (бараа/харилцагч/суваг/ангилал/брэнд/борлуулагч) - бүх мөр (хөтөч дээр эрэмбэлж, хайна)."""
    cfg = DIMENSIONS[dim]

    def build():
        where, params = where_clause(filters)
        extra = ''.join(f', {sql} AS {name}' for name, sql in cfg['extra'].items())
        rows = _fetch(
            f'''
            SELECT {cfg['id']} AS id, {cfg['name']} AS name{extra}, {METRICS_SQL}, {cfg['count']} AS cnt
            FROM {TABLE} {cfg.get('join', '')} WHERE {where}
            GROUP BY 1 ORDER BY revenue DESC
            ''', params)
        total = sum(float(r['revenue']) for r in rows) or 1
        out = []
        for r in rows:
            m = _metrics(r)
            item = {'id': r['id'], 'name': r['name'] or r['id'] or f"({cfg['name_label'].lower()} тодорхойгүй)", 'count': r['cnt'], 'share': m['revenue'] / total * 100,
                    **{k: round(v, 2) if isinstance(v, float) else v for k, v in m.items()}}
            for name in cfg['extra']:
                value = r[name]
                item[name] = value.isoformat() if hasattr(value, 'isoformat') else (value or '')
            out.append(item)
        return out
    return cached(f'dim:{dim}', filters, build)


def daily(filters):
    """Өдөр бүрийн борлуулалт (хугацаа заагаагүй бол сүүлийн 365 хоног)."""
    def build():
        f = dict(filters)
        if not f.get('date_from'):
            last = _fetch(f'SELECT MAX("DocumentDate") AS d FROM {TABLE}', [])[0]['d'] or date.today()
            f['date_from'] = (f.get('date_to') or last) - timedelta(days=364)
        where, params = where_clause(f)
        rows = _fetch(f'SELECT "DocumentDate" AS d, {METRICS_SQL} FROM {TABLE} WHERE {where} GROUP BY 1 ORDER BY 1 DESC', params)
        return [{'date': r['d'].isoformat(), 'dow': r['d'].isoweekday(), **_metrics(r)} for r in rows]
    return cached('daily', filters, build)


def filter_options():
    """Шүүлтийн сонголтууд (харилцагчаас бусад - тэр нь хайлтаар)."""
    def build():
        def distinct(col):
            return [r['v'] for r in _fetch(
                f'SELECT DISTINCT {col} AS v FROM {TABLE} WHERE {col} IS NOT NULL AND {col} <> \'\' ORDER BY 1', [])]
        items = _fetch(f'SELECT "ItemId" AS id, MAX("ItemName") AS name FROM {TABLE} '
                       f'WHERE "ItemId" IS NOT NULL GROUP BY 1 ORDER BY 2', [])
        dates = _fetch(f'SELECT MIN("DocumentDate") AS first, MAX("DocumentDate") AS last, COUNT(*) AS n FROM {TABLE}', [])[0]
        groups = [r['v'] for r in _fetch(
            'SELECT DISTINCT "ItemGroupId" AS v FROM "OpenDataItem" WHERE "ItemGroupId" <> \'\' ORDER BY 1', [])]
        return {
            'channel': distinct('"DistributionChannelName"'),
            'group': groups,
            'warehouse': distinct('"WarehouseName"'),
            'seller': distinct('"SellerName"'),
            'item': [(i['id'], i['name']) for i in items],
            'first': dates['first'], 'last': dates['last'], 'rows': dates['n'],
        }
    return cached('options', {}, build)


def warm_cache():
    """Синкийн дараа бүх хугацааны (шүүлтгүй) tab-уудыг урьдчилан бодож кэшэд хийнэ - анхны ачаалалт хурдан."""
    filters = {'date_from': None, 'date_to': None, **{k: [] for k in MULTI_FILTERS}}
    filter_options()
    kpis(filters)
    summary(filters)
    daily(filters)
    for dim in DIMENSIONS:
        breakdown(filters, dim)


def sales_customers():
    """Борлуулалттай бүх харилцагч (Id, нэр) - шүүлтийн жагсаалтад."""
    def build():
        return _fetch(f'SELECT "CustomerId" AS id, MAX("CustomerName") AS name FROM {TABLE} '
                      f'WHERE NULLIF("CustomerId", \'\') IS NOT NULL GROUP BY 1 ORDER BY 2', [])
    return cached('customers', {}, build)


def search_customers(q, limit=30):
    """Харилцагчийн хайлт (шүүлтийн сонголтод) - нэр эсвэл кодоор."""
    like = f'%{q.strip()}%'
    return _fetch(
        'SELECT "Id" AS id, "Name" AS name FROM "OpenDataCustomer" '
        'WHERE "Name" ILIKE %s OR "Id" ILIKE %s ORDER BY "Name" LIMIT %s', [like, like, limit])


def customer_names(ids):
    if not ids:
        return []
    return _fetch('SELECT "Id" AS id, "Name" AS name FROM "OpenDataCustomer" WHERE "Id" = ANY(%s)', [list(ids)])
