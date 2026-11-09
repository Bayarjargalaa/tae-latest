"""
Цалингийн тулгалт - Хоног бүртгэлийн хоногийг Картын, Бэлэн цалингийн хуудастай тулгаж алдаа, зөрүүг илрүүлнэ.

Борлуулалтын нэмэгдлийн хуудас (SalesBonusEntry) ба цалингийн «Нэмэгдэл цалин /Борлуулалт/»-ыг мөн тулгана
(sales_bonus_issues).

Хаагдаагүй сард цалин хоног бүртгэлээс шууд бодогддог тул хоног өөрөө зөрөхгүй - гол эрсдэл нь тохиргооны дутуу
(олгох хэлбэр, бэлэн / картын үндсэн цалин, нэг гарын мөнгө). Хаагдсан хуудас эцсийнх (ямар ч өөрчлөлт орохгүй) тул
тулгалтад оруулахгүй - сар хаахаас өмнө алдааг илрүүлж засна. Түвшин:
    error   - цалин буруу / дутуу бодогдоно (сар хаахыг хориглоно, мэдсээр байж хаахыг баталгаажуулна)
    warning - шалгах шаардлагатай
    info    - мэдээлэл (санаатай байж болох)
"""
from decimal import Decimal

ZERO = Decimal(0)
LEVEL_ERROR, LEVEL_WARNING, LEVEL_INFO = 'error', 'warning', 'info'
SHEET_LABELS = {'card': 'Картын цалин', 'cash': 'Бэлэн цалин'}
PAY_TYPE_LABELS = {'card': 'Карт', 'cash': 'Бэлэн', 'mixed': 'Хосолсон'}


def expected_sheets(pay_type):
    """Олгох хэлбэрээр ажилтны орох ёстой хуудсууд."""
    return {'card': ['card'], 'cash': ['cash'], 'mixed': ['card', 'cash']}.get(pay_type or '', [])


def _dec(value):
    try:
        return Decimal(value or 0)
    except Exception:  # noqa: BLE001 - хуулбарын хуучин/хоосон утга
        return ZERO


def _fmt(value):
    value = _dec(value)
    return f'{value:,.0f}' if value == value.to_integral() else f'{value:,.1f}'


