from django.db import migrations, models
import django.db.models.deletion


def copy_item_ids(apps, schema_editor):
    """Өмнөх нэг бараатай хавсралтуудыг холбоос хүснэгтэд шилжүүлнэ."""
    ProductAttachment = apps.get_model('shop', 'ProductAttachment')
    ProductAttachmentItem = apps.get_model('shop', 'ProductAttachmentItem')
    ProductAttachmentItem.objects.bulk_create([
        ProductAttachmentItem(attachment_id=a.pk, item_id=a.item_id)
        for a in ProductAttachment.objects.exclude(item_id='')
    ])


def restore_item_ids(apps, schema_editor):
    ProductAttachment = apps.get_model('shop', 'ProductAttachment')
    ProductAttachmentItem = apps.get_model('shop', 'ProductAttachmentItem')
    for link in ProductAttachmentItem.objects.order_by('id'):
        ProductAttachment.objects.filter(pk=link.attachment_id, item_id='').update(item_id=link.item_id)


class Migration(migrations.Migration):

    dependencies = [
        ('shop', '0093_seed_product_action_permissions'),
    ]

    operations = [
        migrations.CreateModel(
            name='ProductAttachmentItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('item_id', models.TextField(db_index=True, verbose_name='Бүтээгдэхүүний ID')),
                ('attachment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='shop.productattachment')),
            ],
            options={
                'verbose_name': 'Хавсралтын бараа',
                'verbose_name_plural': 'Хавсралтын бараанууд',
                'db_table': 'shop_product_attachment_item',
                'unique_together': {('attachment', 'item_id')},
            },
        ),
        # Буцаах үед item_id хоосон утгатай сэргэнэ, дараа нь restore_item_ids бөглөнө
        migrations.AlterField(
            model_name='productattachment',
            name='item_id',
            field=models.TextField(db_index=True, default='', verbose_name='Бүтээгдэхүүний ID'),
        ),
        migrations.RunPython(copy_item_ids, restore_item_ids),
        migrations.RemoveField(
            model_name='productattachment',
            name='item_id',
        ),
    ]
