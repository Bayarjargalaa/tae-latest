"""
Цаг бүртгэл (attendance) - бизнес логик

1. sync_from_device()             - хурууны хээ таних төхөөрөмжөөс ирцийг татаж AttendanceRawLog-д хадгална
2. import_merchandiser_visits()   - түгээлтийн программаас экспортолсон Document.xlsx-с худалдааны
                                     төлөөлөгч/мерчандайзерийн зочилсон бүртгэлийг MerchandiserVisitLog-д хадгална
3. build_attendance_rows()        - түүхий бүртгэлүүд + EmployeeFingerprint (ажилтны хурууны мэдээлэл)-г
                                     нэгтгэж, тухайн огнооны мужид харуулах хүснэгтийн мөрүүдийг тооцоолно.
                                     Урьд нь хадгалсан (AttendanceRecord) мөр байвал тооцоолсноос илүү тэрийг харуулна.
4. save_attendance_row()          - хэрэглэгчийн засварласан нэг мөрийг AttendanceRecord-д upsert хийнэ
"""
import os
import re
from datetime import datetime, time as dt_time

import pandas as pd
from django.conf import settings
from django.utils import timezone

DAYS_OF_WEEK_MN = ["Даваа", "Мягмар", "Лхагва", "Пүрэв", "Баасан", "Бямба", "Ням"]

# Түгээлтийн программаас экспортолсон 'Бараа өрөлтийн жагсаалт' (мерчандайзерийн зураг илгээсэн бүртгэл)
DOCUMENT_XLSX_PATH = os.path.join(settings.BASE_DIR, 'data', 'Document.xlsx')


def load_users_df():
    """EmployeeFingerprint (Ажилтны хурууны мэдээлэл хуудсанд тохируулсан) хүснэгтээс төхөөрөмжийн
    хэрэглэгчийн ID <-> нэр, ажилтны код харгалзааг барина (өмнө нь data/users.xlsx файлаас
    уншдаг байсныг орлож, /dashboard/hr/employee-fingerprint/ хуудаснаас засварлана)."""
    from datamigration.models import OpenDataEmployee
    from shop.models import EmployeeFingerprint

    rows = list(
        EmployeeFingerprint.objects.exclude(device_user_id='').values_list('employee_code', 'device_user_id')
    )
    if not rows:
        return pd.DataFrame(columns=['User ID', 'Name', 'Employee ID'])

    employee_codes = [r[0] for r in rows]
    names = dict(OpenDataEmployee.objects.filter(id__in=employee_codes).values_list('id', 'name'))

    df = pd.DataFrame(rows, columns=['Employee ID', 'User ID'])
    df['Name'] = df['Employee ID'].map(names).fillna('').astype(str).str.strip()
    df['User ID'] = df['User ID'].astype(str).str.strip()
    df['Employee ID'] = df['Employee ID'].astype(str).str.strip()
    return df[['User ID', 'Name', 'Employee ID']]


def sync_from_device(ip=None, port=None, timeout=10):
    """Төхөөрөмжид холбогдож ирцийг татаад AttendanceRawLog-д давхардуулахгүй хадгална.

    Буцаах: (fetched, created) - төхөөрөмжөөс татагдсан нийт бүртгэл, шинээр хадгалагдсан бүртгэл
    """
    from zk import ZK
    from shop.models import AttendanceRawLog

    ip = ip or getattr(settings, 'ATTENDANCE_DEVICE_IP', '192.168.0.201')
    port = port or getattr(settings, 'ATTENDANCE_DEVICE_PORT', 4370)

    # ommit_ping=True: pyzk анхдагчаар OS-ийн `ping` командыг ажиллуулж шалгадаг бөгөөд
    # энэ нь Docker (python:3.12-slim) орчинд ping binary байхгүй эсвэл ICMP хаагдсан үед
    # бодит TCP холболт хийгдэх боломжтой байсан ч "can't reach device" алдаа өгдөг байсан
    zk = ZK(ip, port=port, timeout=timeout, ommit_ping=True)
    conn = zk.connect()
    try:
        records = conn.get_attendance() or []
    finally:
        conn.disconnect()

    logs = [
        AttendanceRawLog(
            device_user_id=str(r.user_id),
            timestamp=timezone.make_aware(r.timestamp) if timezone.is_naive(r.timestamp) else r.timestamp,
            status=r.status,
        )
        for r in records
    ]

    before = AttendanceRawLog.objects.count()
    AttendanceRawLog.objects.bulk_create(logs, ignore_conflicts=True, batch_size=500)
    after = AttendanceRawLog.objects.count()

    return len(logs), after - before


