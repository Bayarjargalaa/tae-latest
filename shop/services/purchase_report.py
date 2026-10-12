"""
Татан авалтын тайлан (/dashboard/purchase-report/) - OpenDataLandedCost (импортын татан авалтын мөр бүр).

Дүн бүгд төгрөгөөр (валютын дүнг хооронд нь нэмэхгүй - EUR, RUB, CNY холилдсон тул):
- Барааны дүн   = ItemAmount (валютын дүн x ханш)
- Гааль         = CustomAmount, Бусад зардал = OtherExpenseAmount (тээвэр г.м.)
- Нийт өртөг    = Amount (бараа + гааль + бусад + НӨАТ - ханшийн зөрүү) = UnitCost x Qty
- Зардлын хувь  = (гааль + бусад) / барааны дүн
- Хүлээгдэж буй ашиг = ProfitAmount (= зарах үнэ x тоо - нийт өртөг), ашгийн хувь = ашиг / (зарах үнэ x тоо)
Нэг баримт (DocumentPkId) олон мөртэй; баримтын дугаар он бүр давтагдана.

Шүүлт бүх tab-д үйлчилнэ; үр дүнг хүснэгтийн хувилбараар кэшлэнэ (shop.services.report_cache).
"""
from datetime import date, datetime, timedelta

from django.db import connection

TABLE = '"OpenDataLandedCost"'
SOURCE_TABLES = ['OpenDataLandedCost']

# Олон сонголттой шүүлт: параметр -> багана
MULTI_FILTERS = {
    'vendor': '"VendorId"',
    'item': '"ItemId"',
    'currency': '"CurrencyId"',
    'warehouse': '"WarehouseName"',
    'doc': '"DocumentPkId"::text',
}

TABS = [
    ('summary', 'Нэгтгэл', '📈'),
    ('tree', 'Шатлалаар', '🗂'),
    ('vendor', 'Харилцагчаар', '🏢'),
    ('item', 'Бараагаар', '📦'),
    ('document', 'Баримтаар', '🧾'),
]
TAB_KEYS = [k for k, _, _ in TABS]

METRICS_SQL = '''
    COUNT(DISTINCT "DocumentPkId") AS docs,
    COUNT(DISTINCT "VendorId") AS vendors,
    COUNT(DISTINCT "ItemId") AS items,
    COUNT(*) AS lines,
    COALESCE(SUM("Qty"), 0) AS qty,
    COALESCE(SUM("ItemAmount"), 0) AS goods,
    COALESCE(SUM("CustomAmount"), 0) AS customs,
    COALESCE(SUM("OtherExpenseAmount"), 0) AS other,
    COALESCE(SUM("VatAmount"), 0) AS vat,
    COALESCE(SUM("Amount"), 0) AS total,
    COALESCE(SUM("ProfitAmount"), 0) AS profit,
    COALESCE(SUM("SalePrice" * "Qty"), 0) AS sale_value
'''


# Тооцоолол / бүтэц өөрчлөгдөхөд нэмэгдүүлнэ - хуучин кэш (өгөгдөл өөрчлөгдөөгүй ч) хэрэглэгдэхгүй
CACHE_VERSION = 5
# Харилцан хамааралтай шүүлтүүд (нэгийг сонгоход бусдын сонголт нарийсна) - facet_data-д
FACETS = ['vendor', 'item', 'currency', 'warehouse']

# Шатлалын (tree tab) түвшнүүд: түлхүүр -> нэр. Анхдагч дараалал: харилцагч › он › сар › өдөр › бараа
TREE_LEVELS = {
    'vendor': 'Харилцагч', 'year': 'Он', 'month': 'Сар', 'day': 'Өдөр', 'item': 'Бараа',
    'document': 'Баримт', 'currency': 'Валют', 'warehouse': 'Агуулах',
}
TREE_DEFAULT = ['vendor', 'year', 'month', 'day', 'item']
# Шатлалын мөрийн багана (массиваар - JSON-ийг багасгана)
LINE_COLUMNS = ['doc', 'number', 'date', 'vendor_id', 'vendor', 'item_id', 'item', 'measure', 'currency', 'warehouse',
                'qty', 'goods', 'customs', 'other', 'vat', 'total', 'profit', 'sale_value']


def cached(name, payload, builder):
    from shop.services.report_cache import cached as report_cached
    return report_cached(f'purchase_report:v{CACHE_VERSION}:{name}', SOURCE_TABLES, payload, builder)


