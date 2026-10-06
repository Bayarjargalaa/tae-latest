"""
Барааны өртөг - бараа тус бүрийн татан авалтын өртөг ба дундаж өртгийг огноогоор харуулна.

- Дундаж өртөг: OpenDataInventory.UnitCost - хөдөлгөөн бүр дээрх хөдөлж буй жигнэсэн дундаж өртөг
  (агуулахаас үл хамааран ижил). Өдөр бүрийн сүүлийн хөдөлгөөний (CreatedDate) өртгийг тухайн өдрийнх гэж
  авна; 0 өртөгтэй мөрийг тооцохгүй.
- Татан авалтын өртөг: OpenDataLandedCost.UnitCost - татан авалт бүрийн нэгжийн өртөг (НӨАТ-тэй). Дараагийн
  татан авалт хүртэл хүчинтэй. Нэг өдөр хэд хэдэн татан авалт байвал тоо хэмжээгээр жигнэсэн дунджийг авна.
  НӨАТ-гүй өртөг = UnitCost / 1.1; дундаж өртөг НӨАТ-гүй тул зөрүүг НӨАТ-гүй өртөгтэй харьцуулна.
- Бараа хоёр хүснэгтэд ItemId-гаар таарна.
"""
from collections import defaultdict
from datetime import date, datetime

from django.db import connection

# Дундаж өртөг ийм хэмжээнээс (харьцангуй) их өөрчлөгдвөл түүхэнд тусдаа цэг болгоно - бутархайн
# зөрүүгээр (6253.295941 -> 6253.29594) өдөр бүр "өөрчлөгдсөн" мэт харагдахаас сэргийлнэ
CHANGE_THRESHOLD = 0.0005

# Татан авалтын өртөг НӨАТ-тэй (10%) бүртгэгддэг; НӨАТ-гүй өртөг = өртөг / 1.1
VAT_FACTOR = 1.1


def _parse_date(value, default):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return default


def parse_filters(params):
    """GET параметрүүд. Огноо заагаагүй бол оны эхнээс өнөөдрийг хүртэл."""
    today = date.today()
    date_from = _parse_date(params.get('date_from'), date(today.year, 1, 1))
    date_to = _parse_date(params.get('date_to'), today)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    return {
        'date_from': date_from,
        'date_to': date_to,
        'items': [v for v in params.getlist('item') if v],
        'landed_only': params.get('landed_only') == 'true',
        'stock_only': params.get('stock_only') == 'true',
    }


