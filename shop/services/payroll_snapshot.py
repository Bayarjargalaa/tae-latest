"""
Цалин бодолтын сар хаах (snapshot) ба цалингийн тайлан.

Сар хаах:
- build_payroll() нь ажилтны одоогийн мэдээллээр (үндсэн цалин, албан тушаал, идэвхтэй эсэх) үргэлж дахин бодогддог.
  Тиймээс өнгөрсөн сарын тайлан цалин өөрчлөгдөхөд өөрчлөгдөж, ажлаас гарсан ажилтан алга болно.
- Сарыг хаахад (close_month) бодогдсон мөрүүдийг ажилтны тухайн үеийн мэдээлэлтэй (EMPLOYEE_DIMS) хамт
  PayrollMonthClose-д хадгална. get_payroll() хаагдсан сард хуулбарыг, хаагдаагүй сард шууд бодолтыг буцаана.

Тайлан (payroll_facts + aggregate):
- Сар x хуудас (карт/бэлэн) x ажилтан бүрийн "баримт" (fact) мөр - үзүүлэлтүүд (METRICS) ба бүлэглэх хэмжигдэхүүнүүд
  (DIMENSIONS: ажилтан, албан тушаал, хэлтэс, хүйс, насны бүлэг, ажилласан жил, олгох хэлбэр, хуудас, сар).
- Карт, бэлэнг нийлүүлэхэд ижил ажилтны мөрүүд бүлэг дотроо нийлбэрлэгдэнэ (ажилтны тоо давхардахгүй).
"""
from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection

ZERO = Decimal(0)

# Хуулбарт хадгалах ажилтны мэдээлэл (тухайн үеийнх)
EMPLOYEE_DIMS = ('department', 'gender', 'birth_date', 'hire_date', 'pay_type')
# Хуулбараас уншихад Decimal болгохгүй текст талбарууд
TEXT_KEYS = {
    'employee_code', 'name', 'positionname', 'ndsh_code', 'cash_bank_account',
    'department', 'gender', 'birth_date', 'hire_date', 'pay_type',
}

GENDER_LABELS = {'M': 'Эрэгтэй', 'F': 'Эмэгтэй'}
PAY_TYPE_LABELS = {'card': 'Карт', 'cash': 'Бэлэн', 'mixed': 'Хосолсон'}
SHEET_LABELS = {'card': 'Картын цалин', 'cash': 'Бэлэн цалин'}

# (түлхүүр, нэр, тайлбар) - тайлангийн үзүүлэлтүүд
METRICS = [
    ('worked_days', 'Ажилласан хоног', ''),
    ('gross', 'Бодогдсон нийт цалин', 'Бодогдсон цалин + Бямба + амралт + нэмэгдэл + унаа'),
    ('sales_bonus', 'Борлуулалтын нэмэгдэл', 'Бодогдсон нийт цалинд багтсан'),
    ('ndsh_employee', 'НДШ ажилтан', ''),
    ('pit', 'ХХОАТ', ''),
    ('deductions', 'Суутгал', 'Урьдчилгаа, эрсдэлийн сан, хуримтлал, авлага, торгууль г.м.'),
    ('advance', 'Урьдчилгаа', 'Суутгалд багтсан'),
    ('benefits', 'ХЧТА', 'Тэтгэмж (байгууллага + НД-с)'),
    ('net_pay', 'Гарт олгох', ''),
    ('payout', 'Олгох дүн', 'Гарт олгох - хадгаламж (картанд орох / бэлнээр олгох)'),
    ('ndsh_employer', 'НДШ байгууллага', ''),
    ('employer_cost', 'Байгууллагын зардал', 'Бодогдсон нийт цалин + НДШ байгууллага'),
]
METRIC_KEYS = [k for k, _, _ in METRICS]
METRIC_LABELS = {k: label for k, label, _ in METRICS}

