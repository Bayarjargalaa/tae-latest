"""
Цалин бодолт - Хоног бүртгэлийн (build_timesheet) хоног/цаг дээр суурилан карт, бэлэн хуудсыг тусад нь бодно.

- Хуудсанд орох ажилчид: EmployeePayProfile.pay_type-аар (карт -> картын, бэлэн -> бэлэн, хосолсон -> хоёуланд)
- Ажилтны мэдээлэл (OpenDataEmployee) зөвхөн ажилтны үндсэн хуудсанд орно:
    * Карт, хосолсон -> картын хуудсанд: үндсэн цалин (BaseSalary), НДШ код (InsuredTypeId),
      удаан жилийн нэмэгдэл (D4), хадгаламж (D5), эрсдэлийн сан (D6), хуримтлал (D7)
    * Бэлэн -> бэлэн хуудсанд үндсэн цалингаас бусад нь (D4, D6, D7); бэлэн үндсэн цалинг тохиргоонд гараар оруулна
  Хосолсон ажилтны бэлэн хуудсанд зөвхөн гараар оруулсан бэлэн үндсэн цалин орно
- Нийт цалин (үндсэн)   = үндсэн цалин + удаан жилийн нэмэгдэл
- Бодогдсон цалин      = нийт цалин / ажиллавал зохих цаг x ажилласан цаг (ажиллавал зохих цаг 0 бол 0)
  Ээлжийн ажилтанд: үндсэн цалин = нэг гарын мөнгө x ажилласан хоног, цагаар хувьтгахгүй
- Бямбад ажилласан нэмэгдэл = үндсэн цалин / ажиллавал зохих цаг x Бямбад ажилласан цаг x ажилтны Бямбын нэмэгдлийн %
- Унааны мөнгө = ажилласан хоног x хоногийн унааны мөнгө (PayrollSetting); хосолсон бол зөвхөн картын хуудсанд.
  Бямбад ажилладаггүй горимтой ч Бямбад ажилласан бол (ажилласан хоногт ороогүй) тэр өдрүүд нэмэгдэнэ.
  Унааны мөнгө бодохгүй албан тушаалд (AttendancePositionRule.no_transport) 0
- Бэлэн хуудсанд Бямбад ажилласан нэмэгдэл, унааны мөнгийг гараар дарж бичиж болно (OVERRIDE_FIELDS; 0 ч байж болно)
- Бодогдсон нийт цалин = бодогдсон цалин + Бямбад ажилласан нэмэгдэл + амралтын мөнгө + борлуулалтын нэмэгдэл + унааны мөнгө
- Картын хуудсанд:
    НДШ ажилтан/байгууллага = min(нийт цалин, НДШ-ийн дээд хэмжээ) x хувь
      (хувь: ажилтанд тусгайлан оруулсан -> НДШ-ийн кодын (NdshCodeRate) -> анхдагч (PayrollSetting))
    ХХОАТ тооцох дүн        = нийт цалин - НДШ ажилтан
    Хөнгөлөлт               = НДШ хассан дүнгийн (ХХОАТ тооцох дүн) шатлалаар (PayrollTaxCredit)
    ХХОАТ                   = max(ХХОАТ тооцох дүн x хувь - хөнгөлөлт, 0)
  Бэлэн хуудсанд татварын суутгал байхгүй.
- Гарт олгох = нийт цалин - нийт татварын суутгал - суутгалууд + ХЧТА (байгууллага, НД-с)
- Картанд орох / Бэлнээр олгох = гарт олгох - хадгаламж (OpenDataEmployee.D5, ажилтны үндсэн хуудсанд)
"""
from decimal import ROUND_HALF_UP, Decimal

from shop.services.timesheet import build_timesheet

ZERO = Decimal(0)

