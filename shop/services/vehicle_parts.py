"""
Тээврийн хэрэгсэл -> Сэлбэг хэрэгсэл: сэлбэг, засвар үйлчилгээний бүртгэл.

- Шинэ бүртгэл: нэг баримт (огноо, машин, жолооч, км, нийлүүлэгч) + олон мөр (тайлбар, төрөл, тоо, үнэ).
  Мөр бүр тусдаа хадгалагдана, дүн = тоо × нэгж үнэ.
- Excel импорт: хуучин "Машины бүртгэл" загвар (Огноо, Тайлбар, Машины дугаар, Хамаарах төрөл, Жолооч, Тоо,
  Үнэ, Дүн). Машины дугаар 4 оронтой тоо бол манай машины бүтэн дугаараар солино. Дахин импортлоход давхардахгүй.
"""
import hashlib
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction

from shop.models import VehiclePartRecord
from shop.services import vehicles as vh
from shop.services.fuel import _decimal, _norm_header, _text

CATEGORIES = [
    'Сэлбэг', 'Явах эд ангийн засвар', 'Тослох материал', 'Хөргөлтийн шингэн', 'Дугуй засвар', 'Аккумлятор',
    'Моторын засвар', 'Цахилгааны засвар', 'Засварын ажлын хөлс', 'Оношлогоо', 'Зөвшөөрөл', 'Даатгал',
    'Угаалга', 'Бусад',
]
CATEGORY_ALIASES = {
    'сэлбэг /бүх төрлийн сэлбэг орно/': 'Сэлбэг',
    'ажлын хөлс': 'Засварын ажлын хөлс',
}
IMPORT_HEADERS = {
    'date': 'Огноо', 'description': 'Тайлбар', 'plate': 'Машины дугаар', 'category': 'Хамаарах төрөл',
    'driver': 'Жолооч', 'quantity': 'Тоо', 'unit_price': 'Үнэ', 'amount': 'Дүн',
    'supplier': 'Нийлүүлэгч', 'km': 'Км заалт',
}


class PartsImportError(ValueError):
    pass


def normalize_category(value):
    text = re.sub(r'\s+', ' ', str(value or '')).strip()
    if not text:
        return 'Бусад'
    low = text.lower()
    if low in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[low]
    for c in CATEGORIES:
        if c.lower() == low:
            return c
    return text[:1].upper() + text[1:60]


def category_options():
    used = set(VehiclePartRecord.objects.values_list('category', flat=True).distinct())
    return CATEGORIES + sorted(used - set(CATEGORIES))


def supplier_options():
    return sorted(set(VehiclePartRecord.objects.exclude(supplier='').values_list('supplier', flat=True)))


def resolve_plate(value, ours=None):
    """'1485' -> '1485УАН' (манай машинаас), '6259 унэ' -> '6259УНЭ', хоосон -> ''."""
    from shop.services.delivery_trips import normalize_plate

    text = _text(value)
    if not text:
        return ''
    if re.fullmatch(r'\d{4}', text):
        match = [p for p in (ours if ours is not None else vh.our_plates()) if p.startswith(text)]
        return match[0] if len(match) == 1 else text
    return normalize_plate(text)


# --- Шүүлт, жагсаалт ---

def part_filters(params):
    from django.utils import timezone
    today = timezone.localdate()
    d_from, d_to = vh.period(params, date(today.year, 1, 1), today)
    return {
        'date_from': d_from, 'date_to': d_to,
        'plate': vh.multi(params, 'plate'), 'category': vh.multi(params, 'category'),
        'driver': vh.multi(params, 'driver'), 'supplier': vh.multi(params, 'supplier'),
        'q': params.get('q', '').strip(),
    }


def part_rows(f):
    from django.db.models import Q

    qs = VehiclePartRecord.objects.filter(date__range=(f['date_from'], f['date_to']))
    if f['plate']:  # сонгосон машинуудын аль нэг (манай бүх машин, машингүй бүлэг ч байж болно)
        plates = {p for p in f['plate'] if not p.startswith('__')}
        if vh.OUR_PLATES in f['plate']:
            plates |= vh.our_plates()
        if vh.NO_PLATE in f['plate']:
            plates.add('')
        qs = qs.filter(vehicle_plate__in=plates)
    if f['category']:
        qs = qs.filter(category__in=f['category'])
    if f['driver']:
        qs = qs.filter(driver_name__in=f['driver'])
    if f['supplier']:
        qs = qs.filter(supplier__in=f['supplier'])
    if f['q']:
        qs = qs.filter(Q(description__icontains=f['q']) | Q(note__icontains=f['q']) | Q(supplier__icontains=f['q'])
                       | Q(vehicle_plate__icontains=f['q']) | Q(driver_name__icontains=f['q']))
    return list(qs.order_by('date', 'id'))


