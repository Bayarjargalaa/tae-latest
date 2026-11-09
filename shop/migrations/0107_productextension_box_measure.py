from django.db import migrations, models

# Өмнө хадгалсан хайрцаг дахь тоонд хэмжих нэгжийг MSSQL-ийн (OpenDataItem.MeasureName) нэгжээр нөхнө
BACKFILL_SQL = """
UPDATE shop_product_extension e SET box_measure = i."MeasureName"
FROM "OpenDataItem" i
WHERE i."Id" = e.item_id AND e.box_measure = '' AND e.qty_per_box IS NOT NULL AND COALESCE(i."MeasureName", '') <> ''
"""


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0106_seed_product_image_upload'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productextension',
            name='qty_per_box',
            field=models.DecimalField(blank=True, decimal_places=3, max_digits=12, null=True, verbose_name='Хайрцаг дахь тоо'),
        ),
        migrations.AddField(
            model_name='productextension',
            name='box_measure',
            field=models.CharField(blank=True, max_length=30, verbose_name='Хайрцаг дахь тооны хэмжих нэгж'),
        ),
        migrations.RunSQL(BACKFILL_SQL, migrations.RunSQL.noop),
    ]
