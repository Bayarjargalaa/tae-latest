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
    ImportAttachment, ImportFreightCost, ImportOrderLine, ImportPayment, ImportPaymentReceipt, ImportShipment,
    ImportSupplierOrder, ImportTransitPoint,
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
MAX_RECEIPTS = 6  # нэг шилжүүлгийн баримтын дээд тоо (SWIFT, хуулга г.м.)
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

# Хайрцаг дахь ширхэг нэрэнд: «1х*48ш», «/1*8ш*530гр/», «-1хайр*4ш», «1х*12 », «-1/12»
_PACK_RE = re.compile(r'(?<![\d.,])1\s*(?:[хx]|хайр)?\s*(?:\*\s*(\d+)\s*(?:ш|(?=[\s/)]|$))|/\s*(\d+)(?=\s|$))',
                      re.IGNORECASE)
# Нэрний савлагааны хэсэг (эхнээс нь төгсгөл хүртэл): «1х*42ш*10 уут RUF Герман», « /1*4кг/ ...», « -1/12»
_PACK_TAIL_RE = re.compile(r'\s*(?:[-/(]\s*)?(?<![\d.,])1\s*(?:[хx]|хайр)?\s*[*/]\s*\d.*$', re.IGNORECASE)
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
    return int(match.group(1) or match.group(2)) if match else 0


def short_item_name(name):
    """Картанд харуулах богино нэр: савлагаа, брэнд, улсыг хасна.
    «Ванилин-сахар 1х*42ш*10 уут RUF Герман» -> «Ванилин-сахар»."""
    full = (name or '').strip()
    short = _PACK_TAIL_RE.sub('', full)
    if short == full:
        country = country_from_text(full)
        if country and full.endswith(country):
            short = full[:-len(country)]
    # Хаагдаагүй « /Knusper kekse» хэсэг (нэрний дунд «Олив/тос» хэвээр)
    open_at = short.rfind(' /')
    if open_at >= 0 and '/' not in short[open_at + 2:]:
        short = short[:open_at]
    return short.strip(' -/,') or full


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


def last_duty_rates():
    """{барааны нэр: гаалийн татварын хувь} - тухайн барааны хамгийн сүүлд хадгалсан захиалгын мөрөөс.
    Мөрүүд хадгалах бүрт дахин үүсдэг тул id хамгийн их = хамгийн сүүлд хадгалсан."""
    return dict(ImportOrderLine.objects.order_by('item_name', '-id').distinct('item_name')
                .values_list('item_name', 'duty_rate'))


def item_catalog():
    """{нэр: {id, measure, pack, duty}} - бүх бараа (нэр давхцвал идэвхтэйг нь).
    duty: сүүлд хадгалсан гаалийн хувь, өмнө захиалж байгаагүй бол default_duty_rate."""
    last_duty = last_duty_rates()
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "Name", "MeasureName", "QtyInPackage", "ActiveStatus" FROM "OpenDataItem" '
                       'WHERE "Name" <> \'\' ORDER BY ("ActiveStatus" = \'Y\') DESC, "Name"')
        catalog = {}
        for item_id, name, measure, qty_in_package, _ in cursor.fetchall():
            name = name.strip()
            catalog.setdefault(name, {'id': item_id, 'measure': measure or 'Ширхэг',
                                      'pack': kg_per_box(name) if is_weight(measure) else pack_size(qty_in_package, name),
                                      'duty': float(last_duty.get(name, default_duty_rate(name)))})
        return catalog


# Барааны нэр / нийлүүлэгчийн нэрэнд бичигддэг улсууд (жиш: "... Ammerland Герман", "HMM Trade /Унгар/")
COUNTRIES = ['Герман', 'Англи', 'Голланд', 'Польш', 'Орос', 'Хятад', 'Латви', 'Литви', 'Эстони', 'Испани',
             'Итали', 'Франц', 'Бельги', 'Австри', 'Швейцари', 'Дани', 'Унгар', 'Чех', 'Турк', 'Грек', 'Солонгос',
             'Япон', 'Тайланд', 'Вьетнам', 'Энэтхэг', 'Америк', 'Канад', 'Бразил', 'Аргентин', 'Австрали',
             'Шинэ Зеланд', 'Ирланд', 'Португали', 'Казахстан', 'Беларусь', 'Украин', 'Монгол']
_COUNTRY_RE = re.compile(r'(?<![А-Яа-яӨөҮүЁё])(' + '|'.join(COUNTRIES) + r')(?![А-Яа-яӨөҮүЁё])')


