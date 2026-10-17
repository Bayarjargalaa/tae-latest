"""
Тээврийн хэрэгсэл -> Шатахуун: Petrovis картын гүйлгээний жагсаалт ("report" Excel) ба сарын үлдэгдэл
("Balance Report" Excel)-ийг импортлож, карт бүрийн эхний үлдэгдэл + гүйлгээ = эцсийн үлдэгдэл эсэхийг тулгана.

- Давхардал: Excel-ийн анхны утгуудаас (карт, огноо, төрөл, дүн, мерчант, харьцсан данс) тооцсон түлхүүрээр
  шалгана - шатахууны төрөл/нэгж үнийг гараас нөхсөн ч дахин импортлоход давхардахгүй. Нэг файлд яг ижил мөр
  хэд байвал дарааллын дугаараар ялгана.
- Худалдан авалтын төрөл/нэгж үнэ хоосон бол тухайн картын өмнөх худалдан авалтынхыг санал болгоно,
  хэмжээг (литр) дүн / нэгж үнээр тооцно.
- Жолооч - карт эзэмшигчийн нэртэй таарах ажилтныг санал болгоно ("Ишдорж Энхбуянт" -> "Энхбуянт.И").
- Машин - манай тээврийн хэрэгсэл (OpenDataAsset) бол км заалт заавал; өмнөх заалтаас хойш явсан км, өмнө
  хийсэн шатахуунаар 100 км-д зарцуулсан литрийг тооцно.
"""
import hashlib
import re
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

from django.db import transaction
from django.utils import timezone

from shop.models import FuelCardBalance, FuelTransaction

PURCHASE = FuelTransaction.PURCHASE
PERSONAL_NOTE = 'Хувийн машин'
TRANSFER_OUT = 'Шилжүүлгийн зарлага'

TXN_HEADERS = {
    'card': 'Карт', 'holder': 'Эзэмшигч', 'merchant': 'Мерчант', 'address': 'Хаяг', 'txn_at': 'Огноо',
    'txn_type': 'Гүйлгээний төрөл', 'description': 'Тайлбар', 'fuel_type': ('төрөл', 'шатахууны төрөл'), 'unit_price': 'нэгж үнэ',
    'quantity': 'хэмжээ', 'amount': 'Үнийн дүн', 'counter': 'Харьцсан данс',
}
BALANCE_HEADERS = {
    'card': 'Карт', 'holder': 'Эзэмшигч', 'opening': 'Эхний үлдэгдэл', 'income': 'Орлого',
    'transfer_out': 'Шилжүүлгийн зарлага', 'purchase': 'Худалдан авалт', 'deduction': 'Хасалт',
    'closing': 'Эцсийн үлдэгдэл',
}
CENT = Decimal('0.01')


class FuelImportError(ValueError):
    pass


# --- Excel унших ---

def _norm_header(value):
    return re.sub(r'\s+', ' ', str(value or '')).strip().lower()


def _text(value):
    if value is None:
        return ''
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return re.sub(r'\s+', ' ', str(value)).strip()


def _decimal(value):
    if value is None or value == '':
        return None
    try:
        return Decimal(str(value).replace(',', '').replace(' ', '')).quantize(CENT)
    except (InvalidOperation, ValueError):
        return None


