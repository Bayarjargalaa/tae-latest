"""
Борлуулалтын нэмэгдэл бодох - албан тушаал бүрийн хүснэгтээр (SalesBonusMember.scheme).

Өгөгдөл (цалин бодох сарын 1-нээс сүүлийн өдөр хүртэл):
- Борлуулалт = харилцагчийн авлагын (дансны авлага 1201xx, OpenDataRecPay) кредит талын нийлбэр, харилцагчийн
  борлуулалтын сувгаар (OpenDataCustomer.DistributionChannelName). ХТ-ийн суваг нь өөрийнх нь нэртэй суваг.
- Буцаалт = OpenDataSaleRefund-ийн дүн, харилцагчийн сувгаар.
- Түгээлт = OpenDataDelivery-ийн дүн, түгээгчээр (DistributorId = ажилтны код); өдөр = түгээлт хийсэн өдрийн тоо.
- Нярав: борлуулалт = борлуулалтын бүртгэл (OpenDataSale.PayAmount), буцаалт = OpenDataSaleRefund - хоёулаа
  өдрөөр. Үндсэн нярав байхгүй өдрүүдэд орлосон хүний
  (SalesBonusSubstitute) өдрүүдийн дүн тэр хүнд бүтнээр очно (storekeeper_allocation).
Автомат утга бүрийг тухайн сард гараар засаж болно (inputs-д null биш утга).

Хүснэгтүүд (мөр бүр: нэмэгдэл = (борлуулалт - буцаалт) x хувь):
- Нярав:  (ажилласан өдрүүдийн борлуулалт - буцаалт) x хувь + тооллого.
- Худалдааны төлөөлөгч, Борлуулагч:
      нийт нэмэгдэл = мөрүүдийн нэмэгдэл
      хасагдах      = нийт x суурь% (10%) x тасралтын хувь
      биелэлтээр    = нийт x суурь% x (100% - төлөвлөгөөт барааны биелэлтийн хувь)
      нэмэгдэл      = нийт - хасагдах - биелэлтээр
- Түгээгч: түгээлтийн дүн x шалгуур бүрийн хувь (биелсэн шалгуураар) + туслахгүй өдөр x мөнгө + хамт өдөр x мөнгө
- Алтжин худалдагч: дэлгүүрийн агуулахын (тохиргоо: altjin.warehouse_id) сарын борлуулалт (OpenDataSale.PayAmount) -
  буцаалт (OpenDataSaleRefund.Amount) = цэвэр дүнд шатлалын хувь (altjin.tiers, жиш: 20 сая хүртэл 1%, түүнээс дээш 2%).
  altjin.mode: 'marginal' - шат бүрийн хувь зөвхөн тэр шатанд орсон хэсэгт (20 сая x 1% + давсан хэсэг x 2%),
  'flat' - цэвэр дүн аль шатанд орсноор бүх дүнд тэр шатны хувь (tier_bonus).
Бүгдэд нь гараар нэмэх/хасах дүн (adjustment) нэмэгдэнэ; эцсийн дүнг 2 орон хүртэл бөөрөнхийлнө.

Сувгаас шилжүүлэх (ХТ, Борлуулагч): нэг ажилтан өөр ажилтны сувгаас тодорхой дүнг гараар авч болно
(inputs.transfers = [{"channel", "amount", "rate"}]). Тэр дүн хүлээн авагчид тусдаа мөрөөр (дүн x хувь) нэмэгдэж,
сувгийн эзний тэр сувгийн мөрийн цэвэр дүнгээс хасагдана (борлуулалт - буцаалт - шилжүүлсэн).
"""
import copy
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import connection

ZERO = Decimal(0)
RECEIVABLE_ACCOUNT_PREFIX = '1201'  # Дансны авлага