def country_from_text(*texts):
    """Текстүүдээс (эхнийхээс нь эхлэн) олдсон улсын нэр, эсвэл ''. Нэрэнд хэд байвал хамгийн сүүлийнх."""
    for text in texts:
        found = _COUNTRY_RE.findall(text or '')
        if found:
            return found[-1]
    return ''


def product_defaults_bulk(items):
    """{item_id: product_defaults(item)} - жагсаалтад нэг дор (импортын мөр, татан авалтыг 2 query-ээр)."""
    ids = [item.id for item in items]
    lines = {}
    for line in (ImportOrderLine.objects.filter(item_id__in=ids).select_related('supplier_order__shipment')
                 .order_by('-supplier_order__shipment__created_at', '-id')):
        lines.setdefault(line.item_id, line)
    vendors = {}
    if ids:
        with connection.cursor() as cursor:
            cursor.execute('SELECT DISTINCT ON (l."ItemId") l."ItemId", COALESCE(c."Name", l."VendorName") '
                           'FROM "OpenDataLandedCost" l LEFT JOIN "OpenDataCustomer" c ON c."Id" = l."VendorId" '
                           'WHERE l."ItemId" = ANY(%s) ORDER BY l."ItemId", l."DocumentDate" DESC', [ids])
            vendors = {item_id: (vendor or '').strip() for item_id, vendor in cursor.fetchall()}
    return {item.id: _defaults(item, lines.get(item.id), vendors.get(item.id, '')) for item in items}


def product_defaults(item):
    """Бүтээгдэхүүний нэмэлт мэдээллийн анхдагч утгууд (OpenDataItem item):
    {'qty_per_box', 'box_measure', 'supplier', 'country', 'source'} - source: утга бүр хаанаас ирсэн.
    Хайрцаг дахь тоо, нийлүүлэгч: хамгийн сүүлийн импортын захиалгын мөр (ImportOrderLine), байхгүй бол
    MSSQL (QtyInPackage / нэрэн дэх 1х*24ш, сүүлийн татан авалтын VendorId). Улс: барааны нэр, дараа нь нийлүүлэгчийн нэр."""
    return product_defaults_bulk([item])[item.id]


def _defaults(item, line, vendor):
    measure = item.measurename or 'Ширхэг'
    result = {'qty_per_box': None, 'box_measure': measure, 'supplier': '', 'country': '', 'source': {}}
    if line:
        shipment = line.supplier_order.shipment
        if line.qty_per_box:
            result['qty_per_box'] = line.qty_per_box.normalize()
            result['box_measure'] = line.measure or measure
            result['source']['qty_per_box'] = f'импортын захиалга {shipment.code}'
        result['supplier'] = line.supplier_order.supplier_name
        result['source']['supplier'] = f'импортын захиалга {shipment.code}'
    if result['qty_per_box'] is None:
        pack = kg_per_box(item.name) if is_weight(measure) else pack_size(item.qtyinpackage, item.name)
        if pack:
            result['qty_per_box'] = Decimal(str(pack)).normalize()
            result['source']['qty_per_box'] = 'ERP (MSSQL)'
    if not result['supplier'] and vendor:
        result['supplier'] = vendor
        result['source']['supplier'] = 'ERP (сүүлийн татан авалт)'
    result['country'] = country_from_text(item.name, result['supplier'])
    if result['country']:
        result['source']['country'] = 'барааны нэр' if country_from_text(item.name) else 'нийлүүлэгчийн нэр'
    return result

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
    # Ирсэн бол өмнөх бүх алхам дууссан (огноо нь бүртгэгдээгүй ч - жиш: ERP татан авалтаас оруулсан)
    if shipment.arrival_actual:
        for step in result:
            step['done'], step['plan'] = True, False
    return result


def current_step(steps):
    """Хамгийн сүүлд дууссан алхмын индекс (-1 = юу ч болоогүй)."""
    idx = -1
    for i, step in enumerate(steps):
        if step['done']:
            idx = i
    return idx


def sync_line_items():
    """Захиалгын мөрийн барааны нэрийг ERP-тэй (OpenDataItem) нийцүүлнэ - мөр нэрийг хадгалсан үеийнхээр хадгалдаг тул
    ERP-д нэр өөрчлөхөд энд хуучин нэр үлдэнэ. Кодтой мөрийн нэрийг одоогийн нэрээр, кодгүй мөрд нэр яг таарвал кодыг нь."""
    with connection.cursor() as cursor:
        cursor.execute('''
            UPDATE shop_import_order_line l SET item_name = LEFT(TRIM(i."Name"), 255)
            FROM "OpenDataItem" i
            WHERE l.item_id <> '' AND i."Id" = l.item_id AND TRIM(i."Name") <> '' AND l.item_name <> TRIM(i."Name")''')
        cursor.execute('''
            UPDATE shop_import_order_line l SET item_id = i.id
            FROM (SELECT DISTINCT ON (TRIM("Name")) "Id" AS id, TRIM("Name") AS name FROM "OpenDataItem"
                  WHERE TRIM("Name") <> '' ORDER BY TRIM("Name"), ("ActiveStatus" = 'Y') DESC) i
            WHERE l.item_id = '' AND l.item_name = i.name''')


