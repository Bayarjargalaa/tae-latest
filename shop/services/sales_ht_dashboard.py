"""
Борлуулалтын тайлан ХТ-р - Dashboard-ын нэгтгэлүүд.

Хүснэгттэй ижил шүүлтийг (sales_ht._sale_conditions) ашиглаж, шүүсэн борлуулалтаас нэг удаагийн
GROUPING SETS query-ээр сар, суваг, борлуулагч, харилцагчийн бүлэг, харилцагч, бараа, гарагаар нэгтгэнэ.
Хөтөч талд үзүүлэлт (дүн, ашиг, тоо, захиалга, харилцагч) болон харуулах хэсгүүдийг уян хатан сонгоно.

- Захиалга: DocumentPkId (нэг баримт = нэг харилцагч, нэг өдөр)
- Бохир ашиг: НӨАТ-гүй дүн - тоо x өртөг (UnitCost)
- Харьцуулах үе (filters['compare']): өмнөх ижил урттай хугацаа, өнгөрсөн жилийн мөн үе, гараар сонгосон
  хугацаа эсвэл харьцуулахгүй. KPI-ийн өөрчлөлт болон сарын динамикийн давхар шугамд ашиглана;
  сарууд нь дарааллаараа (1 дэх сар нь 1 дэх сартай г.м.) харьцуулагдана.
"""
import re
from datetime import date, timedelta

from django.db import connection

from shop.services.sales_ht import (
    COMPARE_CUSTOM,
    COMPARE_LABELS,
    COMPARE_NONE,
    COMPARE_PREV,
    COMPARE_YOY,
    NO_CHANNEL_LABEL,
    NO_CUSTOMER_LABEL,
    _customer_conditions,
    _expand_customer_groups,
    _month_range,
    _sale_conditions,
)

# base CTE-ийн нэгтгэл - дараалал нь _MEASURE_KEYS-тэй таарна.
# Харилцагчгүй борлуулалт (cust = '') харилцагчийн тоонд орохгүй.
_MEASURES_SQL = '''
    COALESCE(SUM(amount), 0), COALESCE(SUM(net), 0), COALESCE(SUM(qty), 0), COALESCE(SUM(profit), 0),
    COUNT(DISTINCT doc), COUNT(DISTINCT NULLIF(cust, '')), COUNT(DISTINCT item)
'''
_MEASURE_KEYS = ('amount', 'net', 'qty', 'profit', 'orders', 'customers', 'items')

# GROUPING SETS-ийн хэмжээсүүд: (үр дүнгийн түлхүүр, base CTE-ийн багана)
_DIMENSIONS = (
    ('month', 'ym'),
    ('channel', 'ch'),
    ('seller', 'seller'),
    ('group', 'grp'),
    ('customer', 'cust'),
    ('item', 'item'),
    ('weekday', 'dow'),
)
_DIMENSION_KEYS = tuple(key for key, _ in _DIMENSIONS)

WEEKDAY_LABELS = {1: 'Даваа', 2: 'Мягмар', 3: 'Лхагва', 4: 'Пүрэв', 5: 'Баасан', 6: 'Бямба', 7: 'Ням'}