DEFAULT_SETTINGS = {
    'deduction_base_pct': 10,
    'default_rates': {'storekeeper': 0.04, 'sales_rep': 0.75, 'cash_seller': 1.2},
    'distributor': {
        'criteria': [
            {'key': 'doc_complete', 'label': 'Баримт бүрдэл', 'rate': 0.5},
            {'key': 'doc_keeping', 'label': 'Баримт хөтлөлт', 'rate': 0.1},
            {'key': 'delivery_full', 'label': 'Хүргэлт бүрэн хийгдэх', 'rate': 0.1},
        ],
        'solo_day': 40000,
        'helper_day': 20000,
    },
    'position_schemes': {
        'Нярав': 'storekeeper',
        'Худалдааны төлөөлөгч': 'sales_rep',
        'Борлуулагч': 'cash_seller',
        'Түгээгч': 'distributor',
        'Алтжин худалдагч': 'altjin_seller',
    },
    # Алтжин худалдагч: дэлгүүрийн агуулахын цэвэр борлуулалтын шатлал. upto - шатны дээд хязгаар (₮, None - түүнээс дээш)
    'altjin': {
        'warehouse_id': '002',
        'mode': 'marginal',
        'tiers': [{'upto': 20000000, 'rate': 1}, {'upto': None, 'rate': 2}],
    },
    'cash_seller_channel': 'Бэлэн борлуулагч',
    # Борлуулагчийн нэмэгдлийн хугацаа: өмнөх сарын N-нээс энэ сарын N-1 хүртэл (1 бол хуанлийн сар)
    'cash_seller_start_day': 21,
}


def D(value, default=ZERO):
    if value is None or value == '':
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return default


def cents(value):
    """Мөнгөн дүнг 2 орон хүртэл бөөрөнхийлнө (бутархай хадгалагдана)."""
    return Decimal(value).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def get_settings(setting):
    """PayrollSetting.sales_bonus_settings-ийг анхдагчтай нэгтгэнэ."""
    result = copy.deepcopy(DEFAULT_SETTINGS)
    saved = setting.sales_bonus_settings or {}
    for key, value in saved.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key].update(value)
        else:
            result[key] = value
    return result


def month_range(year, month):
    import calendar
    from datetime import date
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def channel_names():
    with connection.cursor() as cursor:
        cursor.execute('SELECT "Name" FROM "OpenDataDistributionChannel" ORDER BY "Id"')
        return [r[0] for r in cursor.fetchall()]


def period_range(year, month, scheme, settings):
    """Хүснэгтийн бодох хугацаа: борлуулагчид өмнөх сарын N-нээс энэ сарын N-1 хүртэл, бусдад хуанлийн сар."""
    from datetime import date, timedelta
    start_day = int(settings.get('cash_seller_start_day') or 1) if scheme == 'cash_seller' else 1
    if start_day <= 1:
        return month_range(year, month)
    prev_year, prev_month = (year, month - 1) if month > 1 else (year - 1, 12)
    import calendar
    start = date(prev_year, prev_month, min(start_day, calendar.monthrange(prev_year, prev_month)[1]))
    end = date(year, month, min(start_day, calendar.monthrange(year, month)[1])) - timedelta(days=1)
    return start, end


def period_label(start, end):
    return f'{start.year} он {start:%m.%d}-{end:%m.%d}' if start.year == end.year else f'{start:%Y.%m.%d}-{end:%Y.%m.%d}'


