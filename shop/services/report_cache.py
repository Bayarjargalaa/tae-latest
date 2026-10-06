"""
OpenData тайлангийн кэш - хүснэгтийн "хувилбар"-аар хүчингүй болдог.

Синк (import_views --create-tables) хүснэгт бүрийг DROP/CREATE хийдэг тул pg_class-ийн OID солигдоно; мөн
өөрчлөлтийн тоолуурыг (n_tup_ins/upd/del) нэмж түлхүүрт оруулна. Тиймээс өгөгдөл шинэчлэгдэхэд кэш автоматаар
шинэ түлхүүр рүү шилжинэ - тусад нь цэвэрлэх шаардлагагүй. Кэш нь файл дээр (core.settings.CACHES) тул синк
процесс урьдчилан бэлдсэн үр дүнг вэб сервер ашиглана.
"""
import hashlib
import json

from django.core.cache import cache
from django.db import connection

CACHE_SECONDS = 3 * 60 * 60


def table_version(tables):
    """Хүснэгтүүдийн хувилбарын мөр (OID + өөрчлөлтийн тоолуур)."""
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT c.relname, c.oid, COALESCE(s.n_tup_ins + s.n_tup_upd + s.n_tup_del, 0)
            FROM pg_class c LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
            WHERE c.relname = ANY(%s) AND c.relkind = 'r'
            ORDER BY c.relname
            ''', [list(tables)])
        return ';'.join(f'{name}:{oid}:{n}' for name, oid, n in cursor.fetchall())


def cached(name, tables, payload, builder, timeout=CACHE_SECONDS):
    """builder()-ийн үр дүнг (хүснэгтийн хувилбар + параметрээр) кэшлэнэ."""
    raw = json.dumps(payload, sort_keys=True, default=str)
    digest = hashlib.md5(f'{table_version(tables)}|{raw}'.encode()).hexdigest()
    key = f'report:{name}:{digest}'
    result = cache.get(key)
    if result is None:
        result = builder()
        cache.set(key, result, timeout)
    return result
