"""Бүтээгдэхүүний бичгийн (шинжилгээний бичиг г.м.) дуусах хугацааны төлөв.

Төлөвийг хадгалахгүй - өдөр өнгөрөхөд хуучирна. Барааны тухайн төрлийн бичгүүдээс хамгийн сүүлд дуусахыг
(эсвэл "хугацаагүй"-г) query-ээр олж өнөөдөртэй харьцуулна. Хуучин бичиг түүх болж үлдэх ба шинэ бичиг
хавсаргахад бараа автоматаар хүчинтэй болно.
"""
from datetime import date, timedelta

from django.db.models import CharField, Case, DateField, Exists, F, IntegerField, Max, OuterRef, Q, Subquery, Value, When

# Дуусахад үүнээс цөөн хоног үлдсэн бол "Удахгүй дуусна"
SOON_DAYS = 30

# (код, нэр, тэмдэг, tailwind өнгө) - хяналтын хуудасны дарааллаар (анхаарах шаардлагатай нь эхэнд)
STATUSES = [
    ('expired', 'Хугацаа дууссан', '🔴', 'red'),
    ('soon', 'Удахгүй дуусна', '🟡', 'amber'),
    ('no_date', 'Хугацаа оруулаагүй', '🟠', 'orange'),
    ('none', 'Бичиггүй', '⚪', 'gray'),
    ('valid', 'Хүчинтэй', '🟢', 'green'),
]
STATUS_LABELS = {code: label for code, label, _, _ in STATUSES}
STATUS_PRIORITY = {code: i for i, (code, *_rest) in enumerate(STATUSES)}


# Бараанд үйлчлэх огноо: холбоос дээр тусдаа хугацаа (own_expiry) өгсөн бол түүнийг, үгүй бол бичгийн ерөнхийг
EFFECTIVE_EXPIRES = Case(When(own_expiry=True, then=F('expires_on')), default=F('attachment__expires_on'),
                         output_field=DateField())
EFFECTIVE_UNLIMITED = Q(own_expiry=True, no_expiry=True) | Q(own_expiry=False, attachment__no_expiry=True)


def tracked_types():
    from shop.models import ProductDocType
    return list(ProductDocType.objects.filter(tracks_expiry=True, is_active=True))


def default_type_ids():
    """Барааны жагсаалтын тэмдэг/шүүлтэд ашиглах төрөл - эхний хугацаа хянадаг төрөл (Шинжилгээний бичиг)."""
    types = tracked_types()
    return [types[0].pk] if types else []


def annotate_status(qs, doc_type_ids, today=None):
    """OpenDataItem queryset-д cert_status, cert_expires, cert_unlimited, cert_priority нэмнэ."""
    from shop.models import ProductAttachmentItem
    today = today or date.today()
    links = ProductAttachmentItem.objects.filter(item_id=OuterRef('id'), attachment__doc_type_id__in=doc_type_ids)
    latest = links.order_by().values('item_id').annotate(m=Max(EFFECTIVE_EXPIRES)).values('m')[:1]
    qs = qs.annotate(
        cert_has=Exists(links),
        cert_unlimited=Exists(links.filter(EFFECTIVE_UNLIMITED)),
        cert_expires=Subquery(latest),
    )
    whens = [
        When(cert_has=False, then=Value('none')),
        When(cert_unlimited=True, then=Value('valid')),
        When(cert_expires__isnull=True, then=Value('no_date')),
        When(cert_expires__lt=today, then=Value('expired')),
        When(cert_expires__lte=today + timedelta(days=SOON_DAYS), then=Value('soon')),
    ]
    return qs.annotate(
        cert_status=Case(*whens, default=Value('valid'), output_field=CharField()),
        cert_priority=Case(*[When(cert_status=code, then=Value(p)) for code, p in STATUS_PRIORITY.items()],
                           output_field=IntegerField()),
    )


def days_left(expires, today=None):
    return (expires - (today or date.today())).days if expires else None


def status_text(status, expires, unlimited=False, today=None):
    """Хүнд ойлгомжтой богино тайлбар: "12 хоног үлдсэн", "45 хоногийн өмнө дууссан" г.м."""
    days = days_left(expires, today)
    if status == 'none':
        return 'Бичиггүй'
    if unlimited:
        return 'Хугацаагүй'
    if days is None:
        return 'Хугацаа оруулаагүй'
    if days < 0:
        return f'{-days} хоногийн өмнө дууссан'
    if days == 0:
        return 'Өнөөдөр дуусна'
    if status == 'soon':
        return f'{days} хоног үлдсэн'
    if days < 90:
        return f'{days} хоног үлдсэн'
    years, months = divmod(int(days / 30.4), 12)
    return '≈ ' + ' '.join(p for p in (f'{years} жил' if years else '', f'{months} сар' if months else '') if p) + ' үлдсэн'


def decorate(items, today=None):
    """annotate_status-тай бараа бүрт cert_label, cert_text, cert_days нэмнэ (template-д)."""
    for item in items:
        item.cert_label = STATUS_LABELS.get(item.cert_status, '')
        item.cert_days = days_left(item.cert_expires, today)
        item.cert_text = status_text(item.cert_status, item.cert_expires, item.cert_unlimited, today)
    return items