def _normalize_header(value):
    """Баганын нэрийг харьцуулахад бэлдэнэ: тусгай зайны тэмдэгт (\xa0 гэх мэт) арилгаж, доогуур регистрт хөрвүүлнэ."""
    text = str(value or '').replace('\xa0', ' ').strip()
    return ' '.join(text.split()).lower()


def _find_header_row(raw, marker='Мерчандайзерийн код', max_scan=20):
    """Document.xlsx-ийн толгой мөрийг (багануудын нэр бүхий мөр) '{marker}' гэсэн үгээр хайж олно.

    Баганын дараалал экспорт хийсэн систем/огноо бүрээр өөр байж болзошгүй тул байрлалаар биш,
    үргэлж нэрээр нь хайдаг.
    """
    marker_norm = _normalize_header(marker)
    for i in range(min(max_scan, len(raw))):
        row_norm = raw.iloc[i].apply(_normalize_header)
        if (row_norm == marker_norm).any():
            return i
    raise ValueError(f"Файлаас '{marker}' баганатай толгой мөр олдсонгүй")


def import_merchandiser_visits(file_path=None, file_obj=None):
    """Түгээлтийн программаас экспортолсон Document.xlsx ('Бараа өрөлтийн жагсаалт')-с худалдааны
    төлөөлөгч/мерчандайзер тус бүрийн зочилсон (зураг илгээсэн) огноо/цагийг MerchandiserVisitLog-д хадгална.

    file_obj өгвөл (жиш: хуудаснаас сонгож upload хийсэн Excel файл) түүнийг, үгүй бол
    file_path (эсвэл өгөгдөөгүй бол default DOCUMENT_XLSX_PATH)-г уншина.

    Баганын байрлал биш нэрээр нь (тодорхой бус/өөр дараалалтай экспортод тэсвэртэй байхаар)
    'Үүссэн огноо', 'Зассан огноо', 'Мерчандайзерийн код' гэх мэтийг олно.

    Мөр бүрийн 'Үүссэн огноо' болон 'Зассан огноо' баганыг тус тусад нь нэг цохолт мэт авч,
    хожим build_attendance_rows() тэдгээрийн доторх хамгийн эхний/сүүлийн цагийг тооцоолно.

    Буцаах: (fetched, created)
    """
    from shop.models import MerchandiserVisitLog

    if file_obj is not None:
        source = file_obj
    else:
        source = file_path or DOCUMENT_XLSX_PATH
        if not os.path.exists(source):
            raise FileNotFoundError(source)

    raw = pd.read_excel(source, header=None)
    header_row_idx = _find_header_row(raw)
    headers = raw.iloc[header_row_idx].tolist()
    normalized_headers = [_normalize_header(h) for h in headers]

    def col_idx(label):
        target = _normalize_header(label)
        for i, h in enumerate(normalized_headers):
            if h == target:
                return i
        raise ValueError(f"Файлд '{label}' багана олдсонгүй")

    idx_doc_no = col_idx('№')
    idx_created = col_idx('Үүссэн огноо')
    idx_edited = col_idx('Зассан огноо')
    idx_code = col_idx('Мерчандайзерийн код')
    idx_name = col_idx('Мерчандайзерийн нэр')
    idx_customer = col_idx('Харилцагчийн нэр')

    body = raw.iloc[header_row_idx + 1:]

    logs = []
    for _, row in body.iterrows():
        doc_no = row[idx_doc_no]
        employee_code = row[idx_code]
        if pd.isna(doc_no) or pd.isna(employee_code):
            continue

        doc_no = str(doc_no).strip()
        employee_code = str(employee_code).strip()
        if employee_code.endswith('.0'):
            employee_code = employee_code[:-2]
        employee_name = str(row[idx_name]).strip() if pd.notna(row[idx_name]) else ''
        customer_name = str(row[idx_customer]).strip() if pd.notna(row[idx_customer]) else ''

        for source_column, raw_ts in (('created', row[idx_created]), ('edited', row[idx_edited])):
            if pd.isna(raw_ts):
                continue
            ts = pd.to_datetime(raw_ts).to_pydatetime()
            aware_ts = timezone.make_aware(ts) if timezone.is_naive(ts) else ts
            logs.append(MerchandiserVisitLog(
                document_number=doc_no,
                employee_code=employee_code,
                employee_name=employee_name,
                customer_name=customer_name,
                timestamp=aware_ts,
                source_column=source_column,
            ))

    before = MerchandiserVisitLog.objects.count()
    MerchandiserVisitLog.objects.bulk_create(logs, ignore_conflicts=True, batch_size=500)
    after = MerchandiserVisitLog.objects.count()

    return len(logs), after - before


