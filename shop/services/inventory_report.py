"""Барааны үлдэгдлийн тайлан (/dashboard/inventory/) - InventorySnapshot-ийн шүүлт, эрэмбэлэлт.

URL параметрүүд (бүгд заавал биш, хоорондоо AND):
- q          : чөлөөт хайлт. Үг бүр (ямар ч дараалалд) барааны нэр эсвэл брэндэд агуулагдах ёстой.
               Латин/кирилл ижил дүрстэй үсгийг ялгахгүй (1x*12ш = 1х*12ш). Хуучин `product` параметрийг ч хүлээн авна.
- warehouse  : олон утгатай; сонгосон агуулахуудын АЛЬ НЭГД нь үлдэгдэлтэй бараа. Код (000), түлхүүр (tolgoit)
               эсвэл хуучин дэлгэцийн нэрээр өгч болно.
- brand      : олон утгатай, брэндийн нэр яг таарна.
- min_qty    : хамгийн бага үлдэгдэл - агуулах сонгосон бол тэдгээрт, үгүй бол нийт үлдэгдэлд.
- jijig_min  : 'true' бол Агуулах жижигт 10+ үлдэгдэлтэй.
- stock_only : 'true'/'false' (default true). Checkbox-ийн өмнө hidden 'false' илгээгддэг тул сүүлийн утгыг авна.
- sort       : SORTS-ийн түлхүүр, урдаа '-' бол буурахаар. per_page: PAGE_SIZES-ийн нэг.
"""
import re
from decimal import Decimal, InvalidOperation

from django.db.models import F, Q, Sum

from shop.models_inventory import SNAPSHOT_WAREHOUSES

# (түлхүүр, дэлгэцийн нэр) - SNAPSHOT_WAREHOUSES-ийн дарааллаар
WAREHOUSES = [(key, label) for key, label in SNAPSHOT_WAREHOUSES.values()]
WAREHOUSE_LABELS = dict(WAREHOUSES)
_WAREHOUSE_ALIASES = {}
for _code, (_key, _label) in SNAPSHOT_WAREHOUSES.items():
    for _alias in (_code, _key, _label):
        _WAREHOUSE_ALIASES[_alias.lower()] = _key
_WAREHOUSE_ALIASES['агуулах толгойт'] = 'tolgoit'  # нэр солигдохоос өмнөх хадгалсан холбоосууд

SORTS = {'name': 'itemname', 'brand': 'brandname', 'total': 'total_qty'}
SORTS.update({key: f'{key}_qty' for key, _ in WAREHOUSES})
DEFAULT_SORT = 'name'
PAGE_SIZES = (50, 100, 200)
JIJIG_MIN = 10

# Латин <-> кирилл ижил дүрстэй үсгүүд (барааны нэрэнд 1x*12ш / 1х*12ш холилдож бичигддэг)
_LAT = 'aceopxyABCEHKMOPTXY'
_CYR = 'асеорхуАВСЕНКМОРТХУ'
_TO_CYR = str.maketrans(_LAT, _CYR)
_TO_LAT = str.maketrans(_CYR, _LAT)


def _last(params, name):
    values = [v.strip() for v in params.getlist(name)]
    return values[-1] if values else ''


def _clean_list(params, name):
    seen = []
    for value in params.getlist(name):
        value = value.strip()
        if value and value.lower() != 'none' and value not in seen:
            seen.append(value)
    return seen


def _decimal(value):
    try:
        number = Decimal(value.replace(',', '').strip())
    except (InvalidOperation, AttributeError):
        return None
    return number if number.is_finite() and number >= 0 else None


def parse_filters(params):
    """QueryDict-ээс цэвэрлэсэн шүүлтийн dict үүсгэнэ (буруу утгыг чимээгүй алгасна)."""
    q = ' '.join((_last(params, 'q') or _last(params, 'product')).split())
    if q.lower() == 'none':
        q = ''

    warehouses = []
    for value in _clean_list(params, 'warehouse'):
        key = _WAREHOUSE_ALIASES.get(' '.join(value.split()).lower())
        if key and key not in warehouses:
            warehouses.append(key)

    sort = _last(params, 'sort') or DEFAULT_SORT
    if sort.lstrip('-') not in SORTS:
        sort = DEFAULT_SORT

    try:
        per_page = int(_last(params, 'per_page'))
    except ValueError:
        per_page = PAGE_SIZES[0]
    if per_page not in PAGE_SIZES:
        per_page = PAGE_SIZES[0]

    stock_only = _last(params, 'stock_only')
    return {
        'q': q,
        'warehouse': warehouses,
        'brand': _clean_list(params, 'brand'),
        'min_qty': _decimal(_last(params, 'min_qty')),
        'jijig_min': _last(params, 'jijig_min') == 'true',
        'stock_only': stock_only != 'false',
        'sort': sort,
        'per_page': per_page,
    }


def token_variants(token):
    """Хайлтын үгийн латин/кирилл хувилбарууд."""
    return {token, token.translate(_TO_CYR), token.translate(_TO_LAT)}


def search_q(text):
    """Үг бүр нэр эсвэл брэндэд агуулагдах нөхцөл (үгийн дараалал хамаагүй)."""
    condition = Q()
    for token in re.split(r'\s+', text.strip()):
        if not token:
            continue
        token_q = Q()
        for variant in token_variants(token):
            token_q |= Q(itemname__icontains=variant) | Q(brandname__icontains=variant)
        condition &= token_q
    return condition


def filter_queryset(qs, f):
    """Шүүлт хэрэглэнэ (эрэмбэлэлтгүй) - жагсаалт ба брэндийн сонголтын аль алинд ашиглана."""
    if f['q']:
        qs = qs.filter(search_q(f['q']))
    if f['brand']:
        qs = qs.filter(brandname__in=f['brand'])
    if f['stock_only']:
        qs = qs.filter(total_qty__gt=0)
    if f['jijig_min']:
        qs = qs.filter(jijig_qty__gte=JIJIG_MIN)

    min_qty = f['min_qty']
    if f['warehouse']:
        # Сонгосон агуулахуудын аль нэгэнд нь (min_qty өгсөн бол түүнээс багагүй) үлдэгдэлтэй
        lookup = 'gte' if min_qty is not None else 'gt'
        bound = min_qty if min_qty is not None else 0
        condition = Q()
        for key in f['warehouse']:
            condition |= Q(**{f'{key}_qty__{lookup}': bound})
        qs = qs.filter(condition)
    elif min_qty is not None:
        qs = qs.filter(total_qty__gte=min_qty)
    return qs


def order_queryset(qs, sort):
    field = SORTS[sort.lstrip('-')]
    if sort.startswith('-'):
        return qs.order_by(F(field).desc(nulls_last=True), 'itemname')
    return qs.order_by(F(field).asc(nulls_last=True), 'itemname')


def totals(qs):
    """Шүүсэн бүх барааны (зөвхөн тухайн хуудас биш) агуулах тус бүрийн нийт үлдэгдэл."""
    fields = [f'{key}_qty' for key, _ in WAREHOUSES] + ['total_qty']
    sums = qs.aggregate(**{name: Sum(name) for name in fields})
    return {name: float(sums[name] or 0) for name in fields}