def _datetime(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        dt = datetime(value.year, value.month, value.day)
    else:
        text = _text(value)
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y.%m.%d %H:%M:%S', '%Y/%m/%d %H:%M:%S', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(text, fmt)
                break
            except ValueError:
                continue
        else:
            return None
    return timezone.make_aware(dt.replace(microsecond=0)) if timezone.is_naive(dt) else dt


def _locate(header_row, spec):
    """{field: column index} - толгойн нэрийг том/жижиг үсэг, зайнаас үл хамааран тааруулна."""
    normalized = [_norm_header(h) for h in header_row]
    cols = {}
    for field, labels in spec.items():
        for label in (labels if isinstance(labels, tuple) else (labels,)):
            if _norm_header(label) in normalized:
                cols[field] = normalized.index(_norm_header(label))
                break
    return cols


def read_workbook(file):
    """Excel-ийг уншиж ('transactions' | 'balance', [dict, ...]) буцаана - толгойгоор нь төрлийг тодорхойлно."""
    import openpyxl

    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
    except Exception as exc:  # noqa: BLE001 - эвдэрсэн/өөр төрлийн файл
        raise FuelImportError(f'Excel файл уншигдсангүй: {exc}') from exc
    rows = list(wb.active.iter_rows(values_only=True))
    wb.close()
    for i, row in enumerate(rows[:10]):
        names = {_norm_header(c) for c in row}
        if _norm_header('Гүйлгээний төрөл') in names:
            kind, spec = 'transactions', TXN_HEADERS
        elif _norm_header('Эхний үлдэгдэл') in names:
            kind, spec = 'balance', BALANCE_HEADERS
        else:
            continue
        cols = _locate(row, spec)
        required = ['card', 'txn_at', 'txn_type', 'amount'] if kind == 'transactions' else ['card', 'opening', 'closing']
        missing = [str(spec[f]) for f in required if f not in cols]
        if missing:
            raise FuelImportError(f'Багана олдсонгүй: {", ".join(missing)}')
        data = []
        for raw in rows[i + 1:]:
            rec = {f: (raw[c] if c < len(raw) else None) for f, c in cols.items()}
            if _text(rec.get('card')):
                data.append(rec)
        return kind, data
    raise FuelImportError('Гүйлгээний жагсаалт ("Гүйлгээний төрөл" баганатай) эсвэл үлдэгдлийн тайлан '
                          '("Эхний үлдэгдэл" баганатай) биш байна.')


# --- Импорт ---

def dedupe_key(card, txn_at, txn_type, amount, merchant, counter, seq):
    local = timezone.localtime(txn_at)
    raw = '|'.join([card, f'{local:%Y-%m-%d %H:%M:%S}', txn_type, f'{amount:.2f}', merchant, counter, str(seq)])
    return hashlib.sha1(raw.encode('utf-8')).hexdigest()


def _split_type(txn_type, description):
    """Хуучин бүртгэлд "Худалдан авалт/" , "BO Орлогын гүйлгээ/Хөнгөлөлт 2024.02.29" гэж нийлүүлсэн байдаг."""
    if '/' in txn_type:
        txn_type, rest = (x.strip() for x in txn_type.split('/', 1))
        description = description or rest
    return txn_type, description


def import_transactions(records, user=None, source='import'):
    """Гүйлгээг огнооны дарааллаар нэмнэ; өмнө орсон (түлхүүр нь ижил) мөрийг алгасна.
    Буцаах: {'created', 'skipped', 'invalid', 'months': [date, ...], 'objects': [шинээр нэмсэн]}"""
    parsed, invalid = [], 0
    for rec in records:
        txn_at = _datetime(rec.get('txn_at'))
        amount = _decimal(rec.get('amount'))
        txn_type, description = _split_type(_text(rec.get('txn_type')), _text(rec.get('description')))
        if txn_at is None or amount is None or not txn_type:
            invalid += 1
            continue
        parsed.append({
            'card_no': _text(rec.get('card'))[:30], 'holder': _text(rec.get('holder'))[:150],
            'merchant': _text(rec.get('merchant'))[:150], 'address': _text(rec.get('address'))[:255],
            'txn_at': txn_at, 'txn_type': txn_type[:60], 'description': description[:255],
            'amount': amount, 'counter_account': _text(rec.get('counter'))[:30],
            'raw_fuel_type': _text(rec.get('fuel_type'))[:100], 'raw_unit_price': _decimal(rec.get('unit_price')),
            'raw_quantity': _decimal(rec.get('quantity')),
        })
    parsed.sort(key=lambda p: (p['txn_at'], p['card_no']))

    seen = Counter()
    for p in parsed:
        base = (p['card_no'], p['txn_at'], p['txn_type'], p['amount'], p['merchant'], p['counter_account'])
        p['dedupe_key'] = dedupe_key(*base, seen[base])
        seen[base] += 1

    existing = set(FuelTransaction.objects.filter(dedupe_key__in=[p['dedupe_key'] for p in parsed])
                   .values_list('dedupe_key', flat=True))
    new = []
    for p in parsed:
        if p['dedupe_key'] in existing:
            continue
        existing.add(p['dedupe_key'])
        qty = p['raw_quantity']
        if qty is None and p['raw_unit_price'] and p['amount']:
            qty = (abs(p['amount']) / p['raw_unit_price']).quantize(CENT)
        new.append(FuelTransaction(**p, fuel_type=p['raw_fuel_type'], unit_price=p['raw_unit_price'], quantity=qty,
                                   source=source, created_by=user, updated_by=user))
    with transaction.atomic():
        FuelTransaction.objects.bulk_create(new)
    months = sorted({timezone.localtime(p['txn_at']).date().replace(day=1) for p in parsed})
    return {'created': len(new), 'skipped': len(parsed) - len(new), 'invalid': invalid, 'months': months, 'objects': new}


def import_balances(records, month, user=None):
    """Сарын үлдэгдлийг карт бүрээр нэмнэ/шинэчилнэ. Буцаах: {'created', 'updated'}"""
    created = updated = 0
    with transaction.atomic():
        for rec in records:
            card = _text(rec.get('card'))[:30]
            values = {f: _decimal(rec.get(f)) or Decimal('0.00')
                      for f in ('opening', 'income', 'transfer_out', 'purchase', 'deduction', 'closing')}
            _, is_new = FuelCardBalance.objects.update_or_create(
                month=month, card_no=card,
                defaults={**values, 'holder': _text(rec.get('holder'))[:150], 'updated_by': user})
            created += is_new
            updated += not is_new
    return {'created': created, 'updated': updated}


# --- Сар, шүүлт ---

def parse_month(value):
    try:
        return datetime.strptime(value or '', '%Y-%m').date()
    except ValueError:
        return None


def month_range(month):
    """Тухайн сарын [эхлэх, дараагийн сарын эхлэх) - орон нутгийн цагаар."""
    nxt = date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    tz = timezone.get_current_timezone()
    return (timezone.make_aware(datetime(month.year, month.month, 1), tz),
            timezone.make_aware(datetime(nxt.year, nxt.month, 1), tz))


def available_months():
    from django.db.models.functions import TruncMonth
    months = set(FuelCardBalance.objects.values_list('month', flat=True).distinct())
    months |= {timezone.localtime(m).date() if isinstance(m, datetime) else m
               for m in FuelTransaction.objects.annotate(m=TruncMonth('txn_at')).values_list('m', flat=True).distinct()}
    return sorted(months, reverse=True)


# --- Санал: шатахууны төрөл/үнэ, жолооч ---

def type_price_history():
    """{төрөл: [[огноо, нэгж үнэ], ...]} - огноогоор өсөх; шинэ төрөл сонгоход тухайн өдрийн үнийг санал болгоно."""
    history = defaultdict(dict)
    for fuel_type, price, txn_at in (FuelTransaction.objects.filter(txn_type=PURCHASE, unit_price__isnull=False)
                                     .exclude(fuel_type='').order_by('txn_at')
                                     .values_list('fuel_type', 'unit_price', 'txn_at')):
        history[fuel_type][timezone.localtime(txn_at).date().isoformat()] = float(price)
    return {t: sorted(d.items()) for t, d in sorted(history.items())}


def _previous_purchase_lookup(cards):
    """{карт: [(огноо, төрөл, үнэ), ...]} - төрөл, үнэ хоёулаа бөглөгдсөн худалдан авалтууд."""
    lookup = defaultdict(list)
    for card, txn_at, fuel_type, price in (FuelTransaction.objects
                                           .filter(card_no__in=cards, txn_type=PURCHASE, unit_price__isnull=False)
                                           .exclude(fuel_type='').order_by('txn_at', 'id')
                                           .values_list('card_no', 'txn_at', 'fuel_type', 'unit_price')):
        lookup[card].append((txn_at, fuel_type, price))
    return lookup


def _suggest_fuel(lookup, txn):
    prev = [p for p in lookup.get(txn.card_no, []) if p[0] < txn.txn_at]
    if prev:
        return prev[-1][1], prev[-1][2]
    nxt = lookup.get(txn.card_no, [])  # өмнөх байхгүй бол дараагийнхыг
    return (nxt[0][1], nxt[0][2]) if nxt else ('', None)


def _name_parts(name):
    """'Энхбуянт.И' -> ('энхбуянт', 'и'); 'Сарангэрэл.Э /Алтжин/' -> ('сарангэрэл', 'э')."""
    name = re.sub(r'/[^/]*/?', ' ', name or '').strip().lower()
    m = re.match(r'^([^\s.]+)[\s.]*([^\s.]*)', name)
    return (m.group(1), m.group(2)) if m else ('', '')


def match_employee(holder, employees):
    """Карт эзэмшигчийн нэртэй хамгийн ойр ажилтан ({'code', 'name'}) эсвэл None.
    Эзэмшигч 'Овог Нэр' хэлбэртэй, ажилтан 'Нэр.О' хэлбэртэй байдаг."""
    tokens = [t for t in re.split(r'[\s.]+', (holder or '').lower()) if t]
    best, best_score = None, 0.0
    for emp in employees:
        base, initial = _name_parts(emp['name'])
        if not base:
            continue
        for i, token in enumerate(tokens):
            score = 2.0 if token == base else SequenceMatcher(None, token, base).ratio()
            if score < 0.8:
                continue
            others = tokens[:i] + tokens[i + 1:]
            if initial and others:
                score += 1.0 if any(o.startswith(initial) for o in others) else -0.5
            if score > best_score:
                best, best_score = emp, score
    return best


def driver_options():
    from shop.services.vehicles import driver_options as options
    return options()


def vehicle_options():
    from shop.services.vehicles import vehicle_options as options
    return options()


# --- Км, 100 км-ийн зарцуулалт ---

def plate_metrics(plates):
    """{txn_id: {'prev_km', 'distance', 'per100'}} - машин бүрийн худалдан авалтыг огнооны дарааллаар.
    Км заалттай хоёр цэнэглэлтийн хооронд явсан км, өмнөх заалттай цэнэглэлтээс хойш хийсэн нийт литрээр
    100 км-ийн зарцуулалтыг тооцно (заалтгүй цэнэглэлтийн литр дараагийн заалтад нэмэгдэнэ)."""
    metrics = {}
    by_plate = defaultdict(list)
    for t in (FuelTransaction.objects.filter(vehicle_plate__in=[p for p in plates if p], txn_type=PURCHASE)
              .order_by('txn_at', 'id').only('id', 'vehicle_plate', 'odometer_km', 'quantity')):
        by_plate[t.vehicle_plate].append(t)
    for txns in by_plate.values():
        last_km, liters = None, Decimal('0')
        for t in txns:
            m = {'prev_km': last_km, 'distance': None, 'per100': None, 'liters': None}
            if t.odometer_km is not None:
                if last_km is not None:
                    m['distance'] = t.odometer_km - last_km
                    m['liters'] = liters
                    if m['distance'] > 0 and liters > 0:
                        m['per100'] = float((liters * 100 / m['distance']).quantize(CENT))
                last_km, liters = t.odometer_km, t.quantity or Decimal('0')
            elif last_km is not None:
                liters += t.quantity or Decimal('0')
            metrics[t.id] = m
    return metrics


# --- Сарын хуудас ---

def _category(t):
    if t.amount > 0:
        return 'income'
    if t.txn_type == TRANSFER_OUT:
        return 'transfer_out'
    if t.txn_type == PURCHASE:
        return 'purchase'
    return 'deduction'


def openings_at(start):
    """{карт: үлдэгдэл start агшинд}. Карт бүрийн хамгийн ойрын үлдэгдлийн тайлангаас тооцно:
    - start-аас өмнө эхэлсэн сарын тайлан байвал хамгийн сүүлийнх нь: эхний үлдэгдэл + тэр сарын эхнээс start хүртэлх
      гүйлгээ (тухайн сарын өөрийн тайланг биш өмнөхийг авдаг тул тулгалт өмнөх сартай уялдана; хуучин зөрүү хуримтлагдахгүй);
    - өмнө нь тайлангүй бол start-ын сарын эсвэл дараагийн хамгийн эхний тайлангаас буцааж: эхний үлдэгдэл - start-аас
      тэр сарын эхэн хүртэлх гүйлгээ. Бэлэн (касс) ба тайлангүй карт ороогүй."""
    from django.db.models import Sum

    start_date = timezone.localtime(start).date()
    before, after = {}, {}
    for b in FuelCardBalance.objects.order_by('month'):
        if month_range(b.month)[0] < start:
            before[b.card_no] = b  # хамгийн сүүлийн өмнөх
        else:
            after.setdefault(b.card_no, b)  # хамгийн эхний дараах (start-ын сарынх орно)
    openings = {}
    for card in set(before) | set(after):
        if card in before and not (card in after and after[card].month == start_date):
            anchor = before[card]
            moved = (FuelTransaction.objects.filter(card_no=card, txn_at__gte=month_range(anchor.month)[0], txn_at__lt=start)
                     .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
            openings[card] = anchor.opening + moved
        else:
            anchor = after[card]
            moved = (FuelTransaction.objects.filter(card_no=card, txn_at__gte=start, txn_at__lt=month_range(anchor.month)[0])
                     .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
            openings[card] = anchor.opening - moved
    return openings


def card_movements(d_from, d_to, txns=None):
    """Карт бүрээр: эхний үлдэгдэл (тооцоолсон), орлого, шилжүүлэг, худалдан авалт, хасалт, эцсийн үлдэгдэл.
    Хугацаа яг нэг сар бөгөөд тэр сарын үлдэгдлийн тайлан орсон бол түүнтэй тулгана (report_closing, diff, ok)."""
    from shop.services.vehicles import aware_range, single_month

    start, end = aware_range(d_from, d_to)
    if txns is None:
        txns = list(FuelTransaction.objects.filter(txn_at__gte=start, txn_at__lt=end).order_by('txn_at', 'id'))
    txns = [t for t in txns if not t.is_cash]
    month = single_month(d_from, d_to)
    balances = {b.card_no: b for b in FuelCardBalance.objects.filter(month=month)} if month else {}
    # Сар хоорондын уялдаа: энэ сарын тайлангийн эхний үлдэгдэл = өмнөх сарын тайлангийн эцсийн үлдэгдэл
    prev_closing = {}
    if month:
        prev = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
        prev_closing = dict(FuelCardBalance.objects.filter(month=prev).values_list('card_no', 'closing'))
    openings = openings_at(start)
    sums = defaultdict(lambda: defaultdict(Decimal))
    holders = {}
    for t in txns:
        sums[t.card_no][_category(t)] += t.amount
        holders.setdefault(t.card_no, t.holder)

    rows = []
    for card in sorted(set(openings) | set(sums)):
        b, s = balances.get(card), sums[card]
        total = sum(s.values(), Decimal('0'))
        opening = openings.get(card)
        row = {'card': card, 'holder': (b.holder if b else '') or holders.get(card, ''), 'balance': b,
               'income': s['income'], 'transfer_out': s['transfer_out'], 'purchase': s['purchase'],
               'deduction': s['deduction'], 'total': total, 'opening': opening,
               'closing': opening + total if opening is not None else None,
               'report_closing': b.closing if b else None}
        row['diff'] = (b.closing - row['closing']) if b and row['closing'] is not None else None
        row['opening_diff'] = (b.opening - prev_closing[card]) if b and card in prev_closing else None
        row['ok'] = (row['diff'] == 0 and not row['opening_diff']) if row['diff'] is not None else None
        row['status'] = {True: 'Таарсан', False: 'Зөрүүтэй'}.get(
            row['ok'], 'Тооцоолсон' if opening is not None else 'Эхний үлдэгдэлгүй')
        rows.append(row)

    def col(key):
        return sum((r[key] for r in rows if r[key] is not None), Decimal('0'))
    totals = {k: col(k) for k in ('income', 'transfer_out', 'purchase', 'deduction', 'total', 'opening', 'closing',
                                  'report_closing', 'diff')}
    totals['card'] = 'Нийт'
    return {
        'rows': rows, 'totals': totals, 'month': month, 'has_balance': bool(balances), 'has_opening': bool(openings),
        'mismatch': sum(1 for r in rows if r['ok'] is False),
        'no_opening': sum(1 for r in rows if r['opening'] is None),
    }


def guess_balance_month(records):
    """Үлдэгдлийн файлд огноо байхгүй тул: гүйлгээтэй сар бүрээр эхний + гүйлгээ = эцсийн эсэхийг шалгаж,
    хамгийн олон карт таарсан сарыг буцаана (таарсан карт байхгүй бол None)."""
    from django.db.models import Sum
    from django.db.models.functions import TruncMonth

    cards = {_text(r.get('card'))[:30]: (_decimal(r.get('opening')) or Decimal('0'),
                                         _decimal(r.get('closing')) or Decimal('0')) for r in records}
    moves = defaultdict(dict)
    for m, card, total in (FuelTransaction.objects.filter(card_no__in=cards)
                           .annotate(m=TruncMonth('txn_at')).values_list('m', 'card_no')
                           .annotate(s=Sum('amount')).values_list('m', 'card_no', 's')):
        moves[timezone.localtime(m).date() if isinstance(m, datetime) else m][card] = total
    best, best_score = None, 0
    for month, by_card in sorted(moves.items()):
        score = sum(1 for card, (opening, closing) in cards.items()
                    if by_card.get(card) is not None and opening + by_card[card] == closing)
        if score > best_score:
            best, best_score = month, score
    return best


# --- Шатахууны хуудас: шүүлт ---

STATUS_CHOICES = [
    ('', 'Бүгд'),
    ('need_fuel', 'Төрөл/үнэ дутуу'),
    ('need_plate', 'Машин сонгоогүй'),
    ('need_km', 'Км заалт дутуу (манай машин)'),
    ('need_driver', 'Жолоочгүй'),
    ('done', 'Бүрэн бөглөсөн'),
]


def fuel_filters(params):
    from shop.services import vehicles as vh

    latest = FuelTransaction.objects.order_by('-txn_at').values_list('txn_at', flat=True).first()
    base = timezone.localtime(latest).date().replace(day=1) if latest else timezone.localdate().replace(day=1)
    d_from, d_to = vh.period(params, base, vh.month_end(base))
    return {
        'date_from': d_from, 'date_to': d_to,
        'card': vh.multi(params, 'card'), 'fuel_type': vh.multi(params, 'fuel_type'),
        'plate': vh.multi(params, 'plate'), 'driver': vh.multi(params, 'driver'),
        'station': vh.multi(params, 'station'), 'q': params.get('q', '').strip(),
        'show_all': params.get('show') == 'all',
        'status': [v for v in vh.multi(params, 'status') if v in dict(STATUS_CHOICES)],
    }


def _is_personal(t):
    return not t.vehicle_plate and PERSONAL_NOTE in t.note


def _plate_ok(t, wanted, ours):
    """Сонгосон машинуудын аль нэгэнд таарвал (манай бүх машин, хувийн, машингүй гэсэн бүлэг ч байж болно)."""
    for w in wanted:
        if w == '__ours' and t.vehicle_plate in ours:
            return True
        if w == '__personal' and _is_personal(t):
            return True
        if w == '__none' and not t.vehicle_plate and not _is_personal(t):
            return True
        if t.vehicle_plate and t.vehicle_plate == w:
            return True
    return False


def _status_ok(row, status):
    t = row['t']
    if status == 'need_fuel':
        return row['needs_fuel']
    if status == 'need_plate':
        return bool(t.amount) and not t.vehicle_plate and not _is_personal(t)
    if status == 'need_km':
        return row['needs_km']
    if status == 'need_driver':
        return bool(t.amount) and not t.driver_name
    if status == 'done':
        return not (row['needs_fuel'] or row['needs_km'] or not t.driver_name
                    or not (t.vehicle_plate or _is_personal(t)))
    return True


def _match(row, f, ours):
    """Шүүлт бүрийн дотор сонгосон утгуудын аль нэг (OR), шүүлтүүд хоорондоо бүгд (AND)."""
    t = row['t']
    if f['card'] and t.card_no not in f['card']:
        return False
    if not t.is_purchase:  # шилжүүлэг/орлого - зөвхөн карт, хайлтаар шүүгдэнэ
        if not f['show_all'] or any(f[k] for k in ('fuel_type', 'plate', 'driver', 'station', 'status')):
            return False
        return not f['q'] or f['q'].lower() in f'{t.holder} {t.description} {t.counter_account} {t.txn_type}'.lower()
    if f['fuel_type'] and (row['fuel_type'] or '') not in f['fuel_type']:
        return False
    if f['plate'] and not _plate_ok(t, f['plate'], ours):
        return False
    if f['driver'] and t.driver_name not in f['driver']:
        return False
    if f['station'] and not any(st.lower() in t.merchant.lower() for st in f['station']):
        return False
    if f['status'] and not any(_status_ok(row, st) for st in f['status']):
        return False
    if f['q']:
        hay = f'{t.card_no} {t.holder} {t.merchant} {t.vehicle_plate} {t.driver_name} {t.note} {t.fuel_type}'.lower()
        if f['q'].lower() not in hay:
            return False
    return True


def fuel_data(f):
    """Шатахууны хуудас: шүүсэн мөрүүд (санал, км-ийн тооцоо, картын үлдэгдэлтэй), нэгтгэл, тулгалт."""
    from shop.services.vehicles import aware_range

    start, end = aware_range(f['date_from'], f['date_to'])
    period_txns = list(FuelTransaction.objects.filter(txn_at__gte=start, txn_at__lt=end).order_by('txn_at', 'id'))
    recon = card_movements(f['date_from'], f['date_to'], period_txns)

    # Картын үлдэгдэл гүйлгээ бүрийн дараа (эхний үлдэгдэл тооцогдсон бол)
    running = {r['card']: r['opening'] for r in recon['rows'] if r['opening'] is not None}
    after = {}
    for t in period_txns:
        if t.card_no in running:
            running[t.card_no] += t.amount
            after[t.id] = running[t.card_no]

    candidates = [t for t in period_txns if f['show_all'] or t.is_purchase]
    lookup = _previous_purchase_lookup({t.card_no for t in candidates if t.is_purchase})
    employees = driver_options()
    metrics = plate_metrics({t.vehicle_plate for t in candidates})
    ours = {v['plate'] for v in vehicle_options() if v['ours']}

    rows = []
    for t in candidates:
        row = {'t': t, 'balance_after': after.get(t.id), 'm': metrics.get(t.id, {}), 'fuel_type': '',
               'needs_fuel': False, 'needs_km': False}
        if t.is_purchase:
            fuel_type, price = t.fuel_type, t.unit_price
            row['fuel_suggested'] = False
            if t.amount and (not fuel_type or price is None):
                s_type, s_price = _suggest_fuel(lookup, t)
                row['fuel_suggested'] = bool(s_type or s_price)
                fuel_type, price = fuel_type or s_type, price if price is not None else s_price
            qty = t.quantity
            if qty is None and price:
                qty = (abs(t.amount) / price).quantize(CENT)
            driver = {'code': t.driver_code, 'name': t.driver_name}
            row['driver_suggested'] = False
            if not t.driver_name:
                emp = match_employee(t.holder, employees)
                if emp:
                    driver, row['driver_suggested'] = emp, True
            row.update(fuel_type=fuel_type, unit_price=price, quantity=qty, driver=driver,
                       personal=_is_personal(t), note=t.note.replace(PERSONAL_NOTE, '').strip(' ,'),
                       needs_fuel=bool(t.amount) and (not t.fuel_type or t.unit_price is None),
                       needs_km=t.vehicle_plate in ours and t.odometer_km is None)
        if _match(row, f, ours):
            rows.append(row)

    purchases = [r for r in rows if r['t'].is_purchase]
    by_type = defaultdict(lambda: {'amount': Decimal('0'), 'liters': Decimal('0'), 'count': 0})
    for r in purchases:
        if not r['t'].amount:
            continue
        d = by_type[r.get('fuel_type') or 'Тодорхойгүй']
        d['amount'] += -r['t'].amount
        d['liters'] += r.get('quantity') or 0
        d['count'] += 1
    all_purchases = [t for t in period_txns if t.is_purchase and t.amount]
    return {
        'rows': rows,
        'recon': recon,
        'cards': [(r['card'], r['holder']) for r in recon['rows']]
        + ([(FuelTransaction.CASH_CARD, 'кассаас')] if any(t.is_cash for t in period_txns) else []),
        'by_type': sorted(({'type': k, **v} for k, v in by_type.items()), key=lambda d: -d['amount']),
        'summary': {
            'count': len(purchases),
            'purchase_amount': -sum((r['t'].amount for r in purchases), Decimal('0')),
            'liters': sum((r.get('quantity') or 0 for r in purchases), Decimal('0')),
            # Хугацааны бүх худалдан авалтаар (шүүлтээс үл хамааран) - бөглөх ажлын үлдэгдэл
            'needs_fuel': sum(1 for t in all_purchases if not t.fuel_type or t.unit_price is None),
            'needs_plate': sum(1 for t in all_purchases if not t.vehicle_plate and not _is_personal(t)),
            'needs_km': sum(1 for t in all_purchases if t.vehicle_plate in ours and t.odometer_km is None),
        },
    }


def export_report(f):
    """Шүүсэн гүйлгээний жагсаалт - тайлангийн бүтцээр (хэвлэх, Excel)."""
    from shop.services import vehicles as vh

    data = fuel_data(f)
    rows = []
    for r in data['rows']:
        t, m = r['t'], r['m']
        rows.append({
            'date': t.txn_at, 'card': t.card_no, 'holder': t.holder, 'station': t.merchant, 'txn_type': t.txn_type,
            'amount': t.amount, 'fuel_type': t.fuel_type, 'price': t.unit_price, 'liters': t.quantity,
            'plate': t.vehicle_plate or (PERSONAL_NOTE if r.get('personal') else ''),
            'driver': t.driver_name, 'km': t.odometer_km, 'distance': m.get('distance'), 'per100': m.get('per100'),
            'balance': r['balance_after'], 'note': r.get('note') or (t.description if not t.is_purchase else ''),
        })
    cols = [{'key': 'date', 'label': 'Огноо', 'fmt': 'datetime'}, {'key': 'card', 'label': 'Карт'},
            {'key': 'holder', 'label': 'Эзэмшигч'}, {'key': 'station', 'label': 'Мерчант'}]
    if f['show_all']:
        cols.append({'key': 'txn_type', 'label': 'Гүйлгээ'})
    cols += [{'key': 'amount', 'label': 'Үнийн дүн', 'fmt': 'money'}, {'key': 'fuel_type', 'label': 'Шатахуун'},
             {'key': 'price', 'label': 'Нэгж үнэ', 'fmt': 'money'}, {'key': 'liters', 'label': 'Литр', 'fmt': 'dec'},
             {'key': 'plate', 'label': 'Машин'}, {'key': 'driver', 'label': 'Жолооч'},
             {'key': 'km', 'label': 'Км заалт', 'fmt': 'int'}, {'key': 'distance', 'label': 'Явсан км', 'fmt': 'int'},
             {'key': 'per100', 'label': '100км-д', 'fmt': 'dec'}]
    if f['show_all']:
        cols.append({'key': 'balance', 'label': 'Үлдэгдэл', 'fmt': 'money'})
    cols.append({'key': 'note', 'label': 'Тайлбар'})
    meta = [('Хугацаа', vh.period_label(f['date_from'], f['date_to']))] + fuel_filter_meta(f)
    return {
        'title': 'Шатахууны гүйлгээ', 'meta': meta,
        'tables': [{'columns': cols, 'rows': rows,
                    'totals': {'date': 'Нийт', 'amount': sum((r['amount'] for r in rows), Decimal('0')),
                               'liters': sum((r['liters'] or 0 for r in rows), Decimal('0'))}}],
    }


def fuel_filter_meta(f):
    from shop.services.vehicles import plate_filter_label

    meta = []
    for key, label in (('card', 'Карт'), ('fuel_type', 'Шатахуун'), ('driver', 'Жолооч'), ('station', 'Мерчант')):
        if f[key]:
            meta.append((label, ', '.join(f[key])))
    if f['plate']:
        meta.append(('Машин', ', '.join(plate_filter_label(p) for p in f['plate'])))
    if f['status']:
        meta.append(('Төлөв', ', '.join(dict(STATUS_CHOICES)[st] for st in f['status'])))
    if f['q']:
        meta.append(('Хайлт', f['q']))
    return meta


# --- Бэлэн (кассаас төлсөн) шатахуун ---

def save_cash(data, user, txn=None):
    """Бэлэн шатахууныг гараас нэмэх/засах. data: date, time, amount, station, fuel_type, unit_price, quantity,
    vehicle_plate, personal, driver_name, odometer_km, note. Буцаах: (txn, алдаа)."""
    import uuid
    from datetime import datetime as dt

    try:
        day = dt.strptime(_text(data.get('date')), '%Y-%m-%d')
    except ValueError:
        return None, 'Огноог оруулна уу.'
    try:
        hm = dt.strptime(_text(data.get('time')) or '12:00', '%H:%M')
    except ValueError:
        return None, 'Цаг буруу байна.'
    amount = _decimal(data.get('amount'))
    if not amount or amount <= 0:
        return None, 'Төлсөн дүнг оруулна уу.'
    if txn is not None and not txn.is_cash:
        return None, 'Зөвхөн бэлэн шатахууныг энд засна.'
    txn = txn or FuelTransaction(card_no=FuelTransaction.CASH_CARD, holder='Бэлэн (касс)', txn_type=PURCHASE,
                                 source='manual', dedupe_key=f'manual:{uuid.uuid4().hex}', created_by=user)
    txn.txn_at = timezone.make_aware(day.replace(hour=hm.hour, minute=hm.minute))
    txn.amount = -amount
    txn.merchant = _text(data.get('station'))[:150]
    txn.description = 'Бэлэн'
    payload = {k: data.get(k, '') for k in ('fuel_type', 'unit_price', 'quantity', 'vehicle_plate', 'driver_name',
                                           'odometer_km', 'note')}
    payload['personal'] = data.get('personal') in (True, 'on', '1', 'true')
    error = save_row(txn, payload, user)
    return (None, error) if error else (txn, None)


# --- Мөр хадгалах ---

def save_row(txn, data, user=None):
    """Гараас оруулсан утгыг хадгална. Буцаах: алдааны мессеж эсвэл None."""
    from shop.services.delivery_trips import normalize_plate

    if not txn.is_purchase:
        return 'Зөвхөн худалдан авалтын гүйлгээг засна.'
    fuel_type = _text(data.get('fuel_type'))[:100]
    price = _decimal(data.get('unit_price'))
    qty = _decimal(data.get('quantity'))
    if price is not None and price <= 0:
        return 'Нэгж үнэ 0-ээс их байна.'
    if qty is None and price and txn.amount:
        qty = (abs(txn.amount) / price).quantize(CENT)
    plate = normalize_plate(data.get('vehicle_plate')) if _text(data.get('vehicle_plate')) else ''
    km = data.get('odometer_km')
    try:
        km = int(Decimal(str(km).replace(',', '').replace(' ', ''))) if _text(km) else None
    except (InvalidOperation, ValueError):
        return 'Км заалт буруу байна.'
    if km is not None and not 0 <= km < 10_000_000:
        return 'Км заалт буруу байна.'
    from shop.services.vehicles import driver_code, our_plates
    if plate and km is None and plate in our_plates():
        return f'{plate} манай машин тул км заалтыг оруулна уу.'
    driver = _text(data.get('driver_name'))[:100]

    txn.fuel_type, txn.unit_price, txn.quantity = fuel_type, price, qty
    txn.vehicle_plate, txn.odometer_km = plate, km
    txn.driver_name = driver
    txn.driver_code = driver_code(driver)
    note = _text(data.get('note'))[:240] if 'note' in data else txn.note.replace(PERSONAL_NOTE, '').strip(' ,')
    if data.get('personal') and not plate:
        note = f'{PERSONAL_NOTE}, {note}' if note else PERSONAL_NOTE
    txn.note = note[:255]
    txn.updated_by = user
    txn.save()
    return None