def check_payroll(year, month, timesheet_rows=None, sheet_data=None):
    """Сарын тулгалтын асуудлуудыг буцаана: [{level, code, name, sheet, kind, message, fix}]. Хаагдсан хуудсыг алгасна.

    timesheet_rows - build_timesheet-ийн мөрүүд (өгөөгүй бол бодно).
    sheet_data     - {sheet: (rows, close)} аль хэдийн уншсан хуудас (өгөөгүй хуудсыг get_payroll-оор уншина)."""
    from shop.models import EmployeePayProfile
    from shop.services.payroll_snapshot import get_payroll
    from shop.services.timesheet import build_timesheet

    if timesheet_rows is None:
        _, _, timesheet_rows, _, _ = build_timesheet(year, month)
    sheet_data = dict(sheet_data or {})
    for sheet in ('card', 'cash'):
        if sheet not in sheet_data:
            rows, _, _, close = get_payroll(year, month, sheet, timesheet_rows=timesheet_rows)
            sheet_data[sheet] = (rows, close)
    by_sheet = {s: {r['employee_code']: r for r in rows} for s, (rows, _) in sheet_data.items()}
    closed = {s: close is not None for s, (_, close) in sheet_data.items()}
    profiles = {p.employee_code: p for p in EmployeePayProfile.objects.all()}

    issues = []

    def add(level, t, kind, message, sheet=None, fix='settings'):
        issues.append({
            'level': level, 'code': t['employee_code'], 'name': t['name'], 'sheet': sheet,
            'sheet_label': SHEET_LABELS.get(sheet, ''), 'kind': kind, 'message': message, 'fix': fix,
            'group': 'days',
        })

    main_rows = {}
    for t in timesheet_rows:
        if t.get('is_main', True):
            main_rows[t['employee_code']] = t
            continue
        # Шилжин ажилласан албан тушаалын мөр цалинд (үндсэн мөрөөр бодно) орохгүй
        if _dec(t['worked_days']) > 0 and not all(closed.values()):
            add(LEVEL_INFO, t, 'moved_days',
                f'«{t["positionname"]}» албан тушаалд шилжин ажилласан {_fmt(t["worked_days"])} хоног цалинд '
                'автоматаар орохгүй - шаардлагатай бол гараар нэмэгдэл оруулна уу', fix='timesheet')

    for code, t in main_rows.items():
        worked = _dec(t['worked_days'])
        active = worked > 0 or _dec(t['worked_hours']) > 0
        profile = profiles.get(code)
        pay_type = profile.pay_type if profile else ''
        sheets = expected_sheets(pay_type)

        if not sheets:
            if active and not all(closed.values()):
                add(LEVEL_ERROR, t, 'no_pay_type',
                    f'{_fmt(worked)} хоног ажилласан боловч олгох хэлбэр (карт/бэлэн/хосолсон) тохируулаагүй - '
                    'аль ч цалингийн хуудсанд ороогүй')
            continue

        for sheet in sheets:
            if closed[sheet]:
                continue
            row = by_sheet[sheet].get(code)
            if row is None:
                continue
            if active and pay_type == 'mixed' and sheet == 'cash' and _dec(row.get('base_salary')) == 0:
                # Хосолсон ажилтан бэлэн хуудсаар зөвхөн нэмэгдэл (борлуулалт, амралт) авч болно - юу ч олгогдохгүй
                # бол бэлэн цалин / нэмэгдлээ оруулахаа мартсан байж магадгүй
                if _dec(row.get('gross')) == 0:
                    what = 'бэлэн нэг гарын мөнгө' if t['is_shift'] else 'бэлэн үндсэн цалин'
                    add(LEVEL_WARNING, t, 'mixed_cash_empty',
                        f'Хосолсон боловч бэлэн хуудсанд олгох дүн 0 ({what}, нэмэгдэл оруулаагүй) - '
                        'бэлэн цалинг оруулахаа мартсан эсэхийг шалгана уу', sheet=sheet)
            elif active and _dec(row.get('base_salary')) == 0:
                if t['is_shift']:
                    what = 'картын нэг гарын мөнгө' if sheet == 'card' else 'бэлэн нэг гарын мөнгө'
                else:
                    what = ('картын үндсэн цалин (ажилтны мэдээллийн BaseSalary)' if sheet == 'card'
                            else 'бэлэн үндсэн цалин')
                add(LEVEL_ERROR, t, 'zero_base',
                    f'{_fmt(worked)} хоног ажилласан боловч {what} 0 - цалин бодогдохгүй', sheet=sheet)

            if _dec(row.get('payout')) < 0:
                add(LEVEL_WARNING, t, 'negative_payout',
                    f'Олгох дүн сөрөг ({_fmt(row.get("payout"))}₮) - суутгал цалингаас их', sheet=sheet, fix='payroll')

        if not all(closed.values()) and not t['is_shift'] and worked > _dec(t['required_days']):
            add(LEVEL_WARNING, t, 'over_required',
                f'Ажилласан хоног ({_fmt(worked)}) ажиллавал зохих хоногоос ({_fmt(t["required_days"])}) их',
                fix='timesheet')

    if not all(closed.values()):
        issues += sales_bonus_issues(year, month, by_sheet, closed, profiles, main_rows)

    order = {LEVEL_ERROR: 0, LEVEL_WARNING: 1, LEVEL_INFO: 2}
    issues.sort(key=lambda i: order[i['level']])
    return issues


