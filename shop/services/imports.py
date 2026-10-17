"""
Импортын захиалга (Гадаад харилцаа): нэг захиалга = нэг чингэлэг, дотор нь олон нийлүүлэгчийн захиалга.

- Нийлүүлэгч: OpenDataCustomer.CustomerType = 'Бэлтгэн нийлүүлэгч'; бүртгэлгүй шинэ нийлүүлэгчийг нэрээр нь бичнэ.
- Тээврийн компани: 'Гадаад харилцагч' сувгийн бэлтгэн нийлүүлэгч биш харилцагчид; шинээр бичиж болно.
- Нийлүүлэгчийн бараа: OpenDataItem-д нийлүүлэгчийн холбоос байхгүй тул өмнө нь тэр нийлүүлэгчээс оруулж
  байсан бараа (OpenDataLandedCost.VendorId -> ItemId, мөн манай ImportOrderLine)-г эхэнд санал болгоно.
  Шинэ барааг нэрээр нь бичнэ (item_id хоосон).
- Хайрцаг дахь ширхэг: QtyInPackage, 0 бол нэрэн дэх "1х*48ш"-ээс.
- Эрх: засах - 'import_orders' цэс; үнэ/өртөг/төлбөртэй дэлгэрэнгүй үзэх - засах эрхтэй эсвэл FULL_VIEW_POSITIONS;
  бусад (ХТ) Замын мэдээнээс зөвхөн нийлүүлэгч, бараа, тоо хэмжээ, байршил харна.
"""
import re
from itertools import zip_longest
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django.db import connection, transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from shop.models import (
    ImportAttachment, ImportFreightCost, ImportOrderLine, ImportPayment, ImportShipment, ImportSupplierOrder,
    ImportTransitPoint,
)

SUPPLIER_CUSTOMER_TYPE = 'Бэлтгэн нийлүүлэгч'
CARRIER_CHANNEL = 'Гадаад харилцагч'
FULL_VIEW_POSITIONS = {'Захирал', 'Ерөнхий захирал'}
WEIGHT_MEASURES = {'Клограм', 'Килограм', 'кг'}
MEASURES = ['Ширхэг', 'Клограм', 'Литр']
RECENT_ARRIVED_DAYS = 14  # Замын мэдээнд ирснээс хойш хэдэн хоног харуулах
MAX_ATTACHMENT_MB = 20
# Тээвэрлэх хэлбэр: {нэр: дүрс}. Шинээр бичсэн хэлбэрт TRANSPORT_DEFAULT_ICON
TRANSPORT_MODES = {'Далай': '🚢', 'Төмөр зам': '🚂🚃', 'Ачааны машин': '🚚', 'Түүвэр ачаа': '📦'}
TRANSPORT_DEFAULT_ICON = '🚛'
MAX_ATTACHMENTS = 4  # нэг үе шатанд (нийлүүлэгч тус бүрийн, эсвэл чингэлгийн) хавсаргах файлын дээд тоо
# 8 алхам тус бүрийн хавсралтын үе шат (Төлбөр алхамд төлбөрийн баримт)
STEP_FILE_STAGES = ['order', 'confirm', 'pi', 'payment', 'ci', 'loaded', 'transit', 'arrived']

# Гаалийн тооцоо. Гаалийн үнэ = барааны үнэ + ногдох тээвэр (барааны үнийн жингээр), бүгд төгрөгөөр (ханшаар);
# гаалийн татвар = гаалийн үнэ × гаалийн %; НӨАТ = (гаалийн үнэ + гаалийн татвар) × НӨАТ %.
ANIMAL_DUTY_RATE = Decimal(15)   # малын гаралтай бүтээгдэхүүн (бяслаг, сүүн крем, cooking cream, мах г.м.)
DEFAULT_DUTY_RATE = Decimal(10)
DEFAULT_VAT_RATE = Decimal(10)
# Нэрний эхний үг эсвэл тодорхой хэллэгээр (OpenDataItem-д ангилал хоосон). Миграц 0086-д хуулбар бий.
ANIMAL_ORIGIN_RE = re.compile(
    r'^(бяслаг|сүүн|сүү|масло|цөцгийн|аарц|ааруул|тараг|йогурт|мах|гахайн|үхрийн|хонины|тахианы|зайдас|хиам|'
    r'элэгний|түрс|загас|өндөг)(\s|$)|cream cheese|cooking cream|whipping cream|spray cream|mascarpone|сырок',
    re.IGNORECASE)

_PACK_RE = re.compile(r'1\s*[хx]\s*\*\s*(\d+)\s*ш', re.IGNORECASE)
# Кг-ийн бараа: «1х*4ш*3,4кг» (4 × 3.4) эсвэл «1х*12кг», «/1*4кг/», «1х*4,5кг» - хайрцаг дахь кг
_KG_PIECES_RE = re.compile(r'1\s*[хx]?\s*\*\s*(\d+)\s*ш\s*\*\s*(\d+(?:[.,]\d+)?)\s*(?:кг|kg)', re.IGNORECASE)
_KG_RE = re.compile(r'1\s*[хx]?\s*\*\s*(\d+(?:[.,]\d+)?)\s*(?:кг|kg)', re.IGNORECASE)
ZERO = Decimal(0)


