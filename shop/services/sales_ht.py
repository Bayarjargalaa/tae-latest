"""
Борлуулалтын тайлан ХТ-р - OpenDataSale-г OpenDataDistributionChannel-тэй нэгтгэж, нэр нь
"ХТ"-ээр эхэлсэн (худалдааны төлөөлөгчийн) сувгуудын борлуулалтыг бараа x харилцагч x он-сараар
нэгтгэнэ. Суваг сонговол ХТ-ийн оронд сонгосон сувгуудаар шүүнэ.

- Мөр: бараа ба харилцагч - аль нь ч дээд түвшинд гарч болно (эргүүлэлтийг хөтөч дээр хийнэ).
- Багана: он-сар (YYYY-MM), утга нь тоо ширхэг ба дүн (PayAmount) хоёулаа.
- Харилцагч, харилцагчийн бүлгийг OpenDataCustomer / OpenDataCustomerGroup-оос авна (CustomerId = Id).
  Бүлэг мод бүтэцтэй (SortedOrder нь эцгийнхээ кодоор эхэлдэг) тул эх бүлэг сонгоход дэд бүлгүүд нь орно.
- Бүртгэлтэй ч борлуулалтгүй харилцагч: шүүсэн сувагт бүртгэлтэй харилцагчдаас шүүлтийн
  хугацаанд борлуулалт хийгдээгүйг нь тусад нь гаргана (зөвхөн харилцагч дээд түвшинд үед харагдана).
- Харилцагчийн төлөв (OpenDataCustomer.ActiveStatus Y/N)-ийн шүүлт борлуулалт болон бүртгэлтэй
  харилцагчдын аль алинд үйлчилнэ.
- Үлдэгдэлтэй барааны шүүлт: InventorySnapshot-ын "Агуулах жижиг"-т үлдэгдэлтэй бараа л орно;
  жижиг ба толгойт агуулахын үлдэгдлийг snapshot-оос авч харуулна.
"""
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.db import connection

HT_CHANNEL_PREFIX = 'ХТ'
NO_CHANNEL_LABEL = 'Суваггүй'

ITEM_MODE_WITH = 'with'
ITEM_MODE_ALL = 'all'
ITEM_MODE_WITHOUT = 'without'
ITEM_MODE_LABELS = {
    ITEM_MODE_WITH: 'Борлуулалттай бараа',
    ITEM_MODE_ALL: 'Бүх үлдэгдэлтэй бараа',
    ITEM_MODE_WITHOUT: 'Зөвхөн борлуулалтгүй бараа',
}

CHANNEL_SCOPE_ALL = 'all'
CHANNEL_SCOPE_HT = 'ht'
CHANNEL_SCOPE_LABELS = {
    CHANNEL_SCOPE_ALL: 'Бүх суваг',
    CHANNEL_SCOPE_HT: 'Зөвхөн ХТ сувгууд',
}

COMPARE_PREV = 'prev'
COMPARE_YOY = 'yoy'
COMPARE_CUSTOM = 'custom'
COMPARE_NONE = 'none'
COMPARE_LABELS = {
    COMPARE_PREV: 'Өмнөх ижил хугацаа',
    COMPARE_YOY: 'Өнгөрсөн жилийн мөн үе',
    COMPARE_CUSTOM: 'Сонгосон хугацаа',
    COMPARE_NONE: 'Харьцуулахгүй',
}
NO_CUSTOMER_LABEL = '(харилцагчгүй)'

METRIC_QTY = 'qty'
METRIC_AMOUNT = 'amount'
METRIC_LABELS = {METRIC_AMOUNT: 'Дүн', METRIC_QTY: 'Тоо ширхэг'}

GROUP_ITEM = 'item'
GROUP_CUSTOMER = 'customer'
GROUP_LABELS = {GROUP_ITEM: 'Бараа', GROUP_CUSTOMER: 'Харилцагч'}

SALES_MODE_WITH = 'with'
SALES_MODE_ALL = 'all'
SALES_MODE_WITHOUT = 'without'
CUSTOMER_STATUS_ALL = 'all'
CUSTOMER_STATUS_LABELS = {
    CUSTOMER_STATUS_ALL: 'Бүгд',
    'Y': 'Идэвхтэй',
    'N': 'Идэвхгүй',
}

SALES_MODE_LABELS = {
    SALES_MODE_WITH: 'Борлуулалттай харилцагч',
    SALES_MODE_ALL: 'Бүх бүртгэлтэй харилцагч',
    SALES_MODE_WITHOUT: 'Зөвхөн борлуулалтгүй харилцагч',
}


