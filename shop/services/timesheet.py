"""
Хоног бүртгэл - Цаг бүртгэлийн (build_attendance_rows) мөрүүдийг ажилтан тус бүрээр сарын дүнгээр нэгтгэнэ.

- Ажиллавал зохих хоног: албан тушаалын ажлын горимоор (AttendancePositionRule.schedule_type)
    * Бямбад ажилладаггүй - сарын ажлын өдрүүд (Да-Ба)
    * Бямбад ажилладаг    - ажлын өдрүүд + Бямба гарагууд
    * Ээлжийн             - ажилласан хоногтой тэнцүү; цагийн баганууд хоногийн тоогоор (x 8 биш)
  Байгууллагаас зарласан амралтын өдрүүд (OrganizationHoliday) ажлын өдрүүдээс хасагдана.
- Ажилласан хоног: Цаг бүртгэлд тухайн ажилтны мөр гарсан өдрийн тоо; ажилласан цаг = хоног x 8 - цагийн чөлөө.
  Бямба гарагийг ажиллавал зохих болон ажилласан хоногт оруулах эсэхийг ажилтны тохиргоо
  (EmployeePayProfile.saturday_in_worked_days) тодорхойлно, тохируулаагүй бол албан тушаалын горимоор.
- Хоногийн зөрүү (ажиллавал зохих - ажилласан): тухайн сард гар утга хадгалаагүй бол зөрүүг
  чөлөөтэй хоногт санал болгож бөглөнө; ээлжийн амралт + чөлөөтэй хоногоор тайлбарлагдаагүй зөрүүг тодруулна.
  Цаг бүртгүүлдэггүй албан тушаалд (AttendancePositionRule.worked_equals_required) ажиллавал зохих хоногтой тэнцүү.
- Ажиллавал зохих хоногийг онцгой тохиолдолд бүх ажилтанд, ажилласан хоногийг 'худалдагч' агуулсан албан тушаалд
  гараар дарж бичиж болно (TimesheetEntry) - тооцоолсон утгаас өөр бол л хадгалагдана.
- Бямбад ажилласан: цаг бүртгэлд гарсан Бямба гарагуудын тоо, гараар засч болно; ээлжийн ажилчдад тоолохгүй (0).
- Хоцролт: Цаг бүртгэлийн хоцролтын багцуудын нийлбэр (20-с дээш минут бүгд '21-30' баганад).
- Суутгал: багц бүрийн минут x TimesheetSetting-ийн минут тутмын үнэлгээ.
- Өөр албан тушаалд шилжин ажилласан өдрүүд (Цаг бүртгэлийн мөрийн албан тушаал, AttendanceRecord.position_name)
  ажилтны үндсэн мөрийн доор тухайн албан тушаалын тусдаа мөрөөр гарч, тэр албан тушаалын горимоор тооцогдоно
  (жиш: харуул 10 хоног - ээлжийн зарчмаар, туслах 1 хоног - туслахын зарчмаар). Тусдаа мөрийн ажиллавал зохих
  хоног = тэнд ажилласан хоног; үндсэн мөрийн ажиллавал зохих хоногоос тэр өдрүүд хасагдана. Албан тушаал
  хавсарч ажилласан өдөр (AttendanceRecord.is_additional - нэг өдөр хоёр албан тушаал) хоёр мөрөнд хоёуланд нь
  тоологдож, үндсэн мөрөөс хасагдахгүй.
"""
import calendar
from datetime import date
from decimal import Decimal

from shop.services.attendance import DAYS_OF_WEEK_MN, SATURDAY, build_attendance_rows

HOURS_PER_DAY = 8
MANUAL_DAYS_POSITION_KEYWORD = 'худалдагч'  # албан тушаалын нэрэнд агуулсан бол хоногийг гараар засна


def is_manual_days_position(position_name):
    return MANUAL_DAYS_POSITION_KEYWORD in (position_name or '').lower()
SUNDAY = 6


def month_days(year, month, holidays):
    """Сарын өдөр бүрийн мэдээлэл (хуудасны эхний хуанлид харуулна)."""
    days = []
    for day in range(1, calendar.monthrange(year, month)[1] + 1):
        d = date(year, month, day)
        weekday = d.weekday()
        days.append({
            'date': d,
            'weekday': DAYS_OF_WEEK_MN[weekday],
            'is_saturday': weekday == SATURDAY,
            'is_sunday': weekday == SUNDAY,
            'is_holiday': d in holidays,
        })
    return days