def latest_documents(item_ids, doc_type_ids):
    """{item_id: ProductAttachmentItem} - бараа бүрийн хамгийн сүүлд дуусах (хугацаагүйг тэргүүлэн) бичгийн холбоос
    (link.attachment нь бичиг, link.effective_* нь тухайн бараанд үйлчлэх огноо)."""
    from shop.models import ProductAttachmentItem
    best = {}
    links = (ProductAttachmentItem.objects.filter(item_id__in=list(item_ids), attachment__doc_type_id__in=doc_type_ids)
             .select_related('attachment', 'attachment__doc_type'))

    def rank(link):
        return (link.effective_no_expiry, link.effective_expires or date.min, link.attachment.created_at)

    for link in links:
        current = best.get(link.item_id)
        if current is None or rank(link) > rank(current):
            best[link.item_id] = link
    return best


def status_filter(status):
    """cert_status-аар шүүх нөхцөл (буруу код бол хоосон)."""
    return Q(cert_status=status) if status in STATUS_LABELS else Q()


def parse_doc_meta(post):
    """Хавсаргах/засах формоос (doc_type, issued_on, expires_on, no_expiry) уншиж шалгана.
    Буцаах: (утгын dict, алдааны жагсаалт). Өнгөрсөн дуусах огноог хориглохгүй (хуучин бичиг архивлах)."""
    from shop.models import ProductDocType
    errors = []

    def parse_date(name, label):
        raw = (post.get(name) or '').strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            errors.append(f'{label} буруу байна: {raw}')
            return None

    doc_type = None
    type_id = (post.get('doc_type') or '').strip()
    if type_id:
        doc_type = ProductDocType.objects.filter(pk=type_id if type_id.isdigit() else None).first()
        if doc_type is None:
            errors.append('Бичгийн төрөл олдсонгүй.')
    issued_on = parse_date('issued_on', 'Олгосон огноо')
    expires_on = parse_date('expires_on', 'Дуусах огноо')
    no_expiry = post.get('no_expiry') == '1'
    if no_expiry:
        expires_on = None
    if issued_on and expires_on and expires_on <= issued_on:
        errors.append('Дуусах огноо олгосон огнооноос хойш байх ёстой.')
    return {'doc_type': doc_type, 'issued_on': issued_on, 'expires_on': expires_on, 'no_expiry': no_expiry}, errors


def attachment_status(attachment, today=None, expires=None, no_expiry=None):
    """Нэг бичгийн (status, тайлбар) - хугацаа хянадаггүй төрөлд (None, ''). expires/no_expiry өгвөл
    (тухайн барааны тусдаа огноо) бичгийн ерөнхий огнооны оронд түүнийг ашиглана."""
    today = today or date.today()
    if not attachment.doc_type or not attachment.doc_type.tracks_expiry:
        return None, ''
    if no_expiry is None:
        expires, no_expiry = attachment.expires_on, attachment.no_expiry
    if no_expiry:
        status = 'valid'
    elif expires is None:
        status = 'no_date'
    elif expires < today:
        status = 'expired'
    elif expires <= today + timedelta(days=SOON_DAYS):
        status = 'soon'
    else:
        status = 'valid'
    return status, status_text(status, expires, no_expiry, today)


def parse_item_overrides(post, links, issued_on=None):
    """Засах цонхны бараа тус бүрийн огноо (item_own_<id>, item_expires_<id>, item_no_expiry_<id>).
    Буцаах: ({link: (own, expires, no_expiry)}, алдаанууд). Формд 'items_submitted' байхгүй бол хоосон."""
    if post.get('items_submitted') != '1':
        return {}, []
    result, errors = {}, []
    for link in links:
        own = post.get(f'item_own_{link.item_id}') == '1'
        expires, no_expiry = None, False
        if own:
            no_expiry = post.get(f'item_no_expiry_{link.item_id}') == '1'
            raw = (post.get(f'item_expires_{link.item_id}') or '').strip()
            if raw and not no_expiry:
                try:
                    expires = date.fromisoformat(raw)
                except ValueError:
                    errors.append(f'{link.item_id}: дуусах огноо буруу байна ({raw}).')
                    continue
                if issued_on and expires <= issued_on:
                    errors.append(f'{link.item_id}: дуусах огноо олгосон огнооноос хойш байх ёстой.')
                    continue
        result[link] = (own, expires, no_expiry)
    return result, errors


def items_payload(attachments):
    """{attachment_id: JSON} - засах цонхонд бичигт холбогдсон бараа бүрийн нэр, тусдаа огноо."""
    import json
    from shop.models import ProductAttachmentItem
    from shop.services.product_files import item_names
    ids = [a.pk for a in attachments]
    links = list(ProductAttachmentItem.objects.filter(attachment_id__in=ids).order_by('id'))
    names = item_names(link.item_id for link in links)
    payload = {pk: [] for pk in ids}
    for link in links:
        payload[link.attachment_id].append({
            'id': link.item_id, 'name': names.get(link.item_id) or link.item_id, 'own': link.own_expiry,
            'expires': link.expires_on.isoformat() if link.expires_on else '', 'noExpiry': link.no_expiry,
        })
    return {pk: json.dumps(items, ensure_ascii=False) for pk, items in payload.items()}