def get_channels():
    """Бүх борлуулалтын сувгийн (Id, Name) жагсаалт, кодоор эрэмбэлсэн."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "Name" FROM "OpenDataDistributionChannel" ORDER BY "Id"')
        return cursor.fetchall()


def _channel_condition(filters):
    """Сувгийн шүүлт (SQL, параметрүүдийн жагсаалт): суваг сонгосон бол тэдгээрээр; үгүй бол channel_scope-оор -
    бүх суваг (анхдагч; суваггүй борлуулалт ч орно, dc нь LEFT JOIN) эсвэл нэр нь "ХТ"-ээр эхэлсэн сувгууд.
    LIKE / ANY нөхцөл нь dc хоосон мөрийг өөрөө хасна."""
    if filters['channels']:
        return 'dc."Id" = ANY(%s)', [filters['channels']]
    if filters['all_channels']:
        return 'TRUE', []
    return 'dc."Name" LIKE %s', [HT_CHANNEL_PREFIX + '%']


def get_filter_options(channel_ids=None):
    """Шүүлтийн dropdown-уудын сонголтууд (суваг сонгож болох тул бүх сувгаас).

    items:           борлуулагдсан бараанууд [(нэр, код)] - шүүлтийн утга нь нэр
    customers:       бүртгэлтэй харилцагчид [(Id, нэр)] - OpenDataCustomer-оос
    customer_groups: бүх бүлэг [(нэр, түвшин)] - OpenDataCustomerGroup-ын модны дарааллаар
    """
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT s."ItemName", MAX(COALESCE(s."ItemId", ''))
            FROM "OpenDataSale" s
            WHERE s."ItemName" IS NOT NULL AND s."ItemName" <> ''
            GROUP BY 1
            ORDER BY 1
            '''
        )
        items = cursor.fetchall()

        # ХТ-д (channel_ids) зөвхөн өөрийн сувгийн харилцагчид
        if channel_ids is not None:
            cursor.execute(
                'SELECT "Id", "Name" FROM "OpenDataCustomer" WHERE "DistributionChannelId" = ANY(%s) ORDER BY "Name"',
                [list(channel_ids)],
            )
        else:
            cursor.execute('SELECT "Id", "Name" FROM "OpenDataCustomer" ORDER BY "Name"')
        customers = [(customer_id, ' '.join((name or '').split())) for customer_id, name in cursor.fetchall()]

        # SortedOrder нь түвшин бүрт 4 оронтой код нэмэгддэг зам (1000 -> 10001000 -> ...)
        cursor.execute('SELECT "Id", "SortedOrder" FROM "OpenDataCustomerGroup" ORDER BY "SortedOrder"')
        customer_groups = [(name, max(len(order or '') // 4 - 1, 0)) for name, order in cursor.fetchall()]

    return {'items': items, 'customers': customers, 'customer_groups': customer_groups}


def _expand_customer_groups(cursor, group_names):
    """Сонгосон бүлгүүд болон тэдгээрийн бүх дэд бүлгийн нэрс."""
    cursor.execute(
        '''
        SELECT g."Id"
        FROM "OpenDataCustomerGroup" g
        WHERE EXISTS (
            SELECT 1 FROM "OpenDataCustomerGroup" p
            WHERE p."Id" = ANY(%s) AND g."SortedOrder" LIKE p."SortedOrder" || '%%'
        )
        ''',
        [group_names],
    )
    return list({row[0] for row in cursor.fetchall()} | set(group_names))


def _parse_date(value, default):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return default


def parse_filters(params):
    """GET параметрүүдээс шүүлтийг уншина. Огноо заагаагүй бол оны эхнээс өнөөдрийг хүртэл."""
    today = date.today()
    date_from = _parse_date(params.get('date_from'), date(today.year, 1, 1))
    date_to = _parse_date(params.get('date_to'), today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from

    group_by = params.get('group_by')
    metric = params.get('metric')
    sales_mode = params.get('sales_mode')
    sales_mode = sales_mode if sales_mode in SALES_MODE_LABELS else SALES_MODE_WITH
    # Борлуулалтгүй харилцагчид бараагаар задрах мөргүй тул харилцагч дээд түвшинд л харагдана
    if sales_mode == SALES_MODE_WITHOUT:
        group_by = GROUP_CUSTOMER
    item_mode = params.get('item_mode')
    item_mode = item_mode if item_mode in ITEM_MODE_LABELS else ITEM_MODE_WITH
    # Борлуулалтгүй бараанд харилцагчаар задрах мөр байхгүй тул бараа дээд түвшинд л харагдана
    if item_mode == ITEM_MODE_WITHOUT:
        group_by = GROUP_ITEM
    channel_scope = params.get('channel_scope')
    if channel_scope not in CHANNEL_SCOPE_LABELS:
        channel_scope = CHANNEL_SCOPE_ALL
    return {
        'date_from': date_from,
        'date_to': date_to,
        'items': [v for v in params.getlist('item') if v],
        'customers': [v for v in params.getlist('customer') if v],
        'channels': [v for v in params.getlist('channel') if v],
        # Суваг сонгоогүй үеийн хүрээ: анхдагчаар бүх суваг, "ht" бол зөвхөн нэр нь "ХТ"-ээр эхэлсэн сувгууд.
        # Хуучин холбоосын all_channels=true нь бүх суваг гэсэн утгатай хэвээр.
        'channel_scope': channel_scope,
        'all_channels': channel_scope == CHANNEL_SCOPE_ALL,
        'customer_groups': [v for v in params.getlist('customer_group') if v],
        'stock_only': params.get('stock_only') == 'true',
        'show_tolgoit': params.get('show_tolgoit') == 'true',
        'numbering': params.get('numbering', 'true') != 'false',
        # Dashboard-ын харьцуулах үе (COMPARE_LABELS); 'custom' үед compare_from/compare_to ашиглана
        'compare': params.get('compare') if params.get('compare') in COMPARE_LABELS else COMPARE_PREV,
        'compare_from': _parse_date(params.get('compare_from'), None),
        'compare_to': _parse_date(params.get('compare_to'), None),
        'sales_mode': sales_mode,
        'item_mode': item_mode,
        'customer_status': (params.get('customer_status') if params.get('customer_status') in CUSTOMER_STATUS_LABELS
                            else CUSTOMER_STATUS_ALL),
        'group_by': group_by if group_by in GROUP_LABELS else GROUP_ITEM,
        'metric': metric if metric in METRIC_LABELS else METRIC_AMOUNT,
    }


def _month_range(date_from, date_to):
    months = []
    year, month = date_from.year, date_from.month
    while (year, month) <= (date_to.year, date_to.month):
        months.append(f'{year:04d}-{month:02d}')
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _sale_conditions(filters, group_names, date_from, date_to):
    """OpenDataSale (s) / суваг (dc) / харилцагч (cu)-д тавих WHERE нөхцөлүүд ба параметрүүд."""
    channel_sql, channel_params = _channel_condition(filters)
    where = [channel_sql, 's."DocumentDate"::date BETWEEN %s AND %s']
    params = [*channel_params, date_from, date_to]
    if filters['items']:
        where.append('s."ItemName" = ANY(%s)')
        params.append(filters['items'])
    if filters['customers']:
        where.append('s."CustomerId" = ANY(%s)')
        params.append(filters['customers'])
    if group_names:
        where.append('COALESCE(cu."CustomerGroupId", s."CustomerGroupId") = ANY(%s)')
        params.append(group_names)
    if filters['customer_status'] != CUSTOMER_STATUS_ALL:
        where.append('cu."ActiveStatus" = %s')
        params.append(filters['customer_status'])
    if filters['stock_only']:
        where.append('s."ItemName" IN (SELECT itemname FROM inventory_snapshot WHERE jijig_qty > 0)')
    return where, params


def _customer_conditions(filters, group_names):
    """Бүртгэлтэй харилцагч (cu, сувагтайгаа dc)-д тавих WHERE нөхцөлүүд ба параметрүүд."""
    channel_sql, channel_params = _channel_condition(filters)
    where, params = [channel_sql], list(channel_params)
    if filters['customer_status'] != CUSTOMER_STATUS_ALL:
        where.append('cu."ActiveStatus" = %s')
        params.append(filters['customer_status'])
    if filters['customers']:
        where.append('cu."Id" = ANY(%s)')
        params.append(filters['customers'])
    if group_names:
        where.append('cu."CustomerGroupId" = ANY(%s)')
        params.append(group_names)
    return where, params


def build_report(filters):
    """Шүүлтийн дагуу бараа x харилцагч x сарын нэгтгэлийг буцаана.

    records:         [бараа_индекс, харилцагч_индекс, сар_индекс, тоо, дүн] - pivot-ыг хөтөч/Excel талд хийнэ.
    customers:       харилцагчийн нэрс; customer_groups нь ижил индексээр тухайн харилцагчийн бүлэг.
    idle_customers:  шүүлтийн хугацаанд борлуулалтгүй бүртгэлтэй харилцагчдын индекс.
    idle_items:      үлдэгдэлтэй ч шүүлтийн хугацаанд борлуулалтгүй барааны индекс (item_mode != with үед).
                     "Үлдэгдэлтэй" = stock_only чеклэсэн бол Агуулах жижигт, үгүй бол аль нэг агуулахад.
    stock:           {барааны нэр: [жижиг, толгойт]} - үлдэгдлийн багана харуулах үед л бөглөгдөнө.
    """
    with connection.cursor() as cursor:
        group_names = _expand_customer_groups(cursor, filters['customer_groups']) if filters['customer_groups'] else []
        where, params = _sale_conditions(filters, group_names, filters['date_from'], filters['date_to'])

        # "Зөвхөн борлуулалтгүй" горимд ч борлуулалттай харилцагчдыг хасахын тулд үргэлж уншина
        cursor.execute(
            f'''
            SELECT COALESCE(s."ItemName", ''), COALESCE(s."CustomerId", ''),
                   MAX(COALESCE(cu."Name", s."CustomerName", '')),
                   MAX(COALESCE(cu."CustomerGroupId", s."CustomerGroupId", '')),
                   MAX(COALESCE(cu."ActiveStatus", '')),
                   to_char(s."DocumentDate"::date, 'YYYY-MM'),
                   COALESCE(SUM(NULLIF(s."Qty"::text, '')::float8), 0), COALESCE(SUM(NULLIF(s."PayAmount"::text, '')::float8), 0)
            FROM "OpenDataSale" s
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = s."DistributionChannelId"
            LEFT JOIN "OpenDataCustomer" cu ON cu."Id" = s."CustomerId"
            WHERE {' AND '.join(where)}
            GROUP BY 1, 2, 6
            ''',
            params,
        )
        sales = cursor.fetchall()

        # Шүүсэн сувагт бүртгэлтэй харилцагчид - борлуулалтгүйг нь олоход ашиглана
        registered = []
        if filters['sales_mode'] != SALES_MODE_WITH:
            cu_where, cu_params = _customer_conditions(filters, group_names)
            cursor.execute(
                f'''
                SELECT cu."Id", COALESCE(cu."Name", ''), COALESCE(cu."CustomerGroupId", ''),
                       COALESCE(cu."ActiveStatus", '')
                FROM "OpenDataCustomer" cu
                LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = cu."DistributionChannelId"
                WHERE {' AND '.join(cu_where)}
                ''',
                cu_params,
            )
            registered = cursor.fetchall()

    # Харилцагчийг Id-гаар ялгана (ижил нэртэй өөр харилцагч байж болно)
    # Эх системд нэрийн өмнө/ард хоосон зай, мөр шилжилт байдаг тул цэвэрлэнэ (эрэмбэлэлтэд нөлөөлдөг)
    customer_info = {}
    for _, customer_id, name, group, status, *_ in sales:
        # Харилцагчгүй борлуулалт (жиш: лангууны борлуулалт) - Id, нэр хоёулаа хоосон ирдэг
        customer_info[customer_id] = (' '.join(name.split()) or NO_CUSTOMER_LABEL, group, status)
    idle_ids = {row[0] for row in registered} - set(customer_info)
    for customer_id, name, group, status in registered:
        if customer_id in idle_ids:
            customer_info[customer_id] = (' '.join(name.split()), group, status)
    if filters['sales_mode'] == SALES_MODE_WITHOUT:
        sales = []
        customer_info = {cid: info for cid, info in customer_info.items() if cid in idle_ids}

    idle_item_names = set()
    if filters['item_mode'] != ITEM_MODE_WITH:
        from shop.models_inventory import InventorySnapshot

        stocked = InventorySnapshot.objects.filter(
            **({'jijig_qty__gt': 0} if filters['stock_only'] else {'total_qty__gt': 0}))
        if filters['items']:
            stocked = stocked.filter(itemname__in=filters['items'])
        idle_item_names = set(stocked.values_list('itemname', flat=True)) - {r[0] for r in sales}
        if filters['item_mode'] == ITEM_MODE_WITHOUT:
            sales = []
            customer_info = {}
            idle_ids = set()

    months = _month_range(filters['date_from'], filters['date_to'])
    month_index = {m: i for i, m in enumerate(months)}
    item_names = sorted({r[0] for r in sales} | idle_item_names)
    item_index = {n: i for i, n in enumerate(item_names)}
    customer_ids = sorted(customer_info, key=lambda cid: (customer_info[cid][0], cid))
    customer_index = {cid: i for i, cid in enumerate(customer_ids)}

    records = [
        [item_index[item], customer_index[customer_id], month_index[ym], round(qty, 2), round(amount, 2)]
        for item, customer_id, _, _, _, ym, qty, amount in sales
        if ym in month_index
    ]

    stock = {}
    if filters['stock_only'] or filters['show_tolgoit']:
        from shop.models_inventory import InventorySnapshot

        for name, jijig, tolgoit in InventorySnapshot.objects.filter(itemname__in=item_names).values_list(
            'itemname', 'jijig_qty', 'tolgoit_qty'
        ):
            stock[name] = [float(jijig), float(tolgoit)]

    return {
        'months': months,
        'items': item_names,
        'customers': [customer_info[cid][0] for cid in customer_ids],
        'customer_groups': [customer_info[cid][1] for cid in customer_ids],
        'customer_inactive': [customer_info[cid][2] == 'N' for cid in customer_ids],
        'idle_customers': sorted(customer_index[cid] for cid in idle_ids if cid in customer_index),
        'idle_items': sorted(item_index[name] for name in idle_item_names),
        'records': records,
        'stock': stock,
        'show_jijig': filters['stock_only'],
        'show_tolgoit': filters['show_tolgoit'],
    }


def pivot_rows(report, group_by, metric, sort_key='name', sort_desc=False):
    """Excel экспортод зориулж records-ыг дээд/доод түвшний мөрүүд болгон нэгтгэнэ.

    sort_key нь хөтөч дээрх эрэмбэлэлттэй ижил: 'name', 'total', 'jijig', 'tolgoit' эсвэл сарын индекс.
    Харилцагч дээд түвшинд үед борлуулалтгүй харилцагчид хоосон мөрөөр орно.
    Буцаах: [{'name', 'group', 'values', 'total', 'stock', 'children': [{'name', 'group', 'values', 'total', 'stock'}]}]
    """
    value_pos = 3 if metric == METRIC_QTY else 4
    month_count = len(report['months'])
    top_is_item = group_by == GROUP_ITEM
    top_names = report['items'] if top_is_item else report['customers']
    sub_names = report['customers'] if top_is_item else report['items']

    groups = defaultdict(lambda: defaultdict(lambda: [0.0] * month_count))
    for record in report['records']:
        top, sub = (record[0], record[1]) if top_is_item else (record[1], record[0])
        groups[top][sub][record[2]] += record[value_pos]
    for idle in (report['idle_items'] if top_is_item else report['idle_customers']):
        groups[idle]  # борлуулалтгүй бараа/харилцагч - хоосон бүлэг үүсгэнэ

    def stock_of(item_name):
        return report['stock'].get(item_name, [0.0, 0.0])

    def group_of_customer(index):
        group = report['customer_groups'][index]
        return f'{group} (идэвхгүй)' if report['customer_inactive'][index] else group

    rows = []
    for top in sorted(groups, key=lambda i: top_names[i]):
        children = []
        top_values = [0.0] * month_count
        for sub in sorted(groups[top], key=lambda i: sub_names[i]):
            values = groups[top][sub]
            for i, v in enumerate(values):
                top_values[i] += v
            children.append({
                'name': sub_names[sub],
                'group': group_of_customer(sub) if top_is_item else '',
                'values': values,
                'total': sum(values),
                'stock': None if top_is_item else stock_of(sub_names[sub]),
            })
        rows.append({
            'name': top_names[top],
            'group': '' if top_is_item else group_of_customer(top),
            'values': top_values,
            'total': sum(top_values),
            'stock': stock_of(top_names[top]) if top_is_item else None,
            'children': children,
        })

    if sort_key != 'name':
        def value_of(row):
            if sort_key == 'total':
                return row['total']
            if sort_key in ('jijig', 'tolgoit'):
                return row['stock'][0 if sort_key == 'jijig' else 1] if row['stock'] else 0
            index = int(sort_key) if str(sort_key).isdigit() else -1
            return row['values'][index] if 0 <= index < month_count else 0

        rows.sort(key=value_of, reverse=sort_desc)
        for row in rows:
            row['children'].sort(key=value_of, reverse=sort_desc)
    elif sort_desc:
        rows.reverse()
        for row in rows:
            row['children'].reverse()
    return rows
