"""
Цалин бодолтын хэвлэх загвар - хуудас, хүснэгт бүрт хэвлэгдэх баганыг Цалингийн тохиргоонд сонгоно.

Карт, бэлэн хуудас тус бүр 2 хуудас x 2 хүснэгт (PRINT_SLOTS) байрлалтай. Байрлал бүрт баганын
түлхүүрийн жагсаалтыг PayrollSetting.print_columns-д ({'card': {'p1a': [...], ...}, 'cash': {...}})
хадгална; хадгалаагүй байрлалд DEFAULT_PRINT_COLUMNS хэрэглэгдэнэ. Хоосон байрлал/хуудас хэвлэгдэхгүй.
'separate_pages': True бол хүснэгт бүр тусдаа хуудсанд хэвлэгдэнэ.

Хасагдах багана (татвар, суутгал) агуулсан хүснэгтийн төгсгөлд "... хассан дүн" багана автоматаар бодогдож,
дараагийн хүснэгтийн эхэнд давтагдана (table_specs-ийг үз).
"""
from decimal import Decimal, InvalidOperation

from shop.services.payroll import BENEFIT_FIELDS, DEDUCTION_COLUMNS, EARNING_FIELDS

# Хуудас бүрийн хүснэгтийн байрлал: (түлхүүр, хуудасны дугаар, тайлбар)
PRINT_SLOTS = [
    ('p1a', 1, '1-р хуудас - дээд хүснэгт'),
    ('p1b', 1, '1-р хуудас - доод хүснэгт'),
    ('p2a', 2, '2-р хуудас - дээд хүснэгт'),
    ('p2b', 2, '2-р хуудас - доод хүснэгт'),
]
SLOT_KEYS = [key for key, _, _ in PRINT_SLOTS]

# Хэвлэх боломжтой багана: түлхүүр -> тохиргоо
#   label   - толгойн нэр, group - дээд толгой (ижил group-тэй дараалсан баганыг нэгтгэнэ)
#   kind    - 'no' (дугаар), 'text', 'code', 'money', 'qty' (хоног/цаг), 'rate' (%), 'sign' (гарын үсэг)
#   total   - Дүн мөрөнд нийлбэр гаргах эсэх, card_only - зөвхөн картын хуудсанд
PRINT_COLUMNS = {
    'no': {'label': '№', 'kind': 'no'},
    'name': {'label': 'Ажилчдын нэрс', 'kind': 'text'},
    'positionname': {'label': 'Албан тушаал', 'kind': 'text'},
    'base_salary': {'label': 'Үндсэн цалин', 'kind': 'money', 'total': True},
    'seniority_bonus': {'label': 'Удаан жилийн нэмэгдэл', 'kind': 'money', 'total': True},
    'nominal_salary': {'label': 'Нийт цалин (үндсэн + удаан жил)', 'short': 'Нийт цалин', 'kind': 'money', 'total': True},
    'required_days': {'label': 'Ажиллавал зохих хоног', 'kind': 'qty', 'total': True},
    'required_hours': {'label': 'Ажиллавал зохих цаг', 'kind': 'qty', 'total': True},
    'worked_days': {'label': 'Ажилласан хоног', 'kind': 'qty', 'total': True},
    'worked_hours': {'label': 'Ажилласан цаг', 'kind': 'qty', 'total': True},
    'saturday_hours': {'label': 'Бямбад ажилласан цаг', 'kind': 'qty', 'total': True},
    'saturday_bonus': {'label': 'Бямбад ажилласан нэмэгдэл', 'kind': 'money', 'total': True},
    **{f: {'label': label, 'kind': 'money', 'total': True} for f, label in EARNING_FIELDS},
    'transport': {'label': 'Унааны мөнгө', 'kind': 'money', 'total': True},
    'gross': {'label': 'Бодогдсон нийт цалин', 'kind': 'money', 'total': True},
    'ndsh_code': {'label': 'Код', 'group': 'НДШ Ажилтан', 'kind': 'code', 'card_only': True},
    'ndsh_employee_rate': {'label': '%', 'group': 'НДШ Ажилтан', 'kind': 'rate', 'card_only': True},
    'ndsh_employee': {'label': 'Дүн', 'group': 'НДШ Ажилтан', 'kind': 'money', 'total': True, 'card_only': True},
    'ndsh_employer_rate': {'label': '%', 'group': 'НДШ Байгууллага', 'kind': 'rate', 'card_only': True},
    'ndsh_employer': {'label': 'Дүн', 'group': 'НДШ Байгууллага', 'kind': 'money', 'total': True, 'card_only': True},
    'taxable': {'label': 'ХХОАТ тооцох дүн', 'kind': 'money', 'total': True, 'card_only': True},
    'credit': {'label': 'Хөнгөлөлт шатлалаар', 'kind': 'money', 'total': True, 'card_only': True},
    'pit': {'label': 'ХХОАТ', 'kind': 'money', 'total': True, 'card_only': True},
    'total_tax': {'label': 'Нийт татварын суутгал', 'kind': 'money', 'total': True, 'card_only': True},
    **{f: {'label': label, 'kind': 'money', 'total': True} for f, label, _ in DEDUCTION_COLUMNS},
    **{f: {'label': label, 'kind': 'money', 'total': True} for f, label in BENEFIT_FIELDS},
    'net_pay': {'label': 'Гарт олгох', 'kind': 'money', 'total': True},
    'deposit': {'label': 'Хадгаламж', 'kind': 'money', 'total': True},
    'payout': {'label': 'Картанд орох / Бэлнээр олгох', 'kind': 'money', 'total': True, 'bold': True},
    'signature': {'label': 'Гарын үсэг', 'kind': 'sign'},
}