def position_sort_key():
    """Албан тушаалын эрэмбийн түлхүүр функц: AttendancePositionRule.sort_order (эрэмбэгүй бол төгсгөлд), дараа нь
    нэрээр, албан тушаалгүй нь хамгийн төгсгөлд. Цалин бодолт, хоног бүртгэл, бусад жагсаалт ижил дарааллаар."""
    from shop.models import AttendancePositionRule

    sort_orders = dict(
        AttendancePositionRule.objects.exclude(sort_order__isnull=True).values_list('position_name', 'sort_order')
    )
    return lambda position: (not position, position not in sort_orders, sort_orders.get(position, 0), position or '')


def ordered_active_employees():
    """Идэвхтэй ажилчдыг албан тушаалын эрэмбээр (AttendancePositionRule.sort_order, эрэмбэгүй бол төгсгөлд),
    дараа нь албан тушаалын нэрээр, дотроо ажилтны нэрээр эрэмбэлж буцаана (албан тушаалгүй нь хамгийн төгсгөлд).
    Хоног бүртгэл, цалин бодолт хоёр ижил дарааллаар харуулна."""
    from datamigration.models import OpenDataEmployee

    position_key = position_sort_key()
    return sorted(
        OpenDataEmployee.objects.filter(isreclusion='N').exclude(id__isnull=True).exclude(id=''),
        key=lambda e: (*position_key(e.positionname), e.name or ''),
    )


def build_missing_days(date_from, date_to, attendance_rows):
    """Цаг бүртгэлд 'ажиллаагүй өдөр'-ийг тодруулах: идэвхтэй ажилтан бүрийн ажиллавал зохих өдрүүдээс
    (Хоног бүртгэлтэй ижил дүрмээр) цаг бүртгэлийн мөргүй өдрүүдийг буцаана - хоног дутуу үед аль өдөр
    ажиллаагүйг хайхад ашиглана.

    - Ажлын өдөр: Да-Ба, Бямбыг оруулдаг (ажилтны тохиргоо, эсвэл албан тушаалын горим) бол Бямба ч;
      байгууллагын амралтын өдөр (OrganizationHoliday) ороогүй, өнөөдрөөс хойшхи өдөр ороогүй.
    - Ээлжийн горимтой болон цаг бүртгүүлдэггүй (worked_equals_required) албан тушаалд ажиллавал зохих
      тодорхой өдөр байхгүй тул тооцохгүй.
    - Тухайн өдөр аль ч албан тушаалаар (шилжин/хавсарч) мөртэй бол ажилласан гэж үзнэ.
    """
    from datetime import timedelta
    from django.utils import timezone
    from shop.models import AttendancePositionRule, EmployeePayProfile, OrganizationHoliday

    date_to = min(date_to, timezone.localdate())
    if date_from > date_to:
        return []

    holidays = set(
        OrganizationHoliday.objects.filter(date__gte=date_from, date__lte=date_to).values_list('date', flat=True)
    )
    schedules = dict(AttendancePositionRule.objects.values_list('position_name', 'schedule_type'))
    no_clock_positions = set(
        AttendancePositionRule.objects.filter(worked_equals_required=True).values_list('position_name', flat=True)
    )
    saturday_overrides = dict(
        EmployeePayProfile.objects.exclude(saturday_in_worked_days__isnull=True)
        .values_list('employee_code', 'saturday_in_worked_days')
    )
    worked = {}
    for r in attendance_rows:
        worked.setdefault(r['employee_code'], set()).add(r['date'])

    days = [date_from + timedelta(days=i) for i in range((date_to - date_from).days + 1)]
    missing = []
    for e in ordered_active_employees():
        schedule = schedules.get(e.positionname) or AttendancePositionRule.SCHEDULE_WEEKDAYS
        if schedule == AttendancePositionRule.SCHEDULE_SHIFT or e.positionname in no_clock_positions:
            continue
        with_saturday = saturday_overrides.get(e.id, schedule == AttendancePositionRule.SCHEDULE_SATURDAY)
        worked_dates = worked.get(e.id, set())
        for d in days:
            weekday = d.weekday()
            if weekday == SUNDAY or (weekday == SATURDAY and not with_saturday):
                continue
            if d in holidays or d in worked_dates:
                continue
            missing.append({
                'employee_code': e.id,
                'name': e.name,
                'position_name': e.positionname or '',
                'date': d,
                'weekday': DAYS_OF_WEEK_MN[weekday],
                'is_missing': True,
            })
    return missing


