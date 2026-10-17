"""
Sidebar цэсний төвлөрсөн тохиргоо.

Шинэ цэс нэмэх бол зөвхөн энд MENU_GROUPS-д нэмнэ - _sidebar.html
болон эрх тохируулах хуудас автоматаар шинэчлэгдэнэ.

item талбарууд:
    key            - цэсийг тодорхойлох түлхүүр (active_page, MenuPermission.menu_key-тэй адилхан байх ёстой)
    label           - Харагдах нэр
    icon            - Emoji icon
    url_name        - {% url %} tag-д дамжуулах нэр (жиш: 'shop:dashboard')
    always_visible  - True бол албан тушаалын эрхээс үл хамааран бүх ажилтанд харагдана
"""

# Эдгээр албан тушаал шинээр нэмэгдэж буй цэсийг оролцуулаад бүх цэсийг үргэлж
# автоматаар харна (superuser-тэй адил, MenuPermission-оор тохируулах шаардлагагүй).
ALWAYS_ALL_MENU_POSITIONS = {'Ерөнхий нягтлан'}

MENU_GROUPS = [
    {
        'key': 'general',
        'label': None,
        'items': [
            {'key': 'dashboard', 'label': 'Нүүр хуудас', 'icon': '📊', 'url_name': 'shop:dashboard'},
            {'key': 'products', 'label': 'Бүтээгдэхүүн', 'icon': '📦', 'url_name': 'shop:products', 'always_visible': True},
        ],
    },
    {
        'key': 'personal',
        'label': 'Хувийн мэдээлэл',
        'items': [
            {'key': 'profile', 'label': 'Миний мэдээлэл', 'icon': '👤', 'url_name': 'shop:profile'},
            {'key': 'my_attendance', 'label': 'Цагийн бүртгэл', 'icon': '🕒', 'url_name': 'shop:my_attendance'},
            {'key': 'my_payroll', 'label': 'Цалингийн мэдээлэл', 'icon': '💰', 'url_name': 'shop:my_payroll'},
            {'key': 'my_sales_bonus', 'label': 'Борлуулалтын нэмэгдэл', 'icon': '🎯', 'url_name': 'shop:my_sales_bonus'},
        ],
    },
    {
        'key': 'inventory',
        'label': 'Бараа материал',
        'items': [
            {'key': 'inventory', 'label': 'Барааны үлдэгдэл', 'icon': '📦', 'url_name': 'shop:inventory_report'},
            {'key': 'item_prices', 'label': 'Барааны үнэ', 'icon': '💲', 'url_name': 'shop:item_prices'},
            {'key': 'item_costs', 'label': 'Барааны өртөг', 'icon': '🧾', 'url_name': 'shop:item_costs'},
            {'key': 'product_certificates', 'label': 'Шинжилгээний бичиг', 'icon': '🧪', 'url_name': 'shop:product_certificates'},
        ],
    },
    {
        'key': 'sales',
        'label': 'Борлуулалт',
        'items': [
            {'key': 'sales_report', 'label': 'Борлуулалтын тайлан', 'icon': '📊', 'url_name': 'shop:sales_report'},
            {'key': 'sales_report_ht', 'label': 'Борлуулалтын тайлан ХТ-р', 'icon': '🧑‍💼', 'url_name': 'shop:sales_report_ht'},
            {'key': 'sales_plan', 'label': 'Борлуулалтын төлөвлөгөө', 'icon': '🎯', 'url_name': 'shop:sales_plan'},
        ],
    },
    {
        'key': 'delivery',
        'label': 'Түгээлт',
        'items': [
            {'key': 'delivery_report', 'label': 'Түгээлтийн тайлан', 'icon': '🚛', 'url_name': 'shop:delivery_report'},
            {'key': 'delivery_trips', 'label': 'Түгээлтийн машин', 'icon': '🚚', 'url_name': 'shop:delivery_trips'},
        ],
    },
    {
        'key': 'supply',
        'label': 'Хангамж',
        'items': [
            {'key': 'purchase_report', 'label': 'Татан авалтын тайлан', 'icon': '🚚', 'url_name': 'shop:purchase_report'},
            {'key': 'unloading', 'label': 'Ачаа буулгалт', 'icon': '🏗️', 'url_name': 'shop:unloading'},
            {'key': 'vehicles', 'label': 'Тээврийн хэрэгсэл', 'icon': '🚗', 'url_name': 'shop:vehicles'},
            {'key': 'meal_list', 'label': 'Хоолны бүртгэл', 'icon': '🍲', 'url_name': 'shop:meal_list'},
            {'key': 'meal_attendance', 'label': 'Хоол идэх нэрс', 'icon': '📝', 'url_name': 'shop:meal_attendance_list'},
            {'key': 'meal_material_calc', 'label': 'Хоолны материалын тооцоо', 'icon': '🧮', 'url_name': 'shop:meal_material_calc'},
        ],
    },
    {
        'key': 'import',
        'label': 'Гадаад харилцаа',
        'items': [
            {'key': 'import_orders', 'label': 'Импортын захиалга', 'icon': '🚢', 'url_name': 'shop:import_orders'},
            {'key': 'import_tracking', 'label': 'Замын мэдээ', 'icon': '🧭', 'url_name': 'shop:import_tracking'},
        ],
    },
    {
        'key': 'finance',
        'label': 'Санхүү',
        'items': [
            {'key': 'expense_report', 'label': 'Зардлын тооцоолол сараар', 'icon': '💰', 'url_name': 'shop:expense_report'},
            {'key': 'expense_report_by_year', 'label': 'Зардлын тооцоолол жилээр', 'icon': '📈', 'url_name': 'shop:expense_report_by_year'},
            {'key': 'receivable_report', 'label': 'Авлагын тайлан', 'icon': '📥', 'url_name': 'shop:receivable_report'},
            {'key': 'payable_report', 'label': 'Өглөгийн тайлан', 'icon': '📤', 'url_name': 'shop:payable_report'},
        ],
    },
    {
        'key': 'hr',
        'label': 'Хүний нөөц',
        'items': [
            {'key': 'attendance_calc', 'label': 'Цаг бүртгэл', 'icon': '🕒', 'url_name': 'shop:attendance_calc'},
            {'key': 'timesheet', 'label': 'Хоног бүртгэл', 'icon': '📅', 'url_name': 'shop:timesheet'},
            {'key': 'payroll_card', 'label': 'Картын цалин бодолт', 'icon': '💳', 'url_name': 'shop:payroll_card'},
            {'key': 'payroll_cash', 'label': 'Бэлэн цалин бодолт', 'icon': '💵', 'url_name': 'shop:payroll_cash'},
            {'key': 'cash_bank_accounts', 'label': 'Бэлэн цалингийн данс', 'icon': '🏦', 'url_name': 'shop:cash_bank_accounts'},
            {'key': 'payroll_report', 'label': 'Цалингийн тайлан', 'icon': '📊', 'url_name': 'shop:payroll_report'},
            {'key': 'payroll_advance_card', 'label': 'Картын урьдчилгаа', 'icon': '💳', 'url_name': 'shop:payroll_advance_card'},
            {'key': 'payroll_advance_cash', 'label': 'Бэлэн урьдчилгаа', 'icon': '💵', 'url_name': 'shop:payroll_advance_cash'},
            {'key': 'meal_allowance', 'label': 'Хоолны мөнгө', 'icon': '🍱', 'url_name': 'shop:meal_allowance'},
            {'key': 'sales_bonus', 'label': 'Борлуулалтын нэмэгдэл бодох', 'icon': '🎯', 'url_name': 'shop:sales_bonus'},
            {'key': 'employee_fingerprint', 'label': 'Ажилтны хурууны мэдээлэл', 'icon': '👆', 'url_name': 'shop:employee_fingerprint'},
        ],
    },
]


