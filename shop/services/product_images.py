"""
Бүтээгдэхүүний зураг: файлын жагсаалтын кэш ба картын жижиг хувилбар (thumbnail).

- Зураг: ProductExtension.image_main/2/3, байхгүй бол media/products/{item_id}.jpg|jpeg|png|webp (fallback).
  Fallback-ийг бараа бүрт os.path.exists-ээр шалгах нь Windows-ийн Docker хавтсан дээр маш удаан (1 stat ~6ms)
  тул хавтасны жагсаалтыг нэг удаа уншиж, хавтасны mtime өөрчлөгдөх хүртэл кэшилнэ.
- Thumbnail: media/products/thumbs/{THUMB_SIZE}/{эх файлын нэр}.jpg - картад (~300px) хэдэн MB-ийн эх зургийн оронд
  ~50KB. Анх хэрэгтэй үед нь үүсгэнэ (manage.py product_thumbs-оор урьдчилан үүсгэж болно); эх зураг
  солигдвол (шинэ нэртэй хадгалагдана) шинэ thumbnail үүснэ.
"""
import logging
import os
import threading
import time

from django.conf import settings

logger = logging.getLogger(__name__)

FALLBACK_EXTS = ['jpg', 'jpeg', 'png', 'webp', 'JPG', 'JPEG', 'PNG', 'WEBP']  # давуу эрхийн дарааллаар
THUMB_SIZE = 600  # картанд 2x (retina) дэлгэцэнд хүрэлцэхүйц
THUMB_QUALITY = 82
PLACEHOLDER = 'placeholder.svg'

# Хавтасны mtime-ийг хамгийн ихдээ ийм секунд тутамд шалгана (нэг stat ч Windows-ийн Docker хавтсан дээр ~8ms)
LISTING_CHECK_SECONDS = 10

_lock = threading.Lock()
_listings = {}  # хавтас -> [шалгасан цаг, mtime, set(файлын нэр)]


def _listing(rel_dir):
    """media/<rel_dir> хавтасны файлын нэрс - хавтасны mtime өөрчлөгдсөн үед л дахин уншина."""
    cached = _listings.get(rel_dir)
    now = time.monotonic()
    if cached and now - cached[0] < LISTING_CHECK_SECONDS:
        return cached[2]
    path = os.path.join(settings.MEDIA_ROOT, rel_dir)
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return set()
    if cached and cached[1] == mtime:
        cached[0] = now
        return cached[2]
    with _lock:
        try:
            names = set(os.listdir(path))
        except OSError:
            names = set()
        _listings[rel_dir] = [now, mtime, names]
    return names


def fallback_files():
    """{item_id: 'products/<файл>'} - media/products/{item_id}.<өргөтгөл> файлууд."""
    names = _listing('products')
    found = {}
    for ext in reversed(FALLBACK_EXTS):  # эхний өргөтгөл давуу
        suffix = f'.{ext}'
        for name in names:
            if name.endswith(suffix):
                found[name[:-len(suffix)]] = f'products/{name}'
    return found


def image_name(product, image_type='main'):
    """Зургийн media-гийн харьцангуй зам (жиш: 'products/801003.jpeg') эсвэл None. product.extension хавсаргасан
    бол түүнийг ашиглана (жагсаалтад N+1 query гаргахгүй)."""
    if hasattr(product, 'extension'):
        extension = product.extension
    else:
        from shop.models import ProductExtension
        extension = ProductExtension.objects.filter(item_id=product.id).first()
    if extension:
        field = {'main': extension.image_main, '2': extension.image_2, '3': extension.image_3}.get(image_type)
        if field:
            return field.name
    if image_type == 'main':
        return fallback_files().get(str(product.id))
    return None


def image_url(product, image_type='main'):
    name = image_name(product, image_type)
    return f'{settings.MEDIA_URL}{name}' if name else f'{settings.MEDIA_URL}{PLACEHOLDER}'