def month_data(year, month, start=None, end=None):
    """Хугацааны (анхдагч: хуанлийн сар) автомат утгууд: сувгийн кредит, буцаалт; түгээгчийн түгээлт, өдөр;
    нийт түгээлт; няравын өдрийн борлуулалт, буцаалт."""
    if start is None or end is None:
        start, end = month_range(year, month)
    with connection.cursor() as cursor:
        cursor.execute(
            '''
            SELECT COALESCE(c."DistributionChannelName", ''), SUM(r."CreditAmt")
            FROM "OpenDataRecPay" r LEFT JOIN "OpenDataCustomer" c ON c."Id" = r."CustomerId"
            WHERE r."AccountId" LIKE %s AND r."DocumentDate" BETWEEN %s AND %s
            GROUP BY 1
            ''', [RECEIVABLE_ACCOUNT_PREFIX + '%', start, end],
        )
        credits = {name: D(v) for name, v in cursor.fetchall()}
        # Суваг бүрийн кредит ямар данснаас (дансны нэр) - ХТ-ийн хүснэгт, хэвлэлтэд "Борлуулалт"-ын оронд харуулна
        cursor.execute(
            '''
            SELECT COALESCE(c."DistributionChannelName", ''), r."AccountId", MAX(r."AccountName"), SUM(r."CreditAmt")
            FROM "OpenDataRecPay" r LEFT JOIN "OpenDataCustomer" c ON c."Id" = r."CustomerId"
            WHERE r."AccountId" LIKE %s AND r."DocumentDate" BETWEEN %s AND %s AND r."CreditAmt" > 0
            GROUP BY 1, 2 ORDER BY 1, 4 DESC
            ''', [RECEIVABLE_ACCOUNT_PREFIX + '%', start, end],
        )
        channel_accounts = {}
        for channel, account_id, account_name, amount in cursor.fetchall():
            channel_accounts.setdefault(channel, []).append(
                {'id': account_id, 'name': account_name or account_id, 'amount': D(amount)})
        cursor.execute(
            '''
            SELECT COALESCE(c."DistributionChannelName", ''), SUM(f."Amount")
            FROM "OpenDataSaleRefund" f LEFT JOIN "OpenDataCustomer" c ON c."Id" = f."CustomerId"
            WHERE f."DocumentDate" BETWEEN %s AND %s
            GROUP BY 1
            ''', [start, end],
        )
        returns = {name: D(v) for name, v in cursor.fetchall()}
        cursor.execute(
            '''
            SELECT "DistributorId", SUM("Amount"), COUNT(DISTINCT "DocumentDate")
            FROM "OpenDataDelivery" WHERE "DocumentDate" BETWEEN %s AND %s AND "DistributorId" IS NOT NULL
            GROUP BY 1
            ''', [start, end],
        )
        delivery = {code: {'amount': D(amount), 'days': days} for code, amount, days in cursor.fetchall()}
        cursor.execute('SELECT SUM("Amount") FROM "OpenDataDelivery" WHERE "DocumentDate" BETWEEN %s AND %s', [start, end])
        delivery_total = D(cursor.fetchone()[0])
        # Няравын бодолтод өдрөөр: борлуулалтын бүртгэл (OpenDataSale), буцаалт
        cursor.execute(
            'SELECT "DocumentDate", SUM("PayAmount") FROM "OpenDataSale" WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1',
            [start, end],
        )
        sales_by_day = {d.isoformat(): D(v) for d, v in cursor.fetchall()}
        cursor.execute(
            'SELECT "DocumentDate", SUM("Amount") FROM "OpenDataSaleRefund" WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1',
            [start, end],
        )
        returns_by_day = {d.isoformat(): D(v) for d, v in cursor.fetchall()}
        # Алтжин худалдагчид: агуулахаар борлуулалт, буцаалт
        cursor.execute(
            'SELECT "WarehouseId", SUM("PayAmount") FROM "OpenDataSale" WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1',
            [start, end],
        )
        warehouse_sales = {w: {'sales': D(v), 'returns': ZERO} for w, v in cursor.fetchall()}
        cursor.execute(
            'SELECT "WarehouseId", SUM("Amount") FROM "OpenDataSaleRefund" WHERE "DocumentDate" BETWEEN %s AND %s GROUP BY 1',
            [start, end],
        )
        for w, v in cursor.fetchall():
            warehouse_sales.setdefault(w, {'sales': ZERO, 'returns': ZERO})['returns'] = D(v)
    return {
        'warehouse_sales': warehouse_sales,
        'sales_by_day': sales_by_day,
        'returns_by_day': returns_by_day,
        'credits': credits,
        'channel_accounts': channel_accounts,
        'returns': returns,
        'delivery': delivery,
        'delivery_total': delivery_total,
        'returns_total': sum(returns.values(), ZERO),
    }