# --- Үйлдлийн эрх: хажуугийн цэсэнд харагдахгүй, гэхдээ цэсний эрхтэй адил албан тушаалаар тохируулна ---------
# (MenuPermission-д menu_key-ээр хадгалагдана; template-д `'product_edit' in visible_menu_keys` гэж шалгана)
ACTION_PERMISSIONS = [
    {'key': 'product_edit', 'label': 'Бүтээгдэхүүний мэдээлэл засах', 'icon': '✏️'},
    {'key': 'product_attachment_upload', 'label': 'Бүтээгдэхүүнд шинжилгээний бичиг хавсаргах', 'icon': '📄'},
    # Нүүр хуудсын удирдлагын нэгтгэл (борлуулалт, бараа материал, авлага, өглөг, мөнгөн хөрөнгө) - Ерөнхий нягтлан үргэлж
    {'key': 'exec_summary', 'label': 'Удирдлагын нэгтгэл (нүүр хуудас)', 'icon': '📈'},
]


# --- URL түвшний эрх (shop.access, shop.middleware.MenuPermissionMiddleware) ---------------------------------
# Хажуугийн цэснээс нуусан хуудсыг хаягаар нь ч нээж болохгүй. Цэсний item бүрийн url_name өөрийн key-ээр
# автоматаар хамгаалагдана; энд зөвхөн дэд хуудас (экспорт, хадгалах, засах, тохиргоо г.м.)-ыг аль цэсэнд
# хамаарахыг заана - жагсаасан цэсний аль нэг нь харагддаг бол нээгдэнэ.
# Энд ч, цэсэнд ч, PUBLIC_URL_NAMES-д ч байхгүй (шинээр нэмсэн г.м.) хуудас зөвхөн superuser-т нээгдэнэ.
SUBPAGE_MENU_KEYS = {
    'sales_report_export': ('sales_report',),
    'sales_report_customers': ('sales_report',),
    'sales_report_ht_dashboard': ('sales_report_ht',),
    'sales_report_ht_breakdown': ('sales_report_ht',),
    'sales_report_ht_export': ('sales_report_ht',),
    'unloading_export': ('unloading',),
    'delivery_trips_save': ('delivery_trips',),
    'delivery_trips_list': ('delivery_trips',),
    'delivery_trips_export': ('delivery_trips',),
    'vehicles_fuel_import': ('vehicles',),
    'vehicles_fuel_save': ('vehicles',),
    'vehicles_fuel_cash_save': ('vehicles',),
    'vehicles_export': ('vehicles',),
    'vehicles_parts_save': ('vehicles',),
    'vehicles_parts_import': ('vehicles',),
    # Дэлгэрэнгүй/баримтыг view өөрөө нарийвчилж шалгана (services.imports.can_view_full) - ХТ-д нээгдэхгүй
    'import_shipment': ('import_orders', 'import_tracking'),
    'import_receipt': ('import_orders', 'import_tracking'),
    'import_attachment': ('import_orders', 'import_tracking'),
    'purchase_report_export': ('purchase_report',),
    'purchase_report_suggest': ('purchase_report',),
    'receivable_ledger': ('receivable_report',),
    'receivable_export': ('receivable_report',),
    'payable_ledger': ('payable_report',),
    'payable_export': ('payable_report',),
    'expense_transaction_detail': ('expense_report', 'expense_report_by_year'),
    'item_prices_export': ('item_prices',),
    'item_price_history': ('item_prices',),
    'item_costs_export': ('item_costs',),
    'meal_create': ('meal_list',),
    'meal_edit': ('meal_list',),
    'meal_delete': ('meal_list',),
    'meal_toggle_active': ('meal_list',),
    'meal_cycle_settings_update': ('meal_list',),
    'meal_attendance_summary': ('meal_attendance',),
    'meal_attendance_create': ('meal_attendance',),
    'meal_attendance_edit': ('meal_attendance',),
    'meal_attendance_delete': ('meal_attendance',),
    'attendance_export': ('attendance_calc',),
    'attendance_filter_save': ('attendance_calc',),
    'attendance_sync': ('attendance_calc',),
    'attendance_sync_merchandiser': ('attendance_calc',),
    'attendance_save': ('attendance_calc',),
    'attendance_delete': ('attendance_calc',),
    'attendance_add': ('attendance_calc',),
    'attendance_hide': ('attendance_calc',),
    'attendance_bulk_delete': ('attendance_calc',),
    'attendance_position_settings': ('attendance_calc',),
    'timesheet_export': ('timesheet',),
    'payroll_card_export': ('payroll_card',),
    'payroll_cash_export': ('payroll_cash',),
    'payroll_settings': ('payroll_card', 'payroll_cash'),
    'meal_allowance_export': ('meal_allowance',),
    'product_edit': ('product_edit',),
    'product_attachment_upload': ('product_attachment_upload',),
    'product_attachment_delete': ('product_attachment_upload',),
    'product_attachment_link': ('product_attachment_upload',),
    'product_search': ('product_attachment_upload',),
    'product_attachment_edit': ('product_attachment_upload',),
    'product_doc_types': ('product_attachment_upload',),
}
# Цэсний эрхээс үл хамааран нээлттэй (нэвтрээгүй хэрэглэгчид ч) - эрхийг view өөрөө шалгадаг эсвэл нийтийн хуудас
PUBLIC_URL_NAMES = {
    'home', 'products', 'product_detail', 'register', 'login', 'logout',
    'product_attachment',  # view нь @login_required - нэвтэрсэн бүх хэрэглэгч харж, татна
    'password_reset', 'password_reset_done', 'password_reset_confirm', 'password_reset_complete',
    'ai_chat_message', 'product_stock_lookup',
}


