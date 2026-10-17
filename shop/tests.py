from django.test import SimpleTestCase
from django.urls import get_resolver

from shop.menuconfig import ADMIN_ONLY_URL_NAMES, PUBLIC_URL_NAMES, get_url_menu_keys


class MenuPermissionCoverageTests(SimpleTestCase):
    """shop-ийн хуудас бүр цэсний эрхэд ангилагдсан байх ёстой (shop.access, MenuPermissionMiddleware).
    Шинэ хуудас нэмэхдээ menuconfig-ийн цэс / SUBPAGE_MENU_KEYS / PUBLIC_URL_NAMES / ADMIN_ONLY_URL_NAMES-ийн
    аль нэгэнд оруулаагүй бол энэ тест унана (оруулаагүй хуудас зөвхөн superuser-т нээгдэнэ)."""

    def shop_url_names(self):
        resolver = get_resolver()
        shop_resolver = resolver.namespace_dict['shop'][1]
        return {name for name in shop_resolver.reverse_dict.keys() if isinstance(name, str)}

    def test_every_shop_url_is_classified(self):
        classified = set(get_url_menu_keys()) | PUBLIC_URL_NAMES | ADMIN_ONLY_URL_NAMES
        missing = sorted(self.shop_url_names() - classified)
        self.assertEqual(missing, [], f'Цэсний эрхэд ангилаагүй хуудас: {missing}')

    def test_classifications_do_not_overlap(self):
        menu = set(get_url_menu_keys())
        self.assertEqual(sorted(menu & PUBLIC_URL_NAMES), [])
        self.assertEqual(sorted(menu & ADMIN_ONLY_URL_NAMES), [])
        self.assertEqual(sorted(PUBLIC_URL_NAMES & ADMIN_ONLY_URL_NAMES), [])

    def test_classified_names_exist(self):
        stale = sorted((set(get_url_menu_keys()) | PUBLIC_URL_NAMES | ADMIN_ONLY_URL_NAMES) - self.shop_url_names())
        self.assertEqual(stale, [], f'Байхгүй хуудасны нэр: {stale}')


class ImportCalcTests(SimpleTestCase):
    """services.imports - хайрцаг/тоо/үнийн уялдаа."""

    def test_pack_size_from_name_when_qty_in_package_missing(self):
        from shop.services.imports import pack_size
        self.assertEqual(pack_size(0, "Чихэр Mint T548CT 150g 1х*48ш Walker's Англи"), 48)
        self.assertEqual(pack_size(12, 'Бяслаг 1х*48ш'), 12)
        self.assertEqual(pack_size(None, 'Бяслаг гоуда кг'), 0)

    def test_piece_line(self):
        from decimal import Decimal as D
        from shop.services.imports import compute_line
        per, qty, price, total = compute_line('Ширхэг', D(60), D(48), D(0), D('0.60'), D(0))
        self.assertEqual((per, qty, total), (D(48), D(2880), D('1728.00')))

    def test_weight_line_derives_per_box(self):
        from decimal import Decimal as D
        from shop.services.imports import compute_line
        per, qty, price, total = compute_line('Клограм', D(420), D(0), D(4830), D('3.80'), D(0))
        self.assertEqual((per, qty, total), (D('11.500'), D(4830), D('18354.00')))

    def test_total_edited_last_derives_unit_price(self):
        from decimal import Decimal as D
        from shop.services.imports import compute_line
        _, _, price, total = compute_line('Ширхэг', D(10), D(8), D(0), D(0), D('100'), 'total')
        self.assertEqual((price, total), (D('1.2500'), D('100')))


class DeliveryTripPlateTests(SimpleTestCase):
    def test_normalize_plate(self):
        from shop.services.delivery_trips import normalize_plate
        self.assertEqual(normalize_plate('9167 убр'), '9167УБР')
        self.assertEqual(normalize_plate(' 6259-УНЭ '), '6259УНЭ')
        self.assertEqual(normalize_plate('Портер  шинэ'), 'ПОРТЕР ШИНЭ')