def build_timesheet(year, month, employee_code=None):
    """Сарын хоног бүртгэлийн хүснэгтийг буцаана: (days, calendar_summary, rows, totals, setting).
    employee_code өгвөл зөвхөн тэр ажилтны мөрүүдийг (хувийн мэдээлэл дэх "Цалингийн мэдээлэл") бодно."""
    from shop.models import (
        AttendancePositionRule, EmployeePayProfile, OrganizationHoliday, TimesheetEntry, TimesheetSetting,
    )

    date_from = date(year, month, 1)
    date_to = date(year, month, calendar.monthrange(year, month)[1])

    holidays = set(
        OrganizationHoliday.objects.filter(date__gte=date_from, date__lte=date_to).values_list('date', flat=True)
    )
    days = month_days(year, month, holidays)
    weekdays_count = sum(1 for d in days if not d['is_saturday'] and not d['is_sunday'] and not d['is_holiday'])
    saturdays_count = sum(1 for d in days if d['is_saturday'] and not d['is_holiday'])
    calendar_summary = {
        'weekdays': weekdays_count,
        'saturdays': saturdays_count,
        'holidays': len(holidays),
    }

    schedules = dict(AttendancePositionRule.objects.values_list('position_name', 'schedule_type'))
    worked_equals_required = set(
        AttendancePositionRule.objects.filter(worked_equals_required=True).values_list('position_name', flat=True)
    )
    saturday_overrides = dict(
        EmployeePayProfile.objects.exclude(saturday_in_worked_days__isnull=True)
        .values_list('employee_code', 'saturday_in_worked_days')
    )
    # Үндсэн мөрийн гар утга position_name='' , шилжин ажилласан албан тушаалын мөрийнх тэр албан тушаалын нэр
    entries = {
        (e.employee_code, e.position_name): e
        for e in TimesheetEntry.objects.filter(year=year, month=month)
    }
    setting = TimesheetSetting.get()

    # Ажилтан бүрийн цаг бүртгэлийг тухайн өдрийн албан тушаалаар нь бүлэглэнэ (шилжин ажилласан өдрүүд тусдаа)
    attendance_by_code = {}
    for r in build_attendance_rows(date_from, date_to, employee_code=employee_code):
        main_position = r['default_position']
        position = '' if r['position_name'] == main_position else r['position_name']
        attendance_by_code.setdefault(r['employee_code'], {}).setdefault(position, []).append(r)

    def saturday_included(employee_code, schedule, is_main):
        # Бямбыг оруулах бол ажиллавал зохих хоногт Бямба гарагууд нэмэгдэж, ажилласан хоногт Бямбад
        # ажилласан өдрүүд тоологдоно; үгүй бол аль алинд нь Бямба тоологдохгүй. Ажилтны тохиргоо зөвхөн
        # үндсэн албан тушаалд нь үйлчилнэ - шилжин ажилласан албан тушаалд тэр албан тушаалын горимоор
        default = schedule == AttendancePositionRule.SCHEDULE_SATURDAY
        return saturday_overrides.get(employee_code, default) if is_main else default

    def build_row(e, position, attendance, is_main, moved_days=0):
        """Ажилтны нэг албан тушаалын (үндсэн эсвэл шилжин ажилласан) мөр."""
        schedule = schedules.get(position) or AttendancePositionRule.SCHEDULE_WEEKDAYS
        entry = entries.get((e.id, '' if is_main else position))
        is_shift = schedule == AttendancePositionRule.SCHEDULE_SHIFT

        if is_shift:
            # Ээлжийн ажилтанд Бямба тусгай биш - бүх ажилласан өдөр тоологдоно
            worked_days = Decimal(len(attendance))
            required_days = worked_days
            with_saturday = True
        else:
            with_saturday = saturday_included(e.id, schedule, is_main)
            worked_days = Decimal(sum(
                1 for r in attendance if with_saturday or r['date'].weekday() != SATURDAY
            ))
            if is_main:
                required_days = Decimal(max(weekdays_count + (saturdays_count if with_saturday else 0) - moved_days, 0))
            else:
                # Шилжин ажилласан албан тушаалд зөвхөн тэнд ажилласан өдрүүд л ажиллавал зохих хоног
                required_days = worked_days
        if position in worked_equals_required:
            worked_days = required_days

        # Тооцоолсон утгыг хадгалж, гараар бичсэн бол түүгээр дарна: ажиллавал зохих хоногийг онцгой тохиолдолд
        # бүх ажилтанд, ажилласан хоногийг зөвхөн 'худалдагч' албан тушаалд
        manual_days = is_manual_days_position(position)
        auto_required_days, auto_worked_days = required_days, worked_days
        if entry and entry.required_days is not None:
            required_days = entry.required_days
            if position in worked_equals_required:
                # Цаг бүртгүүлдэггүй албан тушаалын ажилласан хоног засварласан зохих хоногоо дагана
                worked_days = auto_worked_days = required_days
        if manual_days and entry and entry.worked_days is not None:
            worked_days = entry.worked_days

        # Ээлжийн ажилчдад Бямба гарагийг тусад нь тоолохгүй; бусдад цаг бүртгэлээр, гараар засч болно
        auto_saturday_days = Decimal(0) if is_shift else Decimal(
            sum(1 for r in attendance if r['date'].weekday() == SATURDAY)
        )
        saturday_days = auto_saturday_days
        if not is_shift and entry and entry.saturday_days is not None:
            saturday_days = entry.saturday_days

        late_1_10 = sum(r['late_1_10'] for r in attendance)
        late_11_20 = sum(r['late_11_20'] for r in attendance)
        late_21_30 = sum(r['late_20_plus'] for r in attendance)
        deduction = (
            late_1_10 * setting.late_rate_1_10
            + late_11_20 * setting.late_rate_11_20
            + late_21_30 * setting.late_rate_21_30
        )

        leave_days = entry.leave_days if entry else Decimal(0)
        excused_days = entry.excused_days if entry else Decimal(0)
        excused_hours = entry.excused_hours if entry else Decimal(0)

        # Ажиллавал зохих хоногоос дутуу ажилласан бол (гар утга хадгалаагүй үед) зөрүүг чөлөөтэй хоногт
        # санал болгоно - хадгалахад бүртгэгдэнэ, хэрэглэгч ээлжийн амралт руу шилжүүлж болно
        day_gap = required_days - worked_days
        excused_suggested = entry is None and day_gap > 0

        if excused_suggested:
            excused_days = day_gap

        return {
            'employee_code': e.id,
            'name': e.name,
            'positionname': position,
            # False бол үндсэн албан тушаалаас өөр албан тушаалд шилжин ажилласан өдрүүдийн тусдаа мөр
            'is_main': is_main,
            'entry_position': '' if is_main else position,
            'schedule': schedule,
            'is_shift': is_shift,
            'manual_days': manual_days,
            'required_overridden': required_days != auto_required_days,
            'required_days': required_days,
            'auto_required_days': auto_required_days,
            # Ээлжийн ажилтанд цагийн баганад хоногийн тоог өөрийг нь харуулна
            'required_hours': required_days if is_shift else required_days * HOURS_PER_DAY,
            'worked_days': worked_days,
            'auto_worked_days': auto_worked_days,
            'worked_hours': worked_days if is_shift else max(worked_days * HOURS_PER_DAY - excused_hours, Decimal(0)),
            'saturday_days': saturday_days,
            'auto_saturday_days': auto_saturday_days,
            # Бямбад ажилласан өдрүүд ажилласан хоногт орсон эсэх (ороогүй бол унааны мөнгөнд тусад нь нэмнэ)
            'saturday_in_worked_days': with_saturday,
            'leave_days': leave_days,
            'late_1_10': late_1_10,
            'late_11_20': late_11_20,
            'late_21_30': late_21_30,
            'excused_days': excused_days,
            'excused_suggested': excused_suggested,
            'excused_hours': excused_hours,
            'day_gap': day_gap,
            # Ээлжийн амралт, чөлөөтэй хоногоор тайлбарлагдаагүй үлдсэн зөрүү (0 бол таарсан)
            'unexplained_days': day_gap - leave_days - excused_days,
            'deduction': deduction,
        }

    rows = []
    for e in ordered_active_employees():
        if employee_code is not None and e.id != employee_code:
            continue
        main_position = e.positionname or ''
        by_position = attendance_by_code.get(e.id, {})
        secondary = sorted(p for p in by_position if p)

        # Үндсэн мөрийн ажиллавал зохих хоногоос бүхэлдээ өөр албан тушаалд шилжин ажилласан (үндсэн горимд
        # тоологдох) өдрүүдийг хасна. Албан тушаал хавсарч ажилласан өдөр (тухайн өдөр үндсэн албан тушаалын
        # мөр ч бас байгаа) хоёуланд нь тоологдох тул хасахгүй
        main_schedule = schedules.get(e.positionname) or AttendancePositionRule.SCHEDULE_WEEKDAYS
        main_with_saturday = saturday_included(e.id, main_schedule, True)
        main_dates = {r['date'] for r in by_position.get('', [])}
        moved_dates = {r['date'] for p in secondary for r in by_position[p]} - main_dates
        moved_days = sum(1 for d in moved_dates if main_with_saturday or d.weekday() != SATURDAY)
        rows.append(build_row(e, main_position, by_position.get('', []), True, moved_days))
        for position in secondary:
            rows.append(build_row(e, position, by_position[position], False))

    return days, calendar_summary, rows, timesheet_totals(rows), setting


TOTAL_KEYS = (
    'required_days', 'required_hours', 'worked_days', 'worked_hours', 'saturday_days', 'leave_days',
    'late_1_10', 'late_11_20', 'late_21_30', 'excused_days', 'excused_hours', 'deduction',
)


def timesheet_totals(rows):
    """Хоног бүртгэлийн мөрүүдийн нийт дүн (шүүсэн мөрүүдэд ч дахин тооцоход ашиглана)."""
    return {key: sum((r[key] for r in rows), Decimal(0)) for key in TOTAL_KEYS}