def prefetched_shipments():
    sync_line_items()
    return ImportShipment.objects.prefetch_related(
        Prefetch('supplier_orders', queryset=ImportSupplierOrder.objects.prefetch_related('lines', 'payments__receipts')),
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
    shipment.has_items = False
    for order in shipment.supplier_orders.all():
        # Жагсаалтад дэлгэрэнгүйг нээлгүй ямар бараа байгааг харуулах богино нэрс
        order.item_names = [short_item_name(line.item_name) for line in order.lines.all()]
        shipment.has_items = shipment.has_items or bool(order.item_names)
        order.files = {stage: [] for stage in ImportAttachment.SUPPLIER_STAGES}
        for attachment in by_order.get(order.id, []):
            order.files.setdefault(attachment.stage, []).append(attachment)
            counts[attachment.stage] = counts.get(attachment.stage, 0) + 1
        counts['payment'] = counts.get('payment', 0) + sum(bool(p.receipt) + len(p.receipts.all()) for p in order.payments.all())
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
        # Гадаад дахь нэмэлт зардал: мөрүүдийн төлөх дүнгийн жингээр; нийт төлбөр = төлөх дүн + ногдох хэсэг
        order.extra_total = order.foreign_extra or ZERO
        shares = distribute(order.extra_total, [l.total_amount for l in lines]) if order.extra_total else [ZERO] * len(lines)
        for line, share in zip(lines, shares):
            line.extra_share, line.pay_total = share, line.total_amount + share
        order.pay_all_total = order.goods_total + (order.extra_total if lines else ZERO)
        order.gross_total = sum((l.gross_amount for l in lines), ZERO)  # хөнгөлөлтөөс өмнө
        order.box_total = sum((l.box_qty for l in lines), ZERO)
        order.paid_total = sum((p.amount for p in order.payments.all()), ZERO)
        order.pi_balance = (order.pi_amount - order.paid_total) if order.pi_amount is not None else None
        # Төлөх дүн (CI > PI > барааны дүн) ба шилжүүлгүүдийн нийлбэрээр биелэлт
        order.pay_target, order.pay_target_label = payment_target(order, order.goods_total)
        order.pay_remaining = order.pay_target - order.paid_total if order.pay_target else None
        order.pay_over = -order.pay_remaining if order.pay_remaining is not None and order.pay_remaining < Decimal('-0.009') else None
        order.pay_pct = min(float(order.paid_total / order.pay_target * 100), 100) if order.pay_target else None
        running = ZERO
        for payment in order.payments.all():
            running += payment.amount
            payment.running = running
            payment.share = float(payment.amount / order.pay_target * 100) if order.pay_target else None
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


def distribute(total, weights):
    """total-ийг weights-ийн жингээр 0.01 нарийвчлалтай хуваана; тойруулгын үлдэгдлийг хамгийн том жинтэйд нэмнэ."""
    cent = Decimal('0.01')
    weight_sum = sum(weights, ZERO)
    if not weights:
        return []
    if not weight_sum:
        weights, weight_sum = [Decimal(1)] * len(weights), Decimal(len(weights))
    parts = [(total * w / weight_sum).quantize(cent, ROUND_HALF_UP) for w in weights]
    biggest = max(range(len(weights)), key=lambda i: weights[i])
    parts[biggest] += total - sum(parts, ZERO)
    return parts


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
    # Суурь = нийт төлбөр (төлөх дүн + гадаад дахь нэмэлт зардлын хуваарь)
    paid = {line.id: getattr(line, 'pay_total', line.total_amount) for _, line in pairs}
    goods_mnt = {line.id: paid[line.id] * rates[order.currency] for order, line in pairs if order.currency in rates}
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
            base, share, line.tax_currency = paid[line.id], ZERO, order.currency
        line.customs_value = (base + share).quantize(cent, ROUND_HALF_UP)
        line.goods_mnt, line.freight_mnt = base.quantize(cent, ROUND_HALF_UP), share.quantize(cent, ROUND_HALF_UP)  # хэвлэхэд
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
    # Ирсэн захиалгад гараар оруулсан бодит нийт дүнг (₮) мөрүүдэд үнийн дүнгийн (гаалийн үнийн) жингээр хуваарилна
    shipment.tax_calc = {'duty': totals['duty'], 'vat': totals['vat']}
    if shipment.arrival_actual:
        mnt_lines = [(order, line) for order, line in pairs if line.tax_currency == 'MNT']
        for attr, actual in (('duty', shipment.customs_duty_actual), ('vat', shipment.customs_vat_actual)):
            if actual is None or not mnt_lines:
                continue
            amounts = [line.customs_value for _, line in mnt_lines]
            for (order, line), amount in zip(mnt_lines, distribute(actual, amounts)):
                delta = amount - getattr(line, attr + '_amount')
                setattr(line, attr + '_amount', amount)
                setattr(order, 'tax_' + attr, getattr(order, 'tax_' + attr) + delta)
            totals[attr] = actual
    # Бусад зардал (ирсэн): нийлбэрийг ₮-өөр бодогдсон мөрүүдэд гаалийн үнийн жингээр
    shipment.other_rows = [(c.get('name', ''), _dec(str(c.get('amount', '')), default=ZERO)) for c in (shipment.other_costs or [])]
    shipment.other_total = sum((amount for _, amount in shipment.other_rows), ZERO) if shipment.arrival_actual else ZERO
    for _, line in pairs:
        line.other_cost = ZERO
    mnt_pairs = [(order, line) for order, line in pairs if line.tax_currency == 'MNT']
    if shipment.other_total and mnt_pairs:
        for (_, line), amount in zip(mnt_pairs, distribute(shipment.other_total, [l.customs_value for _, l in mnt_pairs])):
            line.other_cost = amount
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


def payment_target(order, goods_total=None):
    """Нийлүүлэгчид төлөх дүн ба эх сурвалж: Commercial invoice > Proforma > барааны дүн. Мэдэгдэхгүй бол (None, '')."""
    if order.ci_amount:
        return order.ci_amount, 'Commercial invoice'
    if order.pi_amount:
        return order.pi_amount, 'Proforma'
    if goods_total:
        return goods_total, 'Барааны дүн'
    return None, ''


def _payment_status(order):
    """Шилжүүлгийн нийлбэрээр төлөв: төлөх дүнд хүрсэн бол бүрэн, хүрээгүй бол урьдчилгаа."""
    # prefetch-ийн кэш хадгалахаас өмнөх тул шинээр уншина
    goods = sum(ImportOrderLine.objects.filter(supplier_order=order).values_list('total_amount', flat=True), ZERO)
    target, _ = payment_target(order, goods)
    paid = sum(ImportPayment.objects.filter(supplier_order=order).values_list('amount', flat=True), ZERO)
    if not paid:
        return ImportSupplierOrder.PAY_NONE
    return ImportSupplierOrder.PAY_FULL if target and paid >= target - Decimal('0.01') else ImportSupplierOrder.PAY_PARTIAL


def _add_receipts(payment, uploads, user, warnings):
    if not uploads:
        return
    room = MAX_RECEIPTS - bool(payment.receipt) - payment.receipts.count()
    for upload in uploads:
        if room <= 0:
            warnings.append(f'{upload.name}: нэг шилжүүлэгт {MAX_RECEIPTS}-аас олон баримт хавсаргах боломжгүй.')
            continue
        if upload.size > MAX_ATTACHMENT_MB * 1024 * 1024:
            warnings.append(f'{upload.name} файл {MAX_ATTACHMENT_MB}MB-аас том тул хавсаргаагүй.')
            continue
        ImportPaymentReceipt.objects.create(payment=payment, file=upload, original_name=upload.name[:255], created_by=user)
        room -= 1


def _delete_payment(payment):
    if payment.receipt:
        payment.receipt.delete(save=False)
    for receipt in payment.receipts.all():
        receipt.file.delete(save=False)
    payment.delete()


def delete_with_files(shipment=None, order=None):
    """Чингэлэг эсвэл нийлүүлэгчийн захиалгыг хавсралт, төлбөрийн баримтын файлтай нь устгана."""
    target = order or shipment
    attachments = (order.attachments.all() if order else shipment.attachments.all())
    payments = ImportPayment.objects.filter(**({'supplier_order': order} if order else
                                               {'supplier_order__shipment': shipment}))
    receipts = ImportPaymentReceipt.objects.filter(payment__in=payments)
    for stored in [a.file for a in attachments] + [p.receipt for p in payments if p.receipt] + [r.file for r in receipts]:
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
        value = _date(post.get(field))
        # Бодит (ачигдсан / ирсэн) огноо ирээдүйд байж болохгүй - төлөв нь шууд "ачигдсан / ирсэн" болчихно
        if field.endswith('_actual') and value and value > today:
            label = 'Ачигдсан' if field == 'load_actual' else 'Ирсэн'
            warnings.append(f'{label} огноо ({value:%Y-%m-%d}) ирээдүйд байгаа тул хадгалсангүй - '
                            f'болоогүй бол төлөвлөсөн огноонд оруулна уу.')
            continue
        setattr(shipment, field, value)
    shipment.load_place = _text(post, 'load_place', 200)
    rates = {}
    for currency, _ in ImportSupplierOrder.CURRENCY_CHOICES:
        rate = _dec(post.get(f'rate_{currency}'), default=None)
        if rate is not None and rate > 0 and currency != 'MNT':
            rates[currency] = str(rate)
    shipment.customs_rates = rates
    shipment.customs_include_freight = post.get('customs_include_freight') == '1'
    # Бусад зардал (ирсэн захиалгад): нэр / дүнгийн мөрүүд, хоёулаа хоосон мөрийг алгасна
    if 'other_name' in post or 'other_present' in post:
        costs = []
        for name, amount in zip_longest(post.getlist('other_name'), post.getlist('other_amount'), fillvalue=''):
            name, value = name.strip()[:200], _dec(amount, default=None)
            if name or value:
                costs.append({'name': name, 'amount': str(value if value is not None and value >= 0 else ZERO)})
        shipment.other_costs = costs
    # Бодит дүн зөвхөн ирсэн захиалгад; талбар илгээгдээгүй бол (ирээгүй үед) хуучин утга хэвээр
    for field in ('customs_duty_actual', 'customs_vat_actual'):
        if field in post:
            value = _dec(post.get(field), default=None)
            setattr(shipment, field, value if value is not None and value >= 0 else None)
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
        if p + 'foreign_extra' in post:  # гадаад дахь нэмэлт зардал (захиалгын валютаар), сөрөг бол 0
            order.foreign_extra = max(_dec(post.get(p + 'foreign_extra')), ZERO)
        order.save()

        # Мөрүүдийг бүхэлд нь солино
        order.lines.all().delete()
        # zip_longest: хуучин (шинэ баганагүй) хуудаснаас илгээсэн ч мөр алдагдахгүй
        rows = zip_longest(*(post.getlist(p + 'line_' + key) for key in
                             ('name', 'measure', 'boxes', 'per', 'qty', 'price', 'total', 'last', 'duty', 'vat',
                              'disc', 'net', 'sale')), fillvalue='')
        for position, (item_name, measure, boxes, per, qty, price, total, last, duty, vat, disc, net, sale) in enumerate(rows):
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
                duty_rate=_rate(duty, Decimal(str(known['duty'])) if known else default_duty_rate(item_name)),
                vat_rate=_rate(vat, DEFAULT_VAT_RATE), sale_price=_dec(sale, default=None))

        for stage in ImportAttachment.SUPPLIER_STAGES:
            _attach(shipment, order, stage, files.getlist(f'{p}att_{stage}'), user, warnings)

        # Шинэ шилжүүлгүүд - нэг дор олон мөр (pay_row = мөрийн түлхүүр), мөр бүр олон баримттай
        added = False
        for row in post.getlist(p + 'pay_row'):
            r = f'{p}pay{row}_'
            amount = _dec(post.get(r + 'amount'), default=None)
            uploads = files.getlist(r + 'files')
            if amount is None and not uploads:
                continue
            payment = ImportPayment.objects.create(
                supplier_order=order, paid_date=_date(post.get(r + 'date')) or today, amount=amount or ZERO,
                note=_text(post, r + 'note', 300), created_by=user)
            _add_receipts(payment, uploads, user, warnings)
            added = True
        # Өмнөх шилжүүлэгт баримт нэмэх
        for payment in ImportPayment.objects.filter(supplier_order=order):
            _add_receipts(payment, files.getlist(f'payment{payment.id}_files'), user, warnings)
        # Шилжүүлэг нэмэгдсэн бол төлөвийг нийлбэрээр нь ахиулна (гараар сонгосныг бууруулахгүй)
        if added:
            rank = [ImportSupplierOrder.PAY_NONE, ImportSupplierOrder.PAY_PARTIAL, ImportSupplierOrder.PAY_FULL]
            status = _payment_status(order)
            if rank.index(status) > rank.index(order.payment_status):
                order.payment_status = status
                order.save(update_fields=['payment_status'])

    for stage in ImportAttachment.SHIPMENT_STAGES:
        _attach(shipment, None, stage, files.getlist(f'att_{stage}'), user, warnings)
    if post.get('delete_attachment'):
        for attachment in shipment.attachments.filter(id=post['delete_attachment']):
            attachment.file.delete(save=False)
            attachment.delete()
    if post.get('delete_payment'):
        for payment in ImportPayment.objects.filter(id=post['delete_payment'], supplier_order__shipment=shipment):
            _delete_payment(payment)
    if post.get('delete_payment_receipt'):
        for receipt in ImportPaymentReceipt.objects.filter(id=post['delete_payment_receipt'],
                                                           payment__supplier_order__shipment=shipment):
            receipt.file.delete(save=False)
            receipt.delete()
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
    arrived = bool(shipment.arrival_actual)  # ирсэн бол бүх шат дууссан (огноогүй ч)
    nodes = []
    if full:
        for step in shipment.steps[:5]:
            nodes.append({'label': step['label'], 'sub': '',
                          'date': step['date'], 'state': 'done' if step['done'] else 'todo'})
    load_idx = len(nodes)
    nodes.append({'label': 'Ачигдсан', 'sub': f'{shipment.load_place}-с' if shipment.load_place else '',
                  'date': shipment.load_actual or (None if arrived else shipment.load_planned),
                  'state': 'done' if shipment.load_actual or arrived else ('plan' if shipment.load_planned else 'todo')})
    for point in shipment.transit_points.all():
        nodes.append({'label': point.place, 'sub': point.note, 'date': point.date,
                      'state': 'plan' if point.date > today and not arrived else 'done'})
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