def _fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        cols = [c.name for c in cursor.description]
        return [dict(zip(cols, r)) for r in cursor.fetchall()]


def _parse_date(value):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def parse_filters(params):
    """GET -> шүүлт. Огноо заагаагүй бол бүх хугацаа."""
    date_from, date_to = _parse_date(params.get('date_from')), _parse_date(params.get('date_to'))
    if date_from and date_to and date_from > date_to:
        date_from, date_to = date_to, date_from
    filters = {'date_from': date_from, 'date_to': date_to, 'q': (params.get('q') or '').strip()}
    for key in MULTI_FILTERS:
        filters[key] = [v for v in params.getlist(key) if v.strip()]
    return filters


def is_filtered(filters):
    return any(filters[k] for k in ('date_from', 'date_to', 'q', *MULTI_FILTERS))


def where_clause(filters, date_from=None, date_to=None, skip=()):
    """WHERE ба параметрүүд. date_from/date_to-г дарж өгвөл (өмнөх хугацаатай харьцуулахад) тэдгээрийг;
    skip - тухайн шүүлтийг алгасна (шүүлтийн сонголтыг бусад шүүлтээр нарийсгахад)."""
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
        if key not in skip and filters.get(key):
            parts.append(f'{column} = ANY(%s)')
            params.append(list(filters[key]))
    if filters.get('q'):
        # Баримтын дугаар, барааны нэр/код, харилцагчаар чөлөөт хайлт
        parts.append('("DocumentNumber" ILIKE %s OR "ItemName" ILIKE %s OR "ItemId" ILIKE %s OR "VendorName" ILIKE %s)')
        params += [f"%{filters['q']}%"] * 4
    return ' AND '.join(parts), params


def _metrics(row):
    """SQL нэгтгэл -> тоон үзүүлэлт + бодсон хувь."""
    m = {k: float(row.get(k) or 0) for k in ('qty', 'goods', 'customs', 'other', 'vat', 'total', 'profit', 'sale_value')}
    for k in ('docs', 'vendors', 'items', 'lines'):
        m[k] = int(row.get(k) or 0)
    m['expenses'] = m['customs'] + m['other']
    m['expense_pct'] = m['expenses'] / m['goods'] * 100 if m['goods'] else 0
    m['margin'] = m['profit'] / m['sale_value'] * 100 if m['sale_value'] else 0
    m['unit_cost'] = m['total'] / m['qty'] if m['qty'] else 0
    return m


def facet_data(filters):
    """Харилцан хамааралтай шүүлтэд (хөтөч дотор шууд нарийсгахад): хугацаа, хайлт, баримтын нөхцөлд тохирох
    (баримт, харилцагч, бараа, валют, агуулах) давхардаагүй хослолууд ба нэрс. Харилцагч, бараа, валют, агуулахын
    сонголтыг энд оруулахгүй - хөтөч бусдынхаа сонголтоор нарийсгана."""
    def build():
        base = {**filters, **{k: [] for k in FACETS}}
        where, params = where_clause(base)
        with connection.cursor() as cursor:
            cursor.execute(f'''
                SELECT DISTINCT "DocumentPkId"::text, COALESCE("VendorId", ''), COALESCE("ItemId", ''),
                       COALESCE("CurrencyId", ''), COALESCE("WarehouseName", '')
                FROM {TABLE} WHERE {where}
            ''', params)
            rows = [list(r) for r in cursor.fetchall()]
            cursor.execute(f'SELECT "VendorId", MAX("VendorName") FROM {TABLE} GROUP BY 1')
            vendors = {k: v for k, v in cursor.fetchall() if k}
            cursor.execute(f'SELECT "ItemId", MAX("ItemName") FROM {TABLE} GROUP BY 1')
            items = {k: v for k, v in cursor.fetchall() if k}
        return {'facets': FACETS, 'rows': rows, 'names': {'vendor': vendors, 'item': items}}
    return cached('facets', filters, build)