def part_data(f):
    rows = part_rows(f)
    by_cat = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
    by_plate = defaultdict(lambda: {'count': 0, 'amount': Decimal('0')})
    for p in rows:
        by_cat[p.category]['count'] += 1
        by_cat[p.category]['amount'] += p.amount
        by_plate[p.vehicle_plate or 'Машингүй']['count'] += 1
        by_plate[p.vehicle_plate or 'Машингүй']['amount'] += p.amount
    return {
        'rows': rows,
        'total': sum((p.amount for p in rows), Decimal('0')),
        'by_category': sorted(({'name': k, **v} for k, v in by_cat.items()), key=lambda d: -d['amount']),
        'by_plate': sorted(({'name': k, **v} for k, v in by_plate.items()), key=lambda d: -d['amount']),
        'future': sum(1 for p in rows if p.date > date.today()),
    }


def part_filter_meta(f):
    meta = [('Хугацаа', vh.period_label(f['date_from'], f['date_to']))]
    if f['plate']:
        meta.append(('Машин', ', '.join(vh.plate_filter_label(p) for p in f['plate'])))
    for key, label in (('category', 'Төрөл'), ('driver', 'Жолооч'), ('supplier', 'Нийлүүлэгч')):
        if f[key]:
            meta.append((label, ', '.join(f[key])))
    if f['q']:
        meta.append(('Хайлт', f['q']))
    return meta


def export_report(f):
    data = part_data(f)
    cols = [{'key': 'date', 'label': 'Огноо', 'fmt': 'date'}, {'key': 'plate', 'label': 'Машин'}] + vh.PART_COLUMNS_SHORT[1:] \
        + [{'key': 'note', 'label': 'Нэмэлт тайлбар'}]
    return {
        'title': 'Сэлбэг, засварын бүртгэл', 'meta': part_filter_meta(f),
        'tables': [
            {'columns': cols, 'rows': [vh._part_row(p) for p in data['rows']],
             'totals': {'date': 'Нийт', 'amount': data['total']}},
            {'title': 'Төрлөөр', 'columns': [{'key': 'name', 'label': 'Төрөл'}, {'key': 'count', 'label': 'Мөр', 'fmt': 'int'},
                                              {'key': 'amount', 'label': 'Дүн ₮', 'fmt': 'money'}],
             'rows': data['by_category'], 'totals': {'name': 'Нийт', 'count': len(data['rows']), 'amount': data['total']}},
            {'title': 'Машинаар', 'columns': [{'key': 'name', 'label': 'Машин'}, {'key': 'count', 'label': 'Мөр', 'fmt': 'int'},
                                               {'key': 'amount', 'label': 'Дүн ₮', 'fmt': 'money'}],
             'rows': data['by_plate'], 'totals': {'name': 'Нийт', 'count': len(data['rows']), 'amount': data['total']}},
        ],
    }


# --- Хадгалах ---

def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = _text(value)
    for fmt in ('%Y-%m-%d', '%Y.%m.%d', '%Y/%m/%d', '%Y-%m-%d %H:%M:%S'):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _km(value):
    text = _text(value).replace(',', '').replace(' ', '')
    if not text:
        return None
    try:
        km = int(Decimal(text))
    except Exception:  # noqa: BLE001
        raise ValueError('Км заалт буруу байна.')
    if not 0 <= km < 10_000_000:
        raise ValueError('Км заалт буруу байна.')
    return km


