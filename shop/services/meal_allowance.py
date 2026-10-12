"""
Хоолны мөнгө - ажилласан ч байгууллагын хоол идээгүй өдөр бүрт мөнгө олгоно.

- Ажилчид, ажилласан хоног: Хоног бүртгэлийн (build_timesheet) ажилтны үндсэн мөр дээр өөр албан тушаалд
  шилжин ажилласан мөрүүдийн хоногийг нэмнэ. Бямбыг ажилласан хоногт оруулдаггүй мөрөнд Бямбад ажилласан
  өдрүүд нэмэгдэнэ (цалин бодолтын унааны мөнгөтэй ижил дүрэм).
- Албан тушаал бүрээр (үндсэн, шилжин ажилласан) тусад нь, өдрөөр нь бодно: цаг бүртгэлтэй өдөр
  (worked_dates) бүр нэг л удаа тоологдоно (хоёр албан тушаалаар ажилласан өдөр эхнийх буюу үндсэнд нь), тэр
  өдөр хоол идээгүй бол тухайн албан тушаалын мөнгө (харуул 15,000, бусад 12,000 г.м.). Цаг бүртгэлгүй өдөр
  хоол идсэн нь ажилласан өдрийг "нөхөхгүй". Ажилласан хоногийг гараар бичсэн / ажиллавал зохихоор бөглөдөг
  (огноо нь таарахгүй) мөрөнд: идээгүй өдөр = ажилласан хоног - (бусад мөрөнд ороогүй) идсэн өдөр.
- Ажилчдын жагсаалтад байхгүй нэрс (зочин г.м.) идсэн өдрөөрөө тусдаа мөр болж орно (мөнгө олгохгүй).
- Бүх тоон багана нь 0 (ажиллаагүй, хоол идээгүй) мөрийг харуулахгүй.
- Гар засвар (MealAllowanceEntry, зөвхөн Ерөнхий нягтлан): ажилласан / идсэн / идээгүй өдрийг дарж бичнэ.
  Идээгүй өдрийг бичвэл олгох дүн = түүнийг x мөнгө (албан тушаалаар задлахгүй, үндсэн албан тушаалын мөнгө);
  зөвхөн ажилласан / идсэн өдрийг бичвэл идээгүй өдөр = автомат идээгүй + ажилласан хоногийн өөрчлөлт -
  идсэн тооны өөрчлөлт (харуул өдөрт 2 удаа иддэг тул "ажилласан - идсэн" биш).
- "Мөнгө олгохгүй" (EmployeePayProfile.eats_meals=False) ажилтанд хоолны мөнгө олгохгүй (0); хүснэгтэд харагдаж,
  идсэн тоонд нь тоологдсоор байна (filter_rows-ийн meals='yes'/'no'-оор ялгаж харж болно).
- Албан тушаалын мөнгө ижил бол задлахгүй - өөр өөр мөнгөтэй үед л breakdown-оор харуулна.
- Идсэн: тухайн сард Хоол идэх нэрсийн бүртгэлд (MealAttendanceName) ажилтны нэр бичигдсэн тоо - хоолны
  нэгтгэлтэй тэнцүү (харуул 24 цагийн ээлжиндээ нэг өдөр 2 удаа идвэл 2). Нэрийг ажилтны нэртэй (зай, том жижиг
  үсгийг үл харгалзан) тулгана. Идээгүй өдрийг харин өдрөөр нь (тэр өдөр нэг ч удаа идээгүй) тоолно.
- Идээгүй өдөр = max(ажилласан хоног - идсэн өдөр, 0); Олгох дүн = идээгүй өдөр x өдрийн мөнгө.
- Өдрийн мөнгө: ажилтны EmployeePayProfile.meal_allowance_per_day -> албан тушаалын
  AttendancePositionRule.meal_allowance_per_day -> PayrollSetting-ийн анхдагч (0 бол олгохгүй).
- Банкны данс: бэлэн цалингийн данс (EmployeePayProfile), байхгүй бол ажилтны мэдээлэл дэх (картын цалингийн) данс.
"""
import calendar
from datetime import date
from decimal import Decimal