WORKDAY_MINUTES = 8 * 60  # 'бусад' албан тушаалд: ирсэн цагаас хойш ажиллах ёстой 8 цаг


def get_position_start_times():
    """{албан тушаал: ажил эхлэх цаг эсвэл None} mapping-г буцаана.

    None утга = тухайн албан тушаалд тогтмол эхлэх цаг байхгүй ('бусад') - 8 цагийн
    дүрмээр (ирсэн цагаас хойш 8 цаг ажиллах ёстой) тооцоологдоно.
    """
    from shop.models import AttendancePositionRule
    return {r.position_name: r.start_time for r in AttendancePositionRule.objects.all()}


def get_employee_positions(employee_codes):
    """{ажилтны код: албан тушаалын нэр} mapping-г OpenDataEmployee-ээс буцаана."""
    from datamigration.models import OpenDataEmployee
    codes = [c for c in set(employee_codes) if c]
    if not codes:
        return {}
    return dict(OpenDataEmployee.objects.filter(id__in=codes).values_list('id', 'positionname'))


def _bucket_delay(delay_minutes):
    """Хоцролтын минутыг 1-10 / 11-20 / 20-с дээш минутын багцад хуваана. Хоцроогүй бол (0, 0, 0)."""
    delay = int(round(delay_minutes))
    if delay <= 0:
        return 0, 0, 0
    if delay <= 10:
        return delay, 0, 0
    if delay <= 20:
        return 10, delay - 10, 0
    return 10, 10, delay - 20


def compute_lateness(position_name, start_times, arrival_time, left_time):
    """Албан тушаалын дүрмээр хоцролтыг тооцоолж (late_1_10, late_11_20, late_20_plus) буцаана.

    - Тогтмол эхлэх цагтай албан тушаал (position_name нь start_times-д байгаа): ирсэн цаг
      тэр цагаас хойш байвал зөрүүг хоцролтоор тооцно.
    - 'Бусад' (start_times-д байхгүй эсвэл start_time нь NULL): ирсэн цагаас хойш 8 цаг
      (480 минут) ажиллаагүй бол дутсан минутыг хоцролтоор тооцно (тарсан цаг тодорхойгүй бол 0).
    """
    start_time = start_times.get(position_name) if position_name else None

    if start_time is not None:
        start_dt = datetime.combine(datetime.today(), start_time)
        arrival_dt = datetime.combine(datetime.today(), arrival_time)
        delay = (arrival_dt - start_dt).total_seconds() / 60
        return _bucket_delay(delay)

    if not left_time:
        return 0, 0, 0

    arrival_dt = datetime.combine(datetime.today(), arrival_time)
    left_dt = datetime.combine(datetime.today(), left_time)
    worked_minutes = (left_dt - arrival_dt).total_seconds() / 60
    if worked_minutes < 0:
        worked_minutes += 24 * 60  # шөнө дамжсан ээлж

    deficit = WORKDAY_MINUTES - worked_minutes
    return _bucket_delay(deficit)