def expected_date(shipment):
    """Ирсэн огноо, ирээгүй бол хүлээгдэж буй огноо: ирэх (төлөвлөсөн), сүүлийн дамжих газар, ачигдсан, ачих огноо."""
    if shipment.arrival_actual:
        return shipment.arrival_actual
    points = list(shipment.transit_points.all())
    return (shipment.arrival_planned or (points[-1].date if points else None)
            or shipment.load_actual or shipment.load_planned)


def tracking_sort_key(shipment, today):
    """Замын мэдээний дараалал: ирээгүй нь эхэнд, түрүүлж ирэх нь дээрээ; ирсэн нь доор, сүүлд ирсэн нь дээрээ.
    Ирэх огноо хоосон бол дараагийн мэдэгдэж буй огноо: сүүлийн дамжих газар (төлөвлөсөн ч), ачигдсан, ачих огноо."""
    if shipment.arrival_actual:
        return (1, -shipment.arrival_actual.toordinal())
    eta = expected_date(shipment) or today + timedelta(days=3650)
    return (0, eta.toordinal())


# Импортын захиалгын жагсаалтын эрэмбэ (?sort=): (утга, нэр)
ORDER_SORTS = [
    ('arrival_desc', 'Ирсэн/ирэх огноо - сүүлийнх нь дээрээ'),
    ('arrival_asc', 'Ирсэн/ирэх огноо - эртийнх нь дээрээ'),
    ('route', 'Замын мэдээ шиг - ирээгүй нь (ойрын) дээрээ'),
    ('created_desc', 'Бүртгэсэн - шинэ нь дээрээ'),
    ('created_asc', 'Бүртгэсэн - хуучин нь дээрээ'),
    ('load_desc', 'Ачигдсан огноо - сүүлийнх нь дээрээ'),
    ('code', 'Захиалгын код'),
    ('supplier', 'Нийлүүлэгч (А-Я)'),
    ('tax_desc', 'Татвар - их нь дээрээ'),
]
ORDER_SORT_KEYS = {key for key, _ in ORDER_SORTS}


