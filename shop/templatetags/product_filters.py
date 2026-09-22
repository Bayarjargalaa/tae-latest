"""
Custom template filters for product images
"""
import os
from django import template
from django.conf import settings

register = template.Library()


@register.filter
def product_image_url(product, image_type='main'):
    """
    Бүтээгдэхүүний зураг авах (ProductExtension байхгүй ч ажиллана)
    
    Usage: {{ product|product_image_url }}
           {{ product|product_image_url:'2' }}
    """
    # Lazy import to avoid circular dependency
    from shop.models import ProductExtension
    
    # ProductExtension шалгах
    try:
        extension = ProductExtension.objects.get(item_id=product.id)
        
        # Database дээр байгаа зураг
        if image_type == 'main' and extension.image_main:
            return extension.image_main.url
        elif image_type == '2' and extension.image_2:
            return extension.image_2.url
        elif image_type == '3' and extension.image_3:
            return extension.image_3.url
    except ProductExtension.DoesNotExist:
        pass
    
    # Fallback: {item_id}.ext хайх
    extensions = ['jpg', 'jpeg', 'png', 'webp', 'JPG', 'JPEG', 'PNG', 'WEBP']
    for ext in extensions:
        filename = f'{product.id}.{ext}'
        filepath = os.path.join(settings.MEDIA_ROOT, 'products', filename)
        
        if os.path.exists(filepath):
            return f'{settings.MEDIA_URL}products/{filename}'
    
    # Placeholder зураг
    return f'{settings.MEDIA_URL}placeholder.svg'


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
