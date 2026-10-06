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