def build_attendance_rows(date_from, date_to):
    """Сонгосон огнооны мужид харуулах ирцийн хүснэгтийн мөрүүдийг буцаана (нэр асц, огноо буурахаар эрэмбэлнэ).

    Тухайн (ажилтны код, огноо) хослолд өмнө нь гараар хадгалсан AttendanceRecord байвал
    түүхий бүртгэлээс тооцоолсныг орлуулж харуулна. Хоцролтыг ажилтны албан тушаалын дүрмээр
    (AttendancePositionRule) тооцоолно - compute_lateness() тайлбарыг үз.
    """
    from shop.models import AttendanceRawLog, AttendanceRecord, MerchandiserVisitLog

    start_dt = timezone.make_aware(datetime.combine(date_from, dt_time.min))
    end_dt = timezone.make_aware(datetime.combine(date_to, dt_time.max))

    raw_qs = AttendanceRawLog.objects.filter(
        timestamp__gte=start_dt, timestamp__lte=end_dt
    ).values('device_user_id', 'timestamp')
    raw_df = pd.DataFrame(list(raw_qs))

    visit_qs = MerchandiserVisitLog.objects.filter(
        timestamp__gte=start_dt, timestamp__lte=end_dt
    ).values('employee_code', 'employee_name', 'customer_name', 'timestamp')
    visit_df = pd.DataFrame(list(visit_qs))

    saved_qs = list(AttendanceRecord.objects.filter(date__gte=date_from, date__lte=date_to))

    users_df = None
    if not raw_df.empty:
        users_df = load_users_df()
        raw_df['device_user_id'] = raw_df['device_user_id'].astype(str)
        # ORM-оос UTC-аар ирсэн timestamp-г орон нутгийн цагийн бүсэд хөрвүүлж, өдөр/цагийг зөв тооцоолно
        raw_df['timestamp'] = pd.to_datetime(raw_df['timestamp'], utc=True).dt.tz_convert(timezone.get_current_timezone())
        merged = raw_df.merge(users_df, left_on='device_user_id', right_on='User ID', how='left')
        merged['Name'] = merged['Name'].fillna('')
        merged.loc[merged['Name'] == '', 'Name'] = 'Тодорхойгүй (#' + merged['device_user_id'] + ')'
        merged['Employee ID'] = merged['Employee ID'].fillna('')
        merged['date'] = merged['timestamp'].dt.date
    else:
        merged = None

    if not visit_df.empty:
        visit_df['timestamp'] = pd.to_datetime(visit_df['timestamp'], utc=True).dt.tz_convert(timezone.get_current_timezone())
        visit_df['date'] = visit_df['timestamp'].dt.date

    # Мөрүүдэд шаардлагатай бүх ажилтны кодны албан тушаалыг нэг дор урьдчилан татна
    all_codes = set()
    if merged is not None:
        all_codes.update(c for c in merged['Employee ID'].tolist() if c)
    if not visit_df.empty:
        all_codes.update(c for c in visit_df['employee_code'].tolist() if c)
    all_codes.update(rec.employee_code for rec in saved_qs)

    start_times = get_position_start_times()
    employee_positions = get_employee_positions(all_codes)

    def rule_start_str(position_name):
        """JS-д дамжуулах туслах утга: тогтмол эхлэх цагтай бол 'ЦЦ:ММ', 'бусад' (8ц дүрэм) бол хоосон."""
        st = start_times.get(position_name) if position_name else None
        return st.strftime('%H:%M') if st else ''

    rows_by_key = {}

    if merged is not None:
        grouped = merged.groupby(['device_user_id', 'Employee ID', 'Name', 'date'])['timestamp'].agg(['min', 'max'])
        for (device_user_id, employee_code, name, d), agg in grouped.iterrows():
            weekday_name = DAYS_OF_WEEK_MN[d.weekday()]
            arrived_dt = agg['min']
            left_dt = agg['max']
            position_name = employee_positions.get(employee_code)
            late_1_10, late_11_20, late_20_plus = compute_lateness(
                position_name, start_times, arrived_dt.time(),
                left_dt.time() if left_dt != arrived_dt else None,
            )

            effective_code = employee_code or f'device:{device_user_id}'
            key = (effective_code, d)
            rows_by_key[key] = {
                'employee_code': effective_code,
                'device_user_id': device_user_id,
                'name': name,
                'date': d,
                'weekday': weekday_name,
                'arrived_time': arrived_dt.strftime('%H:%M'),
                'left_time': left_dt.strftime('%H:%M') if left_dt != arrived_dt else '',
                'late_1_10': late_1_10,
                'late_11_20': late_11_20,
                'late_20_plus': late_20_plus,
                'total_late_minutes': late_1_10 + late_11_20 + late_20_plus,
                'customer_name': '',
                'rule_start': rule_start_str(position_name),
                'is_saved': False,
            }

    if not visit_df.empty:
        for (employee_code, d), group in visit_df.groupby(['employee_code', 'date']):
            weekday_name = DAYS_OF_WEEK_MN[d.weekday()]
            arrived_dt = group['timestamp'].min()
            left_dt = group['timestamp'].max()
            position_name = employee_positions.get(employee_code)
            late_1_10, late_11_20, late_20_plus = compute_lateness(
                position_name, start_times, arrived_dt.time(),
                left_dt.time() if left_dt != arrived_dt else None,
            )

            names = [n for n in group['employee_name'].tolist() if n]
            name = names[0] if names else ''
            customers = sorted({c for c in group['customer_name'].tolist() if c})

            key = (employee_code, d)
            rows_by_key[key] = {
                'employee_code': employee_code,
                'device_user_id': '',
                'name': name,
                'date': d,
                'weekday': weekday_name,
                'arrived_time': arrived_dt.strftime('%H:%M'),
                'left_time': left_dt.strftime('%H:%M') if left_dt != arrived_dt else '',
                'late_1_10': late_1_10,
                'late_11_20': late_11_20,
                'late_20_plus': late_20_plus,
                'total_late_minutes': late_1_10 + late_11_20 + late_20_plus,
                'customer_name': ', '.join(customers),
                'rule_start': rule_start_str(position_name),
                'is_saved': False,
            }

    for rec in saved_qs:
        key = (rec.employee_code, rec.date)
        position_name = employee_positions.get(rec.employee_code)
        rows_by_key[key] = {
            'employee_code': rec.employee_code,
            'device_user_id': rec.device_user_id,
            'name': rec.name,
            'date': rec.date,
            'weekday': rec.weekday,
            'arrived_time': rec.arrived_time,
            'left_time': rec.left_time,
            'late_1_10': rec.late_1_10,
            'late_11_20': rec.late_11_20,
            'late_20_plus': rec.late_20_plus,
            'total_late_minutes': rec.total_late_minutes,
            'customer_name': rec.customer_name,
            'rule_start': rule_start_str(position_name),
            'is_saved': True,
        }

    rows = list(rows_by_key.values())
    # Тогтвортой эрэмбэлэлт ашиглан: нэрээр өсөхөөр, огноогоор буурахаар
    rows.sort(key=lambda r: r['date'], reverse=True)
    rows.sort(key=lambda r: r['name'] or '')
    return rows


