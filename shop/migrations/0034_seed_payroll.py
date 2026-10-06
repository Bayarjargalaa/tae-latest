from decimal import Decimal

from django.db import migrations

# ХХОАТ-ын хөнгөлөлтийн шатлал (сарын, НДШ хассан цалин хүртэл -> сарын хөнгөлөлт) - хуулийн жилийн
# шатлалыг (жилийн 6 сая хүртэл 240,000 гэх мэт) 12-т хуваасан. Цалин бодолтын тохиргоо хуудаснаас засна
DEFAULT_TAX_CREDITS = [
    (Decimal('500000'), Decimal('20000')),
    (Decimal('1000000'), Decimal('18000')),
    (Decimal('1500000'), Decimal('16000')),
    (Decimal('2000000'), Decimal('14000')),
    (Decimal('2500000'), Decimal('12000')),
    (Decimal('3000000'), Decimal('10000')),
    (None, Decimal('0')),
]

PAYROLL_MENU_KEYS = ['payroll_card', 'payroll_cash']


def seed(apps, schema_editor):
    PayrollTaxCredit = apps.get_model('shop', 'PayrollTaxCredit')
    if not PayrollTaxCredit.objects.exists():
        for income_to, credit in DEFAULT_TAX_CREDITS:
            PayrollTaxCredit.objects.create(income_to=income_to, credit_amount=credit)

    # Шинэ цэсүүдийг "Хоног бүртгэл" харагддаг албан тушаалуудад нээнэ (opt-in горимоор анхдагчаар нуугддаг тул)
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    positions = MenuPermission.objects.filter(menu_key='timesheet', is_visible=True).values_list('position_name', flat=True)
    for position_name in positions:
        for key in PAYROLL_MENU_KEYS:
            MenuPermission.objects.get_or_create(position_name=position_name, menu_key=key, defaults={'is_visible': True})


def unseed(apps, schema_editor):
    apps.get_model('shop', 'PayrollTaxCredit').objects.all().delete()
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=PAYROLL_MENU_KEYS).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0033_payroll'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
