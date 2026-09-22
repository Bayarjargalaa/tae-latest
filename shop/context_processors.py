"""
Context processors - Template-д автоматаар дамжуулах өгөгдөл
"""
from datamigration.models import OpenDataEmployee
from shop.models import MenuPermission
from shop.menuconfig import ALWAYS_ALL_MENU_POSITIONS, get_configurable_menu_items, get_effective_menu_groups


def user_position(request):
    """Хэрэглэгчийн албан тушаал болон sidebar цэсний харагдах эрхийг template-д дамжуулах"""
    context = {
        'user_position_name': None,
        'user_employee': None,
        'menu_groups': get_effective_menu_groups(),
        'visible_menu_keys': set(),
    }

    if not request.user.is_authenticated:
        return context

    all_keys = {item['key'] for item in get_configurable_menu_items()}

    # Superuser бол цэсний эрхийн тохиргооноос үл хамааран бүх цэс харагдана
    if request.user.is_superuser:
        context['visible_menu_keys'] = all_keys

    if hasattr(request.user, 'email') and request.user.email:
        try:
            employee = OpenDataEmployee.objects.get(email=request.user.email)
            context['user_position_name'] = employee.positionname
            context['user_employee'] = employee

            if not request.user.is_superuser:
                if employee.positionname in ALWAYS_ALL_MENU_POSITIONS:
                    # Энэ албан тушаал шинээр нэмэгдэх цэсийг оролцуулаад бүгдийг үргэлж харна
                    context['visible_menu_keys'] = all_keys
                else:
                    # Бусад албан тушаалд зөвхөн тодорхой сонгосон (is_visible=True) цэс л харагдана
                    context['visible_menu_keys'] = set(
                        MenuPermission.objects.filter(
                            position_name=employee.positionname or '',
                            is_visible=True,
                        ).values_list('menu_key', flat=True)
                    )
        except OpenDataEmployee.DoesNotExist:
            pass

    return context

