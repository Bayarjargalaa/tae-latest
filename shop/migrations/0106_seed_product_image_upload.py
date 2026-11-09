from django.db import migrations

# Бүтээгдэхүүний зөвхөн зураг оруулах эрх (бусад мэдээлэл засахгүй) - Оффис менежер. Бусад албан тушаалд
# цэсний эрх тохируулах хуудсын "Үйлдлийн эрх" хэсгээс нэмнэ (superuser, Ерөнхий нягтлан үргэлж эрхтэй).
SEED = {
    'product_image_upload': ['Оффис менежер'],
}


def seed(apps, schema_editor):
    MenuPermission = apps.get_model('shop', 'MenuPermission')
    for menu_key, positions in SEED.items():
        for position_name in positions:
            MenuPermission.objects.update_or_create(
                position_name=position_name, menu_key=menu_key, defaults={'is_visible': True},
            )


def unseed(apps, schema_editor):
    apps.get_model('shop', 'MenuPermission').objects.filter(menu_key__in=list(SEED)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0105_bank_account_channels'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