def filter_options(filters):
    """Шүүлтийн сонголтууд (харилцан хамааралтай): утга бүр бусад сонгосон шүүлтийн (хугацаа, харилцагч, бараа,
    валют г.м. - өөрийгөө оруулахгүй) нөхцөлд татан авалттай бол л жагсаалтад, баримтын тоотой. Сонгосон утга
    үргэлж үлдэнэ. Хөтөч дотор (facet_data) мөн ижил дүрмээр шууд нарийсна."""
    def build():
        def distinct(key, sql_id, sql_name):
            where, params = where_clause(filters, skip=(key,))
            rows = _fetch(f'''
                SELECT {sql_id} AS id, MAX({sql_name}) AS name,
                       COUNT(DISTINCT "DocumentPkId") FILTER (WHERE {where}) AS n
                FROM {TABLE} WHERE {sql_id} IS NOT NULL AND {sql_id} <> '' GROUP BY 1
            ''', params)
            selected = set(filters.get(key) or [])
            rows = [r for r in rows if r['n'] or r['id'] in selected]
            rows.sort(key=lambda r: (r['name'] or r['id']).lower())
            return [(r['id'], r['name'] or r['id'], r['n']) for r in rows]

        span = _fetch(f'SELECT MIN("DocumentDate") AS first, MAX("DocumentDate") AS last, COUNT(*) AS n FROM {TABLE}', [])[0]
        # Шүүлтэд тохирох хамгийн сүүлийн татан авалт (огноогүйгээр) - хоосон үр дүнд санал болгоход
        no_dates = {**filters, 'date_from': None, 'date_to': None}
        nd_where, nd_params = where_clause(no_dates)
        latest = _fetch(f'SELECT MAX("DocumentDate") AS d FROM {TABLE} WHERE {nd_where}', nd_params)[0]['d']
        return {
            'vendor': distinct('vendor', '"VendorId"', '"VendorName"'),
            'item': distinct('item', '"ItemId"', '"ItemName"'),
            'currency': distinct('currency', '"CurrencyId"', '"CurrencyId"'),
            'warehouse': distinct('warehouse', '"WarehouseName"', '"WarehouseName"'),
            'first': span['first'], 'last': span['last'], 'rows': span['n'],
            'latest_match': latest,
        }
    return cached('options', filters, build)


def previous_period(filters):
    """Өмнөх ижил урттай хугацаа (огноо хоёулаа заасан үед л)."""
    d_from, d_to = filters['date_from'], filters['date_to']
    if not (d_from and d_to):
        return None
    length = (d_to - d_from).days + 1
    prev_to = d_from - timedelta(days=1)
    return prev_to - timedelta(days=length - 1), prev_to


def kpis(filters):
    def build():
        where, params = where_clause(filters)
        current = _metrics(_fetch(f'SELECT {METRICS_SQL} FROM {TABLE} WHERE {where}', params)[0])
        result = {'current': current, 'previous': None}
        prev = previous_period(filters)
        if prev:
            where, params = where_clause(filters, *prev)
            previous = _metrics(_fetch(f'SELECT {METRICS_SQL} FROM {TABLE} WHERE {where}', params)[0])
            previous['period'] = f'{prev[0]:%Y.%m.%d} – {prev[1]:%Y.%m.%d}'
            result['previous'] = previous
        return result
    return cached('kpis', filters, build)


def summary(filters):
    """Он, сарын нэгтгэл (давхардаагүй тоонууд жил, нийт түвшинд дахин тоологдоно - GROUPING SETS)."""
    def build():
        where, params = where_clause(filters)
        rows = _fetch(f'''
            SELECT y AS year, m AS month, GROUPING(y, m) AS g, {METRICS_SQL}
            FROM (SELECT *, EXTRACT(YEAR FROM "DocumentDate")::int AS y, EXTRACT(MONTH FROM "DocumentDate")::int AS m
                  FROM {TABLE} WHERE {where} AND "DocumentDate" IS NOT NULL) t
            GROUP BY GROUPING SETS ((y, m), (y), ())
            ORDER BY y NULLS LAST, m NULLS FIRST
        ''', params)
        years, total = {}, None
        for r in rows:
            m = _metrics(r)
            if r['g'] == 3:
                total = m
            elif r['g'] == 1:
                years.setdefault(r['year'], {'year': r['year'], 'months': []})['total'] = m
            else:
                years.setdefault(r['year'], {'year': r['year'], 'months': []})['months'].append({'month': r['month'], **m})
        return {'years': list(years.values()), 'total': total}
    return cached('summary', filters, build)