def tier_bonus(net, tiers, mode):
    """Шатлалын нэмэгдэл: (мөрүүд, нийт). Мөр бүр {from, to, rate, base, bonus}. Цэвэр дүн сөрөг бол 0.

    marginal - шат бүрт орсон хэсэгт тэр шатны хувь (20 сая хүртэл 1%, давсан хэсэгт 2%);
    flat     - цэвэр дүн орсон шатны хувь бүх дүнд (20 сая давбал бүхэлд нь 2%)."""
    tiers = sorted(tiers or [], key=lambda t: (t.get('upto') is None, D(t.get('upto'))))
    net = max(D(net), ZERO)
    rows, lower = [], ZERO
    for t in tiers:
        upper = None if t.get('upto') is None else D(t['upto'])
        rate = D(t.get('rate'))
        if mode == 'flat':
            if upper is None or net <= upper or t is tiers[-1]:
                rows.append({'from': lower, 'to': upper, 'rate': rate, 'base': net, 'bonus': net * rate / 100, 'active': True})
                break
        else:
            part = max((net if upper is None else min(net, upper)) - lower, ZERO)
            rows.append({'from': lower, 'to': upper, 'rate': rate, 'base': part, 'bonus': part * rate / 100, 'active': part > 0})
        if upper is None:
            break
        lower = upper
    return rows, sum((r['bonus'] for r in rows), ZERO)


def _base_name(name):
    """"Мөнхжаргал.Т" -> "Мөнхжаргал" (сувгийн нэртэй тааруулахад)."""
    return (name or '').split('.')[0].split('/')[0].strip()


def default_channels(scheme, employee_name, channels, settings):
    rate = settings['default_rates'].get(scheme)
    if scheme == 'sales_rep':
        base = _base_name(employee_name)
        matched = [c for c in channels if base and base in c]
        return [{'channel': c, 'rate': str(rate)} for c in matched]
    if scheme == 'cash_seller':
        name = settings.get('cash_seller_channel')
        return [{'channel': name, 'rate': str(rate)}] if name in channels else []
    if scheme == 'storekeeper':
        return [{'channel': STOREKEEPER_LINE, 'rate': str(rate)}]
    return []  # түгээгч, Алтжин худалдагч - сувгаар бодохгүй


STOREKEEPER_LINE = 'Борлуулалт'


def month_days(year, month):
    from datetime import timedelta
    start, end = month_range(year, month)
    return [(start + timedelta(days=i)).isoformat() for i in range((end - start).days + 1)]


def storekeeper_allocation(year, month, main_codes, substitutes):
    """Өдөр бүрийн няравын борлуулалтыг хэнд хэдэн хувиар оногдохыг бодно: {код: {огноо: хувь (0-1)}}.

    Анхдагчаар бүх өдөр үндсэн няравт (хэд хэдэн үндсэн нярав бол тэнцүү). Орлогч бүртгэсэн өдөр - зөвхөн орлогчид
    (өдрүүд давхцахгүй тул нэг хүн; давхцсан хуучин өгөгдөл байвал эхний бүртгэл)."""
    alloc = {}
    for day in month_days(year, month):
        substitute = next((s.employee_code for s in substitutes if day in (s.dates or [])), None)
        people = [substitute] if substitute else list(dict.fromkeys(main_codes))
        for code in people:
            alloc.setdefault(code, {})[day] = Decimal(1) / len(people)
    return alloc


def ensure_members(settings):
    """Албан тушаал нь хүснэгттэй таарсан идэвхтэй ажилчдыг анх удаа автоматаар нэмнэ (хассан ажилтныг дахин нэмэхгүй)."""
    from datamigration.models import OpenDataEmployee
    from shop.models import SalesBonusMember

    position_schemes = settings['position_schemes']
    existing = set(SalesBonusMember.objects.values_list('employee_code', flat=True))
    channels = None
    for e in OpenDataEmployee.objects.filter(isreclusion='N', positionname__in=list(position_schemes)):
        if e.id in existing:
            continue
        channels = channels if channels is not None else channel_names()
        scheme = position_schemes[e.positionname]
        SalesBonusMember.objects.create(
            employee_code=e.id, scheme=scheme, channels=default_channels(scheme, e.name, channels, settings),
        )


def transfers_map(year, month, scheme, overrides=None):
    """Тухайн сарын, хүснэгтийн сувгаас шилжүүлгүүд: {суваг: [{'code', 'amount'}]} (хадгалсан бодолтуудаас).
    overrides - {ажилтны код: inputs} хадгалж буй (шинэ) утгууд хадгалсныг орлоно."""
    from shop.models import SalesBonusEntry

    inputs_by_code = dict(SalesBonusEntry.objects.filter(year=year, month=month, scheme=scheme).values_list('employee_code', 'inputs'))
    inputs_by_code.update(overrides or {})
    result = {}
    for code, inputs in inputs_by_code.items():
        for t in (inputs or {}).get('transfers') or []:
            amount = D(t.get('amount'))
            if t.get('channel') and amount:
                result.setdefault(t['channel'], []).append({'code': code, 'amount': amount})
    return result


