from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0114_mealattendance_cleared_meals'),
    ]

    operations = [
        migrations.AddField(
            model_name='productextension',
            name='cert_not_required',
            field=models.BooleanField(default=False, verbose_name='Бичиг шаардлагагүй'),
        ),
    ]