# (түлхүүр, нэр) - бүлэглэх хэмжигдэхүүн
DIMENSIONS = [
    ('employee', 'Ажилтан'),
    ('position', 'Албан тушаал'),
    ('department', 'Хэлтэс'),
    ('gender', 'Хүйс'),
    ('age_band', 'Насны бүлэг'),
    ('tenure_band', 'Ажилласан жил'),
    ('pay_type', 'Олгох хэлбэр'),
    ('sheet', 'Цалингийн төрөл'),
    ('month', 'Сар'),
]
DIMENSION_LABELS = dict(DIMENSIONS)
# "...-аар бүлэглэсэн" хэлбэр (гарчиг, Excel-ийн нэр)
DIMENSION_BY_LABELS = {
    'employee': 'Ажилтнаар', 'position': 'Албан тушаалаар', 'department': 'Хэлтсээр', 'gender': 'Хүйсээр',
    'age_band': 'Насны бүлгээр', 'tenure_band': 'Ажилласан жилээр', 'pay_type': 'Олгох хэлбэрээр',
    'sheet': 'Цалингийн төрлөөр', 'month': 'Сараар',
}
AGE_BANDS = [(25, '25 хүртэл'), (35, '25-34'), (45, '35-44'), (55, '45-54'), (None, '55+')]
TENURE_BANDS = [(1, '1 жил хүртэл'), (3, '1-3 жил'), (5, '3-5 жил'), (10, '5-10 жил'), (None, '10+ жил')]
UNKNOWN = 'Тодорхойгүй'


# --- Сар хаах ---------------------------------------------------------------------------------------------------

def employee_dims(codes):
    """Ажилтны одоогийн мэдээлэл: {код: {department, gender, birth_date, hire_date, pay_type}}."""
    from shop.models import EmployeePayProfile

    codes = list(codes)
    if not codes:
        return {}
    pay_types = dict(EmployeePayProfile.objects.filter(employee_code__in=codes).values_list('employee_code', 'pay_type'))
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT "Id", "DepartmentName", "Gender", "BirthDate", "HireDate" FROM "OpenDataEmployee" WHERE "Id" = ANY(%s)',
            [codes],
        )
        result = {
            code: {
                'department': department or '',
                'gender': gender or '',
                'birth_date': birth.isoformat() if birth else '',
                'hire_date': hired.isoformat() if hired else '',
            }
            for code, department, gender, birth, hired in cursor.fetchall()
        }
    for code in codes:
        result.setdefault(code, {'department': '', 'gender': '', 'birth_date': '', 'hire_date': ''})
        result[code]['pay_type'] = pay_types.get(code) or ''
    return result


def _dump_row(row, dims):
    """Мөрийг JSON-д хадгалах хэлбэрт (Decimal -> текст) оруулна."""
    import json
    return json.loads(json.dumps({**row, **dims}, cls=DjangoJSONEncoder))


def _load_row(raw):
    """Хуулбарын мөрийг цалин бодолтын мөр хэлбэрт (тоон текст -> Decimal) буцаана."""
    row = {}
    for key, value in raw.items():
        if isinstance(value, str) and key not in TEXT_KEYS:
            try:
                value = Decimal(value)
            except InvalidOperation:
                pass
        row[key] = value
    return row


def close_month(year, month, sheet, user):
    """Сарын цалин бодолтыг одоогийн бодолтоор нь хаана (дахин хаавал хуулбарыг шинэчилнэ). Мөрийн тоог буцаана."""
    from shop.models import PayrollMonthClose
    from shop.services.payroll import build_payroll

    rows, _, _ = build_payroll(year, month, sheet)
    dims = employee_dims(r['employee_code'] for r in rows)
    PayrollMonthClose.objects.update_or_create(
        year=year, month=month, sheet=sheet,
        defaults={'rows': [_dump_row(r, dims.get(r['employee_code'], {})) for r in rows], 'closed_by': user},
    )
    return len(rows)


def reopen_month(year, month, sheet):
    from shop.models import PayrollMonthClose
    PayrollMonthClose.objects.filter(year=year, month=month, sheet=sheet).delete()