def _query(cursor, filters, group_names, date_from, date_to, grouping_sets=None):
    """grouping_sets=None бол зөвхөн нийт дүн. GROUPING() нь зөвхөн grouping sets-д орсон баганад
    зөвшөөрөгддөг тул ороогүй хэмжээсийн оронд тогтмол утга (GROUPING=1, багана=NULL) сонгоно."""
    where, params = _sale_conditions(filters, group_names, date_from, date_to)
    columns = [column for _, column in _DIMENSIONS]
    used = set(re.findall(r'\w+', grouping_sets or ''))
    dim_select = ', '.join(
        [f'GROUPING({c})' if c in used else '1' for c in columns]
        + [c if c in used else 'NULL' for c in columns]
    )
    group_by = f'GROUP BY GROUPING SETS ({grouping_sets})' if grouping_sets else ''
    cursor.execute(
        f'''
        WITH base AS (
            SELECT to_char(s."DocumentDate"::date, 'YYYY-MM') AS ym,
                   COALESCE(dc."Id", '') AS ch, COALESCE(dc."Name", '') AS ch_name,
                   COALESCE(NULLIF(s."SellerName", ''), '(тодорхойгүй)') AS seller,
                   COALESCE(NULLIF(COALESCE(cu."CustomerGroupId", s."CustomerGroupId"), ''), '(бүлэггүй)') AS grp,
                   COALESCE(s."CustomerId", '') AS cust,
                   COALESCE(cu."Name", s."CustomerName", '') AS cust_name,
                   COALESCE(s."ItemName", '') AS item,
                   EXTRACT(ISODOW FROM s."DocumentDate"::date)::int AS dow,
                   s."DocumentPkId" AS doc,
                   NULLIF(s."PayAmount"::text, '')::float8 AS amount, NULLIF(s."AmountNonVat"::text, '')::float8 AS net, NULLIF(s."Qty"::text, '')::float8 AS qty,
                   COALESCE(NULLIF(s."AmountNonVat"::text, '')::float8, 0) - COALESCE(NULLIF(s."Qty"::text, '')::float8, 0) * COALESCE(NULLIF(s."UnitCost"::text, '')::float8, 0) AS profit
            FROM "OpenDataSale" s
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = s."DistributionChannelId"
            LEFT JOIN "OpenDataCustomer" cu ON cu."Id" = s."CustomerId"
            WHERE {' AND '.join(where)}
        )
        SELECT {dim_select}, MAX(cust_name), MAX(ch_name),
               {_MEASURES_SQL}
        FROM base
        {group_by}
        ''',
        params,
    )
    return cursor.fetchall()


def _channel_label(channel_id, channel_name):
    """'006 ХТ Баруун хойд бүс Тэнгэр'; суваггүй (хоосон Id) бол 'Суваггүй'."""
    return f'{channel_id} {channel_name}' if channel_id else NO_CHANNEL_LABEL


def _shift_year(day, years):
    """Огноог жилээр шилжүүлнэ; 2-р сарын 29 байхгүй жилд 28 болно."""
    try:
        return day.replace(year=day.year + years)
    except ValueError:
        return date(day.year + years, 2, 28)


def compare_range(filters):
    """(үйлчилсэн горим, (эхлэх, дуусах)) - харьцуулахгүй бол (COMPARE_NONE, None).
    Сонгосон хугацааны огноо дутуу бол өмнөх ижил урттай хугацаагаар орлуулна."""
    date_from, date_to = filters['date_from'], filters['date_to']
    mode = filters['compare']
    if mode == COMPARE_NONE:
        return COMPARE_NONE, None
    if mode == COMPARE_YOY:
        return mode, (_shift_year(date_from, -1), _shift_year(date_to, -1))
    if mode == COMPARE_CUSTOM and filters['compare_from'] and filters['compare_to']:
        return mode, tuple(sorted((filters['compare_from'], filters['compare_to'])))
    prev_to = date_from - timedelta(days=1)
    return COMPARE_PREV, (prev_to - (date_to - date_from), prev_to)


def _measures(row):
    offset = 2 * len(_DIMENSIONS) + 2
    return {key: round(float(value or 0), 2) for key, value in zip(_MEASURE_KEYS, row[offset:])}