_DEDUCTIONS = [f for f, _, _ in DEDUCTION_COLUMNS]
_BENEFITS = [f for f, _ in BENEFIT_FIELDS]
_EARNINGS = [f for f, _ in EARNING_FIELDS]
_PERSON = ['no', 'name', 'positionname']

DEFAULT_PRINT_COLUMNS = {
    'card': {
        'p1a': _PERSON + ['base_salary', 'seniority_bonus', 'nominal_salary', 'required_days', 'required_hours',
                          'worked_days', 'worked_hours', 'saturday_hours', 'saturday_bonus', *_EARNINGS,
                          'transport', 'gross'],
        'p1b': [],
        'p2a': _PERSON + ['gross', 'ndsh_code', 'ndsh_employee_rate', 'ndsh_employee', 'ndsh_employer_rate',
                          'ndsh_employer', 'taxable', 'credit', 'pit', 'total_tax'],
        # Эхэнд нь "Нийт татварын суутгал хассан дүн" автоматаар орно (table_specs)
        'p2b': _PERSON + [*_DEDUCTIONS, *_BENEFITS, 'net_pay', 'deposit', 'payout'],
    },
    'cash': {
        'p1a': _PERSON + ['base_salary', 'seniority_bonus', 'required_days', 'required_hours', 'worked_days',
                          'worked_hours', 'saturday_hours', 'saturday_bonus', *_EARNINGS, 'transport', 'gross'],
        'p1b': _PERSON + ['gross', *_DEDUCTIONS, *_BENEFITS, 'net_pay', 'deposit', 'payout', 'signature'],
        'p2a': [],
        'p2b': [],
    },
}


def column_label(key, sheet):
    """Толгойд гарах нэр (payout нь хуудсаар өөр)."""
    if key == 'payout':
        return 'Картанд орох' if sheet == 'card' else 'Бэлнээр олгох'
    col = PRINT_COLUMNS[key]
    return col.get('short', col['label'])


def column_choice_label(key, sheet):
    """Тохиргооны жагсаалтад харагдах бүтэн нэр (бүлэгтэй бол бүлгийн нэртэй)."""
    col = PRINT_COLUMNS[key]
    label = column_label(key, sheet) if key == 'payout' else col['label']
    return f"{col['group']} - {label}" if col.get('group') else label


def available_columns(sheet):
    """Тухайн хуудсанд сонгож болох баганууд (бэлэнд татварын багана байхгүй)."""
    return [k for k, c in PRINT_COLUMNS.items() if sheet == 'card' or not c.get('card_only')]


def clean_columns(keys, sheet):
    """Мэдэгдэхгүй, тухайн хуудсанд хамааралгүй, давхардсан түлхүүрийг хасна."""
    allowed = set(available_columns(sheet))
    result = []
    for key in keys:
        if key in allowed and key not in result:
            result.append(key)
    return result