# Сар бүр гараар оруулах багана (PayrollEntry-ийн талбар, толгойн нэр)
EARNING_FIELDS = [
    ('holiday_pay', 'Амралтын мөнгө'),
    ('sales_bonus', 'Нэмэгдэл цалин /Борлуулалт/'),
]
# Суутгал: (талбар, толгой, гараар оруулах эсэх) - гараар бусад нь ажилтны мэдээллээс (D6, D7)
DEDUCTION_COLUMNS = [
    ('advance', 'Урьдчилгаа', True),
    ('risk_fund', 'Эрсдэлийн сан', False),
    ('employee_savings', 'Хуримтлал', False),
    ('inventory_shortage', 'Тооллогын дутагдал', True),
    ('goods_deduction', 'Барааны суутгал', True),
    ('phone_fee', 'Ярианы төлбөр', True),
    ('fine', 'Торгууль', True),
    ('other_deduction', 'Бусад суутгал', True),
]
DEDUCTION_FIELDS = [(f, label) for f, label, is_manual in DEDUCTION_COLUMNS if is_manual]
AUTO_DEDUCTION_FIELDS = [f for f, _, is_manual in DEDUCTION_COLUMNS if not is_manual]
BENEFIT_FIELDS = [
    ('sick_employer', 'ХЧТА-н мөнгө байгууллага'),
    ('sick_fund', 'ХЧТА-н мөнгө НД-с'),
]
MANUAL_FIELDS = [f for f, _ in EARNING_FIELDS + DEDUCTION_FIELDS + BENEFIT_FIELDS]
# Автомат баганыг гараар дарж бичих: (баганы түлхүүр, PayrollEntry-ийн талбар). NULL бол автомат утга
OVERRIDE_FIELDS = [('saturday_bonus', 'saturday_bonus_override'), ('transport', 'transport_override')]


def entry_has_values(entry):
    """PayrollEntry-д хадгалах утга үлдсэн эсэх: 0-ээс өөр гар утга, эсвэл гараар дарж бичсэн (0 ч байж болно) утга."""
    return any(getattr(entry, f) for f in MANUAL_FIELDS) or any(
        getattr(entry, f) is not None for _, f in OVERRIDE_FIELDS)


def money(value, places=0):
    """Бүхэл төгрөгөөр (places=2 бол мөнгөөр) бөөрөнхийлнө."""
    return Decimal(value).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)


def tax_credit_for(income, credits):
    """Сарын НДШ хассан цалингийн дүнд тохирох ХХОАТ-ын хөнгөлөлт (credits нь income_to өсөхөөр, хоосон нь төгсгөлд)."""
    for c in credits:
        if c.income_to is None or income <= c.income_to:
            return c.credit_amount
    return ZERO


