from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0108_salesplanitem_boxes'),
    ]

    operations = [
        migrations.AddField(
            model_name='salesplan',
            name='items_excluded',
            field=models.BooleanField(default=False, verbose_name='Төлөвлөгөөт бараанд хамруулахгүй'),
        ),
    ]