# Зөвхөн superuser - цэсгүй, зориуд хаалттай (тодорхойлоогүй хуудастай адил боловч жагсааснаар тест хянана)
ADMIN_ONLY_URL_NAMES = {
    'data_sync', 'data_sync_start', 'data_sync_status', 'data_sync_views', 'menu_permission_config',
}


def get_url_menu_keys():
    """{url_name: (цэсний key, ...)} - цэсний item-ийн url_name өөрийн key-ээр, дэд хуудас SUBPAGE_MENU_KEYS-ээр."""
    mapping = {}
    for group in MENU_GROUPS:
        for item in group['items']:
            if not item.get('always_visible'):  # бүх хүнд харагддаг цэс - PUBLIC_URL_NAMES-д
                mapping.setdefault(item['url_name'].split(':')[-1], (item['key'],))
    mapping.update(SUBPAGE_MENU_KEYS)
    return mapping


def get_configurable_menu_items():
    """Эрх тохируулах боломжтой (always_visible биш) бүх цэсний item-үүд, групын нэр/түлхүүртэй."""
    items = []
    for group in MENU_GROUPS:
        for item in group['items']:
            if not item.get('always_visible'):
                items.append({
                    **item,
                    'group_key': group['key'],
                    'group_label': group['label'] or group['key'],
                })
    return items


def get_group_choices():
    """HTML select-д зориулж сонгож болох бүлгүүдийн (key, label) жагсаалт."""
    return [(group['key'], group['label'] or group['key']) for group in MENU_GROUPS]


def get_effective_menu_groups():
    """MenuGroupAssignment-д хийсэн дарж бичих тохиргоог MENU_GROUPS дээр нэмж, sidebar-д ашиглах эцсийн бүлгүүдийг буцаана."""
    from shop.models import MenuGroupAssignment

    overrides = dict(MenuGroupAssignment.objects.values_list('menu_key', 'group_key'))
    valid_group_keys = {group['key'] for group in MENU_GROUPS}

    groups_by_key = {
        group['key']: {'key': group['key'], 'label': group['label'], 'items': []}
        for group in MENU_GROUPS
    }

    for group in MENU_GROUPS:
        for item in group['items']:
            target_key = group['key']
            if not item.get('always_visible'):
                override_key = overrides.get(item['key'])
                if override_key and override_key in valid_group_keys:
                    target_key = override_key
            groups_by_key[target_key]['items'].append(item)

    return [groups_by_key[group['key']] for group in MENU_GROUPS]