def order_sort_default(show):
    """Табын анхдагч эрэмбэ: Ирсэн - сүүлд ирсэн нь дээрээ; бусад - бүртгэсэн шинэ нь дээрээ (хуучин зан төлөв)."""
    return 'arrival_desc' if show == 'arrived' else 'created_desc'


def sort_orders(shipments, sort, today=None):
    """decorate хийсэн чингэлгүүдийг эрэмбэлнэ. Огноо/дүн хоосон нь чиглэлээс үл хамааран доор; тэнцвэл шинэ бүртгэл дээр."""
    today = today or timezone.localdate()
    shipments = sorted(shipments, key=lambda s: s.created_at, reverse=True)  # тогтвортой хоёрдогч эрэмбэ

    def by(value, reverse=False):
        present = [s for s in shipments if value(s) is not None]
        missing = [s for s in shipments if value(s) is None]
        return sorted(present, key=value, reverse=reverse) + missing

    if sort == 'arrival_asc':
        return by(expected_date)
    if sort == 'route':
        return sorted(shipments, key=lambda s: tracking_sort_key(s, today))
    if sort == 'created_asc':
        return shipments[::-1]
    if sort == 'created_desc':
        return shipments
    if sort == 'load_desc':
        return by(lambda s: s.load_actual or s.load_planned, reverse=True)
    if sort == 'code':
        return sorted(shipments, key=lambda s: s.code.lower())
    if sort == 'supplier':
        return by(lambda s: next((o.supplier_name.lower() for o in s.supplier_orders.all() if o.supplier_name), None))
    if sort == 'tax_desc':
        return by(lambda s: s.tax['total'] or None, reverse=True)
    return by(expected_date, reverse=True)  # arrival_desc