class InventoryReportFilterTests(SimpleTestCase):
    """services.inventory_report - /dashboard/inventory/ шүүлтийн параметр задлалт."""

    def parse(self, query):
        from django.http import QueryDict
        from shop.services.inventory_report import parse_filters
        return parse_filters(QueryDict(query))

    def test_defaults(self):
        f = self.parse('')
        self.assertEqual((f['q'], f['warehouse'], f['brand'], f['min_qty']), ('', [], [], None))
        self.assertTrue(f['stock_only'])
        self.assertEqual((f['sort'], f['per_page']), ('name', 50))

    def test_unchecked_stock_only_uses_last_value(self):
        self.assertFalse(self.parse('stock_only=false')['stock_only'])
        self.assertTrue(self.parse('stock_only=false&stock_only=true')['stock_only'])

    def test_legacy_product_param_and_whitespace(self):
        f = self.parse('product=%D0%91%D1%8F%D1%81%D0%BB%D0%B0%D0%B3++500%D0%B3%D1%80+')
        self.assertEqual(f['q'], 'Бяслаг 500гр')

    def test_warehouse_aliases(self):
        f = self.parse('warehouse=000&warehouse=Агуулах Толгойт&warehouse=Агуулах жижиг&warehouse=xxx')
        self.assertEqual(f['warehouse'], ['tolgoit', 'jijig'])

    def test_invalid_values_fall_back(self):
        f = self.parse('sort=;drop&per_page=9999&min_qty=-5')
        self.assertEqual((f['sort'], f['per_page'], f['min_qty']), ('name', 50, None))
        self.assertEqual(self.parse('sort=-tolgoit&min_qty=1,000')['sort'], '-tolgoit')
        self.assertEqual(self.parse('min_qty=1,000')['min_qty'], 1000)

    def test_search_tokens_match_latin_and_cyrillic_lookalikes(self):
        from shop.services.inventory_report import search_q, token_variants
        self.assertIn('1х*12ш', token_variants('1x*12ш'))
        self.assertEqual(len(search_q('фетаки  500').children), 2)


class ProductCertStatusTests(SimpleTestCase):
    """services.product_certs - бичгийн дуусах хугацааны төлөв, тайлбар, формын шалгалт."""

    def doc(self, expires=None, no_expiry=False, tracks=True):
        from types import SimpleNamespace
        return SimpleNamespace(doc_type=SimpleNamespace(tracks_expiry=tracks), expires_on=expires, no_expiry=no_expiry)

    def test_attachment_status(self):
        from datetime import date, timedelta
        from shop.services.product_certs import SOON_DAYS, attachment_status
        today = date(2026, 10, 15)
        self.assertEqual(attachment_status(self.doc(today - timedelta(days=1)), today), ('expired', '1 хоногийн өмнө дууссан'))
        self.assertEqual(attachment_status(self.doc(today), today), ('soon', 'Өнөөдөр дуусна'))
        self.assertEqual(attachment_status(self.doc(today + timedelta(days=SOON_DAYS)), today)[0], 'soon')
        self.assertEqual(attachment_status(self.doc(today + timedelta(days=SOON_DAYS + 1)), today)[0], 'valid')
        self.assertEqual(attachment_status(self.doc(date(2028, 1, 1)), today), ('valid', '≈ 1 жил 2 сар үлдсэн'))
        self.assertEqual(attachment_status(self.doc(no_expiry=True), today), ('valid', 'Хугацаагүй'))
        self.assertEqual(attachment_status(self.doc(), today)[0], 'no_date')
        self.assertEqual(attachment_status(self.doc(tracks=False), today), (None, ''))

    def test_parse_doc_meta_dates(self):
        from django.http import QueryDict
        from shop.services.product_certs import parse_doc_meta
        meta, errors = parse_doc_meta(QueryDict('issued_on=2026-05-01&expires_on=2027-05-01'))
        self.assertEqual((str(meta['expires_on']), errors), ('2027-05-01', []))
        _, errors = parse_doc_meta(QueryDict('issued_on=2026-05-01&expires_on=2026-04-01'))
        self.assertEqual(len(errors), 1)
        _, errors = parse_doc_meta(QueryDict('expires_on=2026-13-40'))
        self.assertEqual(len(errors), 1)
        meta, errors = parse_doc_meta(QueryDict('expires_on=2027-01-01&no_expiry=1'))
        self.assertEqual((meta['expires_on'], meta['no_expiry'], errors), (None, True, []))

    def test_parse_item_overrides(self):
        from datetime import date
        from django.http import QueryDict
        from shop.services.product_certs import parse_item_overrides

        class Link:  # ProductAttachmentItem-ийн оронд (dict-ийн түлхүүр болох тул hash хийгдэх ёстой)
            def __init__(self, item_id):
                self.item_id = item_id

        a, b, c = (Link(i) for i in ('801023', '801024', '801025'))
        self.assertEqual(parse_item_overrides(QueryDict('item_own_801023=1'), [a]), ({}, []))  # items_submitted-гүй
        post = QueryDict('items_submitted=1&item_own_801023=1&item_expires_801023=2027-01-31'
                         '&item_own_801024=0&item_expires_801024=2020-01-01&item_own_801025=1&item_no_expiry_801025=1')
        result, errors = parse_item_overrides(post, [a, b, c])
        self.assertEqual(errors, [])
        self.assertEqual(result[a], (True, date(2027, 1, 31), False))
        self.assertEqual(result[b], (False, None, False))
        self.assertEqual(result[c], (True, None, True))
        _, errors = parse_item_overrides(post, [a], issued_on=date(2027, 2, 1))
        self.assertEqual(len(errors), 1)


