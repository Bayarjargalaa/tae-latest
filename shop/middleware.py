"""
Цэсний эрхийг URL түвшинд мөрдүүлнэ: хажуугийн цэснээс нуусан хуудсыг хаягаар нь, холбоосоор нь, Excel / хадгалах
зэрэг дэд хаягаар нь ч нээж болохгүй - "Та энэ хуудсыг үзэх эрхгүй" (403). Дүрэм нь shop.access-д.
"""
from shop.access import can_access_url, forbidden_response


class MenuPermissionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = request.resolver_match
        # Зөвхөн shop app-ийн хуудсууд (admin, static г.м. өөрийн хамгаалалттай)
        if match is None or match.namespace != 'shop':
            return None
        if can_access_url(request, match.url_name):
            return None
        return forbidden_response(request)
