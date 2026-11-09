"""
Нэхэмжлэх (НХМаягт T-1) - харилцагчийн авлагын үлдэгдлээр нэг мөртэй нэхэмжлэх үүсгэж PDF-ээр харилцагчийн
имэйл рүү илгээнэ.

- Нэхэмжлэгчийн мэдээлэл, дугаарлалт, лого/тамга, имэйлийн загвар: InvoiceSetting (ганц мөр).
- Банкны данс: CompanyBankAccount; харилцагчийн имэйл, хаяг: CustomerContact (OpenDataCustomer-д байхгүй).
- Дүн = авлагын эцсийн үлдэгдэл (НӨАТ-тэй), НӨАТ-гүй дүн = дүн / (1 + НӨАТ%).
- Илгээх хаяг: .env-ийн INVOICE_EMAIL_HOST_USER / INVOICE_EMAIL_HOST_PASSWORD (Gmail бол App Password);
  тохируулаагүй бол үндсэн EMAIL_HOST_USER-ээр.
"""
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

FONT_DIR = '/usr/share/fonts/truetype/dejavu'
FONT, FONT_BOLD = 'DejaVuSans', 'DejaVuSans-Bold'

# --- Дүнг үсгээр -------------------------------------------------------------------------------------------
# Дараа нь үг залгах хэлбэр (гурван мянга, таван зуун төгрөг) - тоо бүр араасаа нэгж/төгрөг авдаг тул үргэлж энэ хэлбэр
_ONES = ['', 'нэг', 'хоёр', 'гурван', 'дөрвөн', 'таван', 'зургаан', 'долоон', 'найман', 'есөн']
_TENS = ['', 'арван', 'хорин', 'гучин', 'дөчин', 'тавин', 'жаран', 'далан', 'наян', 'ерэн']
# (утга, араасаа тоо байвал, төгсгөлд (төгрөгийн өмнө))
_SCALES = [(10 ** 12, 'их наяд', 'их наяд'), (10 ** 9, 'тэрбум', 'тэрбум'), (10 ** 6, 'сая', 'сая'), (10 ** 3, 'мянга', 'мянган')]