def _bonus_people(year, month, settings):
    """Нэмэгдлийн хуудастай ижил: тухайн сарын хүснэгт бүрийн хүмүүс {(код, хүснэгт): (member, alloc)}."""
    from shop.models import SalesBonusMember
    from shop.services import sales_bonus as sb

    people = {(m.employee_code, 'storekeeper'): (m, a) for m, a in sb.storekeeper_people(year, month, settings)}
    for scheme in sb.MONTH_EDITABLE_SCHEMES:
        for m in sb.month_people(year, month, scheme):
            people[(m.employee_code, scheme)] = (m, None)
    for m in SalesBonusMember.objects.filter(is_active=True).exclude(
            scheme__in=('storekeeper',) + tuple(sb.MONTH_EDITABLE_SCHEMES)):
        people[(m.employee_code, m.scheme)] = (m, None)
    return people


def _money(value):
    """Мөнгөн дүн: бүхэл бол таслалгүй, үгүй бол 2 оронтой."""
    value = _dec(value)
    return f'{value:,.0f}' if value == value.to_integral() else f'{value:,.2f}'


def _signed(value):
    return ('+' if value > 0 else '') + _money(value)


# «... цалинд хуваарилсан» - хуудасны нэрийн өгөх-орших тийн ялгал
SHEET_DATIVE = {'card': 'картын цалинд', 'cash': 'бэлэн цалинд'}