def compute(member, inputs, data, settings, alloc=None, transfers_out=None):
    """Нэг ажилтны нэмэгдлийн бодолт. inputs - тухайн сарын оруулсан утгууд (хоосон бол анхдагч).
    alloc - няравт: {огноо: хувь} (storekeeper_allocation) - тэр өдрүүдийн борлуулалт, буцаалтыг авна.
    transfers_out - transfers_map(): бусад ажилтанд шилжүүлсэн дүн сувгийн мөрийн цэвэр дүнгээс хасагдана."""
    scheme = member.scheme
    transfers_out = transfers_out or {}
    result = {'scheme': scheme, 'lines': [], 'steps': []}

    if scheme == 'storekeeper':
        alloc = alloc or {}
        auto_sales = sum((data['sales_by_day'].get(d, ZERO) * f for d, f in alloc.items()), ZERO)
        auto_returns = sum((data['returns_by_day'].get(d, ZERO) * f for d, f in alloc.items()), ZERO)
        line = (inputs.get('lines') or [{}])[0]
        rate = D(line.get('rate'), D((member.channels or [{}])[0].get('rate'), D(settings['default_rates']['storekeeper'])))
        sales = D(line.get('sales'), auto_sales)
        returns = D(line.get('returns'), auto_returns)
        bonus = (sales - returns) * rate / 100
        full_days = sum(1 for f in alloc.values() if f == 1)
        shared = sorted(d for d, f in alloc.items() if f < 1)
        result['lines'].append({
            'channel': STOREKEEPER_LINE, 'rate': rate, 'auto_sales': auto_sales, 'auto_returns': auto_returns,
            'sales': sales, 'returns': returns, 'sales_override': line.get('sales') not in (None, ''),
            'returns_override': line.get('returns') not in (None, ''), 'net': sales - returns, 'bonus': bonus,
        })
        inventory = D(inputs.get('inventory'))
        adjustment = D(inputs.get('adjustment'))
        result.update({
            'subtotal': bonus, 'inventory': inventory, 'days_worked': sum(alloc.values(), ZERO),
            'full_days': full_days, 'shared_days': shared, 'worked_dates': sorted(alloc),
            'adjustment': adjustment, 'total': cents(bonus + inventory + adjustment),
        })
        return result

    if scheme == 'distributor':
        dist = settings['distributor']
        auto = data['delivery'].get(member.employee_code, {'amount': ZERO, 'days': 0})
        amount = D(inputs.get('delivery_amount'), auto['amount'])
        criteria_state = inputs.get('criteria') or {}
        total = ZERO
        criteria = []
        for c in dist['criteria']:
            met = criteria_state.get(c['key'], True)
            value = amount * D(c['rate']) / 100 if met else ZERO
            criteria.append({**c, 'met': met, 'amount': value})
            total += value
        solo_days = D(inputs.get('solo_days'), Decimal(auto['days']))
        helper_days = D(inputs.get('helper_days'))
        solo = solo_days * D(dist['solo_day'])
        helper = helper_days * D(dist['helper_day'])
        total += solo + helper
        result.update({
            'delivery_auto': auto['amount'], 'delivery_amount': amount, 'days_auto': auto['days'],
            'criteria': criteria, 'solo_days': solo_days, 'helper_days': helper_days,
            'solo_amount': solo, 'helper_amount': helper, 'subtotal': total,
        })
    elif scheme == 'altjin_seller':
        cfg = settings['altjin']
        auto = data['warehouse_sales'].get(cfg['warehouse_id'], {'sales': ZERO, 'returns': ZERO})
        sales = D(inputs.get('sales'), auto['sales'])
        returns = D(inputs.get('returns'), auto['returns'])
        tiers, total = tier_bonus(sales - returns, cfg['tiers'], cfg['mode'])
        result.update({
            'auto_sales': auto['sales'], 'auto_returns': auto['returns'], 'sales': sales, 'returns': returns,
            'sales_override': inputs.get('sales') not in (None, ''), 'returns_override': inputs.get('returns') not in (None, ''),
            'net': sales - returns, 'tiers': tiers, 'mode': cfg['mode'], 'subtotal': total,
        })
    else:
        lines_in = inputs.get('lines')
        if lines_in is None:
            lines_in = member.channels
        subtotal = ZERO
        for line in lines_in:
            channel = line.get('channel')
            auto_sales, auto_returns = data['credits'].get(channel, ZERO), data['returns'].get(channel, ZERO)
            sales = D(line.get('sales'), auto_sales)
            returns = D(line.get('returns'), auto_returns)
            rate = D(line.get('rate'))
            # Энэ сувгаас бусад ажилтанд шилжүүлсэн дүн
            out = [t for t in transfers_out.get(channel, []) if t['code'] != member.employee_code]
            transferred = sum((t['amount'] for t in out), ZERO)
            net = sales - returns - transferred
            bonus = net * rate / 100
            subtotal += bonus
            result['lines'].append({
                'channel': channel, 'rate': rate, 'auto_sales': auto_sales, 'auto_returns': auto_returns,
                'sales': sales, 'returns': returns, 'sales_override': line.get('sales') not in (None, ''),
                'returns_override': line.get('returns') not in (None, ''), 'transfers_out': out,
                'transferred': transferred, 'net': net, 'bonus': bonus,
            })
        # Бусад ажилтны сувгаас шилжүүлж авсан дүн (дүн x хувь)
        result['transfers'] = []
        for t in inputs.get('transfers') or []:
            amount, rate = D(t.get('amount')), D(t.get('rate'))
            bonus = amount * rate / 100
            subtotal += bonus
            result['transfers'].append({'channel': t.get('channel'), 'amount': amount, 'rate': rate, 'bonus': bonus})
        result['subtotal'] = subtotal
        total = subtotal
        base_pct = D(settings['deduction_base_pct'])
        deduction_pct = D(inputs.get('deduction_pct'))
        plan_pct = D(inputs.get('plan_pct'), Decimal(100))
        base = subtotal * base_pct / 100
        deduction = base * deduction_pct / 100
        plan_part = base * plan_pct / 100
        plan_loss = base - plan_part
        result.update({
            'base_pct': base_pct, 'deduction_pct': deduction_pct, 'deduction': deduction,
            'plan_pct': plan_pct, 'plan_part': plan_part, 'plan_loss': plan_loss,
        })
        total = subtotal - deduction - plan_loss

    adjustment = D(inputs.get('adjustment'))
    result['adjustment'] = adjustment
    result['total'] = cents(total + adjustment)
    return result


