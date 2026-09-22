"""
Барааны үлдэгдлийн snapshot хадгалах model
2 цаг тутамд шинэчлэгдэнэ
"""
from django.db import models


class InventorySnapshot(models.Model):
    """Барааны үлдэгдлийн snapshot (materialized view)"""
    
    itemname = models.CharField(max_length=500, db_index=True, verbose_name='Барааны нэр')
    brandname = models.CharField(max_length=200, blank=True, null=True, db_index=True, verbose_name='Брэнд')
    
    # 3 гол агуулахын үлдэгдэл
    tolgoit_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Толгойт')
    jijig_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Жижиг')
    altjin_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Алтжин')
    
    # Нийт үлдэгдэл
    total_qty = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Нийт')
    
    # Сүүлийн өртөг (дундаж)
    avg_unitcost = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name='Дундаж өртөг')
    
    # Сүүлийн огнооууд (informational)
    tolgoit_date = models.DateField(blank=True, null=True, verbose_name='Толгойт огноо')
    jijig_date = models.DateField(blank=True, null=True, verbose_name='Жижиг огноо')
    altjin_date = models.DateField(blank=True, null=True, verbose_name='Алтжин огноо')
    
    # Snapshot мэдээлэл
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Шинэчилсэн огноо')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Үүсгэсэн огноо')
    
    class Meta:
        db_table = 'inventory_snapshot'
        verbose_name = 'Барааны үлдэгдэл (snapshot)'
        verbose_name_plural = 'Барааны үлдэгдэл (snapshots)'
        indexes = [
            models.Index(fields=['itemname']),
            models.Index(fields=['brandname']),
            models.Index(fields=['-total_qty']),  # Нийт үлдэгдлээр эрэмбэлэхэд хурдан
            models.Index(fields=['updated_at']),
        ]
        # Бараа бүр нэг л бичлэгтэй
        constraints = [
            models.UniqueConstraint(fields=['itemname'], name='unique_item_snapshot')
        ]
    
    def __str__(self):
        return f"{self.itemname} - Нийт: {self.total_qty}"
    
    @property
    def has_stock(self):
        """Үлдэгдэлтэй эсэх"""
        return self.total_qty > 0
