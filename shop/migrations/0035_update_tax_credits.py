from decimal import Decimal

from django.db import migrations

# 0034-ийн анхны хувилбар оруулсан буруу шатлал - ийм хэвээр (гараар засаагүй) байвал л солино
OLD_DEFAULTS = [
    (Decimal('500000'), Decimal('20000')),
    (Decimal('1000000'), Decimal('18000')),
    (Decimal('1500000'), Decimal('15000')),
    (Decimal('2000000'), Decimal('13000')),
    (Decimal('2500000'), Decimal('11000')),
    (Decimal('3000000'), Decimal('9000')),
    (None, Decimal('0')),
]
# Хуулийн одоогийн шатлал (жилийн дүнг 12-т хуваасан сарын дүнгээр)
NEW_DEFAULTS = [
    (Decimal('500000'), Decimal('20000')),
    (Decimal('1000000'), Decimal('18000')),
    (Decimal('1500000'), Decimal('16000')),
    (Decimal('2000000'), Decimal('14000')),
    (Decimal('2500000'), Decimal('12000')),
    (Decimal('3000000'), Decimal('10000')),
    (None, Decimal('0')),
]


def _current(PayrollTaxCredit):
    rows = [(c.income_to, c.credit_amount) for c in PayrollTaxCredit.objects.all()]
    # income_to өсөхөөр, хоосон (дээд шат) нь төгсгөлд
    return sorted(rows, key=lambda r: (r[0] is None, r[0] or 0))


def forwards(apps, schema_editor):
    PayrollTaxCredit = apps.get_model('shop', 'PayrollTaxCredit')
    if _current(PayrollTaxCredit) == OLD_DEFAULTS:
        PayrollTaxCredit.objects.all().delete()
        for income_to, credit in NEW_DEFAULTS:
            PayrollTaxCredit.objects.create(income_to=income_to, credit_amount=credit)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0034_seed_payroll'),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
