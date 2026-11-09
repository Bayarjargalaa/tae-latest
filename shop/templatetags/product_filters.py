"""
Custom template filters for product images
"""
from django import template

register = template.Library()


@register.filter
def product_image_url(product, image_type='main'):
    """
    Бүтээгдэхүүний эх зураг (ProductExtension байхгүй ч ажиллана) - services.product_images

    Usage: {{ product|product_image_url }}
           {{ product|product_image_url:'2' }}
    """
    from shop.services.product_images import image_url
    return image_url(product, image_type)


@register.filter
def product_thumb_url(product, image_type='main'):
    """Картанд зориулсан жижиг зураг (thumbnail) - {{ product|product_thumb_url }}"""
    from shop.services.product_images import thumb_url
    return thumb_url(product, image_type)


@register.filter
def get_item(dictionary, key):
    """
    Dictionary-аас key-ээр утга авах
    
    Usage: {{ my_dict|get_item:key_variable }}
    """
    if dictionary is None:
        return None
    return dictionary.get(key)


@register.filter
def sum_field(dict_values, field_name):
    """
    Dictionary values-аас тодорхой field-ийн нийлбэрийг тооцоолох
    
    Usage: {{ monthly_data.values|sum_field:'payamount' }}
    """
    total = 0
    for item in dict_values:
        if isinstance(item, dict) and field_name in item:
            total += item.get(field_name, 0) or 0
    return total
