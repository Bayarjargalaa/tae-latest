from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0116_import_payment_receipts'),
    ]

    operations = [
        migrations.AddField(
            model_name='importsupplierorder',
            name='foreign_extra',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=16, verbose_name='Гадаад дахь нэмэлт зардал'),
        ),
    ]
