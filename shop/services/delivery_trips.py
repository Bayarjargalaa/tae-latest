"""
Түгээлтийн машины бүртгэл (харуул хөтөлнө): сонголтын жагсаалтууд.

- Жолооч - "Түгээгч" албан тушаалтай идэвхтэй ажилчид, туслах - "Туслах ажилтан"
- Машин - OpenDataAsset-ийн "Тээврийн хэрэгсэл" бүлгийн хөрөнгийн нэрний улсын дугаар (жиш: "... шинээр 6259УНЭ")
Шинээр бичсэн нэр/дугаар (жагсаалтад байхгүй) бүртгэлд хадгалагдаж, дараагийн удаа сонголтод нэмэгдэнэ.
"""
import re
from datetime import timedelta

from django.db import connection
from django.utils import timezone

from datamigration.models import OpenDataEmployee
from shop.models import DeliveryTrip

DRIVER_POSITION = 'Түгээгч'
HELPER_POSITION = 'Туслах ажилтан'
VEHICLE_GROUP = 'Тээврийн хэрэгсэл'
PLATE_RE = re.compile(r'(\d{4})\s*-?\s*([А-ЯЁӨҮ]{3})', re.IGNORECASE)
# Өмнө бичсэн шинэ нэр/дугаарыг сонголтод хэдэн хоног харуулах
RECENT_DAYS = 120


def normalize_plate(value):
    """'9167 убр' / '9167-УБР' -> '9167УБР'; дугаарын хэлбэргүй бол том үсгээр, зайг шахаж буцаана."""
    value = (value or '').strip().upper()
    m = PLATE_RE.search(value)
    if m:
        return m.group(1) + m.group(2).upper()
    return re.sub(r'\s+', ' ', value)[:30]