def get_item_options():
    """Өртгийн мэдээлэлтэй бараанууд [(ItemId, нэр)] - нэрээр эрэмбэлсэн."""
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT "ItemId", MAX("ItemName") FROM "OpenDataInventory"
            WHERE "ItemId" IS NOT NULL GROUP BY 1 ORDER BY 2
            '''
        )
        return cursor.fetchall()


def _landed_by_day(cursor, filters):
    """{ItemId: [(огноо, жигнэсэн өртөг, [баримтууд])]} - date_to хүртэлх бүх татан авалт, огноогоор."""
    where, params = ['"DocumentDate"::date <= %s', """NULLIF("UnitCost"::text, '')::float8 > 0"""], [filters['date_to']]
    if filters['items']:
        where.append('"ItemId" = ANY(%s)')
        params.append(filters['items'])
    cursor.execute(
        f'''
        SELECT "ItemId", "DocumentDate"::date, "DocumentNumber", COALESCE("VendorName", ''), COALESCE(NULLIF("Qty"::text, '')::float8, 0), NULLIF("UnitCost"::text, '')::float8,
               COALESCE("CurrencyId", ''), COALESCE(NULLIF("Price"::text, '')::float8, 0), COALESCE(NULLIF("Rate"::text, '')::float8, 0), COALESCE(NULLIF("SalePrice"::text, '')::float8, 0)
        FROM "OpenDataLandedCost"
        WHERE {' AND '.join(where)}
        ORDER BY "ItemId", "DocumentDate"::date, "DocumentPkId"
        ''',
        params,
    )
    grouped = defaultdict(lambda: defaultdict(list))
    for item_id, day, number, vendor, qty, unit_cost, currency, price, rate, sale_price in cursor.fetchall():
        grouped[item_id][day].append({
            'date': day.isoformat(), 'number': number, 'vendor': vendor, 'qty': qty, 'unit_cost': unit_cost,
            'currency': currency, 'price': price, 'rate': rate, 'sale_price': sale_price,
        })
    result = {}
    for item_id, days in grouped.items():
        entries = []
        for day in sorted(days):
            docs = days[day]
            total_qty = sum(d['qty'] for d in docs)
            cost = (sum(d['qty'] * d['unit_cost'] for d in docs) / total_qty) if total_qty else docs[-1]['unit_cost']
            entries.append((day, cost, docs))
        result[item_id] = entries
    return result


def _average_costs(cursor, filters):
    """(opening, daily): opening = {ItemId: (огноо, өртөг)} date_from-оос өмнөх сүүлийн дундаж өртөг,
    daily = {ItemId: [(огноо, өртөг)]} хугацааны өдөр бүрийн сүүлийн дундаж өртөг."""
    item_sql, item_params = ('AND "ItemId" = ANY(%s)', [filters['items']]) if filters['items'] else ('', [])
    cursor.execute(
        f'''
        SELECT DISTINCT ON ("ItemId") "ItemId", "DocumentDate"::date, NULLIF("UnitCost"::text, '')::float8
        FROM "OpenDataInventory"
        WHERE NULLIF("UnitCost"::text, '')::float8 > 0 AND "DocumentDate"::date < %s {item_sql}
        ORDER BY "ItemId", "DocumentDate"::date DESC, "CreatedDate" DESC, "DocumentPkId" DESC
        ''',
        [filters['date_from'], *item_params],
    )
    opening = {item_id: (day, cost) for item_id, day, cost in cursor.fetchall()}

    cursor.execute(
        f'''
        SELECT DISTINCT ON ("ItemId", "DocumentDate"::date) "ItemId", "DocumentDate"::date, NULLIF("UnitCost"::text, '')::float8
        FROM "OpenDataInventory"
        WHERE NULLIF("UnitCost"::text, '')::float8 > 0 AND "DocumentDate"::date BETWEEN %s AND %s {item_sql}
        ORDER BY "ItemId", "DocumentDate"::date, "CreatedDate" DESC, "DocumentPkId" DESC
        ''',
        [filters['date_from'], filters['date_to'], *item_params],
    )
    daily = defaultdict(list)
    for item_id, day, cost in cursor.fetchall():
        daily[item_id].append((day, cost))
    return opening, daily


def _item_meta(cursor, item_ids):
    """{ItemId: (нэр, хэмжих нэгж)}"""
    if not item_ids:
        return {}
    cursor.execute(
        '''
        SELECT "ItemId", MAX("ItemName"), MAX(COALESCE("MeasureName", ''))
        FROM "OpenDataInventory" WHERE "ItemId" = ANY(%s) GROUP BY 1
        ''',
        [list(item_ids)],
    )
    return {item_id: (name, measure) for item_id, name, measure in cursor.fetchall()}


def _novat(cost):
    """НӨАТ-гүй өртөг (татан авалтын өртөг НӨАТ-тэй бүртгэгддэг)."""
    return cost / VAT_FACTOR if cost is not None else None


def _pct(value, base):
    return (value - base) / base if value is not None and base else None


def build_costs(filters):
    """Бараа тус бүрийн мөр:
    avg_start / avg_end:       хугацааны эхэн ба төгсгөл дэх дундаж өртөг (эхэнд нь өмнөх сүүлийн утга)
    landed_start / landed_end: тухайн үед хүчинтэй татан авалтын өртөг (сүүлийн татан авалтынх)
    history:                   хугацааны доторх өөрчлөлтийн цэгүүд [огноо, дундаж, татан авалт, тэмдэглэгээ]
    events:                    хугацааны доторх татан авалтын баримтууд
    """
    date_from, date_to = filters['date_from'], filters['date_to']
    with connection.cursor() as cursor:
        landed = _landed_by_day(cursor, filters)
        opening, daily = _average_costs(cursor, filters)
        item_ids = set(landed) | set(opening) | set(daily)
        meta = _item_meta(cursor, item_ids)

    stock = {}
    if item_ids:
        from shop.models_inventory import InventorySnapshot

        names = [meta[i][0] for i in item_ids if i in meta]
        stock = dict(InventorySnapshot.objects.filter(itemname__in=names).values_list('itemname', 'total_qty'))

    rows = []
    for item_id in item_ids:
        name, measure = meta.get(item_id, ('', ''))
        landed_entries = landed.get(item_id, [])
        before = [e for e in landed_entries if e[0] < date_from]
        in_range = [e for e in landed_entries if e[0] >= date_from]
        if filters['landed_only'] and not in_range:
            continue
        qty = float(stock[name]) if name in stock else None
        if filters['stock_only'] and not qty:
            continue

        # Өдөр бүрээр: дундаж өртөг ба тухайн өдөр хүчинтэй татан авалтын өртөг
        landed_cost = before[-1][1] if before else None
        landed_date = before[-1][0] if before else None
        open_day, open_cost = opening.get(item_id, (None, None))
        avg_cost = open_cost
        days = {day: cost for day, cost in daily.get(item_id, [])}
        landed_days = {day: (cost, docs) for day, cost, docs in in_range}

        history = []
        last_recorded = None
        if avg_cost is not None or landed_cost is not None:
            history.append([date_from.isoformat(), avg_cost, landed_cost, _novat(landed_cost), ''])
            last_recorded = avg_cost
        for day in sorted(set(days) | set(landed_days)):
            note = ''
            if day in landed_days:
                landed_cost, docs = landed_days[day]
                landed_date = day
                note = ', '.join(d['number'] for d in docs)
            if day in days:
                avg_cost = days[day]
            changed = (
                last_recorded is None and avg_cost is not None
                or avg_cost is not None and abs(avg_cost - last_recorded) > abs(last_recorded) * CHANGE_THRESHOLD
            )
            if note or changed:
                history.append([day.isoformat(), avg_cost, landed_cost, _novat(landed_cost), note])
                last_recorded = avg_cost
        if avg_cost is None and landed_cost is None:
            continue
        # Төгсгөлийн цэг (графикийг date_to хүртэл үргэлжлүүлнэ)
        if not history or history[-1][0] != date_to.isoformat():
            history.append([date_to.isoformat(), avg_cost, landed_cost, _novat(landed_cost), ''])

        avg_start = open_cost if open_cost is not None else (daily[item_id][0][1] if daily.get(item_id) else None)
        landed_start = before[-1][1] if before else None
        last_avg_day = daily[item_id][-1][0] if daily.get(item_id) else open_day
        last_landed_docs = in_range[-1][2] if in_range else (before[-1][2] if before else [])

        rows.append({
            'id': item_id,
            'name': name,
            'measure': measure,
            'avg_start': avg_start,
            'avg_end': avg_cost,
            'avg_end_date': last_avg_day.isoformat() if last_avg_day else '',
            'avg_change': _pct(avg_cost, avg_start),
            'landed_start': landed_start,
            'landed_start_novat': _novat(landed_start),
            'landed_end': landed_cost,
            'landed_end_novat': _novat(landed_cost),
            'landed_end_date': landed_date.isoformat() if landed_date else '',
            'landed_end_numbers': ', '.join(d['number'] for d in last_landed_docs),
            'landed_change': _pct(landed_cost, landed_start),
            # Дундаж өртөг НӨАТ-гүй тул НӨАТ-гүй татан авалтын өртөгтэй харьцуулна
            'diff': _pct(avg_cost, _novat(landed_cost)),
            'landed_count': sum(len(docs) for _, _, docs in in_range),
            'stock_qty': qty,
            'stock_value': qty * avg_cost if qty is not None and avg_cost is not None else None,
            'history': history,
            'events': [doc for _, _, docs in in_range for doc in docs],
        })

    rows.sort(key=lambda r: r['name'])
    return {
        'date_from': date_from.isoformat(),
        'date_to': date_to.isoformat(),
        'rows': rows,
    }
