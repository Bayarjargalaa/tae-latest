from django.db import migrations

# Бүтээгдэхүүн засах, шинжилгээний бичиг хавсаргах - Гадаад харилцаа. Бусад албан тушаалд
# цэсний эрх тохируулах хуудсын "Үйлдлийн эрх" хэсгээс нэмнэ (superuser, Ерөнхий нягтлан үргэлж эрхтэй).
SEED = {
    'product_edit': ['Гадаад харилцаа'],
    'product_attachment_upload': ['Гадаад харилцаа'],
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
        ('shop', '0092_product_attachment'),
    ]

    operations = [
        migrations.RunPython(seed, unseed),
    ]