class ExecSummaryPeriodTests(SimpleTestCase):
    """services.exec_summary - хугацаа, харьцуулах хугацаа, зарлагын шалтгаан."""

    def parse(self, query, today):
        from django.http import QueryDict
        from shop.services.exec_summary import parse_period
        return parse_period(QueryDict(query), today)

    def test_this_month_compares_same_days_of_previous_month(self):
        from datetime import date
        p = self.parse('', date(2026, 10, 15))
        self.assertEqual((p['date_from'], p['date_to']), (date(2026, 10, 1), date(2026, 10, 15)))
        self.assertEqual((p['cmp_from'], p['cmp_to']), (date(2026, 9, 1), date(2026, 9, 15)))
        self.assertTrue(p['in_progress'])

    def test_last_month_full_previous_month(self):
        from datetime import date
        p = self.parse('period=last_month', date(2026, 10, 15))
        self.assertEqual((p['date_from'], p['date_to']), (date(2026, 9, 1), date(2026, 9, 30)))
        self.assertEqual((p['cmp_from'], p['cmp_to']), (date(2026, 8, 1), date(2026, 8, 31)))
        self.assertFalse(p['in_progress'])

    def test_yoy_and_custom(self):
        from datetime import date
        p = self.parse('period=this_year&compare=yoy', date(2026, 10, 15))
        self.assertEqual((p['cmp_from'], p['cmp_to']), (date(2025, 1, 1), date(2025, 10, 15)))
        p = self.parse('period=custom&date_from=2026-07-10&date_to=2026-07-01', date(2026, 10, 15))
        self.assertEqual((p['date_from'], p['date_to']), (date(2026, 7, 1), date(2026, 7, 10)))
        self.assertEqual((p['cmp_from'], p['cmp_to']), (date(2026, 6, 21), date(2026, 6, 30)))
        self.assertIsNone(self.parse('compare=none', date(2026, 10, 15))['cmp_from'])

    def test_expense_reason(self):
        from shop.services.exec_summary import expense_reason
        self.assertEqual(expense_reason('акт алтжингаас ирсэн'), 'act')
        self.assertEqual(expense_reason('Номинд амталгаа'), 'tasting')
        self.assertEqual(expense_reason('Номин агуулах шинжилгээнд'), 'lab')
        self.assertEqual(expense_reason('гал тогоонд'), 'internal')
        self.assertEqual(expense_reason(''), 'other')

    def test_active_on(self):
        from datetime import date
        from shop.services.exec_summary import _active_on
        day = date(2026, 9, 30)
        self.assertTrue(_active_on({'hired': date(2020, 1, 1), 'left_on': None, 'left_flag': 'N'}, day))
        self.assertFalse(_active_on({'hired': date(2026, 10, 1), 'left_on': None, 'left_flag': 'N'}, day))
        self.assertTrue(_active_on({'hired': date(2020, 1, 1), 'left_on': date(2026, 10, 5), 'left_flag': 'Y'}, day))
        self.assertFalse(_active_on({'hired': date(2020, 1, 1), 'left_on': date(2026, 9, 30), 'left_flag': 'Y'}, day))
        self.assertFalse(_active_on({'hired': date(2020, 1, 1), 'left_on': None, 'left_flag': 'Y'}, day))
        self.assertFalse(_active_on({'hired': None, 'left_on': None, 'left_flag': 'N'}, day))


