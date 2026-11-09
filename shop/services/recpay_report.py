"""
Авлага / өглөгийн тайлан - OpenDataRecPay (харилцагчийн тооцооны гүйлгээ) хүснэгтээс.

- Авлага: 12xxxx (дансны авлага, ажилчид, хувь хүн г.м.) болон 18xxxx (урьдчилж төлсөн зардал) данс.
  Үлдэгдэл = дебит - кредит; нэмэгдсэн = дебит, төлөгдсөн = кредит.
- Өглөг: 3xxxxx (дансны өглөг, богино/урт хугацаат өр төлбөр) данс. Үлдэгдэл = кредит - дебит;
  нэмэгдсэн = кредит, төлөгдсөн = дебит.
- Дүн нь төгрөгөөр (DebitAmt/CreditAmt - валютын гүйлгээний төгрөгийн дүн).
- Эхний үлдэгдэл = эхлэх огнооноос өмнөх, эцсийн үлдэгдэл = дуусах огноо хүртэлх бүх гүйлгээ.
- Насжилт (FIFO): эерэг үлдэгдлийг хамгийн сүүлийн нэмэгдсэн гүйлгээнүүдээс бүрдсэн гэж үзнэ (хуучин нь эхэлж
  төлөгдсөн). Харилцагч + данс бүрээр бодож нэгтгэнэ. Хоёр суурьтай (AGING_BASES):
    * doc - баримтын огнооноос дуусах огноо хүртэл хэд хоног болсноор (анхдагч; ихэнх гүйлгээнд төлөх огноо
      баримтын огноотой ижил тул)
    * due - төлөх огнооноос (DueDate; хоосон эсвэл баримтын огнооноос өмнө бол баримтын огноо) хэд хоног хэтэрснээр
- ХТ / борлуулагч (shop.services.sales_ht_access) зөвхөн өөрийн хариуцсан сувгийн харилцагчдыг
  (OpenDataCustomer.DistributionChannelId) харна - filters['channels'].
"""
from datetime import date, timedelta

from django.db import connection

TABLE = '"OpenDataRecPay"'

KINDS = {
    'receivable': {
        'title': 'Авлагын тайлан',
        'account_where': '("AccountId" LIKE %s OR "AccountId" LIKE %s)',
        'account_params': ['12%', '18%'],
        'sign': '("DebitAmt" - "CreditAmt")',
        'increase': '"DebitAmt"',
        'decrease': '"CreditAmt"',
        'increase_label': 'Нэмэгдсэн (дебит)',
        'decrease_label': 'Төлөгдсөн (кредит)',
        'party': 'Харилцагч',
    },
    'payable': {
        'title': 'Өглөгийн тайлан',
        'account_where': '"AccountId" LIKE %s',
        'account_params': ['3%'],
        'sign': '("CreditAmt" - "DebitAmt")',
        'increase': '"CreditAmt"',
        'decrease': '"DebitAmt"',
        'increase_label': 'Нэмэгдсэн (кредит)',
        'decrease_label': 'Төлөгдсөн (дебит)',
        'party': 'Харилцагч',
    },
}

# Насжилтын суурь: нэр, хоногийн илэрхийлэл, бүлгүүд (нэр, дээд хязгаар хоног), эрсдэлтэй гэж тооцох бүлгүүд
AGING_BASES = {
    'doc': {
        'label': 'Баримтын огнооноос (насжилт)',
        'days': '%s - "DocumentDate"',
        'buckets': [('0-30 хоног', 30), ('31-60 хоног', 60), ('61-90 хоног', 90), ('91-180 хоног', 180), ('180+ хоног', None)],
        'risk_from': 3,
        'risk_label': '90 хоногоос дээш',
    },
    'due': {
        'label': 'Төлөх огнооноос (хугацаа хэтрэлт)',
        'days': '%s - GREATEST(COALESCE("DueDate", "DocumentDate"), "DocumentDate")',
        'buckets': [('Хугацаа болоогүй', 0), ('1-30 хоног хэтэрсэн', 30), ('31-60 хоног', 60), ('61-90 хоног', 90), ('90+ хоног', None)],
        'risk_from': 1,
        'risk_label': 'Хугацаа хэтэрсэн',
    },
}
BUCKET_KEYS = ['b0', 'b1', 'b2', 'b3', 'b4']