def save_entry(post, user, record=None):
    """Маягтаас (баримтын толгой + description[]/category[]/quantity[]/unit_price[] мөрүүд) хадгална.
    record өгвөл тэр нэг мөрийг засна. Буцаах: (хадгалсан мөрийн тоо, алдаа)."""
    day = _parse_date(post.get('date'))
    if not day:
        return 0, 'Огноог оруулна уу.'
    plate = resolve_plate(post.get('vehicle_plate'))
    try:
        km = _km(post.get('odometer_km'))
    except ValueError as exc:
        return 0, str(exc)
    driver = _text(post.get('driver_name'))[:100]
    common = {
        'date': day, 'vehicle_plate': plate, 'odometer_km': km, 'driver_name': driver,
        'driver_code': vh.driver_code(driver), 'supplier': _text(post.get('supplier'))[:150],
        'note': _text(post.get('note'))[:255], 'updated_by': user,
    }
    lines = []
    for desc, cat, qty, price in zip(post.getlist('description'), post.getlist('category'),
                                     post.getlist('quantity'), post.getlist('unit_price')):
        desc = _text(desc)[:255]
        qty_d = _decimal(qty)
        price_d = _decimal(price)
        if not desc and not price_d:
            continue
        if not desc:
            return 0, 'Мөр бүрт тайлбар (юу авсан/хийлгэсэн) бичнэ үү.'
        qty_d = qty_d if qty_d is not None else Decimal('1')
        price_d = price_d or Decimal('0')
        if qty_d <= 0 or price_d < 0:
            return 0, f'"{desc}" мөрийн тоо, үнэ буруу байна.'
        lines.append({'description': desc, 'category': normalize_category(cat), 'quantity': qty_d,
                      'unit_price': price_d, 'amount': (qty_d * price_d).quantize(vh.CENT)})
    if not lines:
        return 0, 'Дор хаяж нэг мөр бөглөнө үү.'
    with transaction.atomic():
        if record:
            for k, v in {**common, **lines[0]}.items():
                setattr(record, k, v)
            record.save()
            extra = lines[1:]
        else:
            extra = lines
        for line in extra:
            VehiclePartRecord.objects.create(**common, **line, created_by=user)
    return len(lines), None


# --- Excel импорт ---

def read_workbook(file):
    """Сэлбэгийн бүртгэлийн загвартай хуудсыг (аль ч sheet) уншиж [dict] буцаана."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001
        raise PartsImportError(f'Excel файл уншигдсангүй: {exc}') from exc
    try:
        for ws in wb.worksheets:
            rows = ws.iter_rows(values_only=True)
            for i, row in zip(range(10), rows):
                names = [_norm_header(c) for c in row]
                if _norm_header('Хамаарах төрөл') in names and _norm_header('Тайлбар') in names:
                    cols = {f: names.index(_norm_header(lbl)) for f, lbl in IMPORT_HEADERS.items()
                            if _norm_header(lbl) in names}
                    if 'date' not in cols:
                        raise PartsImportError('"Огноо" багана олдсонгүй.')
                    out = []
                    for raw in rows:
                        rec = {f: (raw[c] if c < len(raw) else None) for f, c in cols.items()}
                        if any(_text(v) for v in rec.values()):
                            out.append(rec)
                    return out
    finally:
        wb.close()
    raise PartsImportError('Сэлбэгийн бүртгэлийн загвар биш байна ("Огноо", "Тайлбар", "Машины дугаар", '
                           '"Хамаарах төрөл", "Тоо", "Үнэ", "Дүн" баганатай хуудас олдсонгүй).')


def import_records(records, user=None):
    ours = vh.our_plates()
    drivers = vh.driver_options()
    parsed, invalid = [], 0
    for rec in records:
        day = _parse_date(rec.get('date'))
        desc = _text(rec.get('description'))[:255]
        qty = _decimal(rec.get('quantity'))
        price = _decimal(rec.get('unit_price'))
        amount = _decimal(rec.get('amount'))
        if not day or not desc:
            invalid += 1
            continue
        qty = qty if qty is not None and qty > 0 else Decimal('1')
        if amount is None:
            amount = (qty * (price or 0)).quantize(vh.CENT)
        if price is None:
            price = (amount / qty).quantize(vh.CENT)
        driver = _text(rec.get('driver'))[:100]
        try:
            km = _km(rec.get('km'))
        except ValueError:
            km = None
        parsed.append({
            'date': day, 'description': desc, 'vehicle_plate': resolve_plate(rec.get('plate'), ours),
            'category': normalize_category(rec.get('category')), 'quantity': qty, 'unit_price': price,
            'amount': amount, 'driver_name': driver, 'driver_code': vh.driver_code(driver, drivers),
            'supplier': _text(rec.get('supplier'))[:150], 'odometer_km': km,
        })
    seen = Counter()
    for p in parsed:
        base = (f"{p['date']:%Y-%m-%d}", p['vehicle_plate'], p['category'], p['description'], f"{p['quantity']:.2f}",
                f"{p['amount']:.2f}")
        p['dedupe_key'] = hashlib.sha1('|'.join(base + (str(seen[base]),)).encode('utf-8')).hexdigest()
        seen[base] += 1
    existing = set(VehiclePartRecord.objects.filter(dedupe_key__in=[p['dedupe_key'] for p in parsed])
                   .values_list('dedupe_key', flat=True))
    new = [VehiclePartRecord(**p, created_by=user, updated_by=user) for p in parsed if p['dedupe_key'] not in existing]
    with transaction.atomic():
        VehiclePartRecord.objects.bulk_create(new)
    return {'created': len(new), 'skipped': len(parsed) - len(new), 'invalid': invalid,
            'future': sum(1 for p in new if p.date > date.today())}