class FuelDriverMatchTests(SimpleTestCase):
    """services.fuel - карт эзэмшигчийн нэрээр ('Овог Нэр') ажилтан ('Нэр.О') санал болгох."""

    EMPLOYEES = [{'code': '1', 'name': 'Энхбуянт.И'}, {'code': '2', 'name': 'Энхбуянт.Б'},
                 {'code': '3', 'name': 'Сарангэрэл.Э /Алтжин/'}, {'code': '4', 'name': 'Галт'}]

    def test_initial_breaks_tie(self):
        from shop.services.fuel import match_employee
        self.assertEqual(match_employee('Ишдорж Энхбуянт', self.EMPLOYEES)['code'], '1')
        self.assertEqual(match_employee('Батаа Энхбуянт', self.EMPLOYEES)['code'], '2')

    def test_name_with_note_and_single_name(self):
        from shop.services.fuel import match_employee
        self.assertEqual(match_employee('Энхтөр Сарангэрэл', self.EMPLOYEES)['code'], '3')
        self.assertEqual(match_employee('Батзана Галт', self.EMPLOYEES)['code'], '4')
        self.assertIsNone(match_employee('Алтансүх Сундуй', self.EMPLOYEES))


class VehicleReportFormatTests(SimpleTestCase):
    """services.vehicles - хугацаа, форматлалт; services.vehicle_parts - төрөл, дугаар."""

    def test_period_month_param(self):
        from datetime import date
        from shop.services.vehicles import period, single_month
        d_from, d_to = period({'month': '2026-02'}, date(2026, 1, 1), date(2026, 1, 31))
        self.assertEqual((d_from, d_to), (date(2026, 2, 1), date(2026, 2, 28)))
        self.assertEqual(single_month(d_from, d_to), date(2026, 2, 1))
        self.assertIsNone(single_month(date(2026, 2, 1), date(2026, 3, 31)))

    def test_fmt_value(self):
        from decimal import Decimal
        from shop.services.vehicles import fmt_value
        self.assertEqual(fmt_value(Decimal('1234567.00'), 'money'), '1,234,567')
        self.assertEqual(fmt_value(Decimal('12.5'), 'dec'), '12.50')
        self.assertEqual(fmt_value('Нийт', 'date'), 'Нийт')
        self.assertEqual(fmt_value(None, 'money'), '')

    def test_part_category_and_plate(self):
        from shop.services.vehicle_parts import normalize_category, resolve_plate
        self.assertEqual(normalize_category('сэлбэг /бүх төрлийн сэлбэг орно/'), 'Сэлбэг')
        self.assertEqual(normalize_category('Аккумлятор '), 'Аккумлятор')
        self.assertEqual(normalize_category('Ажлын хөлс'), 'Засварын ажлын хөлс')
        self.assertEqual(resolve_plate(1485, {'1485УАН', '1637УНВ'}), '1485УАН')
        self.assertEqual(resolve_plate('6259 унэ', set()), '6259УНЭ')
        self.assertEqual(resolve_plate(None, set()), '')