# --- Эрх ---------------------------------------------------------------------------------------------------

def can_edit(request):
    from shop.access import request_menu_keys
    return request.user.is_superuser or 'import_orders' in request_menu_keys(request)


def can_view_full(request):
    if can_edit(request):
        return True
    from shop.access import get_user_employee
    employee = get_user_employee(request.user)
    return bool(employee and (employee.positionname or '') in FULL_VIEW_POSITIONS)


# --- Лавлах ------------------------------------------------------------------------------------------------

def suppliers():
    """[(Id, Name)] - бэлтгэн нийлүүлэгчид."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "Name" FROM "OpenDataCustomer" WHERE "CustomerType" = %s AND "Name" <> \'\' '
                       'ORDER BY "Name"', [SUPPLIER_CUSTOMER_TYPE])
        return cursor.fetchall()


def carriers():
    """[(Id, Name)] - 'Гадаад харилцагч' сувгийн бэлтгэн нийлүүлэгч биш харилцагчид (тээвэр, логистик)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "Name" FROM "OpenDataCustomer" WHERE "DistributionChannelName" = %s '
                       'AND COALESCE("CustomerType", \'\') <> %s AND "Name" <> \'\' ORDER BY "Name"',
                       [CARRIER_CHANNEL, SUPPLIER_CUSTOMER_TYPE])
        return cursor.fetchall()


def kg_per_box(name):
    """Нэрнээс хайрцаг дахь кг (олдохгүй бол 0)."""
    match = _KG_PIECES_RE.search(name or '')
    if match:
        return float(Decimal(match.group(1)) * Decimal(match.group(2).replace(',', '.')))
    match = _KG_RE.search(name or '')
    return float(match.group(1).replace(',', '.')) if match else 0


def pack_size(qty_in_package, name):
    """Хайрцаг дахь ширхэг: QtyInPackage > 0 бол түүнийг, үгүй бол нэрэн дэх '1х*48ш'-ээс, олдохгүй бол 0."""
    if qty_in_package and qty_in_package > 0:
        return qty_in_package
    match = _PACK_RE.search(name or '')
    return int(match.group(1)) if match else 0


def transport_icon(mode):
    """Тээвэрлэх хэлбэрийн дүрс (хоосон бол '')."""
    if not mode:
        return ''
    for name, icon in TRANSPORT_MODES.items():
        if name.lower() == mode.strip().lower():
            return icon
    return TRANSPORT_DEFAULT_ICON


def transport_modes():
    """Сонголтын жагсаалт: үндсэн 4 + өмнө нь шинээр бичсэн хэлбэрүүд."""
    used = ImportShipment.objects.exclude(transport_mode='').values_list('transport_mode', flat=True).distinct()
    known = {name.lower() for name in TRANSPORT_MODES}
    return list(TRANSPORT_MODES) + sorted({m for m in used if m.lower() not in known})


def default_duty_rate(item_name):
    """Анхдагч гаалийн татварын хувь: малын гаралтай бол 15, бусад 10."""
    return ANIMAL_DUTY_RATE if ANIMAL_ORIGIN_RE.search((item_name or '').strip()) else DEFAULT_DUTY_RATE