def build_payroll(year, month, sheet, employee_code=None):
    """Сарын цалин бодолтын хүснэгтийг буцаана: (rows, totals, setting). sheet: 'card' эсвэл 'cash'.
    employee_code өгвөл зөвхөн тэр ажилтныг (хувийн мэдээлэл дэх "Цалингийн мэдээлэл") бодно."""
    from datamigration.models import OpenDataEmployee
    from shop.models import (
        AttendancePositionRule, EmployeePayProfile, NdshCodeRate, PayrollEntry, PayrollSetting, PayrollTaxCredit,
    )

    is_card = sheet == PayrollEntry.SHEET_CARD
    pay_types = {EmployeePayProfile.PAY_CARD if is_card else EmployeePayProfile.PAY_CASH, EmployeePayProfile.PAY_MIXED}
    profile_qs = EmployeePayProfile.objects.filter(pay_type__in=pay_types)
    entry_qs = PayrollEntry.objects.filter(year=year, month=month, sheet=sheet)
    if employee_code is not None:
        profile_qs = profile_qs.filter(employee_code=employee_code)
        entry_qs = entry_qs.filter(employee_code=employee_code)
    profiles = {p.employee_code: p for p in profile_qs}
    entries = {e.employee_code: e for e in entry_qs}
    setting = PayrollSetting.get()
    credits = list(PayrollTaxCredit.objects.all())
    code_rates = {r.code: r for r in NdshCodeRate.objects.all()}
    no_transport_positions = set(
        AttendancePositionRule.objects.filter(no_transport=True).values_list('position_name', flat=True)
    )

    _, _, timesheet_rows, _, _ = build_timesheet(year, month, employee_code)
    employee_extras = {
        e['id']: e for e in OpenDataEmployee.objects.filter(id__in=profiles.keys()).values(
            'id', 'basesalary', 'insuredtypeid', 'd4', 'd5', 'd6', 'd7',
        )
    }

    rows = []
    for t in timesheet_rows:
        # Өөр албан тушаалд шилжин ажилласан өдрүүдийн мөрийг (хоног бүртгэлд тусдаа) цалинд оруулахгүй -
        # ажилтны цалинг үндсэн албан тушаалын мөрөөр нь бодно
        if not t.get('is_main', True):
            continue
        profile = profiles.get(t['employee_code'])
        if not profile:
            continue
        entry = entries.get(t['employee_code'])
        manual = {f: (getattr(entry, f) if entry else ZERO) for f in MANUAL_FIELDS}

        # Ажилтны мэдээлэл (D4/D6/D7) нь ажилтны үндсэн хуудсанд л (хосолсон бол картад) тооцогдоно
        primary_sheet = PayrollEntry.SHEET_CASH if profile.pay_type == EmployeePayProfile.PAY_CASH else PayrollEntry.SHEET_CARD
        extras = employee_extras.get(t['employee_code'], {}) if sheet == primary_sheet else {}
        seniority_bonus = money(extras.get('d4') or 0)
        auto_deductions = {
            'risk_fund': money(extras.get('d6') or 0),
            'employee_savings': money(extras.get('d7') or 0),
        }

        required_hours = Decimal(t['required_hours'])
        worked_hours = Decimal(t['worked_hours'])
        if t['is_shift']:
            # Ээлжийн ажилтан: нэг гарын мөнгө x ажилласан хоног (цагаар хувьтгахгүй)
            shift_pay = profile.card_shift_pay if is_card else profile.cash_shift_pay
            base_salary = money(shift_pay * Decimal(t['worked_days']))
            nominal_salary = base_salary + seniority_bonus
            earned_salary = nominal_salary
        else:
            shift_pay = None
            # Картын үндсэн цалин ажилтны мэдээллээс (BaseSalary), бэлэн нь тохиргооноос
            base_salary = money(extras.get('basesalary') or 0) if is_card else profile.cash_base_salary
            nominal_salary = base_salary + seniority_bonus
            earned_salary = money(nominal_salary / required_hours * worked_hours) if required_hours else ZERO
        saturday_hours = Decimal(t['saturday_days']) * setting.saturday_hours_per_day
        saturday_bonus = (
            money(base_salary / required_hours * saturday_hours * profile.saturday_bonus_percent / 100, places=2)
            if required_hours else ZERO
        )
        # Хосолсон ажилтанд хоёр хуудсанд давхардахгүйн тулд зөвхөн үндсэн хуудсанд нь
        transport_days = Decimal(t['worked_days'])
        if not t.get('saturday_in_worked_days', True):
            transport_days += Decimal(t['saturday_days'])
        transport = (
            money(transport_days * setting.transport_per_day)
            if sheet == primary_sheet and t['positionname'] not in no_transport_positions else ZERO
        )
        # Гараар дарж бичсэн утга (0 ч байж болно) автомат утгыг орлоно
        auto_values = {'saturday_bonus': saturday_bonus, 'transport': transport}
        overrides = {key: getattr(entry, f, None) if entry else None for key, f in OVERRIDE_FIELDS}
        if overrides['saturday_bonus'] is not None:
            saturday_bonus = overrides['saturday_bonus']
        if overrides['transport'] is not None:
            transport = overrides['transport']
        gross = earned_salary + saturday_bonus + sum(manual[f] for f, _ in EARNING_FIELDS) + transport

        ndsh_employee_rate = ndsh_employer_rate = ZERO
        ndsh_employee = ndsh_employer = taxable = credit = pit = ZERO
        if is_card:
            code_rate = code_rates.get(extras.get('insuredtypeid') or '')

            def pick_rate(kind):
                """Ажилтанд тусгайлан оруулсан -> НДШ-ийн кодын -> анхдагч хувь (kind: 'employee' / 'employer')."""
                for value in (
                    getattr(profile, f'ndsh_{kind}_rate'),
                    getattr(code_rate, f'{kind}_rate') if code_rate else None,
                ):
                    if value is not None:
                        return value
                return getattr(setting, f'ndsh_{kind}_rate')

            ndsh_employee_rate = pick_rate('employee')
            ndsh_employer_rate = pick_rate('employer')
            ndsh_base = min(gross, setting.ndsh_max_base)
            ndsh_employee = money(ndsh_base * ndsh_employee_rate / 100)
            ndsh_employer = money(ndsh_base * ndsh_employer_rate / 100)
            taxable = gross - ndsh_employee
            # Хуулиар хөнгөлөлтийн шатыг жилийн (сарын) цалингийн орлогоос НДШ хассан дүнгээр тодорхойлно
            credit = tax_credit_for(taxable, credits) if taxable > 0 else ZERO
            pit = max(money(taxable * setting.pit_rate / 100) - credit, ZERO)
        total_tax = ndsh_employee + pit

        deductions = sum(manual[f] for f, _ in DEDUCTION_FIELDS) + sum(auto_deductions.values())
        benefits = sum(manual[f] for f, _ in BENEFIT_FIELDS)
        net_pay = gross - total_tax - deductions + benefits
        # Гарт олгохоос хадгаламж (D5) хасаж картанд / бэлнээр олгоно
        deposit = money(extras.get('d5') or 0)
        payout = net_pay - deposit

        rows.append({
            'employee_code': t['employee_code'],
            'name': t['name'],
            'positionname': t['positionname'],
            'is_shift': t['is_shift'],
            'shift_pay': shift_pay,
            'base_salary': base_salary,
            'seniority_bonus': seniority_bonus,
            'nominal_salary': nominal_salary,
            'required_days': t['required_days'],
            'required_hours': required_hours,
            'worked_days': t['worked_days'],
            'worked_hours': worked_hours,
            'saturday_hours': saturday_hours,
            'saturday_bonus': saturday_bonus,
            'transport': transport,
            'saturday_bonus_percent': profile.saturday_bonus_percent,
            'saturday_bonus_auto': auto_values['saturday_bonus'],
            'saturday_bonus_override': overrides['saturday_bonus'],
            'transport_auto': auto_values['transport'],
            'transport_override': overrides['transport'],
            'cash_bank_account': '' if is_card else profile.cash_bank_account,
            'earned_salary': earned_salary,
            'gross': gross,
            'ndsh_code': (extras.get('insuredtypeid') or '') if is_card else '',
            'ndsh_employee_rate': ndsh_employee_rate,
            'ndsh_employee': ndsh_employee,
            'ndsh_employer_rate': ndsh_employer_rate,
            'ndsh_employer': ndsh_employer,
            'taxable': taxable,
            'credit': credit,
            'pit': pit,
            'total_tax': total_tax,
            'net_pay': net_pay,
            'deposit': deposit,
            'payout': payout,
            **manual,
            **auto_deductions,
        })

    return rows, payroll_totals(rows), setting


