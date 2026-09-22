"""
E-commerce shop моделууд
"""
import os
from datetime import date, timedelta
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
    def meals(self):
        number = self.menu_number
        if not number:
            return Meal.objects.none()
        return Meal.objects.filter(numbers__number=number).prefetch_related('ingredients').distinct()

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
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Засварласан хэрэглэгч')
    updated_at = models.DateTimeField('Засварласан огноо', auto_now=True)

    class Meta:
        db_table = 'shop_attendance_record'
        unique_together = ('employee_code', 'date')
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
    өөрөөр хэлбэл (тарсан цаг - ирсэн цаг) < 8 цаг бол дутсан минутыг хоцролтоор тооцно.
    """
    position_name = models.CharField('Албан тушаал', max_length=200, unique=True)
    start_time = models.TimeField('Ажил эхлэх цаг', null=True, blank=True)
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

    def __str__(self):
        return f"{self.employee_code} -> {self.device_user_id}"
