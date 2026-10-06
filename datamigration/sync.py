"""
MSSQL view -> PostgreSQL хүснэгт: нэг хүснэгтийг хурдан, тасалдалгүй татах.

- View-г зөвхөн нэрээр нь (INFORMATION_SCHEMA.VIEWS) хайж аль өгөгдлийн санд байгааг олно - бүх view-ийн жагсаалт
  татахгүй; олдсон санг кэшлэнэ.
- Өгөгдлийг "<хүснэгт>__sync" түр хүснэгтэд PostgreSQL COPY-оор бичээд (pandas.to_sql-ийн мөр мөрөөр INSERT-ээс
  хэд дахин хурдан), нэг гүйлгээнд хуучин хүснэгтийг устгаж түр хүснэгтийн нэрийг солино - тэр хооронд хуудсууд
  хоосон/байхгүй хүснэгттэй тулгарахгүй.
- Дараа нь тайлангийн индексийг сэргээж (opendata_indexes), шаардлагатай кэшийг урьдчилан бэлдэнэ.

Ашиглах: sync_view('OpenDataEmployee')  эсвэл  python manage.py sync_table OpenDataEmployee
Өдөр тутмын бүрэн синк (import_views) ч write_dataframe-ийг ашиглана.
"""
import csv
import io
import logging
import time

from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)

RESERVED = ('class', 'def', 'return', 'for', 'if', 'while')
RECENCY_COLUMNS = ('modifieddate', 'lastupdated', 'updateddate', 'modifiedon', 'lastmodified')


def _engine():
    from decouple import config
    from sqlalchemy import create_engine
    return create_engine(
        # Драйверийг тодорхой заана: SQLAlchemy 2.1+ дээр "postgresql://"-ийн анхдагч нь psycopg (3) болсон,
        # төсөлд psycopg2-binary суусан
        f"postgresql+psycopg2://{config('DB_USER', default='postgres')}:{config('DB_PASSWORD', default='')}"
        f"@{config('DB_HOST', default='localhost')}:{config('DB_PORT', default='5432')}/{config('DB_NAME', default='tae')}"
    )


def _copy_insert(table, conn, keys, data_iter):
    """pandas.to_sql-д: мөрүүдийг PostgreSQL COPY-оор бичнэ."""
    dbapi_conn = conn.connection
    with dbapi_conn.cursor() as cur:
        buf = io.StringIO()
        csv.writer(buf).writerows(data_iter)
        buf.seek(0)
        columns = ', '.join(f'"{k}"' for k in keys)
        name = f'"{table.schema}"."{table.name}"' if table.schema else f'"{table.name}"'
        cur.copy_expert(f'COPY {name} ({columns}) FROM STDIN WITH (FORMAT csv)', buf)


def prepare_dataframe(df, table_name=''):
    """Баганын нэр (reserved үг) засаж, "Id"-аар давхардсан мөрийг (сүүлд шинэчлэгдсэнийг үлдээж) хасна.

    MSSQL талын view нь түүх/хувилбарын хүснэгттэй join хийснээс нэг Id-д олон мөр буцааж болзошгүй."""
    df.columns = [f'{c}_' if c.lower() in RESERVED else c for c in df.columns]
    id_col = next((c for c in df.columns if c.lower() == 'id'), None)
    if id_col:
        before = len(df)
        recency = next((c for c in df.columns if c.lower() in RECENCY_COLUMNS), None)
        if recency:
            df = df.sort_values(by=recency)
        df = df.drop_duplicates(subset=id_col, keep='last')
        if before - len(df):
            logger.warning("%s: '%s'-ээр %s давхардсан мөр хаягдлаа", table_name, id_col, before - len(df))
    return df