TOTAL_KEYS = [
    'base_salary', 'seniority_bonus', 'nominal_salary', 'required_days', 'required_hours', 'worked_days',
    'worked_hours', 'saturday_hours', 'saturday_bonus', 'transport', 'earned_salary', 'gross', 'ndsh_employee', 'ndsh_employer', 'taxable',
    'credit', 'pit', 'total_tax', 'net_pay', 'deposit', 'payout',
] + MANUAL_FIELDS + AUTO_DEDUCTION_FIELDS


def payroll_totals(rows):
    """Цалин бодолтын мөрүүдийн нийт дүн (хаагдсан сарын хуулбарт ч дахин бодоход ашиглана)."""
    return {k: sum((Decimal(r[k]) for r in rows), ZERO) for k in TOTAL_KEYS}


# Ажилчдын авлага (OpenDataRecPay, CustomerId = ажилтны код) -> цалингийн суутгалын багана
RECEIVABLE_ACCOUNTS = [
    ('120106', 'goods_deduction', 'Ажилчид бараа'),
    ('120107', 'inventory_shortage', 'Тооллогын зөрүү'),
    ('120112', 'phone_fee', 'Ярианы төлбөр'),
    ('120605', 'fine', 'Тээврийн хэрэгслийн торгууль'),
]