_TIME_RE = re.compile(r'^([0-1]?\d|2[0-3]):([0-5]\d)$')


def _normalize_time_str(value, field_label):
    """'ЦЦ:ММ' (24 цагийн) форматтай эсэхийг шалгаж, 5 тэмдэгтэд багтаах (жиш: '8:5' -> '08:05') болгоно.

    Хоосон/зөвхөн '-' бол хоосон мөр буцаана. Танигдаагүй утга бол ValueError шиднэ - ингэснээр
    чөлөөт текст талбарт санамсаргүй урт/буруу утга орж DB-ийн 5 тэмдэгтийн баганад (varchar(5))
    багтаагүйгээс болж сервер эвдрэхийн оронд ойлгомжтой алдаа болж дээшээ дамжина.
    """
    text = (value or '').strip()
    if not text or text == '-':
        return ''
    m = _TIME_RE.match(text)
    if not m:
        raise ValueError(f"{field_label} '{text}' буруу форматтай (ЦЦ:ММ байх ёстой)")
    return f'{int(m.group(1)):02d}:{m.group(2)}'


def save_attendance_row(data, user):
    """Хэрэглэгчийн засварласан нэг мөрийг AttendanceRecord-д upsert хийнэ.

    Цаг болон тоон талбаруудыг DB-д бичихийн өмнө шалгаж, буруу утгатай бол ValueError шиднэ
    (дуудагч тал алгасаж, хэрэглэгчид ойлгомжтой мессеж харуулна).
    """
    from shop.models import AttendanceRecord

    arrived_time = _normalize_time_str(data.get('arrived_time'), 'Ирсэн цаг')
    left_time = _normalize_time_str(data.get('left_time'), 'Тарсан цаг')

    try:
        late_1_10 = int(data.get('late_1_10') or 0)
        late_11_20 = int(data.get('late_11_20') or 0)
        late_20_plus = int(data.get('late_20_plus') or 0)
    except (TypeError, ValueError):
        raise ValueError('хоцролтын минут тоо биш байна')

    AttendanceRecord.objects.update_or_create(
        employee_code=data['employee_code'],
        date=data['date'],
        defaults={
            'device_user_id': (data.get('device_user_id', '') or '')[:50],
            'name': (data.get('name', '') or '')[:200],
            'weekday': (data.get('weekday', '') or '')[:20],
            'arrived_time': arrived_time,
            'left_time': left_time,
            'late_1_10': late_1_10,
            'late_11_20': late_11_20,
            'late_20_plus': late_20_plus,
            'total_late_minutes': late_1_10 + late_11_20 + late_20_plus,
            'customer_name': (data.get('customer_name', '') or '')[:1000],
            'updated_by': user,
        }
    )
