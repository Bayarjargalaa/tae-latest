"""
Ачаа буулгалт: сарын татан авалтууд (OpenDataLandedCost), ачаа бүрт оролцсон ажилчид ба тэдний ажлын хөлс,
гаднаас хөлсөлсөн хүмүүс (тоо × нэг хүний хөлс), сарын нэгтгэл. Хуудас ба Excel экспорт хоёулаа month_data-г ашиглана.

Татан авалтын дугаар он бүр давтагддаг тул ачааг DocumentPkId-аар таниулна.
Сарын нэгтгэл буулгасан огноогоор (unload_date) гарна.
"""
import calendar
from datetime import date
from decimal import Decimal

from django.db import connection
from django.db.models import Q

from datamigration.models import OpenDataEmployee
from shop.models import UnloadingEvent, UnloadingWorker

ROLE_LABELS = dict(UnloadingWorker.ROLE_CHOICES)
ROLE_ORDER = {role: i for i, (role, _) in enumerate(UnloadingWorker.ROLE_CHOICES)}


def month_range(year, month):
    start = date(year, month, 1)
    return start, start.replace(day=calendar.monthrange(year, month)[1])


def document_info(doc_id):
    """(дугаар, огноо, илгээгч) - DocumentPkId-аар."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT MAX("DocumentNumber"), MIN("DocumentDate"), MAX("VendorName") FROM "OpenDataLandedCost" '
                       'WHERE "DocumentPkId" = %s', [doc_id])
        return cursor.fetchone()


def employee_names(codes):
    """{код: (нэр, албан тушаал)} - гарсан ажилтныг ч оруулна."""
    return {e.id: (e.name, e.positionname or '') for e in OpenDataEmployee.objects.filter(id__in=set(codes))}


def month_data(year, month):
    start, end = month_range(year, month)
    # Тухайн сарын татан авалтууд + энэ сард буулгасан (эсвэл энэ сарын татан авалтыг өөр сард буулгасан) бүртгэл
    events = {e.document_id: e for e in UnloadingEvent.objects.prefetch_related('workers').filter(
        Q(document_date__range=(start, end)) | Q(unload_date__range=(start, end)))}
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT "DocumentPkId", MAX("DocumentNumber"), MIN("DocumentDate"), MAX("VendorName"), MAX("WarehouseName"),
                   COUNT(DISTINCT "ItemId"), SUM("Qty")
            FROM "OpenDataLandedCost"
            WHERE "DocumentDate" BETWEEN %s AND %s OR "DocumentPkId" = ANY(%s)
            GROUP BY 1 ORDER BY 3, 2
            ''', [start, end, list(events)])
        docs = [{'id': r[0], 'number': r[1], 'date': r[2], 'vendor': r[3] or '', 'warehouse': r[4] or '',
                 'item_count': r[5], 'qty': r[6] or 0} for r in cursor.fetchall()]
        cursor.execute(
            '''
            SELECT "DocumentPkId", "ItemName", MAX("MeasureName"), SUM("Qty")
            FROM "OpenDataLandedCost" WHERE "DocumentPkId" = ANY(%s)
            GROUP BY 1, 2 ORDER BY 1, 4 DESC
            ''', [[d['id'] for d in docs]])
        items = {}
        for doc_id, name, measure, qty in cursor.fetchall():
            items.setdefault(doc_id, []).append({'name': name, 'measure': measure or '', 'qty': qty or 0})

    names = employee_names(w.employee_code for e in events.values() for w in e.workers.all())
    for d in docs:
        event = events.get(d['id'])
        d['items'] = items.get(d['id'], [])
        d['event'] = event
        if event:
            workers = sorted(event.workers.all(), key=lambda w: (ROLE_ORDER.get(w.role, 9), w.id))
            d['workers'] = [{'code': w.employee_code, 'name': names.get(w.employee_code, (w.employee_code, ''))[0],
                             'position': names.get(w.employee_code, ('', ''))[1], 'role': w.role,
                             'role_label': ROLE_LABELS.get(w.role, w.role), 'fee': w.fee} for w in workers]
            d['staff_total'] = sum((w.fee for w in workers), Decimal(0))
            d['people'] = len(workers) + event.outside_count
            d['total'] = d['staff_total'] + event.outside_amount
            d['in_month'] = start <= event.unload_date <= end

    # Сарын нэгтгэл - буулгасан огноо энэ сард
    month_docs = sorted((d for d in docs if d['event'] and d['in_month']), key=lambda d: (d['event'].unload_date, d['number']))
    summary = {}
    for d in month_docs:
        for w in d['workers']:
            row = summary.setdefault(w['code'], {'code': w['code'], 'name': w['name'], 'position': w['position'],
                                                 'loads': 0, 'amount': Decimal(0)})
            row['loads'] += 1
            row['amount'] += w['fee']
    summary_rows = sorted(summary.values(), key=lambda r: (-r['amount'], r['name']))
    staff_total = sum((r['amount'] for r in summary_rows), Decimal(0))
    outside_people = sum(d['event'].outside_count for d in month_docs)
    outside_amount = sum((d['event'].outside_amount for d in month_docs), Decimal(0))
    return {
        'docs': docs,
        'month_docs': month_docs,
        'summary_rows': summary_rows,
        'staff_total': staff_total,
        'outside_people': outside_people,
        'outside_amount': outside_amount,
        'grand_total': staff_total + outside_amount,
        'period_label': f'{year} оны {month}-р сар',
    }
