"""
Context processors - Template-д автоматаар дамжуулах өгөгдөл
"""
from shop.access import get_user_employee, request_menu_keys
from shop.menuconfig import get_effective_menu_groups


def user_position(request):
    """Хэрэглэгчийн албан тушаал болон sidebar цэсний харагдах эрхийг template-д дамжуулах.
    Харагдах цэс = үзэх эрхтэй цэс (shop.access) - URL түвшний хамгаалалттай (middleware) ижил дүрэм."""
    context = {
        'user_position_name': None,
        'user_employee': None,
        'menu_groups': get_effective_menu_groups(),
        'visible_menu_keys': set(),
    }

    if not request.user.is_authenticated:
        return context

    employee = get_user_employee(request.user)
    if employee is not None:
        context['user_position_name'] = employee.positionname
        context['user_employee'] = employee
    context['visible_menu_keys'] = request_menu_keys(request)
    return context