def attach_base_prices(shipments):
    """Бараа бүрт '001' (Үндсэн үнэ) сувгийн хамгийн сүүлийн огнооны үнэ ба бохир ашгийг нэмнэ (compute_taxes-ийн дараа).
    line.base_price - нэгж үнэ, line.sale_amount = үнэ × тоо, line.cost_mnt = гаалийн үнэ (бараа + тээврийн хуваарь)
    + гаалийн татвар + НӨАТ + бусад зардлын хуваарь (other_cost), line.profit = sale_amount - cost_mnt. Үнэ НӨАТ-тэй тул өртгийг ч НӨАТ-тэй нь бодно.
    Ханш дутуу (төгрөгөөр бодогдоогүй) эсвэл үнэгүй бараанд ашиг бодохгүй. Нийлбэрийг order/shipment.profit дээр.
    Мөрөнд гараар оруулсан зарах үнэ (sale_price) байвал түүгээр (line.price_manual); line.erp_price - ERP-ийн үнэ."""
    from datamigration.models import OpenDataItem, OpenDataItemPrice, OpenDataItemPriceChannel

    lines = [l for s in shipments for o in s.supplier_orders.all() for l in o.lines.all()]
    codes = {l.item_id for l in lines if l.item_id}
    prices = {}
    channel = OpenDataItemPriceChannel.objects.filter(code='001').first()
    if codes and channel:
        pkids = dict(OpenDataItem.objects.filter(id__in=codes, pkid__isnull=False).values_list('pkid', 'id'))
        latest = (OpenDataItemPrice.objects
                  .filter(customerpkid__isnull=True, pricechannelpkid=channel.pkid, itempkid__in=pkids, price__isnull=False)
                  .order_by('itempkid', '-pricedate').distinct('itempkid').values_list('itempkid', 'price', 'pricedate'))
        prices = {pkids[pk]: (Decimal(str(price)), date) for pk, price, date in latest}
    cent = Decimal('0.01')
    stale_before = timezone.localdate() - timedelta(days=365)
    for shipment in shipments:
        shipment.sale_total = shipment.profit = ZERO
        shipment.profit_lines = 0
        for order in shipment.supplier_orders.all():
            order.sale_total = order.profit = ZERO
            for line in order.lines.all():
                line.erp_price, line.erp_price_date = prices.get(line.item_id, (None, None))
                line.price_manual = line.sale_price is not None
                if line.price_manual:
                    line.base_price, line.price_date = line.sale_price, None
                else:
                    line.base_price, line.price_date = line.erp_price, line.erp_price_date
                line.price_stale = bool(line.price_date and line.price_date < stale_before)  # 1 жилээс хуучин үнэ
                line.sale_amount = line.cost_mnt = line.profit = line.margin = None
                if line.base_price is None:
                    continue
                line.sale_amount = (line.base_price * line.total_qty).quantize(cent, ROUND_HALF_UP)
                if getattr(line, 'tax_currency', None) != 'MNT':
                    continue
                line.cost_mnt = line.customs_value + line.duty_amount + line.vat_amount + line.other_cost
                line.profit = line.sale_amount - line.cost_mnt
                line.margin = (line.profit / line.sale_amount * 100).quantize(Decimal('0.1')) if line.sale_amount else None
                order.sale_total += line.sale_amount
                order.profit += line.profit
                shipment.profit_lines += 1
            shipment.sale_total += order.sale_total
            shipment.profit += order.profit
        shipment.margin = (shipment.profit / shipment.sale_total * 100).quantize(Decimal('0.1')) if shipment.sale_total else None
    return shipments


