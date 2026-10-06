"""
OpenData* хүснэгтүүдийн индекс.

import_views --create-tables нь хүснэгт бүрийг DROP ... CASCADE хийгээд дахин үүсгэдэг тул индексүүд синк бүрт
устна. Иймээс энд тодорхойлсон индексийг импорт бүрийн дараа (import_views) дахин үүсгэнэ; гараар:
    python manage.py ensure_opendata_indexes

Тайлангууд огноогоор (DocumentDate) шүүж, харилцагч/бараа/сувгаар бүлэглэдэг тул тэдгээрт индекс тавьсан.
"""
import logging

from django.db import connection

logger = logging.getLogger(__name__)

# хүснэгт -> [(индексийн нэрийн дагавар, [баганууд])]
OPENDATA_INDEXES = {
    'OpenDataSale': [
        ('date', ['DocumentDate']),
        ('customer', ['CustomerId']),
        ('item', ['ItemId']),
        ('channel_date', ['DistributionChannelId', 'DocumentDate']),
    ],
    'OpenDataRecPay': [
        ('date', ['DocumentDate']),
        ('account_date', ['AccountId', 'DocumentDate']),
        ('customer', ['CustomerId']),
    ],
    'OpenDataDelivery': [
        ('date', ['DocumentDate']),
        ('distributor_date', ['DistributorId', 'DocumentDate']),
    ],
    'OpenDataSaleRefund': [
        ('date', ['DocumentDate']),
        ('customer', ['CustomerId']),
    ],
    'OpenDataCustomer': [
        ('id', ['Id']),
        ('channel', ['DistributionChannelId']),
    ],
    'OpenDataItem': [
        ('id', ['Id']),
    ],
}


def _table_columns(cursor, table):
    cursor.execute(
        'SELECT column_name FROM information_schema.columns WHERE table_name = %s', [table],
    )
    return {r[0] for r in cursor.fetchall()}


def ensure_indexes(tables=None, analyze=True):
    """Тодорхойлсон индексүүдийг (байхгүй бол) үүсгэж, статистикийг шинэчилнэ. Үүсгэсэн индексийн тоог буцаана.
    Хүснэгт эсвэл багана байхгүй бол алгасна (MSSQL view-ийн бүтэц өөрчлөгдөж болох тул)."""
    created = 0
    targets = tables or list(OPENDATA_INDEXES)
    with connection.cursor() as cursor:
        for table in targets:
            specs = OPENDATA_INDEXES.get(table)
            if not specs:
                continue
            columns = _table_columns(cursor, table)
            if not columns:
                continue
            cursor.execute('SELECT indexname FROM pg_indexes WHERE tablename = %s', [table])
            existing = {r[0] for r in cursor.fetchall()}
            for suffix, cols in specs:
                if not set(cols) <= columns:
                    logger.warning('%s: %s багана алга - индекс алгасав', table, cols)
                    continue
                name = f'idx_{table.lower()}_{suffix}'[:63]
                if name in existing:
                    continue
                col_sql = ', '.join(f'"{c}"' for c in cols)
                cursor.execute(f'CREATE INDEX IF NOT EXISTS "{name}" ON "{table}" ({col_sql})')
                created += 1
            if analyze:
                cursor.execute(f'ANALYZE "{table}"')
    return created