def write_dataframe(df, table_name):
    """DataFrame-ийг түр хүснэгтэд COPY-оор бичээд хуучин хүснэгттэй атомаар солино. Бичсэн мөрийн тоог буцаана."""
    df = prepare_dataframe(df, table_name)
    staging = f'{table_name}__sync'[:63]
    engine = _engine()
    try:
        df.to_sql(staging, engine, if_exists='replace', index=False, method=_copy_insert, chunksize=50000)
        with engine.begin() as conn:
            conn.exec_driver_sql(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
            conn.exec_driver_sql(f'ALTER TABLE "{staging}" RENAME TO "{table_name}"')
    finally:
        engine.dispose()
    return len(df)


def find_view_database(view_name):
    """View аль MSSQL өгөгдлийн санд байгааг нэрээр нь хайна (бүх view-ийн жагсаалт татахгүй). Олдохгүй бол None."""
    from datamigration.utils.view_extractor import MSSQLViewExtractor, get_all_databases

    key = f'opendata_sync:db:{view_name}'
    cached = cache.get(key)
    if cached:
        return cached
    # Ижил нэртэй view хэд хэдэн санд байвал (жиш: OpenDataSaleRefund - бүтэц нь өөр) СҮҮЛИЙН санг сонгоно:
    # хуваарьт синк (import_views) санг дарааллаар нь татдаг тул эцэст нь сүүлийнх нь үлддэг - түүнтэй адил байна
    found = None
    for db_name in get_all_databases():
        with MSSQLViewExtractor(db_name) as extractor:
            if not extractor.connection and not extractor.connect():
                continue
            cur = extractor.connection.cursor()
            cur.execute('SELECT 1 FROM INFORMATION_SCHEMA.VIEWS WHERE TABLE_NAME = ?', view_name)
            if cur.fetchone():
                found = db_name
    if found:
        cache.set(key, found, 24 * 60 * 60)
    return found


def list_views():
    """Бүх MSSQL өгөгдлийн сангийн view-ийн жагсаалт [(view, db)] - кэштэй (6 цаг)."""
    from datamigration.utils.view_extractor import MSSQLViewExtractor, get_all_databases

    cached = cache.get('opendata_sync:views')
    if cached is not None:
        return cached
    result = []
    for db_name in get_all_databases():
        with MSSQLViewExtractor(db_name) as extractor:
            for view in extractor.get_all_views() or []:
                result.append((view, db_name))
                cache.set(f'opendata_sync:db:{view}', db_name, 24 * 60 * 60)
    cache.set('opendata_sync:views', result, 6 * 60 * 60)
    return result


def post_sync(table_name):
    """Синкийн дараах ажил: индекс сэргээх, статистик, кэш урьдчилан бэлдэх."""
    from datamigration.opendata_indexes import OPENDATA_INDEXES, ensure_indexes
    if table_name in OPENDATA_INDEXES:
        ensure_indexes([table_name])
    else:
        with connection.cursor() as cur:
            cur.execute(f'ANALYZE "{table_name}"')
    if table_name in ('OpenDataSale', 'OpenDataItem'):
        from shop.services.sales_report import warm_cache
        warm_cache()


def sync_view(view_name, database=None, log=None):
    """Нэг MSSQL view-г PostgreSQL рүү татна. {'table', 'database', 'rows', 'seconds', 'steps'} буцаана.
    log(text) - явцын мессеж (вэб хуудас, командын мөрөнд)."""
    from datamigration.utils.view_extractor import MSSQLViewExtractor

    log = log or (lambda text: logger.info(text))
    started = time.monotonic()
    steps = {}
    database = database or find_view_database(view_name)
    if not database:
        raise ValueError(f'"{view_name}" view MSSQL өгөгдлийн санд олдсонгүй')
    log(f'{database} санаас татаж байна...')
    t = time.monotonic()
    with MSSQLViewExtractor(database) as extractor:
        df = extractor.get_view_data(view_name)
    if df is None:
        raise RuntimeError('MSSQL-ээс өгөгдөл татаж чадсангүй (холболт эсвэл view-ийн алдаа)')
    steps['fetch'] = round(time.monotonic() - t, 2)
    log(f'{len(df):,} мөр татлаа ({steps["fetch"]}с). PostgreSQL-д бичиж байна...')
    t = time.monotonic()
    rows = write_dataframe(df, view_name)
    steps['write'] = round(time.monotonic() - t, 2)
    log(f'{rows:,} мөр бичлээ ({steps["write"]}с). Индекс, кэш шинэчилж байна...')
    t = time.monotonic()
    post_sync(view_name)
    steps['post'] = round(time.monotonic() - t, 2)
    return {'table': view_name, 'database': database, 'rows': rows,
            'seconds': round(time.monotonic() - started, 2), 'steps': steps}