def _thumb_rel(name):
    # Өргөтгөлийг нь нэрэнд үлдээнэ: 801003.jpeg, 801003.png хоёр өөр thumbnail болно
    return f'products/thumbs/{THUMB_SIZE}', f'{os.path.basename(name)}.jpg'


def make_thumb(name):
    """Эх зургаас thumbnail үүсгэнэ (байгаа бол дахин үүсгэхгүй). Амжилттай бол True."""
    from PIL import Image, ImageOps

    rel_dir, thumb = _thumb_rel(name)
    out_dir = os.path.join(settings.MEDIA_ROOT, rel_dir)
    out = os.path.join(out_dir, thumb)
    if thumb in _listing(rel_dir):
        return True
    src = os.path.join(settings.MEDIA_ROOT, name)
    try:
        os.makedirs(out_dir, exist_ok=True)
        with Image.open(src) as img:
            img = ImageOps.exif_transpose(img)
            img.thumbnail((THUMB_SIZE, THUMB_SIZE))
            if img.mode in ('RGBA', 'LA', 'P'):
                img = img.convert('RGBA')
                background = Image.new('RGB', img.size, 'white')  # картын дэвсгэр цагаан
                background.paste(img, mask=img.split()[-1])
                img = background
            tmp = f'{out}.tmp'
            img.convert('RGB').save(tmp, 'JPEG', quality=THUMB_QUALITY, optimize=True, progressive=True)
            os.replace(tmp, out)
        _listing(rel_dir).add(thumb)  # кэш дэх жагсаалтад шууд нэмнэ (дахин унших хүртэл хүлээхгүй)
        return True
    except Exception:  # эвдэрсэн/танигдахгүй файл - эх зургийг нь харуулна
        logger.warning('Thumbnail үүсгэж чадсангүй: %s', name, exc_info=True)
        return False


def thumb_url(product, image_type='main'):
    """Картанд: thumbnail-ийн URL (байхгүй бол үүсгэнэ), бүтэлгүйтвэл эх зураг, зураггүй бол placeholder."""
    name = image_name(product, image_type)
    if not name:
        return f'{settings.MEDIA_URL}{PLACEHOLDER}'
    if os.path.splitext(name)[1].lower() == '.svg':
        return f'{settings.MEDIA_URL}{name}'
    rel_dir, thumb = _thumb_rel(name)
    if thumb in _listing(rel_dir) or make_thumb(name):
        return f'{settings.MEDIA_URL}{rel_dir}/{thumb}'
    return f'{settings.MEDIA_URL}{name}'


def _remove_thumb(name):
    rel_dir, thumb = _thumb_rel(name)
    try:
        os.remove(os.path.join(settings.MEDIA_ROOT, rel_dir, thumb))
    except OSError:
        pass
    _listing(rel_dir).discard(thumb)


def delete_main_image(extension):
    """ProductExtension.image_main-ийн файл, thumbnail-ийг устгаж талбарыг хоосолно (save хийхгүй)."""
    if extension.image_main:
        name = extension.image_main.name
        extension.image_main.delete(save=False)
        _remove_thumb(name)


def remove_image(extension):
    """Барааг зураггүй болгоно (save хийхгүй): оруулсан зургийг (image_main) устгаж, media/products/{item_id}.jpg
    файл байвал products/removed/ руу зөөнө (буцааж хуулбал дахин харагдана)."""
    delete_main_image(extension)
    # Нэг кодоор хэд хэдэн өргөтгөлтэй файл байж болно (801003.jpg, 801003.png) - бүгдийг нь
    while name := fallback_files().get(extension.item_id):
        removed_dir = os.path.join(settings.MEDIA_ROOT, 'products', 'removed')
        os.makedirs(removed_dir, exist_ok=True)
        os.replace(os.path.join(settings.MEDIA_ROOT, name), os.path.join(removed_dir, os.path.basename(name)))
        _listing('products').discard(os.path.basename(name))
        _remove_thumb(name)