def sales_bonus_issues(year, month, by_sheet, closed, profiles, main_rows):
    """Борлуулалтын нэмэгдлийн тулгалт (хаагдаагүй хуудсанд):
    - нэмэгдлийн хуудасны (SalesBonusEntry) карт / бэлэн дүн цалингийн «Нэмэгдэл цалин /Борлуулалт/»-тай таарах эсэх
    - олгох хэлбэрт нь байхгүй хуудсанд хуваарилсан (олгогдохгүй үлдэх) дүн, нийт = карт + бэлэн
    - хадгалсны дараа борлуулалт / түгээлтийн өгөгдөл өөрчлөгдсөн (одоо дахин бодвол өөр дүн)
    - бодогдох нэмэгдэлтэй боловч хадгалаагүй, ажиллаагүй ажилтанд нэмэгдэл, сөрөг нэмэгдэл"""
    from datamigration.models import OpenDataEmployee
    from shop.models import PayrollEntry, PayrollSetting, SalesBonusEntry, SalesBonusMember
    from shop.services import sales_bonus as sb

    scheme_labels = dict(SalesBonusMember.SCHEME_CHOICES)
    settings = sb.get_settings(PayrollSetting.get())
    entries = {(e.employee_code, e.scheme): e for e in SalesBonusEntry.objects.filter(year=year, month=month)}
    payroll_bonus = {(p.employee_code, p.sheet): p.sales_bonus
                     for p in PayrollEntry.objects.filter(year=year, month=month).exclude(sales_bonus=0)}
    people = _bonus_people(year, month, settings)

    codes = {c for c, _ in entries} | {c for c, _ in payroll_bonus} | {c for c, _ in people}
    names = {c: t['name'] for c, t in main_rows.items()}
    names.update({e['id']: e['name'] for e in OpenDataEmployee.objects.filter(id__in=codes - names.keys()).values('id', 'name')})

    issues = []

    def add(level, code, kind, message, sheet=None, fix='sales_bonus'):
        issues.append({
            'level': level, 'code': code, 'name': names.get(code, code), 'sheet': sheet,
            'sheet_label': SHEET_LABELS.get(sheet, ''), 'kind': kind, 'message': message, 'fix': fix,
            'group': 'bonus',
        })

    # 1) Хадгалсан бодолтыг одоогийн өгөгдлөөр дахин бодох / хадгалаагүй ч бодогдох нэмэгдэл
    data = sb.month_data(year, month)
    cs_data = sb.month_data(year, month, *sb.period_range(year, month, 'cash_seller', settings))
    tmaps = {sc: sb.transfers_map(year, month, sc) for sc in ('sales_rep', 'cash_seller')}
    # Нэмэгдлийн хуудас дэлгэцэн дээр хадгалсан дүнг биш, одоогийн өгөгдлөөр шууд бодсоныг харуулдаг -
    # ажилтан бүрийн тэр (харагдаж буй) дүнгийн карт / бэлэн хуваарилалт. Хадгалсан бодолт хуучирсан ч цалин энэ
    # дүнтэй таарвал цалинд зөв орсон гэж үзнэ (зөвхөн дахин хадгалахыг сануулна)
    live = {}
    for (code, scheme), e in entries.items():
        live.setdefault(code, {'card': ZERO, 'cash': ZERO})
        live[code]['card'] += _dec(e.card_amount)
        live[code]['cash'] += _dec(e.cash_amount)
    for (code, scheme), (member, alloc) in people.items():
        entry = entries.get((code, scheme))
        try:
            result = sb.compute(member, entry.inputs if entry else {}, cs_data if scheme == 'cash_seller' else data,
                                settings, alloc, tmaps.get(scheme))
        except Exception:  # noqa: BLE001 - нэмэгдлийн бодолтын алдаанаас болж тулгалт унахгүй
            continue
        now = _dec(result['total'])
        label = scheme_labels.get(scheme, scheme)
        profile = profiles.get(code)
        if entry is not None:
            card_now, cash_now = sb.allocate(now, profile.pay_type if profile else '', entry.cash_amount)
            live[code]['card'] += _dec(card_now) - _dec(entry.card_amount)
            live[code]['cash'] += _dec(cash_now) - _dec(entry.cash_amount)
        # Нэмэгдэл орох хуудсууд бүгд хаагдсан бол (хаагдсан сар өөрчлөгдөхгүй) тулгахгүй
        if entry is not None:
            target = [s for s, a in (('card', entry.card_amount), ('cash', entry.cash_amount)) if _dec(a)] or ['card']
        else:
            target = expected_sheets(profile.pay_type if profile else '') or ['card']
        if all(closed[s] for s in target):
            continue
        if entry is None:
            if now > 0:
                manual = sum(_dec(payroll_bonus.get((code, s))) for s in ('card', 'cash'))
                if manual:
                    add(LEVEL_INFO, code, 'bonus_unsaved_manual',
                        f'{label}: нэмэгдлийн хуудсанд хадгалаагүй (бодогдох {_money(now)}₮), цалинд гараар {_money(manual)}₮ оруулсан')
                else:
                    add(LEVEL_WARNING, code, 'bonus_unsaved',
                        f'{label}: бодогдох {_money(now)}₮ нэмэгдэл хадгалагдаагүй - цалинд ороогүй')
        elif (now - _dec(entry.total)).copy_abs() >= 1:
            add(LEVEL_WARNING, code, 'bonus_stale',
                f'{label}: нэмэгдлийн хуудас одоогийн өгөгдлөөр {_money(now)}₮ харуулж байгаа ч '
                f'{entry.updated_at:%m/%d}-нд хадгалсан бодолт {_money(entry.total)}₮ хэвээр '
                f'({_signed(now - _dec(entry.total))}₮, хадгалсны дараа борлуулалт / түгээлт нэмэгдсэн). '
                'Нэмэгдлийн хуудсыг дахин хадгална уу')

    # 2) Хадгалсан бодолт ба цалингийн хуудас
    by_code = {}
    for (code, scheme), e in entries.items():
        by_code.setdefault(code, []).append(e)
        label = scheme_labels.get(scheme, scheme)
        if (_dec(e.card_amount) + _dec(e.cash_amount) - _dec(e.total)).copy_abs() >= 1:
            add(LEVEL_ERROR, code, 'bonus_split',
                f'{label}: нийт {_money(e.total)}₮ ≠ карт {_money(e.card_amount)} + бэлэн {_money(e.cash_amount)}')
        if _dec(e.total) < 0:
            add(LEVEL_WARNING, code, 'bonus_negative', f'{label}: нэмэгдэл сөрөг ({_money(e.total)}₮)')

    for code, es in by_code.items():
        profile = profiles.get(code)
        pay_type = profile.pay_type if profile else ''
        allowed = expected_sheets(pay_type)
        amounts = {'card': sum(_dec(e.card_amount) for e in es), 'cash': sum(_dec(e.cash_amount) for e in es)}
        for sheet in ('card', 'cash'):
            if closed[sheet]:
                continue
            amount = amounts[sheet]
            if sheet not in allowed:
                if amount:
                    add(LEVEL_ERROR, code, 'bonus_lost',
                        f'Нэмэгдлээс {_money(amount)}₮-г {SHEET_DATIVE[sheet]} хуваарилсан боловч олгох хэлбэр нь '
                        f'{PAY_TYPE_LABELS.get(pay_type, "тохируулаагүй").lower()} - энэ дүн олгогдохгүй', sheet=sheet)
                continue
            row = by_sheet[sheet].get(code)
            in_payroll = _dec(row.get('sales_bonus')) if row else _dec(payroll_bonus.get((code, sheet)))
            shown = live.get(code, amounts)[sheet]
            # Цалин хадгалсан эсвэл хуудсан дээр харагдаж буй (одоогийн) дүнгийн аль нэгтэй таарвал зөв
            if (in_payroll - amount).copy_abs() >= 1 and (in_payroll - shown).copy_abs() >= 1:
                add(LEVEL_ERROR, code, 'bonus_mismatch',
                    f'Нэмэгдлийн хуудсанд {_money(shown)}₮'
                    + (f' (хадгалсан {_money(amount)}₮)' if (shown - amount).copy_abs() >= 1 else '')
                    + f', цалинд {_money(in_payroll)}₮ ({_signed(in_payroll - shown)}₮ зөрүү) - цалин дээрх гар засварыг '
                    'шалгах эсвэл нэмэгдлийн хуудсыг дахин хадгална уу', sheet=sheet)

    # 3) Нэмэгдэлтэй боловч тухайн сард ажиллаагүй
    for code in sorted({c for c, s in payroll_bonus if not closed[s]}):
        total = sum(_dec(payroll_bonus.get((code, s))) for s in ('card', 'cash') if not closed[s])
        t = main_rows.get(code)
        if total > 0 and (t is None or _dec(t['worked_days']) == 0):
            add(LEVEL_WARNING, code, 'bonus_no_work',
                f'{_money(total)}₮ нэмэгдэлтэй боловч энэ сард ажилласан хоноггүй'
                + ('' if t else ' (идэвхтэй ажилчдын хоног бүртгэлд байхгүй)'), fix='timesheet')

    return issues