def receivable_balances(codes, as_of):
    """{ажилтны код: {талбар: үлдэгдэл}} - as_of огноо хүртэлх (дебит - кредит) үлдэгдэл, зөвхөн эерэг нь."""
    from django.db import connection

    field_by_account = {acc: field for acc, field, _ in RECEIVABLE_ACCOUNTS}
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT "CustomerId", "AccountId", SUM(COALESCE("DebitAmt", 0) - COALESCE("CreditAmt", 0))
            FROM "OpenDataRecPay"
            WHERE "AccountId" = ANY(%s) AND "CustomerId" = ANY(%s) AND "DocumentDate" <= %s
            GROUP BY 1, 2
            ''', [list(field_by_account), list(codes), as_of])
        result = {}
        for code, account, balance in cursor.fetchall():
            balance = money(balance or 0, places=2)
            if balance > 0:
                result.setdefault(code, {})[field_by_account[account]] = balance
    return result


def pull_receivables(year, month, sheet, user=None):
    """Сарын эцсийн авлагын үлдэгдлийг цалин бодолтын суутгалын баганад бичнэ (PayrollEntry).
    Карт, хосолсон ажилтных картын хуудсанд, зөвхөн бэлэн ажилтных бэлэн хуудсанд. Дахин дуудахад шинэчилнэ
    (үлдэгдэлгүй бол 0). Буцаах: (ажилтны тоо, нийт дүн)."""
    import calendar
    from datetime import date

    from shop.models import EmployeePayProfile, PayrollEntry

    pay_types = ([EmployeePayProfile.PAY_CARD, EmployeePayProfile.PAY_MIXED] if sheet == PayrollEntry.SHEET_CARD
                 else [EmployeePayProfile.PAY_CASH])
    codes = list(EmployeePayProfile.objects.filter(pay_type__in=pay_types).values_list('employee_code', flat=True))
    as_of = date(year, month, calendar.monthrange(year, month)[1])
    balances = receivable_balances(codes, as_of)
    fields = [field for _, field, _ in RECEIVABLE_ACCOUNTS]
    entries = {e.employee_code: e for e in PayrollEntry.objects.filter(year=year, month=month, sheet=sheet, employee_code__in=codes)}
    total = ZERO
    for code in codes:
        values = {f: balances.get(code, {}).get(f, ZERO) for f in fields}
        total += sum(values.values())
        entry = entries.get(code)
        if entry is None:
            if any(values.values()):
                PayrollEntry.objects.create(employee_code=code, year=year, month=month, sheet=sheet, updated_by=user, **values)
            continue
        for f, v in values.items():
            setattr(entry, f, v)
        if not entry_has_values(entry):
            entry.delete()
        else:
            entry.updated_by = user
            entry.save()
    return len(balances), total, as_of