from shop.services.bank_accounts import BANK_SHORT_NAMES, print_account
from shop.services.payroll import money

ZERO = Decimal(0)


def _name_key(name):
    return ' '.join((name or '').split()).lower()


def _account(cash_account, card_account, card_bank):
    """Хэвлэх загвартай дансны бичвэр: бэлэн данс, үгүй бол картын данс (IBAN биш бол банкны нэрийг ард нь)."""
    if (cash_account or '').strip():
        return print_account(cash_account), 'cash'
    card_account = (card_account or '').strip()
    if not card_account:
        return '', ''
    text = print_account(card_account)
    short = BANK_SHORT_NAMES.get((card_bank or '').strip())
    if short and not text.endswith(short):
        text = f'{text} {short}'
    return text, 'card'


def build_meal_allowance(year, month):
    """(rows, unmatched, setting): rows - ажилтан бүрийн мөр (Хоног бүртгэлийн дарааллаар), төгсгөлд нь
    ажилчдын жагсаалтад байхгүй нэрсийн мөр; unmatched - тэдгээр нэрс [(нэр, өдрийн тоо)]."""
    from django.db import connection

    from datamigration.models import OpenDataEmployee
    from shop.models import (
        AttendancePositionRule, EmployeePayProfile, MealAllowanceEntry, MealAttendanceName, PayrollSetting,
    )
    from shop.services.timesheet import build_timesheet

    setting = PayrollSetting.get()
    position_rates = dict(
        AttendancePositionRule.objects.exclude(meal_allowance_per_day__isnull=True)
        .values_list('position_name', 'meal_allowance_per_day')
    )
    _, _, all_timesheet_rows, _, _ = build_timesheet(year, month)

    def days_of(t):
        days = Decimal(t['worked_days'])
        if not t.get('saturday_in_worked_days', True):
            days += Decimal(t['saturday_days'])
        return days

    # Ажилтан бүрийн албан тушаалын мөрүүд: үндсэн (эхэнд) + шилжин ажилласан (is_main=False)
    parts_by_code = {}
    for t in all_timesheet_rows:
        parts = parts_by_code.setdefault(t['employee_code'], [])
        if t.get('is_main', True):
            parts.insert(0, t)
        else:
            parts.append(t)
    timesheet_rows = [t for t in all_timesheet_rows if t.get('is_main', True)]
    codes = [t['employee_code'] for t in timesheet_rows]

    profiles = {p.employee_code: p for p in EmployeePayProfile.objects.filter(employee_code__in=codes)}
    manual_entries = {e.employee_code: e for e in MealAllowanceEntry.objects.filter(year=year, month=month)}
    departments = dict(OpenDataEmployee.objects.filter(id__in=codes).values_list('id', 'departmentname'))
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "BankName", "BankAccountId" FROM "OpenDataEmployee" WHERE "Id" = ANY(%s)', [codes])
        card_accounts = {code: (bank, account) for code, bank, account in cursor.fetchall()}

    # Хоолны бүртгэл: нэр -> идсэн өдрүүд
    date_from = date(year, month, 1)
    date_to = date(year, month, calendar.monthrange(year, month)[1])
    eaten = {}
    meal_counts = {}  # нэр -> бичигдсэн тоо (нэг өдөр 2 удаа бол 2)
    labels = {}
    for name, day in MealAttendanceName.objects.filter(
        attendance__date__gte=date_from, attendance__date__lte=date_to,
    ).values_list('name', 'attendance__date'):
        key = _name_key(name)
        if key:
            eaten.setdefault(key, set()).add(day)
            meal_counts[key] = meal_counts.get(key, 0) + 1
            labels.setdefault(key, ' '.join(name.split()))

    pay_labels = dict(EmployeePayProfile.PAY_CHOICES)
    rows = []
    reconcile = []
    matched = set()
    def position_rate_of(position):
        rate = position_rates.get(position)
        return setting.meal_allowance_per_day if rate is None else rate

    for t in timesheet_rows:
        code = t['employee_code']
        profile = profiles.get(code)
        key = _name_key(t['name'])
        matched.add(key)
        eaten_dates = eaten.get(key, set())
        eats_meals = profile.eats_meals if profile else True
        custom_rate = profile.meal_allowance_per_day if profile else None

        # Албан тушаал бүрээр, өдрөөр: цаг бүртгэлийн огноо нь ажилласан хоногтой таарвал (date_based) өдөр бүрийг
        # нэг л удаа (эхний буюу үндсэн мөрт нь) тоолж, тэр өдөр идсэн эсэхээр; эс бөгөөс тоогоор нь бодно
        parts = parts_by_code[code]
        claimed = set()
        part_counts = []  # (ажилласан, идсэн) эсвэл огноо таарахгүй бол None
        for p in parts:
            dates = set(p.get('worked_dates', ()))
            if dates and Decimal(len(dates)) == days_of(p):
                own = dates - claimed
                claimed |= own
                part_counts.append((Decimal(len(own)), Decimal(len(own & eaten_dates))))
            else:
                part_counts.append(None)
        date_based = list(part_counts)  # None - огноо нь ажилласан хоногтой таарахгүй мөр
        # Огноо таарахгүй мөрүүдийн эхнийхэд бусад мөрөнд ороогүй идсэн өдрүүдийг онооно
        leftover_eaten = Decimal(len(eaten_dates - claimed))
        for i, counts in enumerate(part_counts):
            if counts is None:
                part_counts[i] = (days_of(parts[i]), leftover_eaten)
                leftover_eaten = ZERO
        breakdown = []
        for p, (worked, eaten_count) in zip(parts, part_counts):
            if not worked and p is not parts[0]:
                continue
            rate = custom_rate if custom_rate is not None else position_rate_of(p['positionname'])
            if not eats_meals:
                rate = ZERO
            not_eaten = max(worked - eaten_count, ZERO)
            breakdown.append({
                'position': p['positionname'] or '', 'is_main': p is parts[0], 'worked_days': worked,
                'eaten_days': eaten_count, 'not_eaten_days': not_eaten, 'rate': rate,
                'amount': money(not_eaten * rate),
            })

        auto = {
            'worked_days': sum((b['worked_days'] for b in breakdown), ZERO),
            'eaten_days': Decimal(meal_counts.get(key, 0)),
            'not_eaten_days': sum((b['not_eaten_days'] for b in breakdown), ZERO),
        }
        amount = sum((b['amount'] for b in breakdown), ZERO)
        rates = {b['rate'] for b in breakdown if b['worked_days']} or {breakdown[0]['rate']}

        # Гар засвар: хоосон талбарт автомат утга
        entry = manual_entries.get(code)
        manual = {f: getattr(entry, f) if entry else None for f in auto}
        values = {f: auto[f] if manual[f] is None else manual[f] for f in auto}
        if manual['not_eaten_days'] is None and (manual['worked_days'] is not None or manual['eaten_days'] is not None):
            # Идсэн нь хоолны тоо (харуул өдөрт 2) тул "ажилласан - идсэн" биш - өөрчлөлтийн зөрүүгээр
            values['not_eaten_days'] = max(
                auto['not_eaten_days'] + (values['worked_days'] - auto['worked_days'])
                - (values['eaten_days'] - auto['eaten_days']), ZERO)
        if manual['not_eaten_days'] is not None:
            # Идээгүй өдрийг шууд бичсэн бол албан тушаалаар задлахгүй - үндсэн албан тушаалын мөнгөөр
            main_rate = breakdown[0]['rate']
            rates = {main_rate}
            amount = money(values['not_eaten_days'] * main_rate)
        elif values['not_eaten_days'] != auto['not_eaten_days']:
            # Ажилласан / идсэн тоог зассан бол зөрүүг задаргаанд: нэмэгдэл үндсэн албан тушаалд, хасалтыг
            # үндсэнээс эхлэн (0-ээс доош оруулахгүй)
            delta = values['not_eaten_days'] - auto['not_eaten_days']
            breakdown = [dict(b) for b in breakdown]
            if delta > 0:
                breakdown[0]['not_eaten_days'] += delta
            else:
                for b in breakdown:
                    take = min(b['not_eaten_days'], -delta)
                    b['not_eaten_days'] -= take
                    delta += take
            for b in breakdown:
                b['amount'] = money(b['not_eaten_days'] * b['rate'])
            amount = sum((b['amount'] for b in breakdown), ZERO)
        worked_days, eaten_days = values['worked_days'], values['eaten_days']
        # Хоног бүртгэлтэй тулгах (Ерөнхий нягтланд): хоног бүртгэлийн нийт ажилласан хоногоос ялгаатай шалтгаан
        ts_worked = sum((Decimal(p['worked_days']) for p in parts), ZERO)
        saturday_added = sum((Decimal(p['saturday_days']) for p in parts
                              if not p.get('saturday_in_worked_days', True)), ZERO)
        reconcile.append({
            'name': t['name'], 'timesheet': ts_worked, 'meal': worked_days, 'saturday': saturday_added,
            # Хоёр албан тушаалаар ажилласан өдрийг нэг удаа тоолсон (үлдэгдлээр)
            'shared': auto['worked_days'] - ts_worked - saturday_added,
            'manual': worked_days - auto['worked_days'],
        })
        if not worked_days and not eaten_days and not values['not_eaten_days']:
            continue  # бүх багана 0 - харуулахгүй
        bank, card_account = card_accounts.get(code, ('', ''))
        account, account_source = _account(profile.cash_bank_account if profile else '', card_account, bank)
        rows.append({
            'employee_code': code,
            'is_employee': True,
            'name': t['name'],
            'positionname': t['positionname'] or '',
            'department': departments.get(code) or '',
            'pay_type': profile.pay_type if profile else '',
            'pay_label': pay_labels.get(profile.pay_type, '') if profile else '',
            'worked_days': worked_days,
            'moved_days': ZERO if manual['worked_days'] is not None else auto['worked_days'] - breakdown[0]['worked_days'],
            'eats_meals': eats_meals,
            'eaten_days': eaten_days,
            'not_eaten_days': values['not_eaten_days'],
            'auto': auto,
            'manual': manual,
            'is_manual': any(v is not None for v in manual.values()),
            # Хүснэгтэд тайлбарлах задаргаа (хоёр албан тушаалаар ажилласан, харуул г.м.):
            # албан тушаал бүрийн хоног бүртгэлийн хоног, давхардсан өдөр, хоол идсэн өдрийн тоо, идээгүй өдөр
            'worked_parts': [(p['positionname'] or '', days_of(p)) for p in parts if days_of(p)] if len(parts) > 1 else [],
            'shared_days': (sum((days_of(p) for p in parts), ZERO) - auto['worked_days']) if len(parts) > 1 else ZERO,
            'eaten_day_count': len(eaten_dates),
            # Идсэн өдрийн тоо албан тушаалаар (харуул нэг өдөр 2 удаа иддэг тул тоо нь хоолны тооноос бага)
            'eaten_parts': [(b['position'], b['eaten_days']) for b in breakdown if b['eaten_days']],
            # Цаг бүртгэлгүй өдөр хоол идсэн - ажилласан өдрийг "нөхөхгүй" (огноо нь тулгагдах үед л)
            'eaten_outside_days': len(eaten_dates - claimed) if all(c is not None for c in date_based) else 0,
            'not_eaten_parts': ([(b['position'], b['not_eaten_days']) for b in breakdown]
                                if len(breakdown) > 1 and manual['not_eaten_days'] is None else []),
            # Нэг албан тушаалаар эсвэл ижил мөнгөтэй бол нэг дүн (задлахгүй); өөр өөр мөнгөтэй бол None -
            # breakdown-оор албан тушаал бүрийн тооцоог харуулна
            'rate': next(iter(rates)) if len(rates) == 1 else None,
            'breakdown': breakdown if len(rates) > 1 else [],
            'custom_rate': custom_rate,
            'default_rate': position_rate_of(t['positionname']),
            'position_rate': position_rates.get(t['positionname']),
            'amount': amount,
            'account': account,
            'account_source': account_source,
        })

    # Ажилчдын жагсаалтад байхгүй нэрс (зочин г.м.) - идсэн өдөр л тоологдоно, мөнгө олгохгүй
    unmatched = sorted((labels[k], meal_counts[k]) for k in eaten if k not in matched)
    for name, days in unmatched:
        rows.append({
            'employee_code': '', 'is_employee': False, 'name': name, 'positionname': '', 'department': '',
            'pay_type': '', 'pay_label': '', 'worked_days': ZERO, 'moved_days': ZERO, 'eats_meals': True,
            'eaten_days': Decimal(days), 'not_eaten_days': ZERO, 'rate': None, 'breakdown': [],
            'custom_rate': None, 'default_rate': None, 'position_rate': None, 'amount': ZERO,
            'account': '', 'account_source': '', 'auto': {}, 'manual': {}, 'is_manual': False,
            'worked_parts': [], 'shared_days': ZERO, 'eaten_day_count': len(eaten[_name_key(name)]), 'eaten_outside_days': 0,
            'eaten_parts': [], 'not_eaten_parts': [],
        })
    return rows, unmatched, setting, _reconcile_summary(reconcile, all_timesheet_rows)