TRACKING_SHOWS = ('recent', 'active', 'arrived', 'all')


def tracking_shipments(today=None, full=False, pk=None, arrived_from=None, arrived_to=None, show='recent', supplier=''):
    """Замын мэдээ. show: recent - ирээгүй бүх чингэлэг + сүүлийн RECENT_ARRIVED_DAYS хоногт ирсэн (анхдагч),
    active - ирээгүй, arrived - хэзээ ч ирсэн, all - бүгд. pk бол зөвхөн тэр нэг (хэзээ ирснээс үл хамааран).
    arrived_from / arrived_to өгвөл зөвхөн тэр хугацаанд ирсэн чингэлгүүд (аль нэг нь хоосон бол тэр талдаа хязгааргүй).
    supplier өгвөл тэр нийлүүлэгчийн захиалгатай чингэлгүүд."""
    today = today or timezone.localdate()
    if pk is not None:
        qs = prefetched_shipments().filter(pk=pk)
    elif show == 'all' and not (arrived_from or arrived_to):
        qs = prefetched_shipments()
    elif show == 'active' and not (arrived_from or arrived_to):
        qs = prefetched_shipments().filter(arrival_actual__isnull=True)
    elif show == 'arrived' and not (arrived_from or arrived_to):
        qs = prefetched_shipments().filter(arrival_actual__isnull=False)
    elif arrived_from or arrived_to:
        qs = prefetched_shipments().filter(arrival_actual__isnull=False)
        if arrived_from:
            qs = qs.filter(arrival_actual__gte=arrived_from)
        if arrived_to:
            qs = qs.filter(arrival_actual__lte=arrived_to)
    else:
        qs = prefetched_shipments().filter(
            Q(arrival_actual__isnull=True) | Q(arrival_actual__gte=today - timedelta(days=RECENT_ARRIVED_DAYS)))
    qs = filter_supplier(qs, supplier)
    shipments = [decorate(s, today) for s in qs]
    for shipment in shipments:
        shipment.timeline = tracking_timeline(shipment, full, today)
    if full:
        attach_base_prices(shipments)
    shipments.sort(key=lambda s: tracking_sort_key(s, today))
    return shipments