def vehicle_options():
    """[{'plate': '6259УНЭ', 'label': 'Hyundai Porter II'}] - бүртгэлээс хасагдаагүй тээврийн хэрэгсэл."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT "AssetTypeName" FROM "OpenDataAsset" WHERE "AssetGroupId" = %s GROUP BY "AssetTypeName" '
            'HAVING COALESCE(SUM("DebitQty"), 0) - COALESCE(SUM("CreditQty"), 0) > 0', [VEHICLE_GROUP])
        names = [r[0] or '' for r in cursor.fetchall()]
    options = {}
    for name in names:
        m = PLATE_RE.search(name)
        if not m:
            continue
        plate = m.group(1) + m.group(2).upper()
        # 'Авто машин ачааны H-Grace /саарал/ 5392УНД' -> 'H-Grace'
        label = re.sub(r'^Авто\s*машин|/[^/]*/?|шинээр|ачааны', ' ', name[:m.start()])
        label = re.sub(r'\s+', ' ', label).strip()
        options.setdefault(plate, {'plate': plate, 'label': label, 'used': False})
    for plate in _recent_values('vehicle_plate'):
        options.setdefault(plate, {'plate': plate, 'label': '', 'used': True})
    return sorted(options.values(), key=lambda o: (o['used'], o['plate']))


def people_options(position, name_field):
    """[{'code', 'name', 'used'}] - тухайн албан тушаалын идэвхтэй ажилчид + өмнө шинээр бичсэн нэрс."""
    rows = OpenDataEmployee.objects.filter(isreclusion='N', positionname=position).order_by('name').values('id', 'name')
    options = [{'code': r['id'], 'name': (r['name'] or '').strip(), 'used': False} for r in rows if r['name']]
    known = {o['name'] for o in options}
    options += [{'code': '', 'name': n, 'used': True} for n in _recent_values(name_field) if n not in known]
    return options


def _recent_values(field):
    since = timezone.localdate() - timedelta(days=RECENT_DAYS)
    return sorted(set(DeliveryTrip.objects.filter(date__gte=since).exclude(**{field: ''})
                      .values_list(field, flat=True)))


def code_for_name(options, name):
    """Сонголтоос авсан нэр бол ажилтны код, шинээр бичсэн бол ''."""
    return next((o['code'] for o in options if o['name'] == name and o['code']), '')


# --- Жагсаалт (нягтлан): шүүлт, нэгтгэл - хуудас ба Excel хоёулаа list_data-г ашиглана ---

STATUS_CHOICES = [
    ('', 'Бүгд'),
    ('out', 'Ирээгүй'),
    ('back', 'Ирсэн'),
    ('remainder', 'Үлдэгдэлтэй'),
]


def _parse_date(value):
    from datetime import datetime
    try:
        return datetime.strptime(value or '', '%Y-%m-%d').date()
    except ValueError:
        return None


def list_filters(params):
    """GET параметрээс шүүлт. Анхдагч: энэ сарын 1-нээс өнөөдөр хүртэл."""
    today = timezone.localdate()
    date_from = _parse_date(params.get('date_from')) or today.replace(day=1)
    date_to = _parse_date(params.get('date_to')) or today
    if date_to < date_from:
        date_from, date_to = date_to, date_from
    status = params.get('status', '')
    return {
        'date_from': date_from, 'date_to': date_to,
        'driver': params.get('driver', '').strip(), 'helper': params.get('helper', '').strip(),
        'plate': params.get('plate', '').strip(),
        'status': status if status in dict(STATUS_CHOICES) else '',
    }


def _minutes(t):
    return t.hour * 60 + t.minute


def list_data(filters):
    from django.db.models import Q

    qs = DeliveryTrip.objects.filter(date__range=(filters['date_from'], filters['date_to']))
    if filters['driver']:
        qs = qs.filter(driver_name=filters['driver'])
    if filters['helper']:
        qs = qs.filter(helper_name='' if filters['helper'] == 'Туслахгүй' else filters['helper'])
    if filters['plate']:
        qs = qs.filter(vehicle_plate=filters['plate'])
    if filters['status'] == 'out':
        qs = qs.filter(return_time__isnull=True)
    elif filters['status'] == 'back':
        qs = qs.filter(return_time__isnull=False)
    elif filters['status'] == 'remainder':
        qs = qs.filter(Q(returned_count__gt=0) | ~Q(remainder_note=''))

    rows = []
    for t in qs.order_by('date', 'depart_time', 'id'):
        minutes = None
        if t.depart_time and t.return_time:
            minutes = (_minutes(t.return_time) - _minutes(t.depart_time)) % 1440
        rows.append({'trip': t, 'minutes': minutes, 'duration': f'{minutes // 60}:{minutes % 60:02d}' if minutes is not None else ''})

    by_driver = {}
    for r in rows:
        t = r['trip']
        d = by_driver.setdefault(t.driver_name, {'name': t.driver_name, 'trips': 0, 'customers': 0, 'returned': 0, 'days': set()})
        d['trips'] += 1
        d['customers'] += t.customer_count or 0
        d['returned'] += t.returned_count or 0
        d['days'].add(t.date)
    drivers = sorted(by_driver.values(), key=lambda d: -d['trips'])
    for d in drivers:
        d['days'] = len(d['days'])
        d['delivered'] = d['customers'] - d['returned']

    customers = sum(r['trip'].customer_count or 0 for r in rows)
    returned = sum(r['trip'].returned_count or 0 for r in rows)
    return {
        'rows': rows,
        'by_driver': drivers,
        'totals': {
            'trips': len(rows), 'customers': customers, 'returned': returned, 'delivered': customers - returned,
            'out': sum(1 for r in rows if not r['trip'].return_time),
            'delivered_pct': round((customers - returned) * 100 / customers) if customers else None,
        },
    }


def filter_choices():
    """Шүүлтийн сонголт - бүртгэлд байгаа бүх жолооч, туслах, машин."""
    qs = DeliveryTrip.objects.all()
    return {
        'drivers': sorted(set(qs.values_list('driver_name', flat=True))),
        'helpers': ['Туслахгүй'] + sorted(set(qs.exclude(helper_name='').values_list('helper_name', flat=True))),
        'plates': sorted(set(qs.values_list('vehicle_plate', flat=True))),
    }