RECONCILE_REASONS = [
    ('saturday', 'Бямбад ажилласан өдөр нэмэгдсэн',
     'Хоног бүртгэлд Бямбыг ажилласан хоногт оруулдаггүй ажилтны Бямбад ажилласан өдөр хоолны мөнгөнд тоологдоно'),
    ('shared', 'Хоёр албан тушаалаар ажилласан өдрийг нэг удаа тоолсон',
     'Хоног бүртгэлд нэг өдөр хоёр албан тушаалын мөрөнд хоёуланд нь тоологддог'),
    ('manual', 'Гар засвар',
     'Ерөнхий нягтлан хоолны мөнгөний ажилласан хоногийг гараар зассан'),
]


def _reconcile_summary(items, timesheet_rows):
    """Хоног бүртгэлийн нийт ажилласан хоног ба хоолны мөнгөний (шүүлтгүй) нийт ажилласан хоногийн тулгалт:
    шалтгаан тус бүрийн нийт ба ялгаатай ажилчид."""
    timesheet_total = sum((Decimal(t['worked_days']) for t in timesheet_rows), ZERO)
    meal_total = sum((i['meal'] for i in items), ZERO)
    reasons = []
    for key, label, hint in RECONCILE_REASONS:
        people = [(i['name'], i[key]) for i in items if i[key]]
        reasons.append({'key': key, 'label': label, 'hint': hint, 'total': sum((v for _, v in people), ZERO),
                        'people': people})
    return {
        'timesheet_total': timesheet_total,
        'meal_total': meal_total,
        'diff': meal_total - timesheet_total,
        'reasons': [r for r in reasons if r['total'] or r['people']],
        # Шалтгаанаар тайлбарлагдаагүй үлдэгдэл - 0 байх ёстой
        'unexplained': meal_total - timesheet_total - sum((r['total'] for r in reasons), ZERO),
    }


