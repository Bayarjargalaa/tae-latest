"""
Бүтээгдэхүүний хавсралт: iPhone-ын HEIC/HEIF зургийг JPEG болгож хадгална - Windows/Android хөтөч HEIC-ийг
харуулж чаддаггүй тул. Бусад файлыг өөрчлөхгүй.
"""
import io
import os

from django.core.files.uploadedfile import SimpleUploadedFile

HEIC_EXTS = ('.heic', '.heif')
# Бичиг уншигдахуйц, гэхдээ хэт том биш (утасны 12MP зураг ~1-2MB болно)
MAX_SIDE = 3000


def normalize_upload(f):
    """(файл, анхны нэр) - HEIC бол JPEG болгосон шинэ файл, нэрийн өргөтгөлийг .jpg болгоно."""
    base, ext = os.path.splitext(f.name)
    if ext.lower() not in HEIC_EXTS:
        return f, f.name
    import pillow_heif
    from PIL import Image, ImageOps

    pillow_heif.register_heif_opener()
    img = ImageOps.exif_transpose(Image.open(f))  # утасны эргүүлэлтийг засна
    img.thumbnail((MAX_SIDE, MAX_SIDE))
    buf = io.BytesIO()
    img.convert('RGB').save(buf, 'JPEG', quality=88)
    name = f'{base}.jpg'
    return SimpleUploadedFile(name, buf.getvalue(), content_type='image/jpeg'), name


def item_names(item_ids):
    """{OpenDataItem.id: нэр}"""
    from datamigration.models import OpenDataItem
    return dict(OpenDataItem.objects.filter(id__in=set(item_ids)).values_list('id', 'name'))


def valid_item_ids(item_ids):
    """Жинхэнэ байгаа барааны id-ууд (давхардалгүй, анхны дарааллаар)."""
    from datamigration.models import OpenDataItem
    ids = [i.strip() for i in item_ids if i and i.strip()]
    existing = set(OpenDataItem.objects.filter(id__in=ids).values_list('id', flat=True))
    return list(dict.fromkeys(i for i in ids if i in existing))


def link_items(attachment, item_ids):
    """Хавсралтыг бараануудтай холбоно (аль хэдийн холбогдсоныг алгасна). Шинээр холбосон тоог буцаана."""
    from shop.models import ProductAttachmentItem
    have = set(attachment.items.values_list('item_id', flat=True))
    new = [i for i in valid_item_ids(item_ids) if i not in have]
    ProductAttachmentItem.objects.bulk_create([ProductAttachmentItem(attachment=attachment, item_id=i) for i in new])
    return len(new)


def unlink_item(attachment, item_id):
    """Хавсралтыг нэг бараанаас салгана; өөр бараатай холбоогүй болбол файлтайгаа устгана. True = бүр устсан."""
    attachment.items.filter(item_id=item_id).delete()
    if attachment.items.exists():
        return False
    delete_attachment(attachment)
    return True


def delete_attachment(attachment):
    attachment.file.delete(save=False)
    attachment.delete()


def search_items(query, limit=20):
    """Бараа хайх (нэр, код, баркодоор) - идэвхтэй бараа эхэнд."""
    from django.db.models import Case, IntegerField, Q, Value, When
    from datamigration.models import OpenDataItem
    query = (query or '').strip()
    if len(query) < 2:
        return []
    qs = OpenDataItem.objects.all()
    for word in query.split():
        qs = qs.filter(Q(name__icontains=word) | Q(id__icontains=word) | Q(barcode__icontains=word))
    qs = qs.annotate(inactive=Case(When(activestatus='Y', then=Value(0)), default=Value(1), output_field=IntegerField()))
    return [{'id': i, 'name': n} for i, n in qs.order_by('inactive', 'name').values_list('id', 'name')[:limit]]
