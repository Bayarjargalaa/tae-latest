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