# Задаргааны tab: бүлэглэх ID, нэр, нэмэлт багана
DIMENSIONS = {
    'vendor': {
        'id': '"VendorId"', 'name': 'MAX("VendorName")', 'name_label': 'Харилцагч',
        'extra': {
            'currencies': 'STRING_AGG(DISTINCT "CurrencyId", \', \')',
            'first_date': 'MIN("DocumentDate")', 'last_date': 'MAX("DocumentDate")',
        },
    },
    'item': {
        'id': '"ItemId"', 'name': 'MAX("ItemName")', 'name_label': 'Бараа',
        'extra': {
            'measure': 'MAX("MeasureName")',
            'currencies': 'STRING_AGG(DISTINCT "CurrencyId", \', \')',
            'vendor_names': 'STRING_AGG(DISTINCT "VendorName", \', \')',
            # Валютын жигнэсэн дундаж үнэ - нэг валюттай үед л утгатай
            'price_fc': 'CASE WHEN COUNT(DISTINCT "CurrencyId") = 1 THEN SUM("ItemAmountFc") / NULLIF(SUM("Qty"), 0) END',
            'min_unit_cost': 'MIN("UnitCost")', 'max_unit_cost': 'MAX("UnitCost")',
            'last_unit_cost': '(ARRAY_AGG("UnitCost" ORDER BY "DocumentDate" DESC, "DocumentPkId" DESC))[1]',
            'last_sale_price': '(ARRAY_AGG("SalePrice" ORDER BY "DocumentDate" DESC, "DocumentPkId" DESC))[1]',
            'last_date': 'MAX("DocumentDate")',
        },
    },
    'document': {
        'id': '"DocumentPkId"::text', 'name': 'MAX("DocumentNumber")', 'name_label': 'Баримт',
        'extra': {
            'date': 'MIN("DocumentDate")', 'vendor_name': 'MAX("VendorName")', 'vendor_id': 'MAX("VendorId")',
            'currency': 'MAX("CurrencyId")', 'rate': 'MAX("Rate")', 'fc': 'SUM("ItemAmountFc")',
            'warehouse': 'MAX("WarehouseName")',
        },
    },
}


def _plain(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int)):
        return value
    return float(value)


def _group_children(rows, keys):
    """{эцэг: [мөр]} - задаргааны дэд мөрүүд (тоон үзүүлэлттэй)."""
    out = {}
    for r in rows:
        out.setdefault(str(r['parent']), []).append({**{k: _plain(r[k]) for k in keys}, **_metrics(r)})
    return out


def suggest(text, limit=8):
    """Хайх талбарын санал (бичих явцад): текстийг агуулсан харилцагч, бараа (нэр, код), баримтын дугаар -
    бүх өгөгдлөөс, баримтын тоотой. Том жижиг үсэг ялгахгүй."""
    text = (text or '').strip()
    if len(text) < 2:
        return {'vendor': [], 'item': [], 'doc': []}
    like = f'%{text}%'
    # total - бүлэгт нийт хэдэн утга олдсон (limit-ээс их бол "бусад N" гэж харуулна)
    vendors = _fetch(f'''
        SELECT "VendorId" AS id, MAX("VendorName") AS name, COUNT(DISTINCT "DocumentPkId") AS n, MAX("DocumentDate") AS last,
               COUNT(*) OVER () AS total
        FROM {TABLE} WHERE "VendorName" ILIKE %s OR "VendorId" ILIKE %s GROUP BY 1 ORDER BY n DESC LIMIT %s
    ''', [like, like, limit])
    items = _fetch(f'''
        SELECT "ItemId" AS id, MAX("ItemName") AS name, COUNT(DISTINCT "DocumentPkId") AS n, MAX("DocumentDate") AS last,
               COUNT(*) OVER () AS total
        FROM {TABLE} WHERE "ItemName" ILIKE %s OR "ItemId" ILIKE %s GROUP BY 1 ORDER BY n DESC, 2 LIMIT %s
    ''', [like, like, limit])
    docs = _fetch(f'''
        SELECT "DocumentPkId"::text AS id, MAX("DocumentNumber") AS name, MIN("DocumentDate") AS last,
               MAX("VendorName") AS vendor, COUNT(*) AS n, COUNT(*) OVER () AS total
        FROM {TABLE} WHERE "DocumentNumber" ILIKE %s GROUP BY 1 ORDER BY last DESC LIMIT %s
    ''', [like, limit])
    plain = lambda rows: [{k: _plain(v) for k, v in r.items()} for r in rows]
    return {'vendor': plain(vendors), 'item': plain(items), 'doc': plain(docs)}