def summarize(issues, sheet=None, group=None):
    """Загварт харуулах нэгтгэл. sheet өгвөл тухайн хуудасны болон хуудасгүй (ерөнхий) асуудлууд л,
    group өгвөл ('days' - хоног, 'bonus' - борлуулалтын нэмэгдэл) тэр бүлгийнх л."""
    if sheet is not None:
        issues = [i for i in issues if i['sheet'] in (None, sheet)]
    if group is not None:
        issues = [i for i in issues if i['group'] == group]
    counts = {level: sum(1 for i in issues if i['level'] == level) for level in (LEVEL_ERROR, LEVEL_WARNING, LEVEL_INFO)}
    by_code = {}
    for i in issues:
        if i['level'] != LEVEL_INFO:
            by_code.setdefault(i['code'], []).append(i)
    return {
        'issues': issues,
        'errors': counts[LEVEL_ERROR],
        'warnings': counts[LEVEL_WARNING],
        'infos': counts[LEVEL_INFO],
        # Мөрийг тодруулах: {код: 'error'|'warning'}, tooltip: {код: 'мессеж; ...'}
        'row_levels': {c: (LEVEL_ERROR if any(x['level'] == LEVEL_ERROR for x in lst) else LEVEL_WARNING)
                       for c, lst in by_code.items()},
        'row_titles': {c: '\n'.join(f'{"⛔" if x["level"] == LEVEL_ERROR else "⚠"} '
                                    f'{x["sheet_label"] + ": " if x["sheet_label"] else ""}{x["message"]}' for x in lst)
                       for c, lst in by_code.items()},
    }