TOTAL_KEYS = ['worked_days', 'eaten_days', 'not_eaten_days', 'amount']
MANUAL_FIELDS = ['worked_days', 'eaten_days', 'not_eaten_days']
# Хоолны мөнгөний хоног, өдрийг гараар засах, хоног бүртгэлтэй тулгах эрхтэй албан тушаал (superuser-ээс гадна)
MANUAL_EDIT_POSITIONS = {'Ерөнхий нягтлан'}
# Хоолны мөнгө харах, бодох эрхийг Ерөнхий нягтлан асааж / унтраадаг албан тушаал
# (PayrollSetting.meal_allowance_accountant_access)
ACCOUNTANT_POSITIONS = {'Нягтлан'}


def user_position(user):
    """Нэвтэрсэн хэрэглэгчийн албан тушаал (OpenDataEmployee-ийн имэйлээр), олдохгүй бол ''."""
    if not getattr(user, 'email', ''):
        return ''
    from datamigration.models import OpenDataEmployee
    return OpenDataEmployee.objects.filter(email=user.email).values_list('positionname', flat=True).first() or ''


def can_edit_days(user):
    """Хоолны мөнгөний ажилласан / идсэн / идээгүй өдрийг гараар засах, тулгалт харах эрхтэй эсэх."""
    return user.is_superuser or user_position(user) in MANUAL_EDIT_POSITIONS