def allocate(total, pay_type, cash_input):
    """Нэмэгдлийг карт / бэлэнд хуваарилна: карт-бэлэн ажилтанд бүгд тухайн хуудсанд, хосолсонд бэлнийг оруулж
    үлдсэнийг картад."""
    if pay_type == 'cash':
        return ZERO, total
    if pay_type == 'card' or not pay_type:
        return total, ZERO
    cash = min(max(cents(D(cash_input)), ZERO), max(total, ZERO))
    return total - cash, cash


def sync_payroll(code, year, month, user):
    """Ажилтны тухайн сарын бүх нэмэгдлийн бодолтын (хүснэгт бүрээс) карт / бэлэн нийлбэрийг цалин бодолтод бичнэ."""
    from django.db.models import Sum
    from shop.models import PayrollEntry, SalesBonusEntry

    sums = SalesBonusEntry.objects.filter(employee_code=code, year=year, month=month).aggregate(
        card=Sum('card_amount'), cash=Sum('cash_amount'))
    set_payroll_value(code, year, month, PayrollEntry.SHEET_CARD, 'sales_bonus', sums['card'] or ZERO, user)
    set_payroll_value(code, year, month, PayrollEntry.SHEET_CASH, 'sales_bonus', sums['cash'] or ZERO, user)