def item_catalog():
    """{нэр: {id, measure, pack, duty}} - бүх бараа (нэр давхцвал идэвхтэйг нь)."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "Name", "MeasureName", "QtyInPackage", "ActiveStatus" FROM "OpenDataItem" '
                       'WHERE "Name" <> \'\' ORDER BY ("ActiveStatus" = \'Y\') DESC, "Name"')
        catalog = {}
        for item_id, name, measure, qty_in_package, _ in cursor.fetchall():
            name = name.strip()
            catalog.setdefault(name, {'id': item_id, 'measure': measure or 'Ширхэг',
                                      'pack': kg_per_box(name) if is_weight(measure) else pack_size(qty_in_package, name),
                                      'duty': float(default_duty_rate(name))})
        return catalog


def supplier_items(supplier_names):
    """{нийлүүлэгчийн нэр: [барааны нэр, ...]} - өмнө нь тэр нийлүүлэгчээс авч байсан бараа (сүүлд авснаар нь)."""
    result = {name: [] for name in supplier_names}
    if not supplier_names:
        return result
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT c."Name", TRIM(l."ItemName"), MAX(l."DocumentDate")
            FROM "OpenDataLandedCost" l JOIN "OpenDataCustomer" c ON c."Id" = l."VendorId"
            WHERE c."Name" = ANY(%s) AND l."ItemName" <> ''
            GROUP BY 1, 2 ORDER BY 1, 3 DESC
            ''', [list(supplier_names)])
        for supplier, item_name, _ in cursor.fetchall():
            result[supplier].append(item_name)
    own = (ImportOrderLine.objects.filter(supplier_order__supplier_name__in=supplier_names)
           .order_by('-id').values_list('supplier_order__supplier_name', 'item_name'))
    for supplier, item_name in own:
        if item_name not in result[supplier]:
            result[supplier].insert(0, item_name)
    return result


# --- Тооцоо ------------------------------------------------------------------------------------------------

def is_weight(measure):
    return (measure or '') in WEIGHT_MEASURES


def compute_line(measure, boxes, per_box, total_qty, unit_price, total_amount, last_edited='price'):
    """Мөрийн утгуудыг уялдуулна. Ширхэг: нийт = хайрцаг × хайрцаг дахь; кг: хайрцаг дахь = нийт / хайрцаг.
    Сүүлд нийт дүнг засварласан бол нэгж үнийг, үгүй бол нийт дүнг бодно."""
    if is_weight(measure):
        per_box = (total_qty / boxes).quantize(Decimal('0.001'), ROUND_HALF_UP) if boxes else ZERO
    else:
        total_qty = boxes * per_box
    if last_edited == 'total':
        unit_price = (total_amount / total_qty).quantize(Decimal('0.0001'), ROUND_HALF_UP) if total_qty else ZERO
    else:
        total_amount = (total_qty * unit_price).quantize(Decimal('0.01'), ROUND_HALF_UP)
    return per_box, total_qty, unit_price, total_amount


def apply_discount(gross, discount, payable):
    """(хөнгөлөлт %, төлөх дүн). Төлөх дүнг гараар өөрчилсөн бол (хувиас бодсоноос зөрвөл) түүгээр хувийг бодно."""
    rate = _rate(discount, ZERO)
    expected = (gross * (100 - rate) / 100).quantize(Decimal('0.01'), ROUND_HALF_UP)
    typed = _dec(payable, default=None)
    if typed is not None and gross > 0 and ZERO <= typed <= gross and abs(typed - expected) > Decimal('0.01'):
        return ((1 - typed / gross) * 100).quantize(Decimal('0.0001'), ROUND_HALF_UP), typed.quantize(Decimal('0.01'))
    return rate, expected


STEP_LABELS = ['Захиалга', 'Баталгаажсан', 'Proforma', 'Төлбөр', 'Commercial invoice', 'Ачигдсан', 'Замд', 'Ирсэн']


def shipment_steps(shipment, today=None):
    """8 алхам [{label, sub, date, done, plan}]. Нийлүүлэгчийн бичиг баримтын алхам бүгд дууссан үед л дууссан.
    Ирээдүйн огноотой дамжих газар нь төлөвлөгөө (plan) - хүрсэнд тооцохгүй.
    supplier_orders (payments-тэй), transit_points prefetch хийгдсэн байх ёстой."""
    today = today or timezone.localdate()
    orders = list(shipment.supplier_orders.all())

    def all_done(field):
        values = [getattr(o, field) for o in orders]
        return max(values) if orders and all(values) else None

    paid_full = bool(orders) and all(o.payment_status == ImportSupplierOrder.PAY_FULL for o in orders)
    paid_dates = [p.paid_date for o in orders for p in o.payments.all()]
    points = list(shipment.transit_points.all())
    reached = [p for p in points if p.date <= today]
    order_dates = [o.order_date for o in orders if o.order_date]
    steps = [
        ('Order number', min(order_dates) if order_dates else None, bool(order_dates)),
        ('Order confirm', all_done('confirm_date'), None),
        ('Нэхэмжлэх', all_done('pi_date'), None),
        ('Бүрэн төлсөн', max(paid_dates) if paid_full and paid_dates else None, paid_full),
        ('Барааны нэхэмжлэх', all_done('ci_date'), None),
        (f'{shipment.load_place}-с' if shipment.load_place else shipment.get_container_size_display(),
         shipment.load_actual, None),
        (' → '.join(p.place for p in points) or 'Дамжих газар',
         reached[-1].date if reached else (points[0].date if points else None), bool(reached)),
        (shipment.arrival_place or 'Монгол', shipment.arrival_actual, None),
    ]
    result = [{'label': label, 'sub': sub, 'date': d, 'done': bool(d) if done is None else done, 'plan': False}
              for label, (sub, d, done) in zip(STEP_LABELS, steps)]
    result[6]['plan'] = bool(points) and not reached
    return result


def current_step(steps):
    """Хамгийн сүүлд дууссан алхмын индекс (-1 = юу ч болоогүй)."""
    idx = -1
    for i, step in enumerate(steps):
        if step['done']:
            idx = i
    return idx


def prefetched_shipments():
    return ImportShipment.objects.prefetch_related(
        Prefetch('supplier_orders', queryset=ImportSupplierOrder.objects.prefetch_related('lines', 'payments')),
        'transit_points', 'freight_costs', 'attachments',
    )


def decorate(shipment, today=None):
    """Жагсаалт/Замын мэдээнд хэрэгтэй тооцоолсон утгуудыг shipment дээр нэмнэ."""
    today = today or timezone.localdate()
    shipment.steps = shipment_steps(shipment, today)
    shipment.transport_icon = transport_icon(shipment.transport_mode)
    # Хавсралтыг үе шатаар нь бүлэглэнэ: shipment.files[stage], order.files[stage]
    by_order = {}
    shipment.files = {stage: [] for stage in ImportAttachment.SHIPMENT_STAGES}
    for attachment in shipment.attachments.all():
        if attachment.supplier_order_id:
            by_order.setdefault(attachment.supplier_order_id, []).append(attachment)
        else:
            shipment.files.setdefault(attachment.stage, []).append(attachment)
    counts = {stage: len(items) for stage, items in shipment.files.items()}
    for order in shipment.supplier_orders.all():
        order.files = {stage: [] for stage in ImportAttachment.SUPPLIER_STAGES}
        for attachment in by_order.get(order.id, []):
            order.files.setdefault(attachment.stage, []).append(attachment)
            counts[attachment.stage] = counts.get(attachment.stage, 0) + 1
        counts['payment'] = counts.get('payment', 0) + sum(1 for p in order.payments.all() if p.receipt)
    for step, stage in zip(shipment.steps, STEP_FILE_STAGES):
        step['files'] = counts.get(stage, 0)
    shipment.step_idx = current_step(shipment.steps)
    shipment.status_label = shipment.steps[shipment.step_idx]['label'] if shipment.step_idx >= 0 else 'Ноорог'
    shipment.arrived = bool(shipment.arrival_actual)
    points = list(shipment.transit_points.all())
    for point in points:
        point.planned = point.date > today  # ирээдүйн огноо - төлөвлөгөө
    reached = shipment.reached_points = [p for p in points if not p.planned]
    # Ачигдсанаас хойш шат хоорондын хоног: ачигдсан → дамжих газар бүр → ирэх газар
    prev_date = shipment.load_actual
    for point in points:
        point.days = (point.date - prev_date).days if prev_date and point.date >= prev_date else None
        prev_date = point.date
    arrival_date = shipment.arrival_actual or shipment.arrival_planned
    shipment.arrival_days = (arrival_date - prev_date).days if arrival_date and prev_date and arrival_date >= prev_date else None
    if shipment.arrival_actual:
        shipment.location = shipment.arrival_place or 'Ирсэн'
        shipment.location_date = shipment.arrival_actual
    elif reached:
        shipment.location, shipment.location_date = reached[-1].place, reached[-1].date
    elif shipment.load_actual:
        shipment.location, shipment.location_date = shipment.load_place or 'Ачигдсан', shipment.load_actual
    else:
        shipment.location, shipment.location_date = 'Ачигдаагүй', shipment.load_planned
    if shipment.arrival_planned:
        end = shipment.arrival_actual or today
        shipment.delay_days = max((end - shipment.arrival_planned).days, 0)
    else:
        shipment.delay_days = 0
    statuses = {o.payment_status for o in shipment.supplier_orders.all()}
    if not statuses:
        shipment.payment_label, shipment.payment_tone = '—', ''
    elif statuses == {ImportSupplierOrder.PAY_FULL}:
        shipment.payment_label, shipment.payment_tone = 'Бүрэн', 'ok'
    elif statuses == {ImportSupplierOrder.PAY_NONE}:
        shipment.payment_label, shipment.payment_tone = 'Төлөөгүй', 'bad'
    else:
        shipment.payment_label, shipment.payment_tone = 'Хэсэгчлэн', 'warn'
    for order in shipment.supplier_orders.all():
        lines = list(order.lines.all())
        order.goods_total = sum((l.total_amount for l in lines), ZERO)
        order.gross_total = sum((l.gross_amount for l in lines), ZERO)  # хөнгөлөлтөөс өмнө
        order.box_total = sum((l.box_qty for l in lines), ZERO)
        order.paid_total = sum((p.amount for p in order.payments.all()), ZERO)
        order.pi_balance = (order.pi_amount - order.paid_total) if order.pi_amount is not None else None
    orders_all = list(shipment.supplier_orders.all())
    shipment.line_count = sum(len(o.lines.all()) for o in orders_all)
    shipment.box_total = sum((o.box_total for o in orders_all), ZERO)
    # Шилжүүлсэн төлбөрийн нийлбэр валютаар: [(валют, дүн)]
    paid = {}
    for order in shipment.supplier_orders.all():
        if order.paid_total:
            paid[order.currency] = paid.get(order.currency, ZERO) + order.paid_total
    shipment.paid_totals = sorted(paid.items())
    freight = list(shipment.freight_costs.all())
    shipment.freight_total = sum((f.amount for f in freight), ZERO)
    shipment.freight_currency = freight[0].currency if freight else ''
    shipment.has_initial_freight = any(f.kind == ImportFreightCost.KIND_INITIAL for f in freight)
    # Үндсэн (анхны тохиролцоо) ба нэмэгдэл (өөрчлөлтүүдийн нийлбэр)-ийг тусад нь
    shipment.freight_initial = sum((f.amount for f in freight if f.kind == ImportFreightCost.KIND_INITIAL), ZERO)
    shipment.freight_adjust = sum((f.amount for f in freight if f.kind != ImportFreightCost.KIND_INITIAL), ZERO)
    compute_taxes(shipment)
    return shipment


def bank_rates(currencies, on_date):
    """{валют: (ханш, огноо)} - OpenDataCurrencyRate-ээс on_date буюу түүнээс өмнөх хамгийн сүүлийн ханш."""
    currencies = [c for c in currencies if c != 'MNT']
    if not currencies:
        return {}
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT DISTINCT ON ("CurrencyId") "CurrencyId", "Rate", "Date" FROM "OpenDataCurrencyRate" '
            'WHERE "CurrencyId" = ANY(%s) AND "Date" <= %s AND "Rate" > 0 ORDER BY "CurrencyId", "Date" DESC',
            [currencies, on_date])
        return {currency: (Decimal(str(rate)), date) for currency, rate, date in cursor.fetchall()}


def customs_rates(shipment, currencies=()):
    """{валют: Decimal ханш}; MNT = 1. Гараар оруулсан ханш давуу, үгүй бол Монголбанкны ханш (OpenDataCurrencyRate)
    ирсэн огноогоор, ирээгүй бол өнөөдрөөр. shipment.auto_rates = {валют: (ханш, огноо)} - автоматаар авсан нь."""
    rates = {'MNT': Decimal(1)}
    for currency, value in (shipment.customs_rates or {}).items():
        rate = _dec(str(value), default=None)
        if rate and rate > 0:
            rates[currency] = rate
    on_date = shipment.arrival_actual or timezone.localdate()
    shipment.rate_date = on_date
    shipment.auto_rates = bank_rates(currencies, on_date)
    for currency, (rate, _) in shipment.auto_rates.items():
        rates.setdefault(currency, rate)
    return rates


def compute_taxes(shipment):
    """Бараа бүрийн гаалийн үнэ, гаалийн татвар, НӨАТ-ыг (төгрөгөөр) line дээр, нийлбэрийг order/shipment дээр нэмнэ.
    Ханш оруулаагүй валютын барааг тухайн валютаараа тээвэргүй бодно; тээврийг зөвхөн бүх ханш бүрэн үед хуваарилна."""
    orders = list(shipment.supplier_orders.all())
    pairs = [(order, line) for order in orders for line in order.lines.all()]
    needed = sorted({o.currency for o in orders} | ({shipment.freight_currency} if shipment.freight_total else set()))
    rates = customs_rates(shipment, needed)
    # Загварт: [(валют, гараар оруулсан утга, автомат ханш, огноо)]
    manual = shipment.customs_rates or {}
    shipment.rate_rows = [(c, manual.get(c, ''), *shipment.auto_rates.get(c, (None, None))) for c in needed if c != 'MNT']
    shipment.tax_currencies = [c for c in needed if c != 'MNT']
    shipment.tax_missing = [c for c in needed if c not in rates]
    goods_mnt = {line.id: line.total_amount * rates[order.currency] for order, line in pairs if order.currency in rates}
    all_rated = len(goods_mnt) == len(pairs)

    freight_mnt = ZERO
    shipment.tax_freight_note = ''
    if shipment.customs_include_freight and shipment.freight_total:
        if shipment.freight_currency in rates and all_rated:
            freight_mnt = shipment.freight_total * rates[shipment.freight_currency]
        else:
            shipment.tax_freight_note = 'Ханш дутуу тул тээврийн зардлыг гаалийн үнэд оруулаагүй'
    shipment.tax_freight_mnt = freight_mnt
    goods_total_mnt = sum(goods_mnt.values(), ZERO)

    cent = Decimal('0.01')
    totals = {'goods': ZERO, 'freight': ZERO, 'customs_value': ZERO, 'duty': ZERO, 'vat': ZERO}
    for order in orders:
        order.tax_duty = order.tax_vat = ZERO
        order.tax_currency = 'MNT' if order.currency in rates else order.currency
    for order, line in pairs:
        if line.id in goods_mnt:
            base = goods_mnt[line.id]
            share = freight_mnt * base / goods_total_mnt if freight_mnt and goods_total_mnt else ZERO
            line.tax_currency = 'MNT'
        else:
            base, share, line.tax_currency = line.total_amount, ZERO, order.currency
        line.customs_value = (base + share).quantize(cent, ROUND_HALF_UP)
        line.duty_amount = (line.customs_value * line.duty_rate / 100).quantize(cent, ROUND_HALF_UP)
        line.vat_amount = ((line.customs_value + line.duty_amount) * line.vat_rate / 100).quantize(cent, ROUND_HALF_UP)
        order.tax_duty += line.duty_amount
        order.tax_vat += line.vat_amount
        if line.tax_currency == 'MNT':
            totals['goods'] += base
            totals['freight'] += share
            totals['customs_value'] += line.customs_value
            totals['duty'] += line.duty_amount
            totals['vat'] += line.vat_amount
    for order in orders:
        order.tax_total = order.tax_duty + order.tax_vat
    totals = {k: v.quantize(cent, ROUND_HALF_UP) for k, v in totals.items()}
    totals['total'] = totals['duty'] + totals['vat']
    shipment.tax = totals


def next_code(today=None):
    year = (today or timezone.localdate()).year
    prefix = f'IMP-{year}-'
    last = (ImportShipment.objects.filter(code__startswith=prefix).values_list('code', flat=True))
    numbers = [int(c[len(prefix):]) for c in last if c[len(prefix):].isdigit()]
    return f'{prefix}{(max(numbers) if numbers else 0) + 1:02d}'


# --- Хадгалах ----------------------------------------------------------------------------------------------

def _dec(value, default=ZERO):
    value = (value or '').replace(',', '').replace(' ', '').strip()
    if not value:
        return default
    try:
        return Decimal(value)
    except InvalidOperation:
        return default


def _date(value):
    try:
        return datetime.strptime((value or '').strip(), '%Y-%m-%d').date()
    except ValueError:
        return None


def _rate(value, default):
    """Татварын хувь 0-100; хоосон/буруу бол анхдагч."""
    rate = _dec(value, default=None)
    return rate if rate is not None and 0 <= rate <= 100 else default


def _text(post, key, limit):
    return (post.get(key) or '').strip()[:limit]


def _attach(shipment, order, stage, uploads, user, warnings):
    if not uploads:
        return
    room = MAX_ATTACHMENTS - ImportAttachment.objects.filter(shipment=shipment, supplier_order=order, stage=stage).count()
    for upload in uploads:
        if room <= 0:
            warnings.append(f'{upload.name}: нэг хэсэгт {MAX_ATTACHMENTS}-өөс олон файл хавсаргах боломжгүй тул хавсаргаагүй.')
            continue
        if upload.size > MAX_ATTACHMENT_MB * 1024 * 1024:
            warnings.append(f'{upload.name} файл {MAX_ATTACHMENT_MB}MB-аас том тул хавсаргаагүй.')
            continue
        ImportAttachment.objects.create(shipment=shipment, supplier_order=order, stage=stage, file=upload,
                                        original_name=upload.name[:255], created_by=user)
        room -= 1


def delete_with_files(shipment=None, order=None):
    """Чингэлэг эсвэл нийлүүлэгчийн захиалгыг хавсралт, төлбөрийн баримтын файлтай нь устгана."""
    target = order or shipment
    attachments = (order.attachments.all() if order else shipment.attachments.all())
    payments = ImportPayment.objects.filter(**({'supplier_order': order} if order else
                                               {'supplier_order__shipment': shipment}))
    for stored in [a.file for a in attachments] + [p.receipt for p in payments if p.receipt]:
        stored.delete(save=False)
    target.delete()


def _lookup_id(options, name):
    """[(Id, Name)]-оос нэрээр нь код олно (шинээр бичсэн бол '')."""
    for option_id, option_name in options:
        if (option_name or '').strip() == name:
            return option_id
    return ''


@transaction.atomic
def save_shipment(shipment, post, files, user):
    """Детал хуудасны нэг маягтыг бүхэлд нь хадгална. Анхааруулгын жагсаалт буцаана."""
    warnings = []
    today = timezone.localdate()

    shipment.container_size = post.get('container_size') or shipment.container_size
    shipment.container_no = _text(post, 'container_no', 30)
    shipment.seal_no = _text(post, 'seal_no', 30)
    shipment.carrier_name = _text(post, 'carrier_name', 255)
    shipment.carrier_id = _lookup_id(carriers(), shipment.carrier_name) if shipment.carrier_name else ''
    shipment.transport_mode = _text(post, 'transport_mode', 100)
    for field in ('load_planned', 'load_actual', 'arrival_planned', 'arrival_actual'):
        setattr(shipment, field, _date(post.get(field)))
    shipment.load_place = _text(post, 'load_place', 200)
    rates = {}
    for currency, _ in ImportSupplierOrder.CURRENCY_CHOICES:
        rate = _dec(post.get(f'rate_{currency}'), default=None)
        if rate is not None and rate > 0 and currency != 'MNT':
            rates[currency] = str(rate)
    shipment.customs_rates = rates
    shipment.customs_include_freight = post.get('customs_include_freight') == '1'
    shipment.arrival_place = _text(post, 'arrival_place', 200)
    shipment.note = _text(post, 'note', 500)
    shipment.updated_by = user
    shipment.save()

    delete_supplier = post.get('delete_supplier')
    supplier_options = None
    catalog = None
    for order in shipment.supplier_orders.all():
        if str(order.id) == delete_supplier:
            delete_with_files(order=order)
            continue
        p = f'so{order.id}_'
        name = _text(post, p + 'supplier_name', 255)
        if name and name != order.supplier_name:
            supplier_options = supplier_options if supplier_options is not None else suppliers()
            order.supplier_name, order.supplier_id = name, _lookup_id(supplier_options, name)
        order.currency = post.get(p + 'currency') or order.currency
        for field, limit in (('order_no', 50), ('confirm_no', 50), ('pi_no', 50), ('ci_no', 50)):
            setattr(order, field, _text(post, p + field, limit))
        for field in ('order_date', 'confirm_date', 'pi_date', 'ci_date'):
            setattr(order, field, _date(post.get(p + field)))
        for field in ('pi_amount', 'ci_amount'):
            setattr(order, field, _dec(post.get(p + field), default=None))
        if post.get(p + 'payment_status') in dict(ImportSupplierOrder.PAY_CHOICES):
            order.payment_status = post.get(p + 'payment_status')
        order.save()

        # Мөрүүдийг бүхэлд нь солино
        order.lines.all().delete()
        # zip_longest: хуучин (шинэ баганагүй) хуудаснаас илгээсэн ч мөр алдагдахгүй
        rows = zip_longest(*(post.getlist(p + 'line_' + key) for key in
                             ('name', 'measure', 'boxes', 'per', 'qty', 'price', 'total', 'last', 'duty', 'vat',
                              'disc', 'net')), fillvalue='')
        for position, (item_name, measure, boxes, per, qty, price, total, last, duty, vat, disc, net) in enumerate(rows):
            item_name = item_name.strip()[:255]
            if not item_name:
                continue
            catalog = catalog if catalog is not None else item_catalog()
            known = catalog.get(item_name)
            measure = (known['measure'] if known else measure) or 'Ширхэг'
            per_box, total_qty, unit_price, gross = compute_line(
                measure, _dec(boxes), _dec(per), _dec(qty), _dec(price), _dec(total), last)
            discount, payable = apply_discount(gross, disc, net)
            ImportOrderLine.objects.create(
                supplier_order=order, item_id=known['id'] if known else '', item_name=item_name, measure=measure,
                box_qty=_dec(boxes), qty_per_box=per_box, total_qty=total_qty, unit_price=unit_price,
                gross_amount=gross, discount_rate=discount, total_amount=payable, position=position,
                duty_rate=_rate(duty, default_duty_rate(item_name)), vat_rate=_rate(vat, DEFAULT_VAT_RATE))

        for stage in ImportAttachment.SUPPLIER_STAGES:
            _attach(shipment, order, stage, files.getlist(f'{p}att_{stage}'), user, warnings)

        pay_amount = _dec(post.get(p + 'pay_amount'), default=None)
        pay_file = files.get(p + 'pay_file')
        if pay_amount is not None or pay_file:
            ImportPayment.objects.create(
                supplier_order=order, paid_date=_date(post.get(p + 'pay_date')) or today,
                amount=pay_amount or ZERO, receipt=pay_file or '', note=_text(post, p + 'pay_note', 300),
                created_by=user)

    for stage in ImportAttachment.SHIPMENT_STAGES:
        _attach(shipment, None, stage, files.getlist(f'att_{stage}'), user, warnings)
    if post.get('delete_attachment'):
        for attachment in shipment.attachments.filter(id=post['delete_attachment']):
            attachment.file.delete(save=False)
            attachment.delete()
    if post.get('delete_payment'):
        for payment in ImportPayment.objects.filter(id=post['delete_payment'], supplier_order__shipment=shipment):
            if payment.receipt:
                payment.receipt.delete(save=False)
            payment.delete()
    if post.get('delete_transit'):
        shipment.transit_points.filter(id=post['delete_transit']).delete()
    if post.get('delete_freight'):
        shipment.freight_costs.filter(id=post['delete_freight']).delete()

    new_supplier = _text(post, 'new_supplier_name', 255)
    if new_supplier:
        ImportSupplierOrder.objects.create(
            shipment=shipment, supplier_name=new_supplier,
            supplier_id=_lookup_id(supplier_options or suppliers(), new_supplier),
            currency=post.get('new_supplier_currency') or 'EUR', order_date=today,
            position=shipment.supplier_orders.count())

    place = _text(post, 'new_transit_place', 200)
    if place:
        ImportTransitPoint.objects.create(shipment=shipment, place=place,
                                          date=_date(post.get('new_transit_date')) or today,
                                          note=_text(post, 'new_transit_note', 300), created_by=user)

    freight_amount = _dec(post.get('new_freight_amount'), default=None)
    if freight_amount is not None:
        note = _text(post, 'new_freight_note', 300)
        initial = shipment.freight_costs.filter(kind=ImportFreightCost.KIND_INITIAL).first()
        if initial is None:
            ImportFreightCost.objects.create(
                shipment=shipment, kind=ImportFreightCost.KIND_INITIAL, amount=freight_amount,
                currency=post.get('new_freight_currency') or 'USD',
                date=_date(post.get('new_freight_date')) or today, note=note, created_by=user)
        elif not note:
            warnings.append('Тээврийн зардлын өөрчлөлтөд тайлбар бичээгүй тул нэмээгүй. Тайлбартай нь дахин оруулна уу.')
        else:
            ImportFreightCost.objects.create(
                shipment=shipment, kind=ImportFreightCost.KIND_ADJUST, amount=freight_amount,
                currency=initial.currency, date=_date(post.get('new_freight_date')) or today, note=note,
                created_by=user)
    return warnings


def tracking_timeline(shipment, full, today=None):
    """Замын мэдээний нэг шугам: [{label, sub, date, state, days, days_plan, here}].
    full бол бичиг баримт, төлбөрийн шатнаас эхэлнэ, үгүй бол ачигдсанаас. state: done / plan (ирээдүйн огноо) / todo.
    days - өмнөх огноотой шатнаас хэдэн хоног; одоо байгаа шатнаас дараагийнх руу өнөөдөр хүртэлх хоног."""
    today = today or timezone.localdate()
    nodes = []
    if full:
        for step in shipment.steps[:5]:
            nodes.append({'label': step['label'], 'sub': '',
                          'date': step['date'], 'state': 'done' if step['done'] else 'todo'})
    load_idx = len(nodes)
    nodes.append({'label': 'Ачигдсан', 'sub': f'{shipment.load_place}-с' if shipment.load_place else '',
                  'date': shipment.load_actual or shipment.load_planned,
                  'state': 'done' if shipment.load_actual else ('plan' if shipment.load_planned else 'todo')})
    for point in shipment.transit_points.all():
        nodes.append({'label': point.place, 'sub': point.note, 'date': point.date,
                      'state': 'plan' if point.date > today else 'done'})
    nodes.append({'label': shipment.arrival_place or 'Монгол', 'sub': '',
                  'date': shipment.arrival_actual or shipment.arrival_planned,
                  'state': 'done' if shipment.arrival_actual else ('plan' if shipment.arrival_planned else 'todo')})

    here = max((i for i, n in enumerate(nodes) if n['state'] == 'done'), default=-1)
    prev = None
    for i, node in enumerate(nodes):
        node['here'] = i == here and not shipment.arrival_actual
        node['days'] = None
        if i < load_idx:
            continue  # хоногийн зөрүүг зөвхөн ачигдсанаас хойш (ачигдсан → дамжих газрууд → ирэх газар)
        node['days'] = (node['date'] - prev['date']).days if node['date'] and prev else None
        if node['days'] is not None and node['days'] < 0:
            node['days'] = None  # огноо өмнөхөөсөө эрт (буруу оруулсан) - харуулахгүй
        node['days_plan'] = node['state'] != 'done'
        if node['date'] and node['state'] != 'todo':
            prev = node
    # Одоо байгаа шатнаас хойш хэд хоног болж байна (дараагийнх нь огноогүй бол)
    if load_idx <= here < len(nodes) - 1 and not shipment.arrival_actual and nodes[here]['date'] and not nodes[here + 1]['date']:
        nodes[here + 1]['days'] = (today - nodes[here]['date']).days
        nodes[here + 1]['days_now'] = True
    shipment.total_days = ((shipment.arrival_actual or today) - shipment.load_actual).days if shipment.load_actual else None
    return nodes


def tracking_sort_key(shipment, today):
    """Замын мэдээний дараалал: ирээгүй нь эхэнд, түрүүлж ирэх нь дээрээ; ирсэн нь доор, сүүлд ирсэн нь дээрээ.
    Ирэх огноо хоосон бол дараагийн мэдэгдэж буй огноо: сүүлийн дамжих газар (төлөвлөсөн ч), ачигдсан, ачих огноо."""
    if shipment.arrival_actual:
        return (1, -shipment.arrival_actual.toordinal())
    points = list(shipment.transit_points.all())
    eta = (shipment.arrival_planned or (points[-1].date if points else None)
           or shipment.load_actual or shipment.load_planned or today + timedelta(days=3650))
    return (0, eta.toordinal())


def tracking_shipments(today=None, full=False):
    """Замын мэдээ: ирээгүй бүх чингэлэг + сүүлийн RECENT_ARRIVED_DAYS хоногт ирсэн."""
    today = today or timezone.localdate()
    qs = prefetched_shipments().filter(
        Q(arrival_actual__isnull=True) | Q(arrival_actual__gte=today - timedelta(days=RECENT_ARRIVED_DAYS)))
    shipments = [decorate(s, today) for s in qs]
    for shipment in shipments:
        shipment.timeline = tracking_timeline(shipment, full, today)
    shipments.sort(key=lambda s: tracking_sort_key(s, today))
    return shipments
