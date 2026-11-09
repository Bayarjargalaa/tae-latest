"""
Шатахууны мөнгө олгох тооцоо (Тээврийн хэрэгсэл > "Шатахууны мөнгө олгох тооцоо").

- Ажилчид: Цалингийн тохиргоонд "Шатахууны мөнгө олгох" чеклэсэн (EmployeePayProfile.fuel_allowance) ажилчид
  + тухайн сард бүртгэлтэй (FuelAllowanceEntry) ажилчид - дараа нь чекийг авсан / ажлаас гарсан ч тэр сардаа харагдана.
- Ажиллах хоног, ажилласан хоног: Хоног бүртгэлээс (build_timesheet) - ажиллах хоног нь үндсэн мөрийнх,
  ажилласан хоног нь үндсэн + өөр албан тушаалд шилжин ажилласан мөрүүдийн нийлбэр. Гараар засна
  (FuelAllowanceEntry.required_days / worked_days, хоосон бол хоног бүртгэлийн утга).
- Олговол зохих дүн: гараас оруулна. Тухайн сард оруулаагүй бол өмнөх (хамгийн сүүлд оруулсан) сарын дүн дамжина.
- Олгох дүн = олговол зохих дүн x ажилласан хоног / ажиллах хоног (ажиллах хоног 0 бол 0).
"""
from decimal import Decimal

from shop.services.payroll import money

ZERO = Decimal(0)


def _previous_due(codes, year, month):
    """Ажилтан бүрийн тухайн сараас өмнөх хамгийн сүүлийн олговол зохих дүн."""
    from django.db.models import Q
    from shop.models import FuelAllowanceEntry

    result = {}
    for code, due in (FuelAllowanceEntry.objects
                      .filter(employee_code__in=codes, due_amount__isnull=False)
                      .filter(Q(year__lt=year) | Q(year=year, month__lt=month))
                      .order_by('employee_code', '-year', '-month')
                      .values_list('employee_code', 'due_amount')):
        result.setdefault(code, due)
    return result


def build_fuel_allowance(year, month):
    """Ажилтан бүрийн мөр (Хоног бүртгэлийн дарааллаар, хоног бүртгэлд байхгүй нь төгсгөлд)."""
    from django.db import connection

    from datamigration.models import OpenDataEmployee
    from shop.models import EmployeePayProfile, FuelAllowanceEntry
    from shop.services.bank_accounts import BANK_SHORT_NAMES, print_account
    from shop.services.timesheet import build_timesheet

    entries = {e.employee_code: e for e in FuelAllowanceEntry.objects.filter(year=year, month=month)}
    codes = set(EmployeePayProfile.objects.filter(fuel_allowance=True).values_list('employee_code', flat=True))
    codes |= set(entries)
    if not codes:
        return []
    profiles = {p.employee_code: p for p in EmployeePayProfile.objects.filter(employee_code__in=codes)}

    _, _, timesheet_rows, _, _ = build_timesheet(year, month)
    order, main_rows, worked = [], {}, {}
    for t in timesheet_rows:
        code = t['employee_code']
        if code not in codes:
            continue
        if t.get('is_main', True):
            main_rows[code] = t
            order.append(code)
        worked[code] = worked.get(code, ZERO) + Decimal(t['worked_days'])

    employees = {e.id: e for e in OpenDataEmployee.objects.filter(id__in=codes)}
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Id", "BankName", "BankAccountId" FROM "OpenDataEmployee" WHERE "Id" = ANY(%s)', [list(codes)])
        card_accounts = {code: (bank or '', account or '') for code, bank, account in cursor.fetchall()}
    previous_due = _previous_due(codes, year, month)

    rest = sorted(codes - set(order), key=lambda c: (employees[c].name if c in employees else c))
    rows = []
    for code in order + rest:
        t = main_rows.get(code)
        e = employees.get(code)
        entry = entries.get(code)
        profile = profiles.get(code)
        auto_required = Decimal(t['required_days']) if t else ZERO
        auto_worked = worked.get(code, ZERO)
        required = entry.required_days if entry and entry.required_days is not None else auto_required
        worked_days = entry.worked_days if entry and entry.worked_days is not None else auto_worked
        if entry and entry.due_amount is not None:
            due, due_source = entry.due_amount, 'manual'
        elif code in previous_due:
            due, due_source = previous_due[code], 'previous'
        else:
            due, due_source = None, ''
        amount = money(due * worked_days / required) if due and required else ZERO

        cash_account = profile.cash_bank_account if profile else ''
        bank, card_account = card_accounts.get(code, ('', ''))
        if cash_account.strip():
            account = print_account(cash_account)
        elif card_account.strip():
            account = print_account(card_account)
            short = BANK_SHORT_NAMES.get(bank.strip())
            if short and not account.endswith(short):
                account = f'{account} {short}'
        else:
            account = ''
        rows.append({
            'employee_code': code,
            'name': (t['name'] if t else None) or (e.name if e else code),
            'positionname': ((t['positionname'] if t else None) or (e.positionname if e else '')) or '',
            'department': (e.departmentname if e else '') or '',
            'active': bool(e and e.isreclusion == 'N'),
            'enabled': bool(profile and profile.fuel_allowance),
            'in_timesheet': t is not None,
            'required_days': required,
            'worked_days': worked_days,
            'auto_required_days': auto_required,
            'auto_worked_days': auto_worked,
            'required_manual': bool(entry and entry.required_days is not None),
            'worked_manual': bool(entry and entry.worked_days is not None),
            'due_amount': due,
            'due_source': due_source,
            'amount': amount,
            'account': account,
        })
    return rows


def totals_of(rows):
    return {
        'due_amount': sum((r['due_amount'] or ZERO for r in rows), ZERO),
        'amount': sum((r['amount'] for r in rows), ZERO),
    }
