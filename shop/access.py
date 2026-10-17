"""
Цэсний эрх - хажуугийн цэс (context_processors.user_position) болон URL түвшний хамгаалалт
(middleware.MenuPermissionMiddleware) хоёул эндээс авна. Цэснээс нуусан хуудас = тэр хэрэглэгч үзэх эрхгүй.

- superuser, ALWAYS_ALL_MENU_POSITIONS (Ерөнхий нягтлан) - бүх цэс
- бусад ажилтан - албан тушаалд нь MenuPermission.is_visible=True цэсүүд (OpenDataEmployee-ийн имэйлээр)
- Хуудас (url_name) -> цэс: menuconfig.get_url_menu_keys(); нийтийн хуудас: PUBLIC_URL_NAMES;
  аль нь ч биш (тодорхойлоогүй шинэ хуудас) - зөвхөн superuser (fail-closed)
- Тусгай дүрэм (EXTRA_ACCESS): цэсний эрхгүй ч нээгдэх нөхцөл (жиш: Нягтланд хоолны мөнгө)
"""
import logging

logger = logging.getLogger(__name__)


def get_user_employee(user):
    """Нэвтэрсэн хэрэглэгчийн ажилтны мэдээлэл (OpenDataEmployee, имэйлээр) эсвэл None."""
    if not user.is_authenticated or not getattr(user, 'email', ''):
        return None
    from datamigration.models import OpenDataEmployee
    return OpenDataEmployee.objects.filter(email=user.email).first()


def get_visible_menu_keys(user, employee=None):
    """Хэрэглэгчид харагдах (= үзэх эрхтэй) цэсний key-үүд, мөн үйлдлийн эрхүүд (menuconfig.ACTION_PERMISSIONS)."""
    from shop.menuconfig import ACTION_PERMISSIONS, ALWAYS_ALL_MENU_POSITIONS, get_configurable_menu_items
    from shop.models import MenuPermission

    if not user.is_authenticated:
        return set()
    all_keys = {item['key'] for item in get_configurable_menu_items()} | {a['key'] for a in ACTION_PERMISSIONS}
    if user.is_superuser:
        return all_keys
    employee = employee if employee is not None else get_user_employee(user)
    if employee is None:
        return set()
    if employee.positionname in ALWAYS_ALL_MENU_POSITIONS:
        return all_keys
    return set(MenuPermission.objects.filter(
        position_name=employee.positionname or '', is_visible=True,
    ).values_list('menu_key', flat=True)) & all_keys


def request_menu_keys(request):
    """get_visible_menu_keys-ийг хүсэлт дотор нэг л удаа бодно (middleware, context processor, view хуваалцана)."""
    if not hasattr(request, '_visible_menu_keys'):
        request._visible_menu_keys = get_visible_menu_keys(request.user)
    return request._visible_menu_keys


def _meal_allowance_accountant(request):
    """Нягтланд хоолны мөнгө - Ерөнхий нягтлан хоолны мөнгөний хуудаснаас олгосон үед (цэсний эрхгүй ч)."""
    from shop.services.meal_allowance import accountant_has_access
    return accountant_has_access(request.user)


# url_name -> цэсний эрхгүй ч нээгдэх нэмэлт нөхцөл
EXTRA_ACCESS = {
    'meal_allowance': _meal_allowance_accountant,
    'meal_allowance_export': _meal_allowance_accountant,
}


def can_access_url(request, url_name):
    """shop namespace-ийн url_name-ийг энэ хэрэглэгч нээж болох эсэх."""
    from shop.menuconfig import PUBLIC_URL_NAMES, get_url_menu_keys

    if url_name in PUBLIC_URL_NAMES:
        return True
    if not request.user.is_authenticated:
        return False
    if request.user.is_superuser:
        return True
    menu_keys = get_url_menu_keys().get(url_name)
    if menu_keys is None:
        logger.warning('Цэсний эрх тодорхойлоогүй хуудас хаагдлаа: %s (%s)', url_name, request.user)
        return False
    if set(menu_keys) & request_menu_keys(request):
        return True
    extra = EXTRA_ACCESS.get(url_name)
    return bool(extra and extra(request))


def forbidden_response(request):
    """"Та энэ хуудсыг үзэх эрхгүй" (403). JSON / ард дуудах (fetch) хүсэлтэд JSON, нэвтрээгүй бол нэвтрэх хуудас."""
    from django.contrib.auth.views import redirect_to_login
    from django.http import JsonResponse
    from django.shortcuts import render

    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    wants_json = (
        request.headers.get('x-requested-with') == 'XMLHttpRequest'
        or 'application/json' in request.headers.get('accept', '')
        or request.headers.get('sec-fetch-dest') == 'empty'
    )
    if wants_json:
        return JsonResponse({'error': 'Та энэ хуудсыг үзэх эрхгүй.'}, status=403)
    return render(request, 'shop/forbidden.html', {'active_page': ''}, status=403)


def first_allowed_url(request):
    """Хэрэглэгчийн үзэх эрхтэй эхний цэсний хаяг (нэвтэрсний дараа чиглүүлэхэд), эсвэл None."""
    from django.urls import reverse
    from shop.menuconfig import MENU_GROUPS

    keys = request_menu_keys(request)
    for group in MENU_GROUPS:
        for item in group['items']:
            if item['key'] in keys:
                return reverse(item['url_name'])
    return None
