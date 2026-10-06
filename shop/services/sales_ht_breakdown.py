"""
Борлуулалтын тайлан ХТ-р - Задаргаа.

Хүснэгт/dashboard-тай ижил шүүлтээр (sales_ht._sale_conditions) хамгийн нарийн түвшний нэгтгэлийг
(сар x суваг x борлуулагч x харилцагч x бараа) нэг удаа авч хөтөч рүү илгээнэ. Мөрийн түвшин (ХТ ->
харилцагч -> бараа г.м.), багана (үзүүлэлт), шүүлтийг хөтөч дээр сонгож дахин тооцоолно.

- Захиалгын тоо (DocumentPkId) нь дээд түвшинд нэмэгддэггүй (нэг баримтад олон бараа) тул мөр бүрт
  баримтын индексүүдийг илгээж, бүлэг бүрт давхардалгүй тоолно.
- Хамрах хүрээ: бүлэгт худалдан авалт хийсэн харилцагч / тухайн суваг (бүлэг)-т бүртгэлтэй харилцагч;
  бүртгэлтэй харилцагчдыг (registered) тусад нь илгээнэ.
- Өртөг = тоо x өртөг (OpenDataSale.UnitCost, НӨАТ-гүй); бохир ашиг = НӨАТ-гүй борлуулалт - өртөг.
"""
from django.db import connection

from shop.services.sales_ht import (
    NO_CHANNEL_LABEL,
    NO_CUSTOMER_LABEL,
    _customer_conditions,
    _expand_customer_groups,
    _sale_conditions,
)

NO_SELLER_LABEL = '(борлуулагчгүй)'
NO_GROUP_LABEL = '(бүлэггүй)'


class _Index:
    """Утга -> дугаар; хөтөч рүү жагсаалт + индексээр илгээж JSON-ийн хэмжээг багасгана."""

    def __init__(self):
        self.keys, self.labels, self._pos = [], [], {}

    def get(self, key, label=None):
        if key not in self._pos:
            self._pos[key] = len(self.keys)
            self.keys.append(key)
            self.labels.append(label if label is not None else key)
        return self._pos[key]


def _snapshot_updated():
    from shop.models_inventory import InventorySnapshot

    latest = InventorySnapshot.objects.order_by('-updated_at').values_list('updated_at', flat=True).first()
    return latest.strftime('%Y-%m-%d %H:%M') if latest else ''