def get_print_columns(setting, sheet):
    """Байрлал бүрийн баганын жагсаалт: {'p1a': [...], ...} (хадгалаагүй бол анхдагч)."""
    saved = (setting.print_columns or {}).get(sheet) or {}
    return {
        slot: clean_columns(saved[slot], sheet) if slot in saved else list(DEFAULT_PRINT_COLUMNS[sheet][slot])
        for slot in SLOT_KEYS
    }


def format_print_value(value, kind='money'):
    """Хэвлэхэд: мянгатыг таслалаар ялгасан тоо, 0/хоосон бол '-'. qty/rate нь 1 орон хүртэл, мөнгө бутархайтай
    бол 2 оронтой."""
    try:
        number = Decimal(value or 0)
    except (InvalidOperation, TypeError, ValueError):
        return value
    if not number:
        return '-'
    if kind in ('qty', 'rate'):
        places = 1
    else:  # мөнгө: бутархайтай бол 2 орон, бүхэл бол оронгүй
        places = 0 if number == number.to_integral_value() else 2
    text = f'{number:,.{places}f}'
    if kind in ('qty', 'rate') and '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text


# "... хассан дүн" баганад нийт цалингаас хасагдах / нэмэгдэх баганууд (НДШ, ХХОАТ-ыг тусад нь биш
# "Нийт татварын суутгал"-аар нь хасна - давхар хасагдахгүйн тулд)
SUBTRACT_KEYS = ['total_tax', *_DEDUCTIONS, 'deposit']
ADD_KEYS = list(_BENEFITS)


def _column_spec(key, sheet):
    col = PRINT_COLUMNS[key]
    return {
        'key': key, 'label': column_label(key, sheet), 'group': col.get('group'), 'kind': col['kind'],
        'total': col.get('total', False), 'bold': col.get('bold', False),
    }


def _remainder_spec(subtract, add, sheet):
    """Нийт цалингаас subtract багануудыг хасаж, add багануудыг нэмсэн дүнгийн багана."""
    def names(keys):
        return ', '.join(column_label(k, sheet) for k in keys)
    parts = []
    if subtract:
        parts.append(f'{names(subtract)} хассан')
    if add:
        parts.append(f'{names(add)} нэмсэн')
    return {
        'key': None, 'label': f"{', '.join(parts)} дүн", 'group': None, 'kind': 'money', 'total': True,
        'bold': True, 'subtract': list(subtract), 'add': list(add),
    }


def _value(spec, data):
    if 'subtract' in spec:
        return (Decimal(data.get('gross') or 0)
                - sum(Decimal(data.get(k) or 0) for k in spec['subtract'])
                + sum(Decimal(data.get(k) or 0) for k in spec['add']))
    return data.get(spec['key'])


def _cell(spec, row=None, index=None, totals=None):
    kind = spec['kind']
    classes = {'text': 't', 'no': 'c', 'code': 'c', 'qty': 'c', 'rate': 'c', 'sign': 'pr-sign'}.get(kind, '')
    if spec['bold']:
        classes += ' b'
    if totals is not None:
        text = format_print_value(_value(spec, totals), kind) if spec['total'] else ''
    elif kind == 'no':
        text = str(index)
    elif kind in ('text', 'code'):
        text = row.get(spec['key']) or ''
    elif kind == 'sign':
        # Гарын үсгийн баганад бэлэн цалингийн дансыг харуулна (Цалингийн тохиргооноос)
        text = row.get('cash_bank_account') or ''
    else:
        text = format_print_value(_value(spec, row), kind)
    return {'text': text, 'cls': classes.strip()}