def arrival_filter(params):
    """GET-ээс ирсэн огнооны шүүлт (from, to) - буруу утгыг үл тооно, урвуу бол сольно. ?show=all-ийг тусад нь шалгана."""
    from datetime import datetime

    def parse(value):
        try:
            return datetime.strptime(value or '', '%Y-%m-%d').date()
        except ValueError:
            return None
    date_from, date_to = parse(params.get('arrived_from')), parse(params.get('arrived_to'))
    if date_from and date_to and date_to < date_from:
        date_from, date_to = date_to, date_from
    return date_from, date_to


def tracking_show(params, filtered=False):
    """Замын мэдээний таб (?show=); ирсэн огноогоор шүүсэн бол "Ирсэн", таб сонгоогүй нийлүүлэгчээр шүүсэн бол "Бүгд"."""
    show = params.get('show') or ('all' if params.get('supplier') else 'recent')
    return 'arrived' if filtered else (show if show in TRACKING_SHOWS else 'recent')


def filter_supplier(qs, supplier):
    """Тухайн нийлүүлэгчийн захиалгатай чингэлгүүд (олон нийлүүлэгчтэй чингэлэг давхардахгүй)."""
    if not supplier:
        return qs
    return qs.filter(pk__in=ImportShipment.objects.filter(supplier_orders__supplier_name=supplier).values('pk'))


def shipment_suppliers():
    """Шүүлтийн сонголт: [(нийлүүлэгч, чингэлгийн тоо)] - захиалгад орсон нийлүүлэгчид."""
    from django.db.models import Count
    return list(ImportSupplierOrder.objects.exclude(supplier_name='').values('supplier_name')
                .annotate(n=Count('shipment', distinct=True)).order_by('supplier_name').values_list('supplier_name', 'n'))


def shipment_stats(shipments, today=None):
    """Замын мэдээ / захиалгын жагсаалтын дээд хэсгийн жижиг статистик (decorate хийсэн чингэлгүүдээс)."""
    today = today or timezone.localdate()
    pending = [s for s in shipments if not s.arrived]
    return {
        'total': len(shipments),
        'overall': ImportShipment.objects.count(),  # шүүлтээс үл хамааран бүх захиалга
        'transit': sum(1 for s in pending if s.load_actual),
        'wait': sum(1 for s in pending if not s.load_actual),
        'arrived': len(shipments) - len(pending),
        'late': sum(1 for s in pending if s.delay_days),
        'week': sum(1 for s in pending if s.arrival_planned and s.arrival_planned <= today + timedelta(days=7)),
        'boxes': sum(s.box_total or 0 for s in pending if s.load_actual),
    }


def arrival_presets(today=None):
    """Ирсэн огнооны түргэн сонголт [(нэр, from, to)]."""
    today = today or timezone.localdate()
    prev_month_end = today.replace(day=1) - timedelta(days=1)
    return [
        ('Энэ сар', today.replace(day=1), today),
        ('Өмнөх сар', prev_month_end.replace(day=1), prev_month_end),
        ('Энэ он', today.replace(month=1, day=1), today),
        ('Өнгөрсөн он', today.replace(year=today.year - 1, month=1, day=1), today.replace(year=today.year - 1, month=12, day=31)),
    ]