GROUP_BY = {
    'customer': {'label': 'Харилцагчаар', 'key': '"CustomerId"'},
    'account': {'label': 'Дансаар', 'key': '"AccountId"'},
    'group': {'label': 'Харилцагчийн бүлгээр', 'key': 'COALESCE(NULLIF("CustomerGroupId", \'\'), \'(бүлэггүй)\')'},
}

BALANCE_FILTERS = {
    'nonzero': 'Үлдэгдэлтэй',
    'positive': 'Эерэг үлдэгдэлтэй',
    'negative': 'Хасах үлдэгдэлтэй (урьдчилгаа)',
    'overdue': 'Эрсдэлтэй (насжилтаар)',
    'all': 'Бүгд (гүйлгээтэй)',
}

EPS = 0.5  # бөөрөнхийлөлтийн үлдэгдлийг 0 гэж үзэх

CHANNEL_WHERE = '"CustomerId" IN (SELECT "Id" FROM "OpenDataCustomer" WHERE "DistributionChannelId" = ANY(%s))'


def _fetch(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        columns = [c.name for c in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]


def _where(kind, filters, date_to=True):
    """Нийтлэг шүүлтийн WHERE (данс, бүлэг, валют, хайлт, дуусах огноо хүртэл)."""
    cfg = KINDS[kind]
    parts = [cfg['account_where']]
    params = list(cfg['account_params'])
    if date_to:
        parts.append('"DocumentDate" <= %s')
        params.append(filters['date_to'])
    if filters.get('accounts'):
        parts.append('"AccountId" = ANY(%s)')
        params.append(list(filters['accounts']))
    if filters.get('groups'):
        parts.append('COALESCE(NULLIF("CustomerGroupId", \'\'), \'(бүлэггүй)\') = ANY(%s)')
        params.append(list(filters['groups']))
    if filters.get('currency'):
        parts.append('"CurrencyId" = %s')
        params.append(filters['currency'])
    if filters.get('q'):
        parts.append('("CustomerName" ILIKE %s OR "CustomerId" ILIKE %s OR "CustomerGroupId" ILIKE %s)')
        like = f"%{filters['q']}%"
        params += [like, like, like]
    if filters.get('customer'):
        parts.append('"CustomerId" = %s')
        params.append(filters['customer'])
    if filters.get('channels') is not None:
        parts.append(CHANNEL_WHERE)
        params.append(list(filters['channels']))
    return ' AND '.join(parts), params


def filter_options(kind, channels=None):
    """Шүүлтийн сонголтууд: данс, харилцагчийн бүлэг, валют (channels өгвөл зөвхөн тэр сувгуудын харилцагчдаас)."""
    cfg = KINDS[kind]
    where, params = cfg['account_where'], list(cfg['account_params'])
    if channels is not None:
        where, params = f'{where} AND {CHANNEL_WHERE}', params + [list(channels)]
    accounts = _fetch(
        f'SELECT "AccountId" AS id, MAX("AccountName") AS name, COUNT(*) AS n FROM {TABLE} '
        f'WHERE {where} GROUP BY 1 ORDER BY 1', params,
    )
    groups = _fetch(
        f'SELECT COALESCE(NULLIF("CustomerGroupId", \'\'), \'(бүлэггүй)\') AS id, COUNT(DISTINCT "CustomerId") AS n '
        f'FROM {TABLE} WHERE {where} GROUP BY 1 ORDER BY 1', params,
    )
    currencies = [r['id'] for r in _fetch(
        f'SELECT DISTINCT "CurrencyId" AS id FROM {TABLE} WHERE {where} ORDER BY 1', params,
    )]
    return {'accounts': accounts, 'groups': groups, 'currencies': currencies}


def _aging(kind, filters, key_expr):
    """Түлхүүр (харилцагч/данс/бүлэг) бүрийн эерэг үлдэгдлийн насжилт: {key: {b0..b4: дүн}}."""
    cfg = KINDS[kind]
    basis = AGING_BASES[filters.get('aging_basis', 'doc')]
    where, params = _where(kind, filters)
    limits = [limit for _, limit in basis['buckets'][:-1]]
    bucket_case = 'CASE ' + ' '.join(
        f"WHEN late <= {limit} THEN 'b{i}'" for i, limit in enumerate(limits)
    ) + f" ELSE 'b{len(limits)}' END"
    sql = f'''
        WITH base AS (
            SELECT *, {key_expr} AS k FROM {TABLE} WHERE {where}
        ),
        bal AS (
            SELECT "AccountId", "CustomerId", SUM({cfg['sign']}) AS b FROM base
            GROUP BY 1, 2 HAVING SUM({cfg['sign']}) > {EPS}
        ),
        ch AS (
            SELECT base.k, {cfg['increase']} AS amt, {basis['days']} AS late, bal.b,
                   SUM({cfg['increase']}) OVER (
                       PARTITION BY base."AccountId", base."CustomerId"
                       ORDER BY base."DocumentDate" DESC, base."RowNumber" DESC
                   ) AS cum
            FROM base JOIN bal ON bal."AccountId" = base."AccountId" AND bal."CustomerId" = base."CustomerId"
            WHERE {cfg['increase']} > 0
        )
        SELECT k, {bucket_case} AS bucket,
               SUM(LEAST(amt, b - (cum - amt))) AS amount
        FROM ch WHERE cum - amt < b
        GROUP BY 1, 2
    '''
    result = {}
    for r in _fetch(sql, params + [filters['date_to']]):
        result.setdefault(r['k'], {})[r['bucket']] = float(r['amount'] or 0)
    return result


def _rows(kind, filters):
    cfg = KINDS[kind]
    group_by = filters.get('group_by', 'customer')
    key_expr = GROUP_BY[group_by]['key']
    where, params = _where(kind, filters)
    sql = f'''
        SELECT {key_expr} AS k,
               MAX("CustomerName") AS customer_name,
               MAX("AccountName") AS account_name,
               MAX(COALESCE(NULLIF("CustomerGroupId", ''), '(бүлэггүй)')) AS group_name,
               COUNT(DISTINCT "CustomerId") AS customers,
               COUNT(DISTINCT "AccountId") AS accounts,
               STRING_AGG(DISTINCT "AccountId", ', ') AS account_ids,
               SUM(CASE WHEN "DocumentDate" < %s THEN {cfg['sign']} ELSE 0 END) AS opening,
               SUM(CASE WHEN "DocumentDate" >= %s THEN {cfg['increase']} ELSE 0 END) AS increase,
               SUM(CASE WHEN "DocumentDate" >= %s THEN {cfg['decrease']} ELSE 0 END) AS decrease,
               SUM({cfg['sign']}) AS closing,
               MAX("DocumentDate") AS last_date,
               MAX(CASE WHEN {cfg['decrease']} > 0 THEN "DocumentDate" END) AS last_payment,
               COUNT(*) FILTER (WHERE "DocumentDate" >= %s) AS tx_count
        FROM {TABLE} WHERE {where}
        GROUP BY 1
    '''
    d_from = filters['date_from']
    rows = _fetch(sql, [d_from, d_from, d_from, d_from] + params)
    aging = _aging(kind, filters, key_expr)
    risk_from = AGING_BASES[filters.get('aging_basis', 'doc')]['risk_from']

    result = []
    for r in rows:
        buckets = aging.get(r['k'], {})
        row = {
            'key': r['k'],
            'name': {
                'customer': r['customer_name'] or r['k'],
                'account': r['account_name'] or r['k'],
                'group': r['group_name'],
            }[group_by],
            'code': r['k'] if group_by != 'group' else '',
            'group': r['group_name'],
            'account': r['account_name'] if r['accounts'] == 1 else f"{r['accounts']} данс",
            'account_ids': r['account_ids'] or '',
            'customers': r['customers'],
            'opening': float(r['opening'] or 0),
            'increase': float(r['increase'] or 0),
            'decrease': float(r['decrease'] or 0),
            'closing': float(r['closing'] or 0),
            'last_date': r['last_date'].isoformat() if r['last_date'] else '',
            'last_payment': r['last_payment'].isoformat() if r['last_payment'] else '',
            'tx_count': r['tx_count'],
            **{b: round(buckets.get(b, 0.0), 2) for b in BUCKET_KEYS},
        }
        row['risk'] = round(sum(row[b] for b in BUCKET_KEYS[risk_from:]), 2)
        result.append(row)

    balance = filters.get('balance', 'nonzero')
    keep = {
        'nonzero': lambda r: abs(r['closing']) > EPS,
        'positive': lambda r: r['closing'] > EPS,
        'negative': lambda r: r['closing'] < -EPS,
        'overdue': lambda r: r['risk'] > EPS,
        'all': lambda r: abs(r['closing']) > EPS or r['tx_count'] or abs(r['opening']) > EPS,
    }[balance]
    result = [r for r in result if keep(r)]
    result.sort(key=lambda r: -r['closing'])
    return result


def _trend(kind, filters, months=12):
    """Дуусах огноогоор төгссөн сүүлийн N сарын: сарын эцсийн үлдэгдэл, нэмэгдсэн, төлөгдсөн."""
    cfg = KINDS[kind]
    end = filters['date_to']
    start = date(end.year, end.month, 1)
    for _ in range(months - 1):
        start = (start - timedelta(days=1)).replace(day=1)
    where, params = _where(kind, filters)
    opening = _fetch(
        f'SELECT COALESCE(SUM({cfg["sign"]}), 0) AS v FROM {TABLE} WHERE {where} AND "DocumentDate" < %s',
        params + [start],
    )[0]['v']
    monthly = {
        (r['m'].year, r['m'].month): r for r in _fetch(
            f'SELECT DATE_TRUNC(\'month\', "DocumentDate")::date AS m, SUM({cfg["sign"]}) AS net, '
            f'SUM({cfg["increase"]}) AS inc, SUM({cfg["decrease"]}) AS dec '
            f'FROM {TABLE} WHERE {where} AND "DocumentDate" >= %s GROUP BY 1',
            params + [start],
        )
    }
    result, running, cur = [], float(opening or 0), start
    while cur <= end:
        m = monthly.get((cur.year, cur.month), {})
        running += float(m.get('net') or 0)
        result.append({
            'label': f'{cur.year}.{cur.month:02d}',
            'balance': round(running, 2),
            'increase': float(m.get('inc') or 0),
            'decrease': float(m.get('dec') or 0),
        })
        cur = (cur.replace(day=28) + timedelta(days=4)).replace(day=1)
    return result


def build_report(kind, filters):
    rows = _rows(kind, filters)
    positive = [r for r in rows if r['closing'] > EPS]
    pos_total = sum(r['closing'] for r in positive)
    basis = AGING_BASES[filters.get('aging_basis', 'doc')]
    aging_totals = {b: sum(r[b] for r in rows) for b in BUCKET_KEYS}
    risk = sum(aging_totals[b] for b in BUCKET_KEYS[basis['risk_from']:])
    kpis = {
        'closing': sum(r['closing'] for r in rows),
        'positive': pos_total,
        'negative': sum(r['closing'] for r in rows if r['closing'] < -EPS),
        'opening': sum(r['opening'] for r in rows),
        'increase': sum(r['increase'] for r in rows),
        'decrease': sum(r['decrease'] for r in rows),
        'risk': risk,
        'risk_share': (risk / pos_total * 100) if pos_total > EPS else 0,
        'risk_label': basis['risk_label'],
        'count': len(rows),
        'count_positive': len(positive),
        'count_risk': sum(1 for r in rows if r['risk'] > EPS),
    }
    return {
        'rows': rows,
        'kpis': kpis,
        'aging': [
            {'key': k, 'label': label, 'amount': aging_totals[k], 'risk': i >= basis['risk_from'],
             'share': (aging_totals[k] / pos_total * 100) if pos_total > EPS else 0}
            for i, (k, (label, _)) in enumerate(zip(BUCKET_KEYS, basis['buckets']))
        ],
        'top': positive[:10],
        'trend': _trend(kind, filters),
    }


def ledger(kind, filters, customer, account=None, limit=1000):
    """Нэг харилцагчийн (сонгосон бол нэг дансны) хугацааны гүйлгээ, эхний/хуримтлагдах үлдэгдэлтэй."""
    cfg = KINDS[kind]
    f = {**filters, 'customer': customer, 'q': ''}
    if account:
        f['accounts'] = [account]
    where, params = _where(kind, f)
    opening = _fetch(
        f'SELECT COALESCE(SUM({cfg["sign"]}), 0) AS v FROM {TABLE} WHERE {where} AND "DocumentDate" < %s',
        params + [filters['date_from']],
    )[0]['v']
    rows = _fetch(
        f'SELECT "DocumentDate" AS d, "DocumentNumber" AS num, "DocumentDesc" AS descr, "AccountId" AS account, '
        f'"AccountName" AS account_name, "CurrencyId" AS cur, "DueDate" AS due, '
        f'{cfg["increase"]} AS inc, {cfg["decrease"]} AS dec '
        f'FROM {TABLE} WHERE {where} AND "DocumentDate" >= %s ORDER BY "DocumentDate", "RowNumber" LIMIT %s',
        params + [filters['date_from'], limit + 1],
    )
    running = float(opening or 0)
    items = []
    for r in rows[:limit]:
        running += float(r['inc'] or 0) - float(r['dec'] or 0)
        items.append({
            'date': r['d'].isoformat() if r['d'] else '',
            'number': r['num'] or '',
            'desc': r['descr'] or '',
            'account': f"{r['account']} {r['account_name'] or ''}".strip(),
            'currency': r['cur'] or '',
            'due': r['due'].isoformat() if r['due'] else '',
            'increase': float(r['inc'] or 0),
            'decrease': float(r['dec'] or 0),
            'balance': round(running, 2),
        })
    return {'opening': float(opening or 0), 'items': items, 'truncated': len(rows) > limit, 'closing': running}


# ---------------------------------------------------------------------------
# Төлөгдсөн (кредит) талын задаргаа - авлагыг юугаар хаасан бэ (касс, харилцах, буцаалт г.м.)
# ---------------------------------------------------------------------------
# OpenDataRecPay-д харьцсан данс байхгүй тул баримтын (DocumentPkId) ерөнхий журналын (OpenDataGeneralLedger)
# дебит мөрөөс авна. Бараа материал, өртөг, НӨАТ-ын мөр (буцаалтын хажуугийн бичилт) харьцсан данс биш тул
# алгасна. Нэг баримтад олон дебит мөр байвал: тухайн харилцагчийн мөр -> касс/харилцах -> хамгийн их дүнтэй.
CONTRA_SKIP = ('15', '61', '3106', '1202')

# (данс эхлэх, бүлгийн түлхүүр, нэр, тэмдэг) - эхний таарсан нь
CREDIT_CATEGORIES = [
    ('10', 'cash', 'Касс (бэлэн мөнгө)', '💵'),
    ('11', 'bank', 'Харилцах (банк)', '🏦'),
    ('5202', 'refund', 'Борлуулалтын буцаалт', '↩️'),
    ('5201', 'discount', 'Борлуулалтын хөнгөлөлт', '🏷️'),
]
OTHER_CATEGORY = ('other', 'Бусад', '📄')


def _credit_category(account_id):
    for prefix, key, label, icon in CREDIT_CATEGORIES:
        if account_id and account_id.startswith(prefix):
            return key, label, icon
    return OTHER_CATEGORY


def credit_breakdown(kind, filters):
    """Хугацааны кредит (төлөгдсөн) дүнг харьцсан дансаар: [{key, label, icon, amount, count, share, accounts: [...]}].
    Данс бүр гүйлгээнийхээ жагсаалттай (items, шинэ нь эхэнд) - дарахад задарна."""
    cfg = KINDS[kind]
    where, params = _where(kind, filters)
    skip = ' AND '.join('g."AccountId" NOT LIKE %s' for _ in CONTRA_SKIP)
    sql = f'''
        WITH cr AS (
            SELECT "RowNumber" AS rn, "DocumentPkId", "CustomerId", "AccountId", {cfg['decrease']} AS amt,
                   "DocumentDate", "DocumentNumber", "DocumentDesc", "CustomerName"
            FROM {TABLE} WHERE {where} AND "DocumentDate" >= %s AND {cfg['decrease']} > 0
        ),
        contra AS (
            SELECT DISTINCT ON (cr.rn) cr.rn, g."AccountId" AS account, g."AccountName" AS account_name
            FROM cr JOIN "OpenDataGeneralLedger" g ON g."DocumentPkId" = cr."DocumentPkId"
            WHERE g."DebitAmt" > 0 AND g."AccountId" <> cr."AccountId" AND {skip}
            ORDER BY cr.rn, (g."CustomerId" = cr."CustomerId") DESC NULLS LAST,
                     (g."AccountId" LIKE '10%%' OR g."AccountId" LIKE '11%%') DESC, g."DebitAmt" DESC
        ),
        doc_type AS (
            SELECT DISTINCT ON (g."DocumentPkId") g."DocumentPkId", g."DocumentTypeName" AS doc_type
            FROM "OpenDataGeneralLedger" g WHERE g."DocumentPkId" IN (SELECT "DocumentPkId" FROM cr)
        )
        SELECT contra.account, contra.account_name, doc_type.doc_type, cr.amt, cr."DocumentDate" AS d,
               cr."DocumentNumber" AS num, cr."DocumentDesc" AS descr, cr."CustomerId" AS customer_id,
               cr."CustomerName" AS customer_name
        FROM cr LEFT JOIN contra ON contra.rn = cr.rn
        LEFT JOIN doc_type ON doc_type."DocumentPkId" = cr."DocumentPkId"
        ORDER BY cr."DocumentDate" DESC, cr.rn DESC
    '''
    rows = _fetch(sql, params + [filters['date_from']] + [p + '%' for p in CONTRA_SKIP])
    total = sum(float(r['amt'] or 0) for r in rows)
    groups, accounts = {}, {}
    for r in rows:
        key, label, icon = _credit_category(r['account'])
        group = groups.setdefault(key, {'key': key, 'label': label, 'icon': icon, 'amount': 0.0, 'count': 0, 'accounts': []})
        # Харьцсан данс олдоогүй гүйлгээг баримтын төрлөөр нь ялгана
        acc_key = r['account'] or f"?{r['doc_type'] or ''}"
        account = accounts.get(acc_key)
        if account is None:
            account = accounts[acc_key] = {
                'code': r['account'] or '',
                'name': r['account_name'] or r['doc_type'] or 'Харьцсан данс тодорхойгүй',
                'doc_type': r['doc_type'] or '',
                'amount': 0.0, 'count': 0, 'items': [],
            }
            group['accounts'].append(account)
        amount = float(r['amt'] or 0)
        group['amount'] += amount
        group['count'] += 1
        account['amount'] += amount
        account['count'] += 1
        account['items'].append({
            'date': r['d'].isoformat() if r['d'] else '',
            'number': r['num'] or '',
            'customer': (r['customer_name'] or r['customer_id'] or '').strip(),
            'desc': r['descr'] or '',
            'amount': amount,
        })
    order = [c[1] for c in CREDIT_CATEGORIES] + [OTHER_CATEGORY[0]]
    result = sorted(groups.values(), key=lambda g: order.index(g['key']))
    for g in result:
        g['share'] = g['amount'] / total * 100 if total > EPS else 0
        g['accounts'].sort(key=lambda a: -a['amount'])
        for a in g['accounts']:
            a['share'] = a['amount'] / g['amount'] * 100 if g['amount'] > EPS else 0
    return {'groups': result, 'total': total, 'count': sum(g['count'] for g in result)}