def accountant_has_access(user):
    """Нягтланд (цэсний эрхгүй ч) хоолны мөнгө харах, бодох эрх - Ерөнхий нягтлан олгосон үед л.
    Бусад хүнд цэсний эрх (shop.access) үйлчилнэ."""
    if not user.is_staff or user_position(user) not in ACCOUNTANT_POSITIONS:
        return False
    from shop.models import PayrollSetting
    return PayrollSetting.get().meal_allowance_accountant_access


def totals_of(rows):
    return {k: sum((r[k] for r in rows), ZERO) for k in TOTAL_KEYS}


# Шүүлтүүрийн сонголтууд
SHOW_LABELS = {
    '': 'Бүгд',
    'payable': 'Олгох дүнтэй',
    'zero': 'Олгох дүнгүй',
    'not_eaten': 'Идээгүй өдөртэй',
}
ACCOUNT_LABELS = {
    '': 'Бүгд',
    'cash': 'Бэлэн цалингийн данстай',
    'card': 'Картын данстай',
    'none': 'Дансгүй',
}
MEALS_LABELS = {
    '': 'Бүгд',
    'yes': 'Мөнгө олгох',
    'no': 'Мөнгө олгохгүй',
}
SORT_LABELS = {
    '': 'Хоног бүртгэлийн дарааллаар',
    'name': 'Нэрээр',
    'amount': 'Олгох дүнгээр (их нь эхэндээ)',
    'not_eaten': 'Идээгүй өдрөөр (их нь эхэндээ)',
}


