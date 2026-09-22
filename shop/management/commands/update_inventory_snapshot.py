"""
Барааны үлдэгдлийн snapshot-ийг шинэчлэх management command

Ашиглах:
    python manage.py update_inventory_snapshot
    
2 цаг тутамд ажиллуулах:
    Windows Task Scheduler эсвэл cron job ашиглах
"""
from django.core.management.base import BaseCommand
from django.db.models import Max
from django.db.models.functions import Cast
from django.db import models, transaction
from datamigration.models import OpenDataInventory
from shop.models_inventory import InventorySnapshot
from decimal import Decimal
from datetime import datetime


class Command(BaseCommand):
    help = 'Барааны үлдэгдлийн snapshot-ийг шинэчлэх (OpenDataInventory-с)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Хуучин өгөгдлийг устгах',
        )

    def handle(self, *args, **options):
        start_time = datetime.now()
        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS(f'Updating inventory snapshot: {start_time}'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))

        # Clear old data if requested
        if options['clear']:
            self.stdout.write('Clearing old snapshots...')
            deleted_count = InventorySnapshot.objects.all().delete()[0]
            self.stdout.write(self.style.WARNING(f'  Deleted {deleted_count} records\n'))

        # 3 гол агуулах
        target_warehouses = {
            'Агуулах Толгойт': 'tolgoit',
            'Агуулах жижиг': 'jijig',
            'Агуулах алтжин': 'altjin'
        }

        # Get all unique items from all warehouses
        all_items = OpenDataInventory.objects.filter(
            warehousename__in=target_warehouses.keys()
        ).values_list('itemname', flat=True).distinct()

        total_items = len(all_items)
        self.stdout.write(f'Found {total_items} total items\n')

        created_count = 0
        updated_count = 0
        skipped_count = 0

        # Process each item to create/update snapshot
        for idx, item_name in enumerate(all_items, 1):
            if not item_name:
                skipped_count += +1
                continue

            if idx % 100 == 0:
                self.stdout.write(f'  Progress: {idx}/{total_items}...')

            # Get latest stock from each warehouse
            warehouse_data = {}
            total_qty = Decimal('0')
            brand_name = None
            total_cost = Decimal('0')
            cost_count = 0

            for warehouse_full, warehouse_key in target_warehouses.items():
                # Find latest date
                latest_info = OpenDataInventory.objects.filter(
                    warehousename=warehouse_full,
                    itemname=item_name
                ).aggregate(
                    latest_date=Max(Cast('documentdate', models.DateField()))
                )

                latest_date = latest_info['latest_date']

                if latest_date:
                    # Get latest record
                    latest_record = OpenDataInventory.objects.annotate(
                        doc_date_cast=Cast('documentdate', models.DateField())
                    ).filter(
                        warehousename=warehouse_full,
                        itemname=item_name,
                        doc_date_cast=latest_date
                    ).first()

                    if latest_record:
                        # Convert TEXT to float/Decimal
                        try:
                            endqty = Decimal(str(latest_record.endqty)) if latest_record.endqty else Decimal('0')
                        except:
                            endqty = Decimal('0')

                        try:
                            unitcost = Decimal(str(latest_record.unitcost)) if latest_record.unitcost else Decimal('0')
                        except:
                            unitcost = Decimal('0')

                        warehouse_data[warehouse_key] = {
                            'qty': endqty,
                            'date': latest_date,
                            'cost': unitcost
                        }

                        total_qty += endqty

                        if unitcost > 0:
                            total_cost += unitcost
                            cost_count += 1

                        # Get brand (from first found)
                        if not brand_name and latest_record.brandname:
                            brand_name = latest_record.brandname
                else:
                    warehouse_data[warehouse_key] = {
                        'qty': Decimal('0'),
                        'date': None,
                        'cost': Decimal('0')
                    }

            # Calculate average cost
            avg_cost = total_cost / cost_count if cost_count > 0 else Decimal('0')

            # Create/update InventorySnapshot
            with transaction.atomic():
                snapshot, created = InventorySnapshot.objects.update_or_create(
                    itemname=item_name,
                    defaults={
                        'brandname': brand_name or '',
                        'tolgoit_qty': warehouse_data.get('tolgoit', {}).get('qty', Decimal('0')),
                        'jijig_qty': warehouse_data.get('jijig', {}).get('qty', Decimal('0')),
                        'altjin_qty': warehouse_data.get('altjin', {}).get('qty', Decimal('0')),
                        'total_qty': total_qty,
                        'avg_unitcost': avg_cost,
                        'tolgoit_date': warehouse_data.get('tolgoit', {}).get('date'),
                        'jijig_date': warehouse_data.get('jijig', {}).get('date'),
                        'altjin_date': warehouse_data.get('altjin', {}).get('date'),
                    }
                )

                if created:
                    created_count += 1
                else:
                    updated_count += 1

        # OpenDataInventory-д ItemName-ээр холбодог тул бараа MSSQL талд нэрээ
        # өөрчлөхөд хуучин нэрийн snapshot мөр эх сурвалжид байхгүй болсон ч
        # Postgres дээр мөнхөд үлдэж, "давхардсан бараа" болж харагддаг байсан.
        # Одоо байгаа нэрсийн жагсаалтад ороогүй хуучин snapshot-уудыг цэвэрлэнэ.
        current_names = {name for name in all_items if name}
        deleted_count = InventorySnapshot.objects.exclude(itemname__in=current_names).delete()[0]

        # Finish
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write(self.style.SUCCESS(f'\n{"="*60}'))
        self.stdout.write(self.style.SUCCESS('Successfully completed!'))
        self.stdout.write(self.style.SUCCESS(f'{"="*60}'))
        self.stdout.write(f'  Created: {created_count}')
        self.stdout.write(f'  Updated: {updated_count}')
        self.stdout.write(f'  Skipped: {skipped_count}')
        self.stdout.write(f'  Stale removed: {deleted_count}')
        self.stdout.write(f'  Total time: {duration:.2f} seconds')
        self.stdout.write(self.style.SUCCESS(f'{"="*60}\n'))