def get_close(year, month, sheet):
    from shop.models import PayrollMonthClose
    return PayrollMonthClose.objects.filter(year=year, month=month, sheet=sheet).select_related('closed_by').first()


def get_payroll(year, month, sheet, employee_code=None):
    """Цалин бодолт: хаагдсан сард хуулбараас, үгүй бол шууд бодно. (rows, totals, setting, close эсвэл None)."""
    from shop.models import PayrollSetting
    from shop.services.payroll import build_payroll, payroll_totals

    close = get_close(year, month, sheet)
    if close is None:
        rows, totals, setting = build_payroll(year, month, sheet, employee_code)
        return rows, totals, setting, None
    rows = [_load_row(r) for r in close.rows if employee_code is None or r.get('employee_code') == employee_code]
    return rows, payroll_totals(rows), PayrollSetting.get(), close


# --- Тайлан -----------------------------------------------------------------------------------------------------

def month_range_list(year_from, month_from, year_to, month_to):
    """[(он, сар), ...] эхнээс төгсгөл хүртэл (хоёуланг нь оролцуулна)."""
    result = []
    y, m = year_from, month_from
    while (y, m) <= (year_to, month_to):
        result.append((y, m))
        y, m = (y, m + 1) if m < 12 else (y + 1, 1)
    return result


def _band(value, bands):
    if value is None:
        return UNKNOWN
    for limit, label in bands:
        if limit is None or value < limit:
            return label
    return UNKNOWN


def _years_between(start_iso, on_date):
    if not start_iso:
        return None
    try:
        start = date.fromisoformat(start_iso)
    except ValueError:
        return None
    return on_date.year - start.year - ((on_date.month, on_date.day) < (start.month, start.day))


def payroll_facts(months, sheets):
    """Сонгосон сар, хуудсуудын баримт мөрүүд ба хаагдсан эсэх: (facts, {(он, сар, хуудас): close эсвэл None})."""
    import calendar
    from shop.services.payroll import BENEFIT_FIELDS, DEDUCTION_COLUMNS

    facts, status, live_codes = [], {}, set()
    for year, month in months:
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        for sheet in sheets:
            rows, _, _, close = get_payroll(year, month, sheet)
            status[(year, month, sheet)] = close
            for r in rows:
                if close is None:
                    live_codes.add(r['employee_code'])
                facts.append({
                    'year': year, 'month': month, 'month_end': month_end, 'sheet': sheet, 'closed': close is not None,
                    'employee_code': r['employee_code'], 'name': r['name'], 'position': r['positionname'] or '',
                    # Хаагдсан сард тухайн үеийн мэдээлэл, хаагдаагүй сард доор одоогийнхоор нөхнө
                    **{d: r.get(d) for d in EMPLOYEE_DIMS},
                    'worked_days': Decimal(r['worked_days']),
                    'gross': r['gross'], 'sales_bonus': r['sales_bonus'],
                    'ndsh_employee': r['ndsh_employee'], 'pit': r['pit'],
                    'deductions': sum((r[f] for f, _, _ in DEDUCTION_COLUMNS), ZERO),
                    'advance': r['advance'],
                    'benefits': sum((r[f] for f, _ in BENEFIT_FIELDS), ZERO),
                    'net_pay': r['net_pay'], 'payout': r['payout'],
                    'ndsh_employer': r['ndsh_employer'], 'employer_cost': r['gross'] + r['ndsh_employer'],
                })
    current = employee_dims(live_codes | {f['employee_code'] for f in facts if f['gender'] is None})
    # Хосолсон ажилтны ажилласан хоног карт, бэлэн хоёр мөрөнд хоёуланд байдаг - нийлүүлэхэд давхардахгүйн тулд
    # картын мөртэй сарын бэлэн мөрийнхийг тэглэнэ
    card_months = {(f['employee_code'], f['year'], f['month']) for f in facts if f['sheet'] == 'card'}
    for f in facts:
        if not f['closed'] or f['gender'] is None:
            f.update(current.get(f['employee_code'], {}))
        if f['sheet'] == 'cash' and (f['employee_code'], f['year'], f['month']) in card_months:
            f['worked_days'] = ZERO
        f['age_band'] = _band(_years_between(f['birth_date'], f['month_end']), AGE_BANDS)
        f['tenure_band'] = _band(_years_between(f['hire_date'], f['month_end']), TENURE_BANDS)
    return facts, status


