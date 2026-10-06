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
        ],
    },
    {
        'key': 'sales',
        'label': 'Борлуулалт',
        'items': [
            {'key': 'sales_report', 'label': 'Борлуулалтын тайлан', 'icon': '📊', 'url_name': 'shop:sales_report'},
            {'key': 'sales_report_ht', 'label': 'Борлуулалтын тайлан ХТ-р', 'icon': '🧑‍💼', 'url_name': 'shop:sales_report_ht'},
        ],
    },
    {
        'key': 'delivery',
        'label': 'Түгээлт',
        'items': [
            {'key': 'delivery_report', 'label': 'Түгээлтийн тайлан', 'icon': '🚛', 'url_name': 'shop:delivery_report'},
        ],
    },
    {
        'key': 'supply',
        'label': 'Хангамж',
        'items': [
            {'key': 'purchase_report', 'label': 'Татан авалтын тайлан', 'icon': '🚚', 'url_name': 'shop:purchase_report'},
            {'key': 'unloading', 'label': 'Ачаа буулгалт', 'icon': '🏗️', 'url_name': 'shop:unloading'},
            {'key': 'meal_list', 'label': 'Хоолны бүртгэл', 'icon': '🍲', 'url_name': 'shop:meal_list'},
            {'key': 'meal_attendance', 'label': 'Хоол идэх нэрс', 'icon': '📝', 'url_name': 'shop:meal_attendance_list'},
            {'key': 'meal_material_calc', 'label': 'Хоолны материалын тооцоо', 'icon': '🧮', 'url_name': 'shop:meal_material_calc'},
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
            {'key': 'sales_bonus', 'label': 'Борлуулалтын нэмэгдэл бодох', 'icon': '🎯', 'url_name': 'shop:sales_bonus'},
            {'key': 'employee_fingerprint', 'label': 'Ажилтны хурууны мэдээлэл', 'icon': '👆', 'url_name': 'shop:employee_fingerprint'},
        ],
    },
]


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

