"""
Бэлэн цалингийн дансны дугаарыг (EmployeePayProfile.cash_bank_account) цэгцэлж харуулна.

Гараар бичсэн утга олон янз: "MN35 0005 00 5070482122", "Голомт-MN140015001605124117", "MN95 0004000 428059637-ХХБ".
Монгол IBAN = "MN" + 18 оронтой тоо (2 шалгах орон + 4 банкны код + 12 дансны дугаар). "MN"-ийн араас тоонуудыг
зайгүйгээр нийлүүлж, банкийг IBAN-ы банкны кодоор (мэдэгдэхгүй бол бичлэгт байгаа нэрээр) тодорхойлно.
Хадгалсан утгыг өөрчлөхгүй - зөвхөн харуулахад.
"""
import re

IBAN_LENGTH = 20
# IBAN-ы банкны код (MN + 2 шалгах оронгийн дараах 4 орон)
BANK_CODES = {
    '0004': 'Худалдаа хөгжлийн банк',
    '0005': 'Хаан банк',
    '0015': 'Голомт банк',
}
# Бичлэгт банкны нэр бичсэн бол (код мэдэгдэхгүй үед)
BANK_NAME_HINTS = [
    ('ххб', 'Худалдаа хөгжлийн банк'),
    ('голомт', 'Голомт банк'),
    ('хаан', 'Хаан банк'),
    ('хас', 'Хас банк'),
    ('төрийн', 'Төрийн банк'),
    ('капитрон', 'Капитрон банк'),
]
UNKNOWN_BANK = 'Тодорхойгүй'
# Хэвлэхэд дансны ард гарах банкны богино нэр
BANK_SHORT_NAMES = {
    'Худалдаа хөгжлийн банк': 'ХХБ',
    'Хаан банк': 'Хаан',
    'Голомт банк': 'Голомт',
    'Хас банк': 'Хас',
    'Төрийн банк': 'Төрийн',
    'Капитрон банк': 'Капитрон',
}

_IBAN_RE = re.compile(r'MN[\s\-]*([\d\s\-]+)', re.IGNORECASE)


def account_info(raw):
    """{'raw', 'account', 'bank', 'status'} - status: 'ok', 'invalid' (урт буруу / MN-гүй), 'missing' (хоосон)."""
    raw = (raw or '').strip()
    if not raw:
        return {'raw': '', 'account': '', 'bank': '', 'status': 'missing'}
    match = _IBAN_RE.search(raw)
    if match:
        account = 'MN' + re.sub(r'\D', '', match.group(1))
    else:
        # MN-гүй бичсэн бол зөвхөн зайг хасна
        account = re.sub(r'\s+', '', raw)
    lowered = raw.lower()
    bank = BANK_CODES.get(account[4:8]) if match else None
    bank = bank or next((name for hint, name in BANK_NAME_HINTS if hint in lowered), UNKNOWN_BANK)
    status = 'ok' if match and len(account) == IBAN_LENGTH else 'invalid'
    return {'raw': raw, 'account': account, 'bank': bank, 'status': status}


def print_account(raw):
    """Хэвлэхэд нэг загвараар: "MN35 0005 00 5070482122 Хаан" (шалгах орон, банкны код, 2 + 10 оронтой данс).
    IBAN биш (урт буруу) бол гараар бичсэнээр нь."""
    info = account_info(raw)
    if info['status'] != 'ok':
        return info['raw']
    a = info['account']
    text = f'{a[:4]} {a[4:8]} {a[8:10]} {a[10:]}'
    short = BANK_SHORT_NAMES.get(info['bank'])
    return f'{text} {short}' if short else text


# --- Картын цалингийн багц гүйлгээ (Худалдаа хөгжлийн банк) -------------------------------------------------------
TDB_BANK_CODE = '0004'


def iban_check_digits(bban):
    """Монгол IBAN-ы шалгах 2 орон (ISO 7064 mod 97-10): bban = 4 банкны код + 12 дансны дугаар."""
    number = int(''.join(str(int(ch, 36)) for ch in bban + 'MN00'))
    return f'{98 - number % 97:02d}'


def card_account(raw, bank_code=TDB_BANK_CODE):
    """Ажилтны мэдээлэл дэх картын дансыг IBAN болгоно: {'account', 'status', 'converted'}.
    "MN..." бол цэгцэлж, хуучин дансны дугаар (зөвхөн тоо, ≤12 орон, ХХБ) бол банкны код + 12 орон болгож шалгах
    оронг бодно (converted=True). "100004000440036205" шиг MN-гүй 18 оронтой бол MN нэмнэ."""
    info = account_info(raw)
    if info['status'] != 'invalid' or 'mn' in (raw or '').lower():
        return {'account': info['account'], 'status': info['status'], 'converted': False}
    digits = re.sub(r'\D', '', raw)
    if len(digits) == IBAN_LENGTH - 2:  # MN-гүй IBAN
        return {'account': 'MN' + digits, 'status': 'ok', 'converted': True}
    if 5 <= len(digits) <= 12 and bank_code:
        bban = bank_code + digits.zfill(12)
        return {'account': 'MN' + iban_check_digits(bban) + bban, 'status': 'ok', 'converted': True}
    return {'account': info['account'], 'status': 'invalid', 'converted': False}


def tdb_branch(account):
    """ХХБ-ны IBAN-аас салбарын код: MNkk 0004 000 [ССС] ... -> ССС (дансны дугаарын эхний 3 орон)."""
    if len(account or '') == IBAN_LENGTH and account[4:8] == TDB_BANK_CODE:
        return account[11:14]
    return ''


def bulk_name(name):
    """Багц гүйлгээний "Хүлээн авагчийн нэр": "Мөнхбат.Д" -> "Мөнхбат", "Очгэрэл //" -> "Очгэрэл",
    "Сарангэрэл.Э /Алтжин/" -> "Сарангэрэл" (налуу зураасан доторх тайлбар, эцгийн нэрийн үсгийг хасна)."""
    text = re.sub(r'/[^/]*/', ' ', name or '').replace('/', ' ')
    text = re.sub(r'\.\s*\S{1,2}\s*$', '', text.strip())
    return re.sub(r'\s+', ' ', text).strip(' .')