def dim_value(fact, dim):
    """Баримтын хэмжигдэхүүний (түлхүүр, харуулах нэр). Хоосон утгын түлхүүр нь "Тодорхойгүй" (шүүлтүүрт ашиглана)."""
    if dim == 'all':
        return 'all', 'Нийт'
    if dim == 'employee':
        return fact['employee_code'], fact['name']
    if dim in ('position', 'department'):
        value = fact[dim] or UNKNOWN
        return value, value
    if dim == 'gender':
        return (fact['gender'] or UNKNOWN), GENDER_LABELS.get(fact['gender'], UNKNOWN)
    if dim == 'pay_type':
        return (fact['pay_type'] or UNKNOWN), PAY_TYPE_LABELS.get(fact['pay_type'], UNKNOWN)
    if dim == 'sheet':
        return fact['sheet'], SHEET_LABELS[fact['sheet']]
    if dim == 'month':
        return f"{fact['year']}-{fact['month']:02d}", f"{fact['year']}.{fact['month']:02d}"
    return fact[dim], fact[dim]  # age_band, tenure_band - нэр нь өөрөө


def band_order(dim):
    bands = AGE_BANDS if dim == 'age_band' else TENURE_BANDS
    return {label: i for i, (_, label) in enumerate(bands)} | {UNKNOWN: len(bands)}


def aggregate(facts, dim, months, sort_metric='payout'):
    """Баримтыг dim-ээр бүлэглэнэ. Бүлэг бүрт үзүүлэлтүүдийн нийлбэр, ажилтны тоо, ажилтан-сарын тоо,
    сар бүрийн үзүүлэлт (pivot-д) буцаана. Эрэмбэ: сар, нас, ажилласан жил дарааллаар, бусад нь sort_metric-ээр буурахаар."""
    groups = {}
    for f in facts:
        key, label = dim_value(f, dim)
        g = groups.get(key)
        if g is None:
            g = groups[key] = {
                'key': key, 'label': label, 'employees': set(), 'employee_months': set(), 'by_month': {},
                'position': f['position'] if dim == 'employee' else '',
                **{m: ZERO for m in METRIC_KEYS},
            }
        g['employees'].add(f['employee_code'])
        g['employee_months'].add((f['employee_code'], f['year'], f['month']))
        ym = (f['year'], f['month'])
        bm = g['by_month'].setdefault(ym, {m: ZERO for m in METRIC_KEYS})
        for m in METRIC_KEYS:
            g[m] += f[m]
            bm[m] += f[m]
    result = list(groups.values())
    for g in result:
        g['employee_count'] = len(g.pop('employees'))
        employee_months = len(g.pop('employee_months'))
        g['employee_months'] = employee_months
        # Дундажийг ажилтан-сараар (хосолсон ажилтны карт, бэлэн нэг сард нэг л тоологдоно)
        g['avg_payout'] = g['payout'] / employee_months if employee_months else ZERO
        g['avg_gross'] = g['gross'] / employee_months if employee_months else ZERO
        g['month_values'] = [g['by_month'].get(ym) for ym in months]
    if dim in ('month', 'sheet'):
        result.sort(key=lambda g: g['key'])  # сар дарааллаар; карт, бэлэн
    elif dim in ('age_band', 'tenure_band'):
        order = band_order(dim)
        result.sort(key=lambda g: order.get(g['label'], 99))
    else:
        result.sort(key=lambda g: (-g[sort_metric], str(g['label'])))
    return result