def filter_rows(rows, params):
    """GET шүүлтүүр: meals (yes/no - мөнгө олгох/олгохгүй, анхдагч бүгд), q (нэр/код/албан тушаал), position, department,
    pay_type, show, account, sort."""
    meals = params.get('meals') or ''
    q = _name_key(params.get('q'))
    position = params.get('position') or ''
    department = params.get('department') or ''
    pay_type = params.get('pay_type') or ''
    show = params.get('show') or ''
    account = params.get('account') or ''
    result = []
    for r in rows:
        if (meals == 'yes' and not r['eats_meals']) or (meals == 'no' and r['eats_meals']):
            continue
        if q and q not in _name_key(f"{r['name']} {r['employee_code']} {r['positionname']}"):
            continue
        if position and r['positionname'] != position:
            continue
        if department and r['department'] != department:
            continue
        if pay_type and r['pay_type'] != pay_type:
            continue
        if show == 'payable' and not r['amount']:
            continue
        if show == 'zero' and r['amount']:
            continue
        if show == 'not_eaten' and not r['not_eaten_days']:
            continue
        if account == 'none' and r['account']:
            continue
        if account in ('cash', 'card') and r['account_source'] != account:
            continue
        result.append(r)
    sort = params.get('sort') or ''
    if sort == 'name':
        result.sort(key=lambda r: r['name'])
    elif sort == 'amount':
        result.sort(key=lambda r: -r['amount'])
    elif sort == 'not_eaten':
        result.sort(key=lambda r: -r['not_eaten_days'])
    return result
