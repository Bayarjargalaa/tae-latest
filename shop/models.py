"""
E-commerce shop моделууд
"""
import os
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from datamigration.models import OpenDataItem, OpenDataEmployee

# Барааны үлдэгдлийн snapshot model
from .models_inventory import InventorySnapshot


def product_image_main_path(instance, filename):
    """Үндсэн зургийн нэр автоматаар {item_id}_main.{ext}"""
    ext = filename.split('.')[-1].lower()
    return f'products/{instance.item_id}_main.{ext}'


def product_image_2_path(instance, filename):
    """2-р зургийн нэр автоматаар {item_id}_2.{ext}"""
    ext = filename.split('.')[-1].lower()
    return f'products/{instance.item_id}_2.{ext}'


def product_image_3_path(instance, filename):
    """3-р зургийн нэр автоматаар {item_id}_3.{ext}"""
    ext = filename.split('.')[-1].lower()
    return f'products/{instance.item_id}_3.{ext}'


class UserProfile(models.Model):
    """Хэрэглэгчийн нэмэлт мэдээлэл"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField('Утас', max_length=20, blank=True)
    is_employee = models.BooleanField('Ажилтан эсэх', default=False)
    employee_email = models.EmailField('Ажилтны имэйл', blank=True, null=True)
    distributor_id = models.TextField('Түгээгчийн ID', blank=True, null=True)
    
    class Meta:
        db_table = 'shop_user_profile'
        verbose_name = 'Хэрэглэгчийн профайл'
        verbose_name_plural = 'Хэрэглэгчийн профайлууд'
    
    def __str__(self):
        return f"{self.user.username} - Profile"


class MenuPermission(models.Model):
    """Sidebar цэсийг албан тушаал тус бүрээр харуулах эсэхийг тохируулна.

    ALWAYS_ALL_MENU_POSITIONS-д (жиш: 'Ерөнхий нягтлан') ороогүй албан тушаалд
    opt-in горим ажиллана: зөвхөн энд is_visible=True гэж тодорхой бичсэн цэс л
    харагдана, тохиргоогүй/шинэ цэс default-аар нуугдана.
    """
    position_name = models.CharField('Албан тушаал', max_length=200)
    menu_key = models.CharField('Цэсний түлхүүр', max_length=100)
    is_visible = models.BooleanField('Харуулах эсэх', default=True)

    class Meta:
        db_table = 'shop_menu_permission'
        unique_together = ('position_name', 'menu_key')
        verbose_name = 'Цэсний эрх'
        verbose_name_plural = 'Цэсний эрхүүд'

    def __str__(self):
        return f"{self.position_name} - {self.menu_key} ({'харагдана' if self.is_visible else 'нуугдана'})"


class MenuGroupAssignment(models.Model):
    """Цэс аль бүлэгт харагдахыг менюконфигийн default-аас дарж тохируулна (HTML хуудсаар удирдана)."""
    menu_key = models.CharField('Цэсний түлхүүр', max_length=100, unique=True)
    group_key = models.CharField('Бүлгийн түлхүүр', max_length=100)

    class Meta:
        db_table = 'shop_menu_group_assignment'
        verbose_name = 'Цэсний бүлэглэлт'
        verbose_name_plural = 'Цэсний бүлэглэлтүүд'

    def __str__(self):
        return f"{self.menu_key} -> {self.group_key}"


class Meal(models.Model):
    """Хоолны бүртгэл (Хангамж цэсний доор)"""
    MEAL_TYPE_CHOICES = [
        ('1', '1-р хоол'),
        ('2', '2-р хоол'),
        ('3', 'Хачир'),
    ]
    meal_type = models.CharField('Төрөл', max_length=1, choices=MEAL_TYPE_CHOICES, default='1')
    name = models.CharField('Хоолны нэр', max_length=200)
    description = models.TextField('Тайлбар', blank=True)
    is_active = models.BooleanField('Идэвхтэй', default=True)
    # Идэвхгүй болсон өдөр - үүнээс өмнөх өдрийн бүртгэлд хоол хэвээр харагдана
    deactivated_at = models.DateField('Идэвхгүй болсон огноо', null=True, blank=True)
    created_at = models.DateTimeField('Үүсгэсэн', auto_now_add=True)
    updated_at = models.DateTimeField('Шинэчилсэн', auto_now=True)

    class Meta:
        db_table = 'shop_meal'
        ordering = ['meal_type', 'name']
        verbose_name = 'Хоол'
        verbose_name_plural = 'Хоолны бүртгэл'

    def __str__(self):
        prefix = f"{self.number_display}. " if self.number_display else ""
        return f"{prefix}{self.name} ({self.get_meal_type_display()})"

    @staticmethod
    def visible_on_q(date):
        """Тухайн өдөрт харагдах хоолны нөхцөл (идэвхтэй, эсвэл тэр өдрөөс хойш идэвхгүй болсон)."""
        return models.Q(is_active=True) | models.Q(deactivated_at__gt=date)

    def is_visible_on(self, date):
        return self.is_active or (self.deactivated_at is not None and date < self.deactivated_at)

    @property
    def number_list(self):
        return list(self.numbers.order_by('number').values_list('number', flat=True))

    @property
    def number_display(self):
        return ', '.join(str(n) for n in self.number_list)


class MealNumberAssignment(models.Model):
    """Нэг хоолыг олон дугаарт (өөр өөр 7 хоногт) сонгогдохоор холбоно.

    Жиш: нэг хоолыг 3 болон 8 дугаарт хоёуланд нь өгвөл, 10 өдрийн циклийн 3-р
    БОЛОН 8-р өдөрт (өөрөөр хэлбэл 2 өөр 7 хоногт) хоёуланд нь сонгогдоно.
    """
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='numbers')
    number = models.PositiveIntegerField('Дугаар')

    class Meta:
        db_table = 'shop_meal_number_assignment'
        ordering = ['number']
        verbose_name = 'Хоолны дугаар'
        verbose_name_plural = 'Хоолны дугаарууд'

    def __str__(self):
        return f"{self.meal.name} - {self.number}"


class MealCycleSettings(models.Model):
    """Хоолны 10 ажлын өдрийн (2 долоо хоног) циклийн эхлэх огноо.

    Энэ огноо (ажлын өдөр байх ёстой) Meal.number=1-тэй тохирно. Түүнээс хойш
    ажлын өдрүүдэд 1..10 дугаар дараалан сонгогдож, 10 дахь өдрийн дараа дахин
    1-ээс эхэлнэ. Django admin-аар засварлана.
    """
    anchor_date = models.DateField('Циклийн эхлэх огноо (1-р дугаартай өдөр)')
    effective_from = models.DateField(
        'Хэрэгжиж эхэлсэн огноо', null=True, blank=True,
        help_text='Тохируулахад сонгосон огноо. Үүнээс өмнөх огноонд хоол харагдахгүй.',
    )

    class Meta:
        db_table = 'shop_meal_cycle_settings'
        verbose_name = 'Хоолны циклийн тохиргоо'
        verbose_name_plural = 'Хоолны циклийн тохиргоо'

    def __str__(self):
        return f"Цикл эхлэх огноо: {self.anchor_date}"

    @classmethod
    def get_anchor_date(cls):
        """Тохиргоо байхгүй бол энэ долоо хоногийн Даваагаар нэг удаа тогтоож хадгална.

        Санамж: анкор огноог тооцоод хадгалахгүй бол долоо хоног бүр "өнөөдрийн 7
        хоногийн Даваа"-гаар дахин тооцоологдож, циклийн тоолол хэзээ ч урагшлахгүй
        байх алдаа гарна - тиймээс эхний хандалт дээр DB-д тогтмол хадгална.
        """
        setting = cls.objects.first()
        if setting:
            return setting.anchor_date
        today = date.today()
        default_anchor = today - timedelta(days=today.weekday())
        setting = cls.objects.create(anchor_date=default_anchor)
        return setting.anchor_date

    @classmethod
    def get_effective_from(cls):
        setting = cls.objects.first()
        return setting.effective_from if setting else None

    @classmethod
    def set_number_for_date(cls, target_date, number):
        """Сонгосон огноог өгсөн дугаартай (1-10) тохируулж, циклийн анкор огноог
        дахин тооцоолж хадгална. Ингэснээр тэр өдрөөс хойшхи бүх хугацаанд шинэ
        дараалал (тухайн өдрөөс цааш ажлын өдөр бүрт дараагийн дугаар) үргэлжилнэ.
        Сонгосон огноог effective_from болгож хадгалснаар түүнээс өмнөх огноонд
        хоол харагдахгүй болно.
        """
        target_ordinal = _workday_ordinal(target_date)
        anchor_ordinal = target_ordinal - (number - 1)
        weeks, day_in_week = divmod(anchor_ordinal, 5)
        anchor_date = _WEEKDAY_REFERENCE_MONDAY + timedelta(weeks=weeks, days=day_in_week)

        setting = cls.objects.first()
        if setting:
            setting.anchor_date = anchor_date
            setting.effective_from = target_date
            setting.save()
        else:
            setting = cls.objects.create(anchor_date=anchor_date, effective_from=target_date)
        return setting


# 2024-01-01 нь Даваа гараг тул ажлын өдрийн дугаарлалтын харьцангуй тооцоололд
# лавлагаа цэг болгон ашиглана (өөрөө анкор огноо биш).
_WEEKDAY_REFERENCE_MONDAY = date(2024, 1, 1)


def _workday_ordinal(target_date):
    """target_date хүртэлх (харьцангуй) ажлын өдрийн эрэмбийн дугаар."""
    delta_days = (target_date - _WEEKDAY_REFERENCE_MONDAY).days
    weeks, remainder = divmod(delta_days, 7)
    return weeks * 5 + min(remainder, 5)


def get_menu_number_for_date(target_date, anchor_date=None):
    """Өгсөн огноонд харгалзах хоолны дугаарыг (1-10) буцаана.

    Амралтын өдөр (Бямба/Ням) эсвэл циклийн тохиргоонд сонгосон "хэрэгжиж эхэлсэн
    огноо"-ноос өмнөх огноо бол None буцаана (тухайн үед хоол товлогдоогүй).
    """
    if target_date.weekday() >= 5:
        return None

    effective_from = MealCycleSettings.get_effective_from()
    if effective_from and target_date < effective_from:
        return None

    if anchor_date is None:
        anchor_date = MealCycleSettings.get_anchor_date()
    diff = _workday_ordinal(target_date) - _workday_ordinal(anchor_date)
    return (diff % 10) + 1


class MealAttendance(models.Model):
    """Тухайн өдөр хоол идэх хүмүүсийн бүртгэл (огноогоор хоолны дугаар автоматаар тодорхойлогдоно)."""
    date = models.DateField('Огноо', unique=True)
    change_comment = models.TextField('Өөрчлөлтийн тайлбар', blank=True)
    ingredients_changed = models.BooleanField('Орц стандарт жораас өөрчлөгдсөн эсэх', default=False)
    created_at = models.DateTimeField('Үүсгэсэн', auto_now_add=True)
    updated_at = models.DateTimeField('Шинэчилсэн', auto_now=True)

    class Meta:
        db_table = 'shop_meal_attendance'
        ordering = ['-date']
        verbose_name = 'Хоол идэх бүртгэл'
        verbose_name_plural = 'Хоол идэх бүртгэлүүд'

    def __str__(self):
        return f"{self.date} ({self.names.count()} хүн)"

    @property
    def menu_number(self):
        return get_menu_number_for_date(self.date)

    @property
    def scheduled_meals(self):
        """Циклийн дугаараар товлогдсон хоолнууд (солилтгүй)."""
        number = self.menu_number
        if not number:
            return Meal.objects.none()
        return (
            Meal.objects.filter(Meal.visible_on_q(self.date), numbers__number=number)
            .prefetch_related('ingredients').distinct()
        )

    # Товлоогүй өдөр ч "Хоол солих"-оор сонгож нэмэх боломжтой байлгах хоолны төрөл (хачир)
    ALWAYS_SLOT_MEAL_TYPES = ('3',)

    @staticmethod
    def slot_key(original=None, meal_type=None):
        """Солилтын түлхүүр: товлосон хоолны id, товлоогүй төрөлд 'type-<төрөл>'."""
        return str(original.pk) if original else f'type-{meal_type}'

    def meal_slots(self, swaps=None):
        """Тухайн өдрийн хоолны байрууд: [{key, meal_type, original (товлосон, эсвэл None), meal (бодит)}].
        "Хоол солих"-оор сольсон бол meal нь сольсон хоол; ALWAYS_SLOT_MEAL_TYPES-ийн товлоогүй төрөлд
        original=None, сонгоогүй бол meal=None. swaps: {key: Meal} - өгөөгүй бол хадгалагдсан солилтоор."""
        if swaps is None:
            swaps = {
                self.slot_key(s.original_meal, s.meal.meal_type): s.meal for s in self.swaps.all()
            } if self.pk else {}
        scheduled = list(self.scheduled_meals)
        slots = []
        for m in scheduled:
            key = self.slot_key(m)
            slots.append({'key': key, 'meal_type': m.meal_type, 'type_label': m.get_meal_type_display(),
                          'original': m, 'meal': swaps.get(key, m)})
        present = {m.meal_type for m in scheduled}
        for meal_type in self.ALWAYS_SLOT_MEAL_TYPES:
            if meal_type not in present:
                key = self.slot_key(meal_type=meal_type)
                slots.append({'key': key, 'meal_type': meal_type, 'type_label': dict(Meal.MEAL_TYPE_CHOICES)[meal_type],
                              'original': None, 'meal': swaps.get(key)})
        slots.sort(key=lambda s: s['meal_type'])
        return slots

    @property
    def meals(self):
        """Тухайн өдрийн бодит хоолнууд (сольсон хоол товлосныхоо байранд) - нэгтгэл, орцонд үүгээр тооцно."""
        return [s['meal'] for s in self.meal_slots() if s['meal']]

    def ingredients_for_meal(self, meal):
        """Тухайн өдөрт хадгалагдсан орцны хувилбар (байхгүй бол стандарт жор)."""
        overrides = self.ingredient_overrides.filter(meal=meal) if self.pk else MealAttendanceIngredient.objects.none()
        if overrides.exists():
            return overrides
        return meal.ingredients.all()


class MealAttendanceIngredient(models.Model):
    """Тухайн өдрийн бодит орц - стандарт жороос (MealIngredient) хазайсан тохиолдолд
    тухайн өдрийн бүртгэлд дангаар нь хадгална, стандарт жорт нөлөөлөхгүй."""
    attendance = models.ForeignKey(MealAttendance, on_delete=models.CASCADE, related_name='ingredient_overrides')
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='attendance_overrides')
    item_id = models.CharField('Орцын барааны код', max_length=50)
    quantity = models.DecimalField('Хэмжээ', max_digits=12, decimal_places=3, null=True, blank=True)
    unit = models.CharField('Нэгж', max_length=50, blank=True)

    class Meta:
        db_table = 'shop_meal_attendance_ingredient'
        verbose_name = 'Өдрийн бодит орц'
        verbose_name_plural = 'Өдрийн бодит орцууд'

    @property
    def item(self):
        return OpenDataItem.objects.filter(pk=self.item_id).first()

    def __str__(self):
        return f"{self.attendance.date} - {self.meal.name} - {self.item_id}"


class MealAttendanceSwap(models.Model):
    """Тухайн өдөр товлосон хоолыг (1-р/2-р хоол, хачир) өөр хоолоор сольсон бүртгэл. original_meal хоосон бол
    товлоогүй төрлийн (хачир) хоолыг нэмсэн."""
    attendance = models.ForeignKey(MealAttendance, on_delete=models.CASCADE, related_name='swaps')
    original_meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='+', verbose_name='Товлосон хоол',
                                      null=True, blank=True)
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='attendance_swaps', verbose_name='Сольсон хоол')

    class Meta:
        db_table = 'shop_meal_attendance_swap'
        constraints = [
            models.UniqueConstraint(fields=['attendance', 'original_meal'], name='uniq_meal_attendance_swap'),
        ]
        verbose_name = 'Хоол солилт'
        verbose_name_plural = 'Хоол солилтууд'

    def __str__(self):
        original = self.original_meal.name if self.original_meal else 'товлоогүй'
        return f"{self.attendance.date}: {original} -> {self.meal.name}"


class MealAttendanceName(models.Model):
    """MealAttendance-д бүртгэгдсэн нэг хүний нэр."""
    attendance = models.ForeignKey(MealAttendance, on_delete=models.CASCADE, related_name='names')
    name = models.CharField('Нэр', max_length=200)
    order = models.PositiveIntegerField('Дараалал', default=0)

    class Meta:
        db_table = 'shop_meal_attendance_name'
        ordering = ['order', 'id']
        verbose_name = 'Хоол идэх хүний нэр'
        verbose_name_plural = 'Хоол идэх хүмүүсийн нэрс'

    def __str__(self):
        return self.name


class MealIngredient(models.Model):
    """Хоолны орц - OpenDataItem-ийн 1502-р эхэлсэн кодтой бараанаас сонгоно.

    OpenDataItem нь managed=False, PK constraint-гүй MSSQL view тул жинхэнэ
    ForeignKey ашиглах боломжгүй - зөвхөн код (id)-ийг текстээр хадгална.
    """
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='ingredients', verbose_name='Хоол')
    item_id = models.CharField('Орцын барааны код', max_length=50)
    quantity = models.DecimalField('Хэмжээ', max_digits=12, decimal_places=3, null=True, blank=True)
    unit = models.CharField('Нэгж', max_length=50, blank=True)

    class Meta:
        db_table = 'shop_meal_ingredient'
        verbose_name = 'Хоолны орц'
        verbose_name_plural = 'Хоолны орцууд'

    @property
    def item(self):
        return OpenDataItem.objects.filter(pk=self.item_id).first()

    def __str__(self):
        return f"{self.meal.name} - {self.item_id}"


class ProductExtension(models.Model):
    """OpenDataItem-ийн нэмэлт мэдээлэл (зураг, монгол нэр гэх мэт)"""
    item_id = models.TextField('Бүтээгдэхүүний ID', primary_key=True, unique=True)
    
    # Нэмэлт баганууд
    name_mn = models.CharField('Монгол нэр', max_length=500, blank=True)
    country_of_origin = models.CharField('Үйлдвэрлэсэн улс', max_length=100, blank=True)
    qty_per_box = models.IntegerField('Хайрцаг дахь тоо', null=True, blank=True)
    supplier = models.CharField('Нийлүүллэгч', max_length=200, blank=True)
    
    # Зургийн талбарууд
    image_main = models.ImageField('Үндсэн зураг', upload_to=product_image_main_path, blank=True, null=True)
    image_2 = models.ImageField('Зураг 2', upload_to=product_image_2_path, blank=True, null=True)
    image_3 = models.ImageField('Зураг 3', upload_to=product_image_3_path, blank=True, null=True)
    
    # Огноо
    created_at = models.DateTimeField('Үүсгэсэн', auto_now_add=True)
    updated_at = models.DateTimeField('Шинэчилсэн', auto_now=True)
    
    class Meta:
        db_table = 'shop_product_extension'
        verbose_name = 'Бүтээгдэхүүний нэмэлт мэдээлэл'
        verbose_name_plural = 'Бүтээгдэхүүний нэмэлт мэдээлэл'
    
    def __str__(self):
        return f"{self.item_id} - Extension"
    
    @property
    def item(self):
        """OpenDataItem холбох"""
        try:
            return OpenDataItem.objects.get(id=self.item_id)
        except OpenDataItem.DoesNotExist:
            return None
    
    def get_image_url(self, image_type='main'):
        """
        Зургийн URL авах (fallback логиктой)
        1. Database дээр байвал тэрийг ашиглах
        2. Байхгүй бол {item_id}.jpg/png/jpeg хайх
        3. Олдохгүй бол placeholder
        """
        # Database дээр байгаа зураг
        if image_type == 'main' and self.image_main:
            return self.image_main.url
        elif image_type == '2' and self.image_2:
            return self.image_2.url
        elif image_type == '3' and self.image_3:
            return self.image_3.url
        
        # Fallback: {item_id}.ext хайх
        extensions = ['jpg', 'jpeg', 'png', 'webp', 'JPG', 'JPEG', 'PNG', 'WEBP']
        for ext in extensions:
            filename = f'{self.item_id}.{ext}'
            filepath = os.path.join(settings.MEDIA_ROOT, 'products', filename)
            
            if os.path.exists(filepath):
                return f'{settings.MEDIA_URL}products/{filename}'
        
        # Placeholder зураг
        return f'{settings.MEDIA_URL}placeholder.svg'
    
    @property
    def image_url(self):
        """Үндсэн зургийн URL (shortcut)"""
        return self.get_image_url('main')


class AttendanceRawLog(models.Model):
    """Хурууны хээ/царай таних төхөөрөмжөөс татсан түүхий ирцийн бүртгэл (нэг тэмдэглэл = нэг цохолт)"""
    device_user_id = models.CharField('Төхөөрөмжийн хэрэглэгчийн ID', max_length=50, db_index=True)
    timestamp = models.DateTimeField('Цаг тэмдэглэсэн огноо')
    status = models.IntegerField('Төхөөрөмжийн статус', blank=True, null=True)
    synced_at = models.DateTimeField('Татсан огноо', auto_now_add=True)

    class Meta:
        db_table = 'shop_attendance_raw_log'
        unique_together = ('device_user_id', 'timestamp')
        ordering = ['-timestamp']
        verbose_name = 'Ирцийн түүхий бүртгэл'
        verbose_name_plural = 'Ирцийн түүхий бүртгэлүүд'

    def __str__(self):
        return f"{self.device_user_id} - {self.timestamp}"


class AttendanceRecord(models.Model):
    """Ажилтан, өдөр тус бүрээр тооцоолсон/гараар засварлаж хадгалсан цаг бүртгэлийн мөр.

    Цаг бүртгэлийн тооцоо хуудсан дээр 'Хадгалах' дарахад энд upsert хийгдэнэ.
    Дараа нь тухайн (ажилтны код, огноо) хослолыг харуулахдаа төхөөрөмжийн
    түүхий өгөгдлөөс дахин тооцоолохын оронд энд хадгалсан утгыг харуулна.
    """
    employee_code = models.CharField('Ажилтны код', max_length=50, db_index=True)
    device_user_id = models.CharField('Төхөөрөмжийн хэрэглэгчийн ID', max_length=50, blank=True)
    name = models.CharField('Нэр', max_length=200)
    date = models.DateField('Огноо')
    weekday = models.CharField('Гариг', max_length=20, blank=True)
    arrived_time = models.CharField('Ирсэн цаг', max_length=5, blank=True)
    left_time = models.CharField('Тарсан цаг', max_length=5, blank=True)
    late_1_10 = models.PositiveIntegerField('1-10 минут', default=0)
    late_11_20 = models.PositiveIntegerField('11-20 минут', default=0)
    late_20_plus = models.PositiveIntegerField('20-с дээш минут', default=0)
    total_late_minutes = models.PositiveIntegerField('Нийт хоцорсон минут', default=0)
    customer_name = models.CharField('Харилцагчийн нэр', max_length=1000, blank=True)
    # Тухайн өдөр өөр албан тушаалд шилжин ажилласан бол (жиш: харуул туслахаар) тэр албан тушаал - хоцролт,
    # хоног бүртгэлийг түүгээр тооцно. Хоосон бол ажилтны үндсэн албан тушаал (OpenDataEmployee.positionname)
    position_name = models.CharField('Албан тушаал (тухайн өдөр)', max_length=200, blank=True)
    # True бол тухайн өдөр үндсэн мөрөөс гадна өөр албан тушаалыг хавсарч ажилласан нэмэлт мөр (гараар нэмсэн,
    # төхөөрөмжийн бүртгэлгүй). Нэг өдөрт үндсэн мөр ганц, нэмэлт мөр албан тушаал бүрт нэг байна
    is_additional = models.BooleanField('Хавсарсан албан тушаалын мөр', default=False)
    # True бол энэ (ажилтан, огноо)-ны мөрийг хүснэгтээс нууна - төхөөрөмжийн түүхий бүртгэлээс автоматаар
    # үүсэх мөрийг ч мөн (түүхий өгөгдлийг устгахгүйгээр) хасна. Энэ бичлэгийг устгавал мөр сэргэнэ.
    is_deleted = models.BooleanField('Устгасан', default=False)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_attendance_record'
        constraints = [
            models.UniqueConstraint(
                fields=['employee_code', 'date'], condition=models.Q(is_additional=False),
                name='unique_attendance_primary_row',
            ),
            models.UniqueConstraint(
                fields=['employee_code', 'date', 'position_name'], condition=models.Q(is_additional=True),
                name='unique_attendance_additional_row',
            ),
        ]
        ordering = ['-date', 'name']
        verbose_name = 'Цаг бүртгэлийн мөр'
        verbose_name_plural = 'Цаг бүртгэлийн мөрүүд'

    def __str__(self):
        return f"{self.name} - {self.date}"


class MerchandiserVisitLog(models.Model):
    """Түгээлтийн (distribution) программаас экспортолсон 'Бараа өрөлтийн жагсаалт' (Document.xlsx)-с
    уншиж хадгалсан худалдааны төлөөлөгч/мерчандайзерийн зочилсон (зураг илгээсэн) түүхий бүртгэл.

    Мерчандайзер нар хурууны хээ таних төхөөрөмж ашигладаггүй тул тэдний ирц/явцыг
    зочилсон харилцагч дээр зураг илгээсэн Үүссэн/Зассан огноогоор орлуулж тооцоолно.
    """
    document_number = models.CharField('Баримтын дугаар', max_length=50, db_index=True)
    employee_code = models.CharField('Мерчандайзерийн код', max_length=50, db_index=True)
    employee_name = models.CharField('Мерчандайзерийн нэр', max_length=200, blank=True)
    customer_name = models.CharField('Харилцагчийн нэр', max_length=500, blank=True)
    timestamp = models.DateTimeField('Огноо/цаг')
    source_column = models.CharField('Эх сурвалж багана', max_length=20)  # 'created' эсвэл 'edited'
    synced_at = models.DateTimeField('Импортолсон огноо', auto_now_add=True)

    class Meta:
        db_table = 'shop_merchandiser_visit_log'
        unique_together = ('document_number', 'source_column')
        ordering = ['-timestamp']
        verbose_name = 'Мерчандайзерийн зочилсон түүхий бүртгэл'
        verbose_name_plural = 'Мерчандайзерийн зочилсон түүхий бүртгэлүүд'

    def __str__(self):
        return f"{self.employee_code} - {self.timestamp}"


class AttendancePositionRule(models.Model):
    """Албан тушаал тус бүрийн ажил эхлэх цагийн дүрэм (Цаг бүртгэлийн тооцоонд ашиглана).

    start_time тодорхойлогдсон бол: ирсэн цаг тэр цагаас хойш байвал зөрүүг хоцролтоор тооцно.
    start_time хоосон (NULL) бол: 'ирсэн цагаас хойш 8 цаг ажиллах ёстой' дүрэм хэрэгжинэ -
    12:00-13:00 цайны цагийг оруулан (тарсан цаг - ирсэн цаг) < 9 цаг бол дутсан минутыг хоцролтоор тооцно.
    """
    SCHEDULE_WEEKDAYS = 'weekdays'
    SCHEDULE_SATURDAY = 'saturday'
    SCHEDULE_SHIFT = 'shift'
    SCHEDULE_CHOICES = [
        (SCHEDULE_WEEKDAYS, 'Бямбад ажилладаггүй'),
        (SCHEDULE_SATURDAY, 'Бямбад ажилладаг'),
        (SCHEDULE_SHIFT, 'Ээлжийн'),
    ]

    position_name = models.CharField('Албан тушаал', max_length=200, unique=True)
    start_time = models.TimeField('Ажил эхлэх цаг', null=True, blank=True)
    # Хоног бүртгэлд ажиллавал зохих хоногийг тодорхойлно: ажлын өдрүүд (Да-Ба), ажлын өдрүүд + Бямба,
    # эсвэл ээлжийн (ажилтан бүрт гараар оруулна)
    schedule_type = models.CharField('Ажлын горим', max_length=20, choices=SCHEDULE_CHOICES, default=SCHEDULE_WEEKDAYS)
    # Хоног бүртгэл зэрэг жагсаалтад албан тушаалыг харуулах дараалал (бага нь эхэнд, хоосон бол төгсгөлд)
    sort_order = models.PositiveIntegerField('Эрэмбэ', null=True, blank=True)
    # Цаг бүртгүүлдэггүй албан тушаал (Ерөнхий захирал гэх мэт): Хоног бүртгэлд ажилласан хоногийг
    # цаг бүртгэлээс биш, ажиллавал зохих хоногоор нь бөглөнө
    worked_equals_required = models.BooleanField('Ажилласан хоног = ажиллавал зохих хоног', default=False)
    # Цалин бодолтод тухайн албан тушаалын ажилтанд унааны мөнгө бодохгүй (Имарт худалдагч гэх мэт)
    no_transport = models.BooleanField('Унааны мөнгө бодохгүй', default=False)
    # Хоолны мөнгө (өдөрт) - хоосон бол PayrollSetting-ийн анхдагч; ажилтнаар (EmployeePayProfile) дарж бичиж болно
    meal_allowance_per_day = models.DecimalField('Хоолны мөнгө (өдөрт, ₮)', max_digits=10, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField('Шинэчилсэн огноо', auto_now=True)

    class Meta:
        db_table = 'shop_attendance_position_rule'
        ordering = ['position_name']
        verbose_name = 'Албан тушаалын ажлын цагийн дүрэм'
        verbose_name_plural = 'Албан тушаалын ажлын цагийн дүрмүүд'

    def __str__(self):
        return f"{self.position_name} - {self.start_time or '8 цагийн дүрэм'}"


class EmployeeFingerprint(models.Model):
    """Ажилтны хурууны хээ таних төхөөрөмж дээрх код (өмнө нь data/users.xlsx файлд хадгалагддаг байсныг орлоно).

    Цаг бүртгэлийн тооцоонд төхөөрөмжийн түүхий бүртгэлийг (AttendanceRawLog.device_user_id)
    ажилтантай (employee_code = OpenDataEmployee.id) холбоход ашиглана.
    """
    employee_code = models.CharField('Ажилтны код', max_length=50, unique=True, db_index=True)
    device_user_id = models.CharField('Төхөөрөмжийн код', max_length=50, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_employee_fingerprint'
        ordering = ['employee_code']
        verbose_name = 'Ажилтны хурууны мэдээлэл'
        verbose_name_plural = 'Ажилтны хурууны мэдээлэл'
        constraints = [
            # Нэг хурууны код хоёр өөр ажилтанд зэрэг оноогдож болохгүй (нэг код = нэг бодит хүн
            # төхөөрөмж дээр) - хоосон утгыг (device_user_id='') хязгаарлахгүй
            models.UniqueConstraint(
                fields=['device_user_id'],
                condition=~models.Q(device_user_id=''),
                name='unique_nonblank_device_user_id',
            ),
        ]

    def __str__(self):
        return f"{self.employee_code} -> {self.device_user_id}"


class OrganizationHoliday(models.Model):
    """Байгууллагаас амралтын өдөр гэж зарласан өдөр - Хоног бүртгэлийн ажиллавал зохих хоногоос хасагдана."""
    date = models.DateField('Огноо', unique=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_organization_holiday'
        ordering = ['date']
        verbose_name = 'Байгууллагын амралтын өдөр'
        verbose_name_plural = 'Байгууллагын амралтын өдрүүд'

    def __str__(self):
        return str(self.date)


class TimesheetEntry(models.Model):
    """Хоног бүртгэлд ажилтан тус бүрийн сарын гараар оруулах утгууд (ээлжийн амралт, чөлөө гэх мэт).

    Ажилласан хоног/цаг, хоцролт зэргийг Цаг бүртгэлээс тооцоолдог. Зөвхөн 'худалдагч' агуулсан албан
    тушаалд ажиллавал зохих / ажилласан хоногийг гараар дарж бичиж болно (хоосон бол тооцоолсноор).
    """
    employee_code = models.CharField('Ажилтны код', max_length=50, db_index=True)
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    required_days = models.DecimalField('Ажиллавал зохих хоног (гараар)', max_digits=5, decimal_places=1, null=True, blank=True)
    worked_days = models.DecimalField('Ажилласан хоног (гараар)', max_digits=5, decimal_places=1, null=True, blank=True)
    # Бямбад ажилласан хоногийг бүх ажилтанд (ээлжийнхээс бусад) гараар засч болно (хоосон бол цаг бүртгэлээр)
    saturday_days = models.DecimalField('Бямбад ажилласан (гараар)', max_digits=5, decimal_places=1, null=True, blank=True)
    leave_days = models.DecimalField('Ээлжийн амралт (хоног)', max_digits=5, decimal_places=1, default=0)
    excused_days = models.DecimalField('Чөлөөтэй хоног', max_digits=5, decimal_places=1, default=0)
    excused_hours = models.DecimalField('Цагийн чөлөө', max_digits=6, decimal_places=1, default=0)
    # Хоосон бол ажилтны үндсэн албан тушаалын мөр; өөр албан тушаалд шилжин ажилласан өдрүүдийн
    # (AttendanceRecord.position_name) тусдаа мөрийн гар утга бол тэр албан тушаалын нэр
    position_name = models.CharField('Албан тушаал (шилжин ажилласан)', max_length=200, blank=True, default='')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_timesheet_entry'
        unique_together = ('employee_code', 'year', 'month', 'position_name')
        verbose_name = 'Хоног бүртгэлийн гар утга'
        verbose_name_plural = 'Хоног бүртгэлийн гар утгууд'

    def __str__(self):
        return f"{self.employee_code} {self.year}-{self.month:02d}"


class TimesheetSetting(models.Model):
    """Хоног бүртгэлийн нэгдсэн тохиргоо (ганц мөр, pk=1): хоцролтын багц бүрийн минут тутмын суутгал (₮)."""
    late_rate_1_10 = models.DecimalField('1-10 минутын хоцролт (₮/минут)', max_digits=10, decimal_places=2, default=0)
    late_rate_11_20 = models.DecimalField('11-20 минутын хоцролт (₮/минут)', max_digits=10, decimal_places=2, default=0)
    late_rate_21_30 = models.DecimalField('21-30 минутын хоцролт (₮/минут)', max_digits=10, decimal_places=2, default=0)
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_timesheet_setting'
        verbose_name = 'Хоног бүртгэлийн тохиргоо'
        verbose_name_plural = 'Хоног бүртгэлийн тохиргоо'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


def _money_field(label):
    return models.DecimalField(label, max_digits=14, decimal_places=2, default=0)


class EmployeePayProfile(models.Model):
    """Ажилтны цалингийн тогтмол мэдээлэл: олгох хэлбэр (карт/бэлэн/хосолсон), бэлэн үндсэн цалин, нэг гарын мөнгө.

    Картын үндсэн цалин, НДШ код, удаан жил, эрсдэлийн сан, хуримтлалыг ажилтны мэдээллээс (OpenDataEmployee) авна.

    Карт - зөвхөн Картын цалин бодолтод (НДШ, ХХОАТ суутгана), Бэлэн - зөвхөн Бэлэн цалин бодолтод
    (татварын суутгалгүй), Хосолсон - хоёуланд нь өөр өөрийн үндсэн цалингаар харагдана.
    """
    PAY_CARD = 'card'
    PAY_CASH = 'cash'
    PAY_MIXED = 'mixed'
    PAY_CHOICES = [
        (PAY_CARD, 'Карт'),
        (PAY_CASH, 'Бэлэн'),
        (PAY_MIXED, 'Хосолсон'),
    ]

    employee_code = models.CharField('Ажилтны код', max_length=50, unique=True)
    pay_type = models.CharField('Олгох хэлбэр', max_length=10, choices=PAY_CHOICES, blank=True)
    cash_base_salary = _money_field('Бэлэн үндсэн цалин')
    # Ээлжийн ажилтанд: цалин = нэг гарын мөнгө x ажилласан хоног (үндсэн цалингийн оронд)
    card_shift_pay = _money_field('Картын нэг гарын мөнгө')
    cash_shift_pay = _money_field('Бэлэн нэг гарын мөнгө')
    # Бодогдсон Бямбад ажилласан нэмэгдлийн хэдэн хувийг олгох (100 = бүтэн, 50 = тал)
    saturday_bonus_percent = models.DecimalField('Бямбын нэмэгдэл (%)', max_digits=5, decimal_places=2, default=Decimal('50'))
    # Бямба гарагийг ажиллавал зохих болон ажилласан хоногт оруулах эсэх (Бямбад ажилласан хоног, Бямбын
    # нэмэгдэлд үргэлж тоологдоно). None бол албан тушаалын ажлын горимоор (Бямбад ажилладаг -> оруулна)
    saturday_in_worked_days = models.BooleanField('Бямбыг ажилласан хоногт оруулах', null=True, blank=True, default=None)
    # Хоосон бол PayrollSetting-ийн анхдагч хувь хэрэглэгдэнэ (тэтгэвэрт гарсан ажилтан гэх мэт өөр хувьтай үед бөглөнө)
    ndsh_employee_rate = models.DecimalField('НДШ ажилтан (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    ndsh_employer_rate = models.DecimalField('НДШ байгууллага (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    # Бэлэн цалин шилжүүлэх данс (банкны нэртэй чөлөөт бичвэр) - ажилтны мэдээлэл дэх данс нь картын цалингийнх тул тусад нь
    cash_bank_account = models.CharField('Бэлэн цалингийн данс', max_length=100, blank=True)
    # Хоолны мөнгө олгох эсэх - False бол олгохгүй (хоолны нэрсийн бүртгэлд бичигдэж, идсэн тоонд нь орно)
    eats_meals = models.BooleanField('Хоолны мөнгө олгох', default=True)
    # Хоолны мөнгө (өдөрт) - хоосон бол албан тушаалын (AttendancePositionRule), тэр нь хоосон бол
    # PayrollSetting.meal_allowance_per_day; 0 бол олгохгүй
    meal_allowance_per_day = models.DecimalField('Хоолны мөнгө (өдөрт, ₮)', max_digits=10, decimal_places=2, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_employee_pay_profile'
        verbose_name = 'Ажилтны цалингийн мэдээлэл'
        verbose_name_plural = 'Ажилчдын цалингийн мэдээлэл'

    def __str__(self):
        return f"{self.employee_code} - {self.get_pay_type_display() or '-'}"


class MealAllowanceEntry(models.Model):
    """Хоолны мөнгөний сарын гар засвар (зөвхөн Ерөнхий нягтлан): ажилласан / идсэн / идээгүй өдөр.
    Хоосон (NULL) талбарт автомат утга (shop.services.meal_allowance) хэрэглэгдэнэ."""
    employee_code = models.CharField('Ажилтны код', max_length=50)
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    worked_days = models.DecimalField('Ажилласан хоног', max_digits=5, decimal_places=1, null=True, blank=True)
    eaten_days = models.DecimalField('Идсэн өдөр', max_digits=5, decimal_places=1, null=True, blank=True)
    not_eaten_days = models.DecimalField('Идээгүй өдөр', max_digits=5, decimal_places=1, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_meal_allowance_entry'
        unique_together = [('employee_code', 'year', 'month')]
        verbose_name = 'Хоолны мөнгөний гар засвар'
        verbose_name_plural = 'Хоолны мөнгөний гар засварууд'

    def __str__(self):
        return f"{self.employee_code} {self.year}-{self.month:02d}"


class PayrollSetting(models.Model):
    """Цалин бодолтын нэгдсэн тохиргоо (ганц мөр, pk=1) - хуулиар өөрчлөгдөх хувь хэмжээг хуудаснаас засна."""
    ndsh_employee_rate = models.DecimalField('НДШ ажилтан (%)', max_digits=5, decimal_places=2, default=Decimal('11.5'))
    ndsh_employer_rate = models.DecimalField('НДШ байгууллага (%)', max_digits=5, decimal_places=2, default=Decimal('12.5'))
    ndsh_max_base = models.DecimalField('НДШ ногдуулах дээд хэмжээ (₮)', max_digits=14, decimal_places=2, default=Decimal('7920000'))
    pit_rate = models.DecimalField('ХХОАТ (%)', max_digits=5, decimal_places=2, default=Decimal('10'))
    saturday_hours_per_day = models.DecimalField('Бямба гарагийн ажлын цаг', max_digits=4, decimal_places=1, default=Decimal('6'))
    transport_per_day = models.DecimalField('Унааны мөнгө (хоногт, ₮)', max_digits=10, decimal_places=2, default=Decimal('1000'))
    # Хоолны мөнгө: ажилласан ч хоол идээгүй өдөр бүрт олгох дүн (ажилтнаар EmployeePayProfile-д өөрчилж болно)
    meal_allowance_per_day = models.DecimalField('Хоолны мөнгө (өдөрт, ₮)', max_digits=10, decimal_places=2, default=Decimal('0'))
    # Нягтлан албан тушаалд хоолны мөнгө харах, бодох эрх олгох эсэх (Ерөнхий нягтлан хоолны мөнгөний хуудаснаас)
    meal_allowance_accountant_access = models.BooleanField('Нягтланд хоолны мөнгө харах, бодох эрх', default=True)
    # Хэвлэх хуудасны толгой, гарын үсгийн мөр
    company_name = models.CharField('Байгууллагын нэр', max_length=200, blank=True, default='Төгс Амин Эрдэнэ ХХК')
    card_approver = models.CharField('Картын цалин батлах захирал', max_length=100, blank=True, default='Б.Болор-Эрдэнэ')
    cash_approver = models.CharField('Бэлэн цалин батлах захирал', max_length=100, blank=True, default='Б.Очгэрэл')
    prepared_by = models.CharField('Тооцоо гаргасан нягтлан', max_length=100, blank=True, default='О.Баяржаргал')
    # Урьдчилгаа цалин олгох өдөр (хэвлэхэд "2026 ОНЫ 09 САРЫН 20 УРЬДЧИЛГАА ЦАЛИН")
    advance_day = models.PositiveSmallIntegerField('Урьдчилгаа олгох өдөр', default=20)
    # Борлуулалтын нэмэгдлийн нийтлэг тохиргоо (хасагдах суурь %, түгээгчийн шалгуур г.м.) - shop.services.sales_bonus.DEFAULT_SETTINGS
    sales_bonus_settings = models.JSONField('Борлуулалтын нэмэгдлийн тохиргоо', default=dict, blank=True)
    # Хэвлэх баганууд: {'card': {'p1a': [...], ...}, 'cash': {...}} - shop.services.payroll_print-ийг үз
    print_columns = models.JSONField('Хэвлэх баганууд', default=dict, blank=True)
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_payroll_setting'
        verbose_name = 'Цалин бодолтын тохиргоо'
        verbose_name_plural = 'Цалин бодолтын тохиргоо'

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class NdshCodeRate(models.Model):
    """НДШ-ийн код (OpenDataEmployee.InsuredTypeId) тус бүрийн шимтгэлийн хувь - хоосон бол PayrollSetting-ийн анхдагч хувь."""
    code = models.CharField('НДШ-ийн код', max_length=20, unique=True)
    employee_rate = models.DecimalField('НДШ ажилтан (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    employer_rate = models.DecimalField('НДШ байгууллага (%)', max_digits=5, decimal_places=2, null=True, blank=True)
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_ndsh_code_rate'
        ordering = ['code']
        verbose_name = 'НДШ-ийн кодын хувь'
        verbose_name_plural = 'НДШ-ийн кодын хувь'

    def __str__(self):
        return self.code


class PayrollTaxCredit(models.Model):
    """ХХОАТ-ын хөнгөлөлтийн шатлал: сарын цалингаас НДШ хассан дүн income_to хүртэл бол credit_amount хөнгөлнө
    (income_to хоосон = дээд шат). Хуулийн жилийн дүнг 12-т хуваан сарын дүнгээр оруулна."""
    income_to = models.DecimalField('Сарын цалин, НДШ хассан (хүртэл, ₮)', max_digits=14, decimal_places=2, null=True, blank=True)
    credit_amount = models.DecimalField('Хөнгөлөлт (₮)', max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'shop_payroll_tax_credit'
        ordering = [models.F('income_to').asc(nulls_last=True)]
        verbose_name = 'ХХОАТ-ын хөнгөлөлтийн шат'
        verbose_name_plural = 'ХХОАТ-ын хөнгөлөлтийн шатлал'


class PayrollEntry(models.Model):
    """Цалин бодолтын сар бүр гараар оруулах утгууд (карт, бэлэн хуудас тус тусдаа)."""
    SHEET_CARD = 'card'
    SHEET_CASH = 'cash'
    SHEET_CHOICES = [(SHEET_CARD, 'Карт'), (SHEET_CASH, 'Бэлэн')]

    employee_code = models.CharField('Ажилтны код', max_length=50, db_index=True)
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    sheet = models.CharField('Хуудас', max_length=10, choices=SHEET_CHOICES)
    holiday_pay = _money_field('Амралтын мөнгө')
    sales_bonus = _money_field('Нэмэгдэл цалин /Борлуулалт/')
    advance = _money_field('Урьдчилгаа')
    inventory_shortage = _money_field('Тооллогын дутагдал')
    goods_deduction = _money_field('Барааны суутгал')
    phone_fee = _money_field('Ярианы төлбөр')
    fine = _money_field('Торгууль')
    other_deduction = _money_field('Бусад суутгал')
    sick_employer = _money_field('ХЧТА-н мөнгө байгууллага')
    sick_fund = _money_field('ХЧТА-н мөнгө НД-с')
    # Автомат бодолтыг гараар дарж бичих (хоосон/NULL бол автомат, 0 бичвэл 0) - shop.services.payroll.OVERRIDE_FIELDS
    saturday_bonus_override = models.DecimalField('Бямбад ажилласан нэмэгдэл (гараар)', max_digits=14, decimal_places=2, null=True, blank=True)
    transport_override = models.DecimalField('Унааны мөнгө (гараар)', max_digits=14, decimal_places=2, null=True, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_payroll_entry'
        unique_together = ('employee_code', 'year', 'month', 'sheet')
        verbose_name = 'Цалин бодолтын гар утга'
        verbose_name_plural = 'Цалин бодолтын гар утгууд'

    def __str__(self):
        return f"{self.employee_code} {self.year}-{self.month:02d} {self.sheet}"


class PayrollMonthClose(models.Model):
    """Хаагдсан (баталгаажсан) сарын цалин бодолтын хуулбар (snapshot) - карт, бэлэн хуудас тус тусдаа.

    Цалин бодолт нь ажилтны одоогийн мэдээллээр (үндсэн цалин, албан тушаал, идэвхтэй эсэх) үргэлж дахин бодогддог
    тул сарыг хаахад бодогдсон мөрүүдийг ажилтны тухайн үеийн мэдээлэлтэй (хэлтэс, хүйс, төрсөн/ажилд орсон огноо,
    олгох хэлбэр) хамт хадгална. Хаагдсан сарыг цалин бодолт, хувийн мэдээлэл, цалингийн тайланд энэ хуулбараас
    харуулж, засварлахыг хориглоно (дахин нээж болно). shop.services.payroll_snapshot-ийг үз."""
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    sheet = models.CharField('Хуудас', max_length=10, choices=PayrollEntry.SHEET_CHOICES)
    rows = models.JSONField('Бодогдсон мөрүүд', default=list)
    closed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Хаасан хэрэглэгч')
    closed_at = models.DateTimeField('Хаасан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_payroll_month_close'
        unique_together = ('year', 'month', 'sheet')
        verbose_name = 'Хаагдсан сарын цалин'
        verbose_name_plural = 'Хаагдсан сарын цалингууд'

    def __str__(self):
        return f"{self.year}-{self.month:02d} {self.sheet}"


class SalesBonusMember(models.Model):
    """Борлуулалтын нэмэгдэл бодох ажилтан: аль хүснэгтэд (scheme) бодогдох, сувгийн мөрүүд ба тэдгээрийн хувь.

    channels: [{"channel": "Cүлжээ дэлгүүр", "rate": "0.75"}, ...] - сар бүр анхдагчаар энэ мөрүүдээр бодогдоно
    (тухайн сард хувь өөрчилбөл энд ч хадгалагдаж дараагийн сард үйлчилнэ). shop.services.sales_bonus-ийг үз.
    """
    SCHEME_STOREKEEPER = 'storekeeper'
    SCHEME_SALES_REP = 'sales_rep'
    SCHEME_CASH_SELLER = 'cash_seller'
    SCHEME_DISTRIBUTOR = 'distributor'
    SCHEME_ALTJIN_SELLER = 'altjin_seller'
    SCHEME_CHOICES = [
        (SCHEME_STOREKEEPER, 'Нярав'),
        (SCHEME_SALES_REP, 'Худалдааны төлөөлөгч'),
        (SCHEME_CASH_SELLER, 'Борлуулагч'),
        (SCHEME_DISTRIBUTOR, 'Түгээгч'),
        (SCHEME_ALTJIN_SELLER, 'Алтжин худалдагч'),
    ]
    SOURCE_CREDIT = 'credit'
    SOURCE_DELIVERY = 'delivery'
    SOURCE_CHOICES = [
        (SOURCE_CREDIT, 'Авлагын кредит (сувгаар)'),
        (SOURCE_DELIVERY, 'Түгээлт (нийт)'),
    ]

    employee_code = models.CharField('Ажилтны код', max_length=50, unique=True)
    scheme = models.CharField('Нэмэгдлийн хүснэгт', max_length=20, choices=SCHEME_CHOICES)
    channels = models.JSONField('Сувгууд ба хувь', default=list, blank=True)
    # Няравын борлуулалтын суурь: авлагын кредит (сувгаар) эсвэл нийт түгээлт
    source = models.CharField('Борлуулалтын суурь', max_length=10, choices=SOURCE_CHOICES, default=SOURCE_CREDIT)
    is_active = models.BooleanField('Идэвхтэй', default=True)
    sort_order = models.PositiveIntegerField('Дараалал', default=0)
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_sales_bonus_member'
        ordering = ['scheme', 'sort_order', 'employee_code']
        verbose_name = 'Борлуулалтын нэмэгдлийн ажилтан'
        verbose_name_plural = 'Борлуулалтын нэмэгдлийн ажилчид'

    def __str__(self):
        return f'{self.employee_code} ({self.get_scheme_display()})'


class SalesBonusEntry(models.Model):
    """Сарын борлуулалтын нэмэгдлийн бодолт - гараар оруулсан утгууд (inputs) ба бодогдсон дүн.

    inputs: {"lines": [{"channel", "rate", "sales", "returns"}], "deduction_pct", "plan_pct", "inventory",
             "delivery_amount", "criteria": {key: bool}, "solo_days", "helper_days", "adjustment", "note"}
    sales/returns/delivery_amount null бол өгөгдлөөс автоматаар. Хадгалахад card_amount / cash_amount нь
    цалин бодолтын (PayrollEntry.sales_bonus) карт / бэлэн хуудсанд бичигдэнэ.
    """
    employee_code = models.CharField('Ажилтны код', max_length=50, db_index=True)
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    scheme = models.CharField('Нэмэгдлийн хүснэгт', max_length=20, choices=SalesBonusMember.SCHEME_CHOICES)
    inputs = models.JSONField('Оруулсан утгууд', default=dict, blank=True)
    total = _money_field('Борлуулалтын нэмэгдэл')
    card_amount = _money_field('Картад')
    cash_amount = _money_field('Бэлэнд')
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_sales_bonus_entry'
        # Нэг ажилтан нэг сард хэд хэдэн хүснэгтээр бодогдож болно (жиш: ХТ нь няравыг орлосон) - цалин бодолтод нийлбэр
        unique_together = [('employee_code', 'year', 'month', 'scheme')]
        verbose_name = 'Борлуулалтын нэмэгдлийн бодолт'
        verbose_name_plural = 'Борлуулалтын нэмэгдлийн бодолтууд'

    def __str__(self):
        return f'{self.employee_code} {self.year}-{self.month:02d}: {self.total}'


class SalesBonusMonthMember(models.Model):
    """Тухайн сард хүснэгтэд (одоогоор Түгээгч) гараар нэмсэн эсвэл хассан ажилтан. Байнгын гишүүнчлэлийг
    (SalesBonusMember) өөрчлөхгүй - жиш: өөр албан тушаалтай / ажлаас гарсан ажилтан тэр сард түгээлт хийсэн бол
    нэмж, байнгын түгээгч тэр сард түгээлт хийгээгүй бол хасна. shop.services.sales_bonus.month_people-ийг үз."""
    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    scheme = models.CharField('Нэмэгдлийн хүснэгт', max_length=20, choices=SalesBonusMember.SCHEME_CHOICES)
    employee_code = models.CharField('Ажилтны код', max_length=50)
    # False - тэр сард нэмсэн, True - байнгын гишүүнийг тэр сард хассан
    excluded = models.BooleanField('Хассан', default=False)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_sales_bonus_month_member'
        unique_together = [('year', 'month', 'scheme', 'employee_code')]
        verbose_name = 'Сарын нэмэгдлийн ажилтан (нэмсэн/хассан)'
        verbose_name_plural = 'Сарын нэмэгдлийн ажилчид (нэмсэн/хассан)'

    def __str__(self):
        return f"{self.employee_code} {self.year}-{self.month:02d} {self.scheme} {'хассан' if self.excluded else 'нэмсэн'}"


class SalesBonusSubstitute(models.Model):
    """Үндсэн нярав байхгүй өдрүүдэд няравыг орлосон ажилтан ба өдрүүд (сараар). Тэр өдрүүдийн борлуулалт,
    буцаалт бүтнээр орлогчид очно (үндсэн нярав авахгүй). Нэг өдөр зөвхөн нэг орлогчтой - өдрүүд давхцахгүй.
    shop.services.sales_bonus.storekeeper_allocation-ийг үз."""
    MODE_REPLACE = 'replace'
    MODE_CHOICES = [(MODE_REPLACE, 'Орлосон')]

    year = models.PositiveSmallIntegerField('Он')
    month = models.PositiveSmallIntegerField('Сар')
    employee_code = models.CharField('Ажилтны код', max_length=50)
    mode = models.CharField('Хэлбэр', max_length=10, choices=MODE_CHOICES, default=MODE_REPLACE)
    dates = models.JSONField('Өдрүүд', default=list, blank=True)  # ["2026-08-05", ...]
    note = models.CharField('Тайлбар', max_length=200, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_sales_bonus_substitute'
        ordering = ['year', 'month', 'id']
        verbose_name = 'Нярав орлолт'
        verbose_name_plural = 'Нярав орлолтууд'

    def __str__(self):
        return f'{self.year}-{self.month:02d} {self.employee_code} ({self.get_mode_display()}, {len(self.dates)} өдөр)'


class OpenDataSyncLog(models.Model):
    """MSSQL -> PostgreSQL нэг хүснэгт татсан түүх (Өгөгдөл шинэчлэх хуудаснаас / sync_table командаас)."""
    STATUS_RUNNING = 'running'
    STATUS_SUCCESS = 'success'
    STATUS_ERROR = 'error'
    STATUS_CHOICES = [(STATUS_RUNNING, 'Татаж байна'), (STATUS_SUCCESS, 'Амжилттай'), (STATUS_ERROR, 'Алдаа')]

    table_name = models.CharField('Хүснэгт', max_length=128, db_index=True)
    database = models.CharField('MSSQL өгөгдлийн сан', max_length=128, blank=True)
    status = models.CharField('Төлөв', max_length=10, choices=STATUS_CHOICES, default=STATUS_RUNNING)
    rows = models.PositiveIntegerField('Мөрийн тоо', null=True, blank=True)
    seconds = models.FloatField('Хугацаа (сек)', null=True, blank=True)
    message = models.TextField('Мессеж', blank=True)
    started_at = models.DateTimeField('Эхэлсэн', auto_now_add=True)
    finished_at = models.DateTimeField('Дууссан', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Хэрэглэгч')

    class Meta:
        db_table = 'shop_opendata_sync_log'
        ordering = ['-started_at']
        verbose_name = 'Өгөгдөл татсан түүх'
        verbose_name_plural = 'Өгөгдөл татсан түүх'

    def __str__(self):
        return f'{self.table_name} {self.started_at:%Y-%m-%d %H:%M} ({self.get_status_display()})'



class UnloadingEvent(models.Model):
    """Ачаа буулгалт - нэг татан авалт (OpenDataLandedCost.DocumentPkId) бүрийн чингэлэг буулгалт ба ажлын хөлс.
    Оролцсон ажилчид UnloadingWorker-т (хүн бүр өөрийн хөлстэй); гаднаас хөлсөлсөн хүмүүсийг тоо × нэг хүний хөлсөөр."""
    # Дугаар нь он бүр давтагддаг тул татан авалтыг DocumentPkId-аар таниулна
    document_id = models.BigIntegerField('Татан авалтын ID (DocumentPkId)', unique=True)
    document_number = models.CharField('Татан авалтын дугаар', max_length=50)
    document_date = models.DateField('Татан авалтын огноо', null=True, blank=True)
    vendor_name = models.CharField('Илгээгч', max_length=255, blank=True)
    unload_date = models.DateField('Буулгасан огноо', db_index=True)
    outside_count = models.PositiveSmallIntegerField('Гаднаас хөлсөлсөн хүний тоо', default=0)
    outside_fee = models.DecimalField('Гаднаас хөлсөлсөн нэг хүний хөлс', max_digits=14, decimal_places=2, default=0)
    note = models.CharField('Тайлбар', max_length=300, blank=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_unloading_event'
        ordering = ['-unload_date', 'document_number']
        verbose_name = 'Ачаа буулгалт'
        verbose_name_plural = 'Ачаа буулгалтууд'

    def __str__(self):
        return f'{self.document_number} ({self.unload_date})'

    @property
    def outside_amount(self):
        return self.outside_fee * self.outside_count


class UnloadingWorker(models.Model):
    """Ачаа буулгалтад оролцсон ажилтан ба үүрэг."""
    ROLE_CUSTOMS = 'customs'
    ROLE_CHECK = 'check'
    ROLE_RECEIVE = 'receive'
    ROLE_UNLOAD = 'unload'
    ROLE_CHOICES = [
        (ROLE_CUSTOMS, 'Гааль мэдүүлсэн'),
        (ROLE_CHECK, 'Хянаж авсан'),
        (ROLE_RECEIVE, 'Орлого хүлээж авсан'),
        (ROLE_UNLOAD, 'Буулгаж зөөсөн'),
    ]

    event = models.ForeignKey(UnloadingEvent, on_delete=models.CASCADE, related_name='workers')
    employee_code = models.CharField('Ажилтны код', max_length=50, db_index=True)
    role = models.CharField('Үүрэг', max_length=10, choices=ROLE_CHOICES, default=ROLE_UNLOAD)
    fee = models.DecimalField('Ажлын хөлс', max_digits=14, decimal_places=2, default=0)

    class Meta:
        db_table = 'shop_unloading_worker'
        unique_together = [('event', 'employee_code')]
        verbose_name = 'Ачаа буулгасан ажилтан'
        verbose_name_plural = 'Ачаа буулгасан ажилчид'

    def __str__(self):
        return f'{self.event.document_number}: {self.employee_code} ({self.get_role_display()})'


class UnloadingSettings(models.Model):
    """Ачаа буулгалтын анхдагч тохиргоо (ганц мөр): шинэ ачаанд урьдчилан бөглөгдөх хүмүүс, ажлын хөлс."""
    customs_code = models.CharField('Гааль мэдүүлэх ажилтан', max_length=50, blank=True)
    check_code = models.CharField('Хянаж авах ажилтан', max_length=50, blank=True)
    receive_code = models.CharField('Орлого хүлээж авах ажилтан', max_length=50, blank=True)
    key_fee = models.DecimalField('Гааль/хяналт/орлогын хүний хөлс', max_digits=14, decimal_places=2, default=100000)
    worker_fee = models.DecimalField('Бусад ажилтны хөлс', max_digits=14, decimal_places=2, default=60000)
    outside_fee = models.DecimalField('Гаднаас хөлсөлсөн хүний хөлс', max_digits=14, decimal_places=2, default=80000)

    class Meta:
        db_table = 'shop_unloading_settings'
        verbose_name = 'Ачаа буулгалтын тохиргоо'
        verbose_name_plural = 'Ачаа буулгалтын тохиргоо'

    # Анх үүсгэхэд ажилтныг нэрээр нь олж бөглөнө
    DEFAULT_NAMES = {'customs_code': 'Галт', 'check_code': 'Баяржаргал', 'receive_code': 'Энхжаргал'}

    @classmethod
    def load(cls):
        obj = cls.objects.first()
        if obj is None:
            obj = cls()
            for field, name in cls.DEFAULT_NAMES.items():
                emp = (OpenDataEmployee.objects.filter(isreclusion='N', name__istartswith=name).order_by('id').first())
                setattr(obj, field, emp.id if emp else '')
            obj.save()
        return obj

    def role_codes(self):
        return {'customs': self.customs_code, 'check': self.check_code, 'receive': self.receive_code}

    def role_fee(self, role):
        return self.worker_fee if role == 'unload' else self.key_fee


# ---------------------------------------------------------------------------
# Импорт - гадаадаас ирэх ачаа: нэг захиалга = нэг чингэлэг, дотор нь олон нийлүүлэгч
# ---------------------------------------------------------------------------

class ImportShipment(models.Model):
    """Импортын захиалга (нэг чингэлэг). Төлөв нь огноонуудаас тооцоологдоно (services.imports.shipment_steps)."""
    SIZE_CHOICES = [
        ('20', '20ft'), ('20R', '20ft хөргүүртэй'), ('40', '40ft'), ('40HC', '40ft HC'), ('40R', '40ft хөргүүртэй'),
        ('other', 'Бусад'),
    ]

    code = models.CharField('Захиалгын код', max_length=30, unique=True)
    container_size = models.CharField('Чингэлгийн хэмжээ', max_length=10, choices=SIZE_CHOICES, default='40')
    container_no = models.CharField('Чингэлгийн дугаар', max_length=30, blank=True)
    seal_no = models.CharField('Лацны дугаар', max_length=30, blank=True)
    # Тээврийн компани: OpenDataCustomer-оос сонгосон бол carrier_id-тэй, шинээр бичсэн бол зөвхөн нэр
    carrier_id = models.CharField('Тээврийн компанийн код', max_length=50, blank=True)
    carrier_name = models.CharField('Тээврийн компани', max_length=255, blank=True)
    # Далай / Төмөр зам / Ачааны машин / Түүвэр ачаа (services.imports.TRANSPORT_MODES) эсвэл шинээр бичсэн
    transport_mode = models.CharField('Тээвэрлэх хэлбэр', max_length=100, blank=True)
    load_planned = models.DateField('Ачих огноо (төлөвлөсөн)', null=True, blank=True)
    load_actual = models.DateField('Ачигдсан огноо', null=True, blank=True)
    load_place = models.CharField('Ачигдсан газар', max_length=200, blank=True)
    arrival_place = models.CharField('Ирэх газар', max_length=200, blank=True, default='Улаанбаатар')
    arrival_planned = models.DateField('Ирэх огноо (төлөвлөсөн)', null=True, blank=True)
    arrival_actual = models.DateField('Ирсэн огноо', null=True, blank=True)
    note = models.CharField('Тайлбар', max_length=500, blank=True)
    # Гаалийн тооцоо: {валют: 1 нэгж = хэдэн төгрөг} (Монголбанкны ханш), тээврийг гаалийн үнэд оруулах эсэх
    customs_rates = models.JSONField('Гаалийн ханш', default=dict, blank=True)
    customs_include_freight = models.BooleanField('Тээврийн зардлыг гаалийн үнэд оруулах', default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_import_shipment'
        ordering = ['-created_at']
        verbose_name = 'Импортын захиалга'
        verbose_name_plural = 'Импортын захиалгууд'

    def __str__(self):
        return self.code


class ImportSupplierOrder(models.Model):
    """Чингэлэг доторх нэг нийлүүлэгчийн захиалга: Order number -> Order confirm -> Proforma -> Commercial invoice."""
    PAY_NONE = 'none'
    PAY_PARTIAL = 'partial'
    PAY_FULL = 'full'
    PAY_CHOICES = [(PAY_NONE, 'Төлөөгүй'), (PAY_PARTIAL, 'Урьдчилгаа төлсөн'), (PAY_FULL, 'Бүрэн төлсөн')]
    CURRENCY_CHOICES = [(c, c) for c in ('EUR', 'USD', 'GBP', 'CNY', 'RUB', 'KRW', 'JPY', 'MNT')]

    shipment = models.ForeignKey(ImportShipment, on_delete=models.CASCADE, related_name='supplier_orders')
    # OpenDataCustomer (CustomerType = 'Бэлтгэн нийлүүлэгч')-оос сонгосон бол supplier_id-тэй, шинэ бол зөвхөн нэр
    supplier_id = models.CharField('Нийлүүлэгчийн код', max_length=50, blank=True)
    supplier_name = models.CharField('Нийлүүлэгч', max_length=255)
    currency = models.CharField('Валют', max_length=3, choices=CURRENCY_CHOICES, default='EUR')
    order_no = models.CharField('Order number', max_length=50, blank=True)
    order_date = models.DateField('Захиалсан огноо', null=True, blank=True)
    confirm_no = models.CharField('Order confirm №', max_length=50, blank=True)
    confirm_date = models.DateField('Баталгаажсан огноо', null=True, blank=True)
    pi_no = models.CharField('Proforma invoice №', max_length=50, blank=True)
    pi_date = models.DateField('Proforma огноо', null=True, blank=True)
    pi_amount = models.DecimalField('Proforma дүн', max_digits=16, decimal_places=2, null=True, blank=True)
    ci_no = models.CharField('Commercial invoice №', max_length=50, blank=True)
    ci_date = models.DateField('Commercial invoice огноо', null=True, blank=True)
    ci_amount = models.DecimalField('Commercial invoice дүн', max_digits=16, decimal_places=2, null=True, blank=True)
    payment_status = models.CharField('Төлбөрийн төлөв', max_length=10, choices=PAY_CHOICES, default=PAY_NONE)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'shop_import_supplier_order'
        ordering = ['position', 'id']
        verbose_name = 'Нийлүүлэгчийн захиалга'
        verbose_name_plural = 'Нийлүүлэгчийн захиалгууд'

    def __str__(self):
        return f'{self.shipment.code}: {self.supplier_name}'


class ImportOrderLine(models.Model):
    """Захиалсан бараа. Ширхэгийн бараа: нийт = хайрцаг × хайрцаг дахь; кг: хайрцаг дахь = нийт / хайрцаг."""
    supplier_order = models.ForeignKey(ImportSupplierOrder, on_delete=models.CASCADE, related_name='lines')
    # OpenDataItem-ээс сонгосон бол item_id-тэй, шинэ бараа бол зөвхөн нэр
    item_id = models.CharField('Барааны код', max_length=50, blank=True)
    item_name = models.CharField('Бараа', max_length=255)
    measure = models.CharField('Хэмжих нэгж', max_length=30, default='Ширхэг')
    box_qty = models.DecimalField('Хайрцаг', max_digits=12, decimal_places=2, default=0)
    qty_per_box = models.DecimalField('Хайрцаг дахь', max_digits=12, decimal_places=3, default=0)
    total_qty = models.DecimalField('Нийт тоо', max_digits=14, decimal_places=3, default=0)
    unit_price = models.DecimalField('Нэгж үнэ', max_digits=16, decimal_places=4, default=0)
    # Нийлүүлэгчийн хөнгөлөлт: gross_amount = тоо × үнэ (хөнгөлөлтөөс өмнө), total_amount = төлөх дүн (хөнгөлөлтийн дараа).
    # Татвар, шилжүүлэх дүн, нийлбэрүүд total_amount-аас бодогдоно.
    gross_amount = models.DecimalField('Нийт дүн (хөнгөлөлтөөс өмнө)', max_digits=16, decimal_places=2, default=0)
    discount_rate = models.DecimalField('Хөнгөлөлт %', max_digits=7, decimal_places=4, default=0)
    total_amount = models.DecimalField('Төлөх дүн', max_digits=16, decimal_places=2, default=0)
    # Анхдагч: малын гаралтай бараа 15%, бусад 10% (services.imports.default_duty_rate); гараар засна
    duty_rate = models.DecimalField('Гаалийн татвар %', max_digits=5, decimal_places=2, default=10)
    vat_rate = models.DecimalField('НӨАТ %', max_digits=5, decimal_places=2, default=10)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'shop_import_order_line'
        ordering = ['position', 'id']
        verbose_name = 'Импортын бараа'
        verbose_name_plural = 'Импортын бараа'

    def __str__(self):
        return self.item_name


def import_receipt_path(instance, filename):
    """Шилжүүлгийн баримт - таахааргүй нэртэй; зөвхөн эрх шалгадаг view-ээр (import_receipt) үзүүлнэ."""
    import uuid
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f'import_receipts/{instance.supplier_order.shipment_id}/{uuid.uuid4().hex}{ext}'


class ImportPayment(models.Model):
    """Нийлүүлэгчид хийсэн шилжүүлэг ба баримтын зураг."""
    supplier_order = models.ForeignKey(ImportSupplierOrder, on_delete=models.CASCADE, related_name='payments')
    paid_date = models.DateField('Төлсөн огноо')
    amount = models.DecimalField('Дүн', max_digits=16, decimal_places=2, default=0)
    receipt = models.FileField('Баримт', upload_to=import_receipt_path, blank=True)
    note = models.CharField('Тайлбар', max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shop_import_payment'
        ordering = ['paid_date', 'id']
        verbose_name = 'Импортын төлбөр'
        verbose_name_plural = 'Импортын төлбөрүүд'


def import_attachment_path(instance, filename):
    """Үе шатын хавсралт - таахааргүй нэртэй; зөвхөн эрх шалгадаг view-ээр (import_attachment) үзүүлнэ."""
    import uuid
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f'import_files/{instance.shipment_id}/{uuid.uuid4().hex}{ext}'


class ImportAttachment(models.Model):
    """Үе шатын зураг/файл. Нийлүүлэгчийн бичиг баримтын үе шат бол supplier_order-тэй, чингэлгийн үе шат бол үгүй."""
    STAGE_ORDER = 'order'
    STAGE_CONFIRM = 'confirm'
    STAGE_PI = 'pi'
    STAGE_CI = 'ci'
    STAGE_LOADED = 'loaded'
    STAGE_TRANSIT = 'transit'
    STAGE_ARRIVED = 'arrived'
    STAGE_CHOICES = [
        (STAGE_ORDER, 'Order number'), (STAGE_CONFIRM, 'Order confirm'), (STAGE_PI, 'Proforma invoice'),
        (STAGE_CI, 'Commercial invoice'), (STAGE_LOADED, 'Ачигдсан'), (STAGE_TRANSIT, 'Замд'), (STAGE_ARRIVED, 'Ирсэн'),
    ]
    SUPPLIER_STAGES = (STAGE_ORDER, STAGE_CONFIRM, STAGE_PI, STAGE_CI)
    SHIPMENT_STAGES = (STAGE_LOADED, STAGE_TRANSIT, STAGE_ARRIVED)
    IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')

    shipment = models.ForeignKey(ImportShipment, on_delete=models.CASCADE, related_name='attachments')
    supplier_order = models.ForeignKey(ImportSupplierOrder, on_delete=models.CASCADE, null=True, blank=True,
                                       related_name='attachments')
    stage = models.CharField('Үе шат', max_length=10, choices=STAGE_CHOICES)
    file = models.FileField('Файл', upload_to=import_attachment_path)
    original_name = models.CharField('Файлын нэр', max_length=255, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shop_import_attachment'
        ordering = ['created_at', 'id']
        verbose_name = 'Импортын хавсралт'
        verbose_name_plural = 'Импортын хавсралтууд'

    def __str__(self):
        return self.original_name or self.file.name

    @property
    def is_image(self):
        return os.path.splitext(self.file.name)[1].lower() in self.IMAGE_EXTS


class ImportTransitPoint(models.Model):
    """Ачигдсанаас хойш дамжсан газар (огноотой)."""
    shipment = models.ForeignKey(ImportShipment, on_delete=models.CASCADE, related_name='transit_points')
    place = models.CharField('Газар', max_length=200)
    date = models.DateField('Огноо')
    note = models.CharField('Тайлбар', max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shop_import_transit_point'
        ordering = ['date', 'id']
        verbose_name = 'Дамжсан газар'
        verbose_name_plural = 'Дамжсан газрууд'


class ImportFreightCost(models.Model):
    """Тээврийн зардал: анхны тохирсон үнэ (initial) ба тайлбартай өөрчлөлтүүд (+/-)."""
    KIND_INITIAL = 'initial'
    KIND_ADJUST = 'adjust'
    KIND_CHOICES = [(KIND_INITIAL, 'Анхны тохиролцоо'), (KIND_ADJUST, 'Өөрчлөлт')]

    shipment = models.ForeignKey(ImportShipment, on_delete=models.CASCADE, related_name='freight_costs')
    kind = models.CharField('Төрөл', max_length=10, choices=KIND_CHOICES, default=KIND_ADJUST)
    date = models.DateField('Огноо')
    amount = models.DecimalField('Дүн', max_digits=16, decimal_places=2)
    currency = models.CharField('Валют', max_length=3, default='USD')
    note = models.CharField('Тайлбар', max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shop_import_freight_cost'
        ordering = ['date', 'id']
        verbose_name = 'Тээврийн зардал'
        verbose_name_plural = 'Тээврийн зардал'


# ---------------------------------------------------------------------------
# Түгээлтийн машины бүртгэл - харуул машин гарах/ирэхэд бөглөнө (цаасан дэвтрийн оронд)
# ---------------------------------------------------------------------------

class DeliveryTrip(models.Model):
    """Түгээлтийн машин нэг удаа гарч ирсэн бүртгэл. Жолооч/туслахыг сонголтоос эсвэл шинээр бичсэн нэрээр
    хадгална (код нь сонголтоос авсан үед л бөглөгдөнө), машиныг улсын дугаараар (OpenDataAsset-аас эсвэл шинээр)."""
    date = models.DateField('Огноо', db_index=True)
    driver_code = models.CharField('Жолоочийн код', max_length=50, blank=True)
    driver_name = models.CharField('Жолооч', max_length=100)
    helper_code = models.CharField('Туслахын код', max_length=50, blank=True)
    helper_name = models.CharField('Туслах', max_length=100, blank=True)  # хоосон = туслахгүй
    vehicle_plate = models.CharField('Машины дугаар', max_length=30)
    depart_time = models.TimeField('Гарсан цаг', null=True, blank=True)
    customer_count = models.PositiveSmallIntegerField('Харилцагчийн тоо', null=True, blank=True)
    return_time = models.TimeField('Ирсэн цаг', null=True, blank=True)
    returned_count = models.PositiveSmallIntegerField('Буцаж ирсэн айлын тоо', null=True, blank=True)
    remainder_note = models.CharField('Үлдэгдлийн шалтгаан', max_length=300, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_delivery_trip'
        ordering = ['date', 'depart_time', 'id']
        verbose_name = 'Түгээлтийн машин'
        verbose_name_plural = 'Түгээлтийн машины бүртгэл'

    def __str__(self):
        return f'{self.date} {self.vehicle_plate} {self.driver_name}'


# ---------------------------------------------------------------------------
# Бүтээгдэхүүний хавсралт - шинжилгээний бичиг г.м. (утаснаас зураг дарж оруулж болно)
# ---------------------------------------------------------------------------

def product_attachment_path(instance, filename):
    """Таахааргүй нэртэй; зөвхөн нэвтэрсэн хэрэглэгчид view-ээр (product_attachment) үзүүлнэ."""
    import uuid
    ext = os.path.splitext(filename)[1].lower()[:10]
    return f'product_files/{uuid.uuid4().hex}{ext}'


class ProductDocType(models.Model):
    """Бүтээгдэхүүний бичгийн төрөл (шинжилгээний бичиг, эрүүл ахуйн гэрчилгээ г.м.) - хэрэглэгч нэмж болно.
    tracks_expiry=True төрлийн бичгийн дуусах хугацааг хянана (services.product_certs)."""
    name = models.CharField('Нэр', max_length=100, unique=True)
    tracks_expiry = models.BooleanField('Хугацаа хянах', default=True)
    is_active = models.BooleanField('Идэвхтэй', default=True)
    sort_order = models.PositiveSmallIntegerField('Эрэмбэ', default=0)

    class Meta:
        db_table = 'shop_product_doc_type'
        ordering = ['sort_order', 'name']
        verbose_name = 'Бичгийн төрөл'
        verbose_name_plural = 'Бичгийн төрлүүд'

    def __str__(self):
        return self.name


class ProductAttachment(models.Model):
    """Бүтээгдэхүүний шинжилгээний бичиг, гэрчилгээ г.м. Нэг зураг/файлд олон барааны бичиг байж болох тул
    олон бараатай холбогдоно (ProductAttachmentItem). Нэвтэрсэн бүх хэрэглэгч харж, татна;
    хавсаргах/холбох/устгах нь 'product_attachment_upload' эрхтэй албан тушаалд.
    Дуусах хугацаа нь бичиг дээр хадгалагдах тул холбогдсон бүх бараанд нэг дор үйлчилнэ."""
    IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
    HEIC_EXTS = ('.heic', '.heif')  # хадгалахдаа JPEG болгоно (services.product_files.normalize_upload)
    ALLOWED_EXTS = IMAGE_EXTS + HEIC_EXTS + ('.pdf',)

    file = models.FileField('Файл', upload_to=product_attachment_path)
    original_name = models.CharField('Файлын нэр', max_length=255, blank=True)
    note = models.CharField('Тайлбар', max_length=200, blank=True)
    doc_type = models.ForeignKey(ProductDocType, on_delete=models.PROTECT, null=True, blank=True,
                                 related_name='attachments', verbose_name='Төрөл')
    issued_on = models.DateField('Олгосон огноо', null=True, blank=True)
    expires_on = models.DateField('Дуусах огноо', null=True, blank=True, db_index=True)
    no_expiry = models.BooleanField('Хугацаагүй', default=False)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'shop_product_attachment'
        ordering = ['-created_at', '-id']
        verbose_name = 'Бүтээгдэхүүний хавсралт'
        verbose_name_plural = 'Бүтээгдэхүүний хавсралтууд'

    def __str__(self):
        return self.original_name or self.file.name

    @property
    def is_image(self):
        return os.path.splitext(self.file.name)[1].lower() in self.IMAGE_EXTS


class ProductAttachmentItem(models.Model):
    """Хавсралт ↔ бараа (OpenDataItem.id) холбоос. Сүүлийн холбоос салгагдвал хавсралт файлтайгаа устна.
    own_expiry=True бол энэ бараанд бичгийн ерөнхий огноо биш, энд хадгалсан огноо үйлчилнэ
    (нэг бичигт олон бараа өөр өөр хугацаатай байх үед)."""
    attachment = models.ForeignKey(ProductAttachment, on_delete=models.CASCADE, related_name='items')
    item_id = models.TextField('Бүтээгдэхүүний ID', db_index=True)
    own_expiry = models.BooleanField('Тусдаа хугацаатай', default=False)
    expires_on = models.DateField('Дуусах огноо (энэ бараанд)', null=True, blank=True)
    no_expiry = models.BooleanField('Хугацаагүй (энэ бараанд)', default=False)

    @property
    def effective_expires(self):
        return self.expires_on if self.own_expiry else self.attachment.expires_on

    @property
    def effective_no_expiry(self):
        return self.no_expiry if self.own_expiry else self.attachment.no_expiry

    class Meta:
        db_table = 'shop_product_attachment_item'
        unique_together = [('attachment', 'item_id')]
        verbose_name = 'Хавсралтын бараа'
        verbose_name_plural = 'Хавсралтын бараанууд'

    def __str__(self):
        return f'{self.attachment_id} - {self.item_id}'


class SalesPlan(models.Model):
    """Борлуулалтын сарын төлөвлөгөө - суваг (OpenDataDistributionChannel.Id, ХТ г.м.) бүрийн дүн (₮, НӨАТ-тэй
    PayAmount-тай харьцуулна). Удирдлагын нэгтгэлийн (/dashboard/) биелэлтэд ашиглана."""
    month = models.DateField('Сар (1-ний өдөр)', db_index=True)
    channel_id = models.CharField('Сувгийн код', max_length=20)
    amount = models.DecimalField('Төлөвлөгөө (₮)', max_digits=16, decimal_places=2, default=0)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_sales_plan'
        unique_together = [('month', 'channel_id')]
        verbose_name = 'Борлуулалтын төлөвлөгөө'
        verbose_name_plural = 'Борлуулалтын төлөвлөгөө'

    def __str__(self):
        return f'{self.month:%Y-%m} {self.channel_id}: {self.amount}'


class SalesPlanItem(models.Model):
    """Төлөвлөгөөт бараа - сар бүр онцолж борлуулах бараа ба суваг тус бүрийн тоо ширхгийн зорилт."""
    month = models.DateField('Сар (1-ний өдөр)', db_index=True)
    item_id = models.TextField('Барааны код')
    channel_id = models.CharField('Сувгийн код', max_length=20)
    target_qty = models.DecimalField('Зорилт (ширхэг)', max_digits=14, decimal_places=2, default=0)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_sales_plan_item'
        unique_together = [('month', 'item_id', 'channel_id')]
        verbose_name = 'Төлөвлөгөөт бараа'
        verbose_name_plural = 'Төлөвлөгөөт бараа'

    def __str__(self):
        return f'{self.month:%Y-%m} {self.item_id} {self.channel_id}: {self.target_qty}'


# ---------------------------------------------------------------------------
# Тээврийн хэрэгсэл - шатахууны картын гүйлгээ (Petrovis "report" Excel) ба сарын үлдэгдэл ("Balance Report")
# ---------------------------------------------------------------------------

class FuelTransaction(models.Model):
    """Шатахууны картын нэг гүйлгээ. raw_* талбар нь Excel-ээс ирсэн утга (давхардал шалгах түлхүүрт ашиглагдана),
    fuel_type/unit_price/quantity нь Excel-ээс эсвэл гараас нөхсөн утга. Машин, жолооч, км-ийг гараас бөглөнө."""
    PURCHASE = 'Худалдан авалт'
    CASH_CARD = 'Бэлэн'  # кассаас бэлнээр төлсөн шатахуун (картын үлдэгдэлд орохгүй)
    SOURCE_CHOICES = [('import', 'Petrovis импорт'), ('legacy', 'Хуучин бүртгэл'), ('manual', 'Гараас')]

    dedupe_key = models.CharField('Давхардлын түлхүүр', max_length=64, unique=True)
    source = models.CharField('Эх сурвалж', max_length=10, choices=SOURCE_CHOICES, default='import')
    card_no = models.CharField('Карт', max_length=30, db_index=True)
    holder = models.CharField('Эзэмшигч', max_length=150, blank=True)
    merchant = models.CharField('Мерчант', max_length=150, blank=True)
    address = models.CharField('Хаяг', max_length=255, blank=True)
    txn_at = models.DateTimeField('Огноо', db_index=True)
    txn_type = models.CharField('Гүйлгээний төрөл', max_length=60)
    description = models.CharField('Тайлбар', max_length=255, blank=True)
    amount = models.DecimalField('Үнийн дүн', max_digits=14, decimal_places=2)
    counter_account = models.CharField('Харьцсан данс', max_length=30, blank=True)
    raw_fuel_type = models.CharField('Төрөл (Excel)', max_length=100, blank=True)
    raw_unit_price = models.DecimalField('Нэгж үнэ (Excel)', max_digits=12, decimal_places=2, null=True, blank=True)
    raw_quantity = models.DecimalField('Хэмжээ (Excel)', max_digits=12, decimal_places=2, null=True, blank=True)

    fuel_type = models.CharField('Шатахууны төрөл', max_length=100, blank=True)
    unit_price = models.DecimalField('Нэгж үнэ', max_digits=12, decimal_places=2, null=True, blank=True)
    quantity = models.DecimalField('Хэмжээ (л)', max_digits=12, decimal_places=2, null=True, blank=True)
    vehicle_plate = models.CharField('Машины дугаар', max_length=30, blank=True, db_index=True)
    driver_code = models.CharField('Жолоочийн код', max_length=50, blank=True)
    driver_name = models.CharField('Жолооч', max_length=100, blank=True)
    odometer_km = models.PositiveIntegerField('Км заалт', null=True, blank=True)
    note = models.CharField('Тайлбар (гараас)', max_length=255, blank=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_fuel_transaction'
        ordering = ['txn_at', 'id']
        verbose_name = 'Шатахууны гүйлгээ'
        verbose_name_plural = 'Шатахууны гүйлгээ'

    def __str__(self):
        return f'{self.txn_at:%Y-%m-%d %H:%M} {self.card_no} {self.txn_type} {self.amount}'

    @property
    def is_purchase(self):
        return self.txn_type == self.PURCHASE

    @property
    def is_cash(self):
        return self.card_no == self.CASH_CARD


class FuelCardBalance(models.Model):
    """Шатахууны картын сарын үлдэгдэл (Balance Report): эхний үлдэгдэл + гүйлгээ = эцсийн үлдэгдэл байх ёстой."""
    month = models.DateField('Сар (1-ний өдөр)', db_index=True)
    card_no = models.CharField('Карт', max_length=30)
    holder = models.CharField('Эзэмшигч', max_length=150, blank=True)
    opening = models.DecimalField('Эхний үлдэгдэл', max_digits=14, decimal_places=2, default=0)
    income = models.DecimalField('Орлого', max_digits=14, decimal_places=2, default=0)
    transfer_out = models.DecimalField('Шилжүүлгийн зарлага', max_digits=14, decimal_places=2, default=0)
    purchase = models.DecimalField('Худалдан авалт', max_digits=14, decimal_places=2, default=0)
    deduction = models.DecimalField('Хасалт', max_digits=14, decimal_places=2, default=0)
    closing = models.DecimalField('Эцсийн үлдэгдэл', max_digits=14, decimal_places=2, default=0)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_fuel_card_balance'
        unique_together = [('month', 'card_no')]
        ordering = ['month', 'card_no']
        verbose_name = 'Шатахууны картын үлдэгдэл'
        verbose_name_plural = 'Шатахууны картын үлдэгдэл'

    def __str__(self):
        return f'{self.month:%Y-%m} {self.card_no}: {self.opening} -> {self.closing}'


class Vehicle(models.Model):
    """Манай тээврийн хэрэгслийн мэдээлэл (машины тайлангийн толгойд). Жагсаалт нь OpenDataAsset-ийн
    "Тээврийн хэрэгсэл"-тэй нэгдэж харагдана; энд нэмсэн идэвхтэй машин ч км заалт шаардана."""
    plate = models.CharField('Улсын дугаар', max_length=30, unique=True)
    make = models.CharField('Марк', max_length=60, blank=True)
    model = models.CharField('Модел', max_length=60, blank=True)
    vin = models.CharField('Арлын дугаар', max_length=40, blank=True)
    year = models.PositiveSmallIntegerField('Үйлдвэрлэсэн он', null=True, blank=True)
    imported_year = models.PositiveSmallIntegerField('Монголд орж ирсэн он', null=True, blank=True)
    country = models.CharField('Үйлдвэрлэсэн улс', max_length=40, blank=True)
    engine_cc = models.PositiveIntegerField('Хөдөлгүүрийн багтаамж', null=True, blank=True)
    capacity_kg = models.PositiveIntegerField('Даац (кг)', null=True, blank=True)
    purpose = models.CharField('Зориулалт', max_length=60, blank=True)
    body_type = models.CharField('Төрөл', max_length=60, blank=True)
    is_active = models.BooleanField('Ашиглагдаж байгаа', default=True)
    note = models.CharField('Тайлбар', max_length=255, blank=True)

    class Meta:
        db_table = 'shop_vehicle'
        ordering = ['plate']
        verbose_name = 'Тээврийн хэрэгсэл'
        verbose_name_plural = 'Тээврийн хэрэгсэл'

    def __str__(self):
        return f'{self.plate} {self.make} {self.model}'.strip()


class VehiclePartRecord(models.Model):
    """Сэлбэг хэрэгсэл, засвар үйлчилгээний нэг мөр (нэг баримтын олон мөрийг тусад нь хадгална)."""
    date = models.DateField('Огноо', db_index=True)
    vehicle_plate = models.CharField('Машины дугаар', max_length=30, blank=True, db_index=True)
    category = models.CharField('Төрөл', max_length=60)
    description = models.CharField('Тайлбар', max_length=255)
    quantity = models.DecimalField('Тоо', max_digits=12, decimal_places=2, default=1)
    unit_price = models.DecimalField('Нэгж үнэ', max_digits=14, decimal_places=2, default=0)
    amount = models.DecimalField('Дүн', max_digits=14, decimal_places=2, default=0)
    driver_code = models.CharField('Жолоочийн код', max_length=50, blank=True)
    driver_name = models.CharField('Жолооч', max_length=100, blank=True)
    odometer_km = models.PositiveIntegerField('Км заалт', null=True, blank=True)
    supplier = models.CharField('Нийлүүлэгч / засварын газар', max_length=150, blank=True)
    note = models.CharField('Нэмэлт тайлбар', max_length=255, blank=True)
    dedupe_key = models.CharField('Импортын түлхүүр', max_length=64, unique=True, null=True, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'shop_vehicle_part_record'
        ordering = ['date', 'id']
        verbose_name = 'Сэлбэг, засвар'
        verbose_name_plural = 'Сэлбэг, засварын бүртгэл'

    def __str__(self):
        return f'{self.date} {self.vehicle_plate} {self.description} {self.amount}'