def build_breakdown(filters):
    """
    records:    [сар, суваг, борлуулагч, харилцагч, бараа, дүн, НӨАТ-гүй дүн, өртөг, тоо, хөнгөлөлт, [баримтууд]]
                (эхний 5 нь доорх жагсаалтуудын индекс)
    registered: [[суваг, бүлэг, идэвхтэй(1/0)]] - шүүлтийн хүрээнд бүртгэлтэй харилцагч бүр
    stock:      [[барааны нэр, жижиг, толгойт, алтжин]] - InventorySnapshot-ын одоогийн үлдэгдэл
    """
    with connection.cursor() as cursor:
        group_names = _expand_customer_groups(cursor, filters['customer_groups']) if filters['customer_groups'] else []
        where, params = _sale_conditions(filters, group_names, filters['date_from'], filters['date_to'])
        cursor.execute(
            f'''
            SELECT to_char(s."DocumentDate"::date, 'YYYY-MM'),
                   COALESCE(dc."Id", ''), MAX(COALESCE(dc."Name", '')),
                   COALESCE(NULLIF(s."SellerName", ''), ''),
                   COALESCE(s."CustomerId", ''), MAX(COALESCE(cu."Name", s."CustomerName", '')),
                   MAX(COALESCE(NULLIF(COALESCE(cu."CustomerGroupId", s."CustomerGroupId"), ''), '')),
                   COALESCE(s."ItemName", ''), MAX(COALESCE(s."ItemId", '')),
                   COALESCE(SUM(NULLIF(s."PayAmount"::text, '')::float8), 0), COALESCE(SUM(NULLIF(s."AmountNonVat"::text, '')::float8), 0),
                   COALESCE(SUM(COALESCE(NULLIF(s."Qty"::text, '')::float8, 0) * COALESCE(NULLIF(s."UnitCost"::text, '')::float8, 0)), 0),
                   COALESCE(SUM(NULLIF(s."Qty"::text, '')::float8), 0), COALESCE(SUM(NULLIF(s."DiscountAmount"::text, '')::float8), 0),
                   array_agg(DISTINCT s."DocumentPkId")
            FROM "OpenDataSale" s
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = s."DistributionChannelId"
            LEFT JOIN "OpenDataCustomer" cu ON cu."Id" = s."CustomerId"
            WHERE {' AND '.join(where)}
            GROUP BY 1, 2, 4, 5, 8
            ORDER BY 1
            ''',
            params,
        )
        rows = cursor.fetchall()

        cu_where, cu_params = _customer_conditions(filters, group_names)
        cursor.execute(
            f'''
            SELECT COALESCE(dc."Id", ''), COALESCE(dc."Name", ''), COALESCE(NULLIF(cu."CustomerGroupId", ''), ''),
                   COALESCE(cu."ActiveStatus", '')
            FROM "OpenDataCustomer" cu
            LEFT JOIN "OpenDataDistributionChannel" dc ON dc."Id" = cu."DistributionChannelId"
            WHERE {' AND '.join(cu_where)}
            ''',
            cu_params,
        )
        registered_rows = cursor.fetchall()

    months, channels, sellers, groups, customers, items, docs = (_Index() for _ in range(7))
    customer_groups = {}  # харилцагчийн индекс -> бүлгийн индекс
    item_codes = {}

    def channel_idx(channel_id, channel_name):
        label = f'{channel_id} {channel_name}' if channel_id else NO_CHANNEL_LABEL
        return channels.get(channel_id, label)

    records = []
    for (month, ch_id, ch_name, seller, cust_id, cust_name, group, item, item_id,
         amount, net, cost, qty, discount, doc_ids) in rows:
        cust_idx = customers.get(cust_id, ' '.join((cust_name or '').split()) or NO_CUSTOMER_LABEL)
        customer_groups[cust_idx] = groups.get(group, group or NO_GROUP_LABEL)
        item_idx = items.get(item, item or '(хоосон)')
        item_codes[item_idx] = item_id
        records.append([
            months.get(month),
            channel_idx(ch_id, ch_name),
            sellers.get(seller, seller or NO_SELLER_LABEL),
            cust_idx,
            item_idx,
            round(amount, 2), round(net, 2), round(cost, 2), round(qty, 3), round(discount, 2),
            [docs.get(d) for d in doc_ids if d is not None],
        ])

    registered = [
        [channel_idx(ch_id, ch_name), groups.get(group, group or NO_GROUP_LABEL), 1 if status == 'Y' else 0]
        for ch_id, ch_name, group, status in registered_rows
    ]

    # Барааны үлдэгдэл (snapshot): [нэр, жижиг, толгойт, алтжин]. Үлдэгдэлтэй барааны нэр төрлийн хуваарь болох
    # тул зарагдаагүй бараа ч орно; бараа сонгосон бол зөвхөн тэдгээр.
    from shop.models_inventory import InventorySnapshot

    snapshot = InventorySnapshot.objects.all()
    if filters['items']:
        snapshot = snapshot.filter(itemname__in=filters['items'])
    stock = [
        [name, float(jijig), float(tolgoit), float(altjin)]
        for name, jijig, tolgoit, altjin in snapshot.order_by('itemname').values_list(
            'itemname', 'jijig_qty', 'tolgoit_qty', 'altjin_qty')
    ]
    stock_pos = {row[0]: i for i, row in enumerate(stock)}

    return {
        'date_from': filters['date_from'].isoformat(),
        'date_to': filters['date_to'].isoformat(),
        'months': months.labels,
        'channels': channels.labels,
        'sellers': sellers.labels,
        'groups': groups.labels,
        'customers': customers.labels,
        'customer_group': [customer_groups[i] for i in range(len(customers.labels))],
        'items': items.labels,
        'item_codes': [item_codes[i] for i in range(len(items.labels))],
        'item_stock': [stock_pos.get(name, -1) for name in items.keys],  # бараа -> stock-ийн индекс
        'stock': stock,
        'stock_updated': _snapshot_updated(),
        'records': records,
        'registered': registered,
        'doc_count': len(docs.keys),
    }