def storekeeper_people(year, month, settings):
    """Тухайн сарын няравын хүснэгтийн хүмүүс: [(member, alloc)] - үндсэн няравууд + орлогч/хамт ажилласан хүмүүс.
    Орлогч нь өөр албан тушаалтай (өөр хүснэгтэд байгаа) байж болох тул түр "member" объект үүсгэнэ."""
    from types import SimpleNamespace
    from shop.models import SalesBonusMember, SalesBonusSubstitute

    mains = list(SalesBonusMember.objects.filter(is_active=True, scheme='storekeeper').order_by('sort_order', 'employee_code'))
    subs = list(SalesBonusSubstitute.objects.filter(year=year, month=month))
    alloc = storekeeper_allocation(year, month, [m.employee_code for m in mains], subs)
    people = [(m, alloc.get(m.employee_code, {})) for m in mains]
    main_codes = {m.employee_code for m in mains}
    for code in dict.fromkeys(s.employee_code for s in subs):
        if code in main_codes:
            continue
        member = SalesBonusMember.objects.filter(employee_code=code).first()
        people.append((SimpleNamespace(
            employee_code=code, scheme='storekeeper', is_substitute=True,
            channels=member.channels if member and member.scheme == 'storekeeper' else [],
            source=None, sort_order=999,
        ), alloc.get(code, {})))
    return people


# Сараар ажилтан нэмж / хасаж болох хүснэгтүүд
MONTH_EDITABLE_SCHEMES = ('distributor',)


def month_people(year, month, scheme):
    """Тухайн сарын хүснэгтийн хүмүүс: байнгын идэвхтэй гишүүд - тэр сард хассан + тэр сард нэмсэн
    (SalesBonusMonthMember). Нэмсэн ажилтан өөр хүснэгтэд / гишүүнгүй байж болох тул түр "member" объект үүсгэнэ."""
    from types import SimpleNamespace
    from shop.models import SalesBonusMember, SalesBonusMonthMember

    overrides = list(SalesBonusMonthMember.objects.filter(year=year, month=month, scheme=scheme))
    excluded = {o.employee_code for o in overrides if o.excluded}
    people = [m for m in SalesBonusMember.objects.filter(is_active=True, scheme=scheme) if m.employee_code not in excluded]
    codes = {m.employee_code for m in people}
    for o in overrides:
        if o.excluded or o.employee_code in codes:
            continue
        codes.add(o.employee_code)
        people.append(SimpleNamespace(
            employee_code=o.employee_code, scheme=scheme, is_month_extra=True, channels=[], source=None, sort_order=999,
        ))
    return people


def recompute_storekeepers(year, month, settings, user):
    """Орлолт өөрчлөгдсөний дараа тухайн сарын хадгалсан няравын бодолтуудыг шинэ хуваарилалтаар дахин бодож,
    хуваарилалтгүй болсон (орлолтоо хассан) хүний бодолтыг устгаад цалин бодолтыг шинэчилнэ."""
    from shop.models import EmployeePayProfile, SalesBonusEntry

    people = {m.employee_code: (m, a) for m, a in storekeeper_people(year, month, settings)}
    pay_types = dict(EmployeePayProfile.objects.values_list('employee_code', 'pay_type'))
    data = None
    for entry in SalesBonusEntry.objects.filter(year=year, month=month, scheme='storekeeper'):
        if entry.employee_code not in people:
            entry.delete()
        else:
            data = data or month_data(year, month)
            member, alloc = people[entry.employee_code]
            result = compute(member, entry.inputs, data, settings, alloc)
            card, cash = allocate(result['total'], pay_types.get(entry.employee_code), entry.cash_amount)
            entry.total, entry.card_amount, entry.cash_amount, entry.updated_by = result['total'], card, cash, user
            entry.save()
        sync_payroll(entry.employee_code, year, month, user)


def set_payroll_value(code, year, month, sheet, field, value, user):
    """PayrollEntry-ийн нэг гар утгыг бичнэ; бүх гар утга 0 болсон мөрийг устгана."""
    from shop.models import PayrollEntry
    from shop.services.payroll import entry_has_values

    entry = PayrollEntry.objects.filter(employee_code=code, year=year, month=month, sheet=sheet).first()
    if entry is None:
        if value:
            PayrollEntry.objects.create(
                employee_code=code, year=year, month=month, sheet=sheet, updated_by=user, **{field: value},
            )
        return
    setattr(entry, field, value)
    if not entry_has_values(entry):
        entry.delete()
    else:
        entry.updated_by = user
        entry.save()