def build_print_table(specs, rows, totals):
    """Нэг хүснэгтийн толгой (1-2 мөр), биеийн мөрүүд, Дүн мөрийг буцаана."""
    has_groups = any(c['group'] for c in specs)
    top, sub = [], []
    for spec in specs:
        cls = 'pr-sign' if spec['kind'] == 'sign' else ''
        if spec['group']:
            # Ижил бүлгийн дараалсан баганыг дээд толгойд нэгтгэнэ
            if top and top[-1].get('group') == spec['group']:
                top[-1]['colspan'] += 1
            else:
                top.append({'label': spec['group'], 'group': spec['group'], 'colspan': 1, 'rowspan': 1, 'cls': cls})
            sub.append({'label': spec['label'], 'colspan': 1, 'rowspan': 1, 'cls': cls})
        else:
            top.append({'label': spec['label'], 'colspan': 1, 'rowspan': 2 if has_groups else 1, 'cls': cls})
    head_rows = [top, sub] if has_groups else [top]

    body = [[_cell(c, row=r, index=i) for c in specs] for i, r in enumerate(rows, start=1)]

    # Дүн мөр: нийлбэргүй эхний багануудыг нэгтгэж "Дүн" гэж бичнэ
    foot = [_cell(c, totals=totals) for c in specs]
    lead = 0
    while lead < len(specs) and not specs[lead]['total']:
        lead += 1
    if lead:
        foot = [{'text': 'Дүн', 'cls': 't', 'colspan': lead}] + foot[lead:]
    else:
        foot = [{'text': 'Дүн', 'cls': 't', 'colspan': 1}] + foot
        head_rows[0].insert(0, {'label': '', 'colspan': 1, 'rowspan': len(head_rows), 'cls': ''})
        body = [[{'text': '', 'cls': ''}] + cells for cells in body]
    return {'head_rows': head_rows, 'rows': body, 'foot': foot}


def table_specs(columns, sheet):
    """Байрлал бүрийн баганын тодорхойлолт (хоосон байрлалыг алгасна): [(байрлал, хуудас, specs), ...].

    Хүснэгтэд нийт цалингаас хасагдах/нэмэгдэх багана (SUBTRACT_KEYS/ADD_KEYS) байвал, дараа нь өөр хүснэгт
    байгаа тохиолдолд, тэр хүснэгтийн төгсгөлд "... хассан дүн" баганыг автоматаар нэмж, дараагийн
    хүснэгтийн №/нэр/албан тушаалын дараа эхний багана болгон давтана. Дүн нь өмнөх бүх хүснэгтийн
    хасагдах багануудыг хуримтлуулж бодогдоно.
    """
    slots = [(slot, page, columns[slot]) for slot, page, _ in PRINT_SLOTS if columns[slot]]
    result = []
    subtract, add = [], []
    carry = None
    for i, (slot, page, keys) in enumerate(slots):
        specs = [_column_spec(k, sheet) for k in keys]
        if carry:
            lead = 0
            while lead < len(keys) and keys[lead] in ('no', 'name', 'positionname'):
                lead += 1
            specs.insert(lead, carry)
            carry = None
        found = False
        for k in keys:
            if k in SUBTRACT_KEYS and k not in subtract:
                subtract.append(k)
                found = True
            elif k in ADD_KEYS and k not in add:
                add.append(k)
                found = True
        if found and i < len(slots) - 1:
            carry = _remainder_spec(subtract, add, sheet)
            specs.append(carry)
        result.append((slot, page, specs))
    return result


def get_separate_pages(setting, sheet):
    """True бол хүснэгт бүр тусдаа хуудсанд хэвлэгдэнэ (жиш: картын 2-р хуудасны 2 хүснэгт -> 3 хуудас)."""
    return bool(((setting.print_columns or {}).get(sheet) or {}).get('separate_pages'))


def page_counts(columns):
    """(хуудсаар бүлэглэсэн үеийн хуудасны тоо, хүснэгт бүрийг тусад нь хэвлэх үеийн хуудасны тоо)."""
    filled = [(slot, page) for slot, page, _ in PRINT_SLOTS if columns[slot]]
    return len({page for _, page in filled}), len(filled)


def build_print_pages(setting, sheet, rows, totals):
    """Хэвлэх хуудсууд: [{'tables': [...]}, ...] - хоосон хүснэгт, хуудсыг алгасна."""
    separate = get_separate_pages(setting, sheet)
    pages = {}
    for slot, page_no, specs in table_specs(get_print_columns(setting, sheet), sheet):
        pages.setdefault(slot if separate else page_no, []).append(build_print_table(specs, rows, totals))
    return [{'tables': tables} for tables in pages.values()]
