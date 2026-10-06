from django.db import migrations, models


class Migration(migrations.Migration):
    """Татан авалтын дугаар он бүр давтагддаг тул ачааг DocumentPkId-аар таниулна (хүснэгт хоосон үед нэмэгдсэн)."""

    dependencies = [
        ('shop', '0062_seed_unloading_menu_permission'),
    ]

    operations = [
        migrations.AddField(
            model_name='unloadingevent',
            name='document_id',
            field=models.BigIntegerField(default=0, unique=True, verbose_name='Татан авалтын ID (DocumentPkId)'),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='unloadingevent',
            name='document_number',
            field=models.CharField(max_length=50, verbose_name='Татан авалтын дугаар'),
        ),
    ]