def breakdown(filters, tab):
    def build():
        dim = DIMENSIONS[tab]
        where, params = where_clause(filters)
        extra = ', '.join(f'{sql} AS {key}' for key, sql in dim['extra'].items())
        rows = _fetch(f'''
            SELECT {dim['id']} AS id, {dim['name']} AS name, {extra}, {METRICS_SQL}
            FROM {TABLE} WHERE {where} GROUP BY 1 ORDER BY total DESC
        ''', params)
        out = [{'id': r['id'], 'name': r['name'] or '(тодорхойгүй)',
                **{k: _plain(r[k]) for k in dim['extra']}, **_metrics(r)} for r in rows]
        result = {'rows': out}
        if tab == 'document':
            # Баримтын мөрүүд (дэлгэрэнгүй нээхэд)
            lines = _fetch(f'''
                SELECT "DocumentPkId"::text AS doc, "ItemId" AS item_id, "ItemName" AS item, "MeasureName" AS measure,
                       "Qty" AS qty, "Price" AS price, "ItemAmountFc" AS fc, "ItemAmount" AS goods,
                       "CustomAmount" AS customs, "OtherExpenseAmount" AS other, "Amount" AS total,
                       "UnitCost" AS unit_cost, "SalePrice" AS sale_price
                FROM {TABLE} WHERE {where} ORDER BY "DocumentPkId", "Amount" DESC
            ''', params)
            by_doc = {}
            for line in lines:
                by_doc.setdefault(line.pop('doc'), []).append({k: _plain(v) for k, v in line.items()})
            result['lines'] = by_doc
        if tab == 'vendor':
            # Мөр задлахад: харилцагч бүрийн бараанууд
            children = _fetch(f'''
                SELECT "VendorId" AS parent, "ItemId" AS id, MAX("ItemName") AS name, MAX("MeasureName") AS measure,
                       MAX("DocumentDate") AS last_date, {METRICS_SQL}
                FROM {TABLE} WHERE {where} GROUP BY 1, 2 ORDER BY total DESC
            ''', params)
            result['children'] = _group_children(children, ('id', 'name', 'measure', 'last_date'))
        if tab == 'item':
            # Мөр задлахад: бараа бүрийн татан авалт (баримт бүрээр)
            children = _fetch(f'''
                SELECT "ItemId" AS parent, "DocumentPkId"::text AS doc, MAX("DocumentNumber") AS number,
                       MIN("DocumentDate") AS date, MAX("VendorName") AS vendor, MAX("CurrencyId") AS currency,
                       SUM("ItemAmountFc") / NULLIF(SUM("Qty"), 0) AS price_fc, MAX("SalePrice") AS sale_price,
                       {METRICS_SQL}
                FROM {TABLE} WHERE {where} GROUP BY 1, 2 ORDER BY date DESC
            ''', params)
            result['children'] = _group_children(children, ('doc', 'number', 'date', 'vendor', 'currency', 'price_fc', 'sale_price'))
        if tab == 'item' and len(filters['item']) == 1:
            # Нэг бараа сонгосон бол нэгж өртгийн түүх (татан авалт бүрээр)
            result['history'] = [{k: _plain(v) for k, v in r.items()} for r in _fetch(f'''
                SELECT "DocumentDate" AS date, MAX("DocumentNumber") AS number, MAX("VendorName") AS vendor,
                       MAX("CurrencyId") AS currency, SUM("Qty") AS qty, SUM("Amount") / NULLIF(SUM("Qty"), 0) AS unit_cost,
                       SUM("ItemAmountFc") / NULLIF(SUM("Qty"), 0) AS price_fc, MAX("SalePrice") AS sale_price
                FROM {TABLE} WHERE {where} GROUP BY "DocumentDate", "DocumentPkId" ORDER BY 1
            ''', params)]
        return result
    return cached(f'breakdown:{tab}', filters, build)


def parse_levels(value):
    """URL-ын levels=vendor,year,... -> мэдэгдэх, давхардаагүй түвшнүүд (хоосон бол анхдагч)."""
    levels = []
    for key in (value or '').split(','):
        key = key.strip()
        if key in TREE_LEVELS and key not in levels:
            levels.append(key)
    return levels or list(TREE_DEFAULT)