def build_dashboard(filters):
    """Dashboard-ын өгөгдөл.

    kpi / compare_kpi:       одоогийн ба харьцуулах үеийн нийт үзүүлэлтүүд (харьцуулахгүй бол compare_kpi=None)
    months / compare_months: сар бүрийн үзүүлэлт; month_channel нь {суваг: [сар бүрийн үзүүлэлт]}
    channel, seller, group, customer, item, weekday: хэмжээс тус бүрийн мөрүүд {key, label, үзүүлэлтүүд}
    coverage:        суваг тус бүрт бүртгэлтэй харилцагч ба тэдгээрээс худалдан авалт хийсэн нь
    """
    n_dim = len(_DIMENSIONS)
    date_from, date_to = filters['date_from'], filters['date_to']
    compare_mode, compare = compare_range(filters)

    with connection.cursor() as cursor:
        group_names = _expand_customer_groups(cursor, filters['customer_groups']) if filters['customer_groups'] else []
        rows = _query(
            cursor, filters, group_names, date_from, date_to,
            '(), (ym), (ym, ch), (ch), (seller), (grp), (cust), (item), (dow)',
        )
        compare_rows = _query(cursor, filters, group_names, *compare, '(), (ym)') if compare else []

        cu_where, cu_params = _customer_conditions(filters, group_names)
        cursor.execute(
            f'''
            SELECT cu."Id", COALESCE(dc."Id", ''), COALESCE(dc."Name", '')
            FROM "OpenDataCustomer" cu
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = cu."DistributionChannelId"
            WHERE {' AND '.join(cu_where)}
            ''',
            cu_params,
        )
        registered = cursor.fetchall()

    empty = {key: 0 for key in _MEASURE_KEYS}
    months = _month_range(date_from, date_to)
    month_pos = {m: i for i, m in enumerate(months)}
    result = {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'compare_mode': compare_mode,
        'compare_label': COMPARE_LABELS[compare_mode] if compare else '',
        'compare_from': compare[0].isoformat() if compare else '',
        'compare_to': compare[1].isoformat() if compare else '',
        'kpi': dict(empty),
        'compare_kpi': dict(empty) if compare else None,
        'months': [{'key': m, 'label': m, **empty} for m in months],
        'compare_months': [],
        'month_channel': {},
        'channel_names': {},
        **{key: [] for key in ('channel', 'seller', 'group', 'customer', 'item', 'weekday')},
    }

    for row in rows:
        # GROUPING() = 0 бол тухайн хэмжээсээр бүлэглэсэн мөр
        active = [key for key, flag in zip(_DIMENSION_KEYS, row[:n_dim]) if not flag]
        values = dict(zip(_DIMENSION_KEYS, row[n_dim:2 * n_dim]))
        cust_name, ch_name = row[2 * n_dim], row[2 * n_dim + 1]
        m = _measures(row)

        if not active:
            result['kpi'] = m
        elif active == ['month']:
            if values['month'] in month_pos:
                result['months'][month_pos[values['month']]].update(m)
        elif active == ['month', 'channel']:
            series = result['month_channel'].setdefault(values['channel'], [dict(empty) for _ in months])
            if values['month'] in month_pos:
                series[month_pos[values['month']]] = m
        elif active == ['channel']:
            result['channel_names'][values['channel']] = ch_name or NO_CHANNEL_LABEL
            result['channel'].append({'key': values['channel'], 'label': _channel_label(values['channel'], ch_name), **m})
        elif active == ['customer']:
            label = ' '.join((cust_name or '').split()) or NO_CUSTOMER_LABEL
            result['customer'].append({'key': values['customer'], 'label': label, **m})
        elif active == ['weekday']:
            result['weekday'].append({'key': values['weekday'], 'label': WEEKDAY_LABELS.get(values['weekday'], ''), **m})
        elif len(active) == 1:
            key = active[0]
            result[key].append({'key': values[key], 'label': values[key] or '(хоосон)', **m})

    # Харьцуулах үе: нийт ба сар бүрийн үзүүлэлт (сарууд нь харьцуулах үеийн өөрийн сарын дарааллаар)
    if compare:
        compare_months = _month_range(*compare)
        compare_pos = {m: i for i, m in enumerate(compare_months)}
        result['compare_months'] = [{'key': m, 'label': m, **empty} for m in compare_months]
        for row in compare_rows:
            month = row[n_dim]  # ym багана
            if row[0]:  # GROUPING(ym) = 1 -> нийт дүн
                result['compare_kpi'] = _measures(row)
            elif month in compare_pos:
                result['compare_months'][compare_pos[month]].update(_measures(row))

    result['weekday'].sort(key=lambda r: r['key'])
    result['channel'].sort(key=lambda r: r['key'])

    # Хамрах хүрээ: сувагт бүртгэлтэй харилцагчдаас хэд нь энэ хугацаанд худалдан авалт хийсэн бэ
    buyers = {r['key'] for r in result['customer']}
    coverage = {}
    for customer_id, channel_id, channel_name in registered:
        entry = coverage.setdefault(channel_id, {
            'key': channel_id, 'label': _channel_label(channel_id, channel_name), 'registered': 0, 'buying': 0,
        })
        entry['registered'] += 1
        entry['buying'] += customer_id in buyers
    result['coverage'] = sorted(coverage.values(), key=lambda r: r['key'])
    result['registered_total'] = len(registered)
    result['registered_buying'] = sum(r['buying'] for r in coverage.values())
    return result
