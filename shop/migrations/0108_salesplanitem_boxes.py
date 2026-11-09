from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0107_productextension_box_measure'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesplanitem',
            name='target_boxes',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True, verbose_name='Зорилт (хайрцаг)'),
        ),
        migrations.AddField(
            model_name='salesplanitem',
            name='qty_per_box',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Хайрцаг дахь тоо'),
        ),
    ]