def _triple(n):
    words = []
    if n >= 100:
        words += [_ONES[n // 100], 'зуун']
        n %= 100
    if n >= 10:
        words.append(_TENS[n // 10])
        n %= 10
    if n:
        words.append(_ONES[n])
    return words


def amount_in_words(amount):
    """1234500.5 -> 'Нэг сая хоёр зуун гучин дөрвөн мянга таван зуун төгрөг 50 мөнгө'."""
    amount = Decimal(amount).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    whole, cents = int(amount), int((amount - int(amount)) * 100)
    words, rest = [], whole
    for value, mid, last in _SCALES:
        if rest >= value:
            words += _triple(rest // value) + [mid if rest % value else last]
            rest %= value
    words += _triple(rest)
    text = ' '.join(w for w in words if w) or 'тэг'
    text = f'{text} төгрөг' + (f' {cents:02d} мөнгө' if cents else '')
    return text[0].upper() + text[1:]


def vat_split(amount, vat_rate):
    """(НӨАТ-гүй дүн, НӨАТ) - дүн НӨАТ-тэй."""
    amount, rate = Decimal(amount), Decimal(vat_rate or 0)
    net = (amount / (1 + rate / 100)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    return net, amount - net


def money(v):
    return f'{Decimal(v):,.2f}'


# --- Өгөгдөл -----------------------------------------------------------------------------------------------

def bank_text(accounts):
    return '\n'.join(f'{a.bank_name} {a.account_number}' + (f' ({a.account_name})' if a.account_name else '')
                     for a in accounts)


def customer_channel(customer_id):
    with connection.cursor() as cursor:
        cursor.execute('SELECT "DistributionChannelId" FROM "OpenDataCustomer" WHERE "Id" = %s', [customer_id])
        row = cursor.fetchone()
    return row[0] if row else None


def default_bank_ids(banks, customer_id):
    """Харилцагчийн сувагт оноосон данснууд; оноогоогүй бол анхдагч данс."""
    channel = customer_channel(customer_id) if customer_id else None
    by_channel = {b.pk for b in banks if channel and channel in (b.channels or [])}
    return by_channel or {b.pk for b in banks if b.is_default}


def receivable_customers(date_to, q='', channels=None, limit=500):
    """date_to-ны байдлаар авлагын эерэг үлдэгдэлтэй харилцагчид (үлдэгдлээр буурахаар) - сонгох жагсаалтад."""
    from shop.services.recpay_report import EPS, KINDS, TABLE, _where

    where, params = _where('receivable', {'date_to': date_to, 'q': q, 'channels': channels})
    sign = KINDS['receivable']['sign']
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT b.cid, COALESCE(c."Name", b.name), b.balance FROM ('
            f'  SELECT "CustomerId" AS cid, MAX("CustomerName") AS name, SUM({sign}) AS balance FROM {TABLE} '
            f'  WHERE {where} GROUP BY 1 HAVING SUM({sign}) > {EPS}'
            f') b LEFT JOIN "OpenDataCustomer" c ON c."Id" = b.cid ORDER BY b.balance DESC LIMIT %s',
            params + [limit],
        )
        return [{'id': cid, 'name': name or cid, 'balance': float(balance)} for cid, name, balance in cursor.fetchall()]


def customer_defaults(customer_id, date_to):
    """Шинэ нэхэмжлэхийн анхдагч утгууд: харилцагчийн нэр, регистр, имэйл, хаяг, авлагын үлдэгдэл (date_to хүртэл)."""
    from shop.models import CustomerContact, InvoiceSetting
    from shop.services.recpay_report import KINDS, TABLE, _where

    with connection.cursor() as cursor:
        cursor.execute('SELECT "Name", "RegistryNumber" FROM "OpenDataCustomer" WHERE "Id" = %s', [customer_id])
        row = cursor.fetchone() or (None, None)
        where, params = _where('receivable', {'date_to': date_to, 'customer': customer_id})
        cursor.execute(
            f'SELECT COALESCE(SUM({KINDS["receivable"]["sign"]}), 0), MAX("CustomerName") FROM {TABLE} WHERE {where}',
            params,
        )
        balance, rp_name = cursor.fetchone()
    contact = CustomerContact.objects.filter(customer_id=customer_id).first()
    setting = InvoiceSetting.get()
    today = timezone.localdate()
    return {
        'customer_id': customer_id,
        'customer_name': row[0] or rp_name or customer_id,
        'registry_number': row[1] or '',
        'email': contact.email if contact else '',
        'address': contact.address if contact else '',
        'invoice_date': today,
        'due_date': today + timedelta(days=setting.due_days),
        'description': f'Авлагын үлдэгдэл ({date_to:%Y.%m.%d}-ний байдлаар)',
        'amount': Decimal(balance or 0).quantize(Decimal('0.01')),
    }


@transaction.atomic
def take_number():
    """Дараагийн нэхэмжлэхийн дугаарыг авч тоолуурыг нэмэгдүүлнэ (давхардахгүй)."""
    from shop.models import Invoice, InvoiceSetting

    InvoiceSetting.get()
    setting = InvoiceSetting.objects.select_for_update().get(pk=1)
    number = setting.next_number
    while Invoice.objects.filter(number=f'{setting.number_prefix}{number}').exists():
        number += 1
    setting.next_number = number + 1
    setting.save(update_fields=['next_number', 'updated_at'])
    return f'{setting.number_prefix}{number}'


def recipients(raw):
    return [e.strip() for e in (raw or '').replace(';', ',').split(',') if e.strip()]


# --- PDF ---------------------------------------------------------------------------------------------------

def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if FONT not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(FONT, f'{FONT_DIR}/DejaVuSans.ttf'))
        pdfmetrics.registerFont(TTFont(FONT_BOLD, f'{FONT_DIR}/DejaVuSans-Bold.ttf'))


def _fit(c, text, font, size, width, min_size=6):
    """Өргөнд багтах хүртэл үсгийн хэмжээг багасгана."""
    from reportlab.pdfbase.pdfmetrics import stringWidth

    while size > min_size and stringWidth(text, font, size) > width:
        size -= 0.5
    c.setFont(font, size)


def _image(field):
    try:
        return field.path if field and field.name and field.storage.exists(field.name) else None
    except (ValueError, NotImplementedError):
        return None


def render_pdf(invoice, setting):
    """НХМаягт T-1 загвараар нэхэмжлэхийн PDF (bytes)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas
    from reportlab.platypus import Paragraph, Table, TableStyle

    _register_fonts()
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle(f'Нэхэмжлэх {invoice.number}')
    width, height = A4
    left, right = 40, width - 40

    c.setFont(FONT_BOLD, 10)
    c.drawString(left, height - 45, 'НХМаягт T-1')
    c.setFont(FONT, 7.5)
    c.drawString(370, height - 42, 'Сангийн сайдын 2017 оны 12 дугаар сарын 5')
    c.drawString(370, height - 52, 'өдрийн 347 тоот тушаалын хавсралт')

    logo = _image(setting.logo)
    if logo:
        c.drawImage(ImageReader(logo), left, height - 135, width=136, height=64, preserveAspectRatio=True, anchor='sw', mask='auto')
    c.setFont(FONT_BOLD, 12.5)
    c.drawCentredString(395, height - 98, f'НЭХЭМЖЛЭХ № {invoice.number}')

    def field(x, y, label, value, label_w, line_end):
        c.setFont(FONT, 8.5)
        c.drawString(x, y, label)
        if value:
            _fit(c, value, FONT_BOLD, 8.5, line_end - x - label_w - 4)
            c.drawCentredString((x + label_w + line_end) / 2, y, value)
        c.setLineWidth(0.8)
        c.line(x + label_w, y - 4, line_end, y - 4)

    top = height - 160
    c.setFont(FONT_BOLD, 8.5)
    c.drawString(left, top, 'Нэхэмжлэгч:')
    c.drawString(310, top, 'Төлөгч:')
    step = 21
    banks = (invoice.bank_text or '').splitlines() or ['']
    left_rows = [('Байгууллагын нэр:', setting.company_name, 82), ('Хаяг:', setting.address, 28),
                 ('Утас, Факс:', setting.phone, 82), ('И-мэйл:', setting.email, 82), ('Банк:', banks[0], 82)]
    left_rows += [('', b, 82) for b in banks[1:]] or [('', '', 82)]
    right_rows = [('Байгууллагын нэр:', invoice.customer_name, 82), ('Хаяг:', invoice.address, 28),
                  ('Гэрчилгээний №:', invoice.registry_number, 82),
                  ('Нэхэмжилсэн огноо:', f'{invoice.invoice_date:%Y/%m/%d}', 98),
                  ('Төлбөр хийх хугацаа:', f'{invoice.due_date:%Y/%m/%d}', 98)]
    for i, (label, value, lw) in enumerate(left_rows):
        field(left, top - step * (i + 1), label, value, lw, 285)
    for i, (label, value, lw) in enumerate(right_rows):
        field(310, top - step * (i + 1), label, value, lw, right)

    net, vat = vat_split(invoice.amount, invoice.vat_rate)
    cell = ParagraphStyle('cell', fontName=FONT, fontSize=8, leading=10)
    head = ParagraphStyle('head', fontName=FONT_BOLD, fontSize=7, leading=8.5, alignment=1)
    headers = ['№', 'Материал', 'Хэмжих<br/>нэгж', 'Тоо<br/>хэмжээ', 'Нэгж үнэ', 'НӨАТ', 'НӨАТ-гүй дүн', 'Нийт дүн']
    data = [
        [Paragraph(h, head) for h in headers],
        ['1', Paragraph(invoice.description, cell), invoice.unit, '1', money(net), money(vat), money(net), money(invoice.amount)],
        ['Нийт', '', '', '1', '', money(vat), money(net), money(invoice.amount)],
    ]
    table = Table(data, colWidths=[20, 128, 40, 40, 70, 62, 77, 78])
    border = colors.HexColor('#c9bcbc')
    table.setStyle(TableStyle([
        ('FONT', (0, 0), (-1, -1), FONT, 7.5),
        ('FONT', (0, 2), (-1, 2), FONT_BOLD, 7.5),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e2d9d9')),
        ('GRID', (0, 0), (-1, -1), 0.6, border),
        ('SPAN', (0, 2), (2, 2)),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (2, 1), (2, 1), 'CENTER'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, 0), 2),
        ('RIGHTPADDING', (0, 0), (-1, 0), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    table_top = top - step * (max(len(left_rows), len(right_rows)) + 1) - 8
    _, table_h = table.wrapOn(c, right - left, 400)
    table.drawOn(c, left, table_top - table_h)

    y = table_top - table_h - 40
    words = amount_in_words(invoice.amount)
    c.setFont(FONT, 8.5)
    c.drawString(left, y, 'Мөнгөний дүн')
    _fit(c, words, FONT_BOLD, 8.5, 380)
    c.drawCentredString(310, y + 2, words)
    c.setLineWidth(0.8)
    c.line(118, y - 4, 500, y - 4)
    c.setFont(FONT, 8.5)
    c.drawString(508, y, 'болно')
    c.drawCentredString(310, y - 16, '(үсгээр)')

    y -= 60
    c.drawString(118, y, 'Нэхэмжлэл хүлээн авсан')
    c.drawString(372, y, '/')
    c.drawString(452, y, '/')
    c.drawString(118, y - 20, 'Нэхэмжлэл бичсэн')
    stamp = _image(setting.stamp)
    if stamp:
        c.drawImage(ImageReader(stamp), 228, y - 44, width=134, height=50, preserveAspectRatio=True, anchor='c', mask='auto')
    # Нэхэмжлэх үүсгэсэн хэрэглэгчийн нэр; тодорхойгүй бол тохиргооны нэр
    c.drawString(372, y - 20, f'/ {sender_name(invoice.created_by) or setting.prepared_by} /')

    c.setFont(FONT, 7.5)
    c.drawString(left, 30, f'Хэвлэсэн огноо : {timezone.localtime():%Y/%m/%d %H:%M:%S}')
    c.showPage()
    c.save()
    return buffer.getvalue()


# --- Имэйл -------------------------------------------------------------------------------------------------

def sender():
    return getattr(settings, 'INVOICE_EMAIL_HOST_USER', '') or settings.EMAIL_HOST_USER


def sender_name(user):
    """Имэйлийн "Хүндэтгэсэн"-ий доор гарах нэр: ажилтны нэр (OpenDataEmployee), эсвэл хэрэглэгчийн нэр."""
    if user is None:
        return ''
    from shop.access import get_user_employee

    employee = get_user_employee(user)
    return (employee.name if employee and employee.name else '') or user.get_full_name() or user.username


def _context(invoice, setting, user=None):
    return {
        'sender_name': sender_name(user),
        'number': invoice.number, 'company': setting.company_name, 'customer': invoice.customer_name,
        'date': f'{invoice.invoice_date:%Y.%m.%d}', 'due_date': f'{invoice.due_date:%Y.%m.%d}',
        'amount': money(invoice.amount), 'bank': invoice.bank_text, 'phone': setting.phone,
    }


def _format(template, ctx):
    try:
        return template.format(**ctx)
    except (KeyError, IndexError, ValueError):
        return template


def send_invoice(invoice, setting, subject=None, body=None, user=None):
    """PDF хавсаргаж invoice.email рүү илгээнэ; төлөв, алдааг invoice-д хадгална. Амжилттай бол True."""
    from django.core.mail import EmailMessage, get_connection

    to = recipients(invoice.email)
    if not to:
        invoice.status, invoice.error = invoice.STATUS_FAILED, 'Имэйл хаяг хоосон'
        invoice.save(update_fields=['status', 'error'])
        return False
    ctx = _context(invoice, setting, user)
    from_email = sender()
    user = getattr(settings, 'INVOICE_EMAIL_HOST_USER', '')
    conn = get_connection(
        username=user or None,
        password=(getattr(settings, 'INVOICE_EMAIL_HOST_PASSWORD', '') or None) if user else None,
        fail_silently=False,
    )
    message = EmailMessage(
        subject=_format(subject or setting.email_subject, ctx),
        body=_format(body or setting.email_body, ctx),
        from_email=f'{setting.company_name} <{from_email}>' if from_email else None,
        to=to,
        reply_to=[from_email] if from_email else None,
        connection=conn,
    )
    message.attach(f'Nehemjleh_{invoice.number}.pdf', render_pdf(invoice, setting), 'application/pdf')
    try:
        message.send()
    except Exception as exc:  # SMTP, сүлжээ г.м. - хэрэглэгчид харуулж, дахин илгээх боломжтой үлдээнэ
        invoice.status, invoice.error = invoice.STATUS_FAILED, str(exc)[:1000]
        invoice.save(update_fields=['status', 'error'])
        return False
    invoice.status, invoice.error, invoice.sent_at = invoice.STATUS_SENT, '', timezone.now()
    invoice.save(update_fields=['status', 'error', 'sent_at'])
    return True