def tree_lines(filters):
    """Шатлалын tab: шүүлтэд тохирох татан авалтын мөр бүр (массив) - шатлалыг хөтөч дотор (түвшний дараалал
    солигдоход дахин ачаалахгүй) нэгтгэнэ."""
    def build():
        where, params = where_clause(filters)
        with connection.cursor() as cursor:
            cursor.execute(f'''
                SELECT "DocumentPkId"::text, "DocumentNumber", "DocumentDate"::text, "VendorId", "VendorName", "ItemId", "ItemName",
                       "MeasureName", "CurrencyId", "WarehouseName",
                       COALESCE("Qty", 0), COALESCE("ItemAmount", 0), COALESCE("CustomAmount", 0), COALESCE("OtherExpenseAmount", 0),
                       COALESCE("VatAmount", 0), COALESCE("Amount", 0), COALESCE("ProfitAmount", 0), COALESCE("SalePrice", 0) * COALESCE("Qty", 0)
                FROM {TABLE} WHERE {where} ORDER BY "DocumentDate", "DocumentPkId"
            ''', params)
            return [[v if isinstance(v, (str, type(None))) else round(float(v), 2) for v in row] for row in cursor.fetchall()]
    return cached('tree_lines', filters, build)


def tree_rows(filters, levels):
    """Excel-д: шатлалын мөрүүд (түвшин, нэр, үзүүлэлт) - хөтчийнхтэй ижил нэгтгэл (давхардаагүй баримт, бараа)."""
    idx = {c: i for i, c in enumerate(LINE_COLUMNS)}

    def key_label(level, line):
        date = line[idx['date']] or ''
        if level == 'year':
            return date[:4], f'{date[:4]} он'
        if level == 'month':
            return date[:7], date[:7].replace('-', '.')
        if level == 'day':
            return date, date
        pairs = {'vendor': ('vendor_id', 'vendor'), 'item': ('item_id', 'item'), 'document': ('doc', 'number'),
                 'currency': ('currency', 'currency'), 'warehouse': ('warehouse', 'warehouse')}[level]
        return line[idx[pairs[0]]] or '', line[idx[pairs[1]]] or '(тодорхойгүй)'

    def metrics(lines):
        m = {k: sum(l[idx[k]] for l in lines) for k in ('qty', 'goods', 'customs', 'other', 'vat', 'total', 'profit', 'sale_value')}
        m['docs'] = len({l[idx['doc']] for l in lines})
        m['items'] = len({l[idx['item_id']] for l in lines})
        m['expenses'] = m['customs'] + m['other']
        m['expense_pct'] = m['expenses'] / m['goods'] * 100 if m['goods'] else 0
        m['margin'] = m['profit'] / m['sale_value'] * 100 if m['sale_value'] else 0
        return m

    out = []

    def walk(lines, depth):
        if depth >= len(levels):
            return
        groups = {}
        for line in lines:
            key, label = key_label(levels[depth], line)
            groups.setdefault(key, [label, []])[1].append(line)
        chronological = levels[depth] in ('year', 'month', 'day')
        # Хөтчийнхтэй ижил: он/сар/өдөр сүүлийнх эхэнд, бусад нийт өртгөөр
        items = sorted(groups.items(), key=lambda kv: kv[0], reverse=True) if chronological else \
            sorted(groups.items(), key=lambda kv: -sum(l[idx['total']] for l in kv[1][1]))
        for _, (label, group) in items:
            out.append({'depth': depth, 'level': levels[depth], 'name': label, **metrics(group)})
            walk(group, depth + 1)

    lines = tree_lines(filters)
    walk(lines, 0)
    return out, metrics(lines) if lines else None


def currency_mix(filters):
    """Валют бүрийн татан авалт (валютын дүн ба ₮) - нэгтгэл tab-ын хажуугийн жагсаалт."""
    def build():
        where, params = where_clause(filters)
        return [{k: _plain(v) for k, v in r.items()} for r in _fetch(f'''
            SELECT COALESCE("CurrencyId", '?') AS currency, SUM("ItemAmountFc") AS fc, SUM("ItemAmount") AS goods,
                   SUM("ItemAmount") / NULLIF(SUM("ItemAmountFc"), 0) AS avg_rate, COUNT(DISTINCT "DocumentPkId") AS docs
            FROM {TABLE} WHERE {where} GROUP BY 1 ORDER BY goods DESC NULLS LAST
        ''', params)]
    return cached('currency', filters, build)
