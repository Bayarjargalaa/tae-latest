"""
Борлуулалтын тайлан ХТ-р - нэвтэрсэн худалдааны төлөөлөгч (ХТ) зөвхөн өөрийн хариуцсан сувгийг харна.

- Хэрэглэгч -> ажилтан: OpenDataEmployee.Email = хэрэглэгчийн имэйл (бусад хуудастай адил).
- Хязгаарлагдах албан тушаал: RESTRICTED_POSITIONS. Superuser болон бусад албан тушаал бүх сувгийг харна.
- Ажилтан -> суваг (автоматаар, кодоор): ажилтны код = борлуулалтын SellerId. Сүүлийн OWNER_LOOKBACK_DAYS
  хоногт тухайн сувагт ХАМГИЙН ОЛОН борлуулалт хийсэн борлуулагч тэр сувгийг хариуцна гэж үзнэ - бусдын
  сувагт хааяа хийсэн цөөн борлуулалтаар тэр сувгийн бүх мэдээллийг харахгүй, ХТ солигдоход шинэ ХТ нь
  автоматаар авна.
- Суваг олдоогүй ХТ юу ч харахгүй (sales_ht_access.NO_ACCESS_CHANNEL).
"""
from dataclasses import dataclass, field

from django.db import connection

RESTRICTED_POSITIONS = {'Худалдааны төлөөлөгч', 'Борлуулагч'}
OWNER_LOOKBACK_DAYS = 90
NO_ACCESS_CHANNEL = '__no_access__'  # ямар ч сувагтай таарахгүй утга


@dataclass
class ChannelScope:
    employee_code: str
    employee_name: str
    position: str
    channels: list = field(default_factory=list)  # [(Id, Name)]

    @property
    def channel_ids(self):
        return [channel_id for channel_id, _ in self.channels]


def _employee_for(user):
    from datamigration.models import OpenDataEmployee

    email = (getattr(user, 'email', '') or '').strip()
    if not email:
        return None
    return OpenDataEmployee.objects.filter(email__iexact=email).first()


def _owned_channels(seller_id):
    """Сүүлийн OWNER_LOOKBACK_DAYS хоногт seller_id хамгийн олон борлуулалт хийсэн сувгууд [(Id, Name)]."""
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            WITH counts AS (
                SELECT s."DistributionChannelId" AS ch, s."SellerId" AS seller, count(*) AS n
                FROM "OpenDataSale" s
                WHERE s."DocumentDate"::date >= CURRENT_DATE - %s
                  AND s."DistributionChannelId" IS NOT NULL AND s."SellerId" IS NOT NULL
                GROUP BY 1, 2
            ), ranked AS (
                SELECT ch, seller, rank() OVER (PARTITION BY ch ORDER BY n DESC) AS rk FROM counts
            )
            SELECT r.ch, COALESCE(dc."Name", '')
            FROM ranked r
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = r.ch
            WHERE r.rk = 1 AND r.seller = %s
            ORDER BY r.ch
            ''',
            [OWNER_LOOKBACK_DAYS, seller_id],
        )
        return cursor.fetchall()


def get_channel_scope(user):
    """Хязгаарлалтгүй бол None; ХТ бол түүний хариуцсан сувгуудтай ChannelScope (хоосон байж болно)."""
    if user.is_superuser:
        return None
    employee = _employee_for(user)
    if employee is None or (employee.positionname or '') not in RESTRICTED_POSITIONS:
        return None
    return ChannelScope(
        employee_code=employee.id,
        employee_name=employee.name or '',
        position=employee.positionname or '',
        channels=_owned_channels(employee.id),
    )


def apply_channel_scope(filters, scope):
    """Шүүлтийг ХТ-ийн сувгаар хязгаарлана: сонгосон сувгуудаас зөвхөн зөвшөөрөгдсөнийг үлдээж, юу ч
    сонгоогүй бол бүх зөвшөөрөгдсөн сувгаар; суваггүй ХТ-д хоосон үр дүн."""
    if scope is None:
        return filters
    allowed = scope.channel_ids
    selected = [c for c in filters['channels'] if c in allowed]
    filters['channels'] = selected or allowed or [NO_ACCESS_CHANNEL]
    filters['all_channels'] = False
    return filters
