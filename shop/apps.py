from django.apps import AppConfig


# Цаг бүртгэл/Хоног бүртгэлийн хадгалсан шүүлтийн session түлхүүрүүд (shop.views) - шинээр нэвтрэхэд цэвэрлэнэ
FILTER_SESSION_KEYS = ('attendance_filter', 'timesheet_filter')


def _reset_saved_filters(sender, request, user, **kwargs):
    for key in FILTER_SESSION_KEYS:
        request.session.pop(key, None)


class ShopConfig(AppConfig):
    name = 'shop'

    def ready(self):
        from django.contrib.auth.signals import user_logged_in
        user_logged_in.connect(_reset_saved_filters, dispatch_uid='shop_reset_saved_filters')
