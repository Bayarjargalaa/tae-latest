"""
Динамик модель үүсгэх утилити - Views-үүдийг Django models болгох
"""
from django.db import models
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


def mssql_to_django_field(mssql_type: str, max_length: int = None, nullable: str = 'YES') -> models.Field:
    """
    MSSQL data type-ыг Django Field-д хөрвүүлэх
    
    Args:
        mssql_type: MSSQL data type
        max_length: Maximum length (for char/varchar)
        nullable: 'YES' or 'NO'
    
    Returns:
        Django Field instance
    """
    null = (nullable == 'YES')
    blank = null
    
    # Type mapping
    type_lower = mssql_type.lower()
    
    # Text types
    if type_lower in ('varchar', 'nvarchar', 'char', 'nchar'):
        if max_length and max_length > 0:
            if max_length > 255:
                return models.TextField(null=null, blank=blank)
            return models.CharField(max_length=max_length, null=null, blank=blank)
        return models.TextField(null=null, blank=blank)
    
    if type_lower in ('text', 'ntext'):
        return models.TextField(null=null, blank=blank)
    
    # Numeric types
    if type_lower in ('int', 'integer'):
        return models.IntegerField(null=null, blank=blank)
    
    if type_lower in ('bigint',):
        return models.BigIntegerField(null=null, blank=blank)
    
    if type_lower in ('smallint', 'tinyint'):
        return models.SmallIntegerField(null=null, blank=blank)
    
    if type_lower in ('decimal', 'numeric', 'money', 'smallmoney'):
        return models.DecimalField(max_digits=18, decimal_places=2, null=null, blank=blank)
    
    if type_lower in ('float', 'real'):
        return models.FloatField(null=null, blank=blank)
    
    # Boolean
    if type_lower in ('bit',):
        return models.BooleanField(null=null, blank=blank)
    
    # Date/Time types
    if type_lower in ('date',):
        return models.DateField(null=null, blank=blank)
    
    if type_lower in ('time',):
        return models.TimeField(null=null, blank=blank)
    
    if type_lower in ('datetime', 'datetime2', 'smalldatetime'):
        return models.DateTimeField(null=null, blank=blank)
    
    # Binary types
    if type_lower in ('binary', 'varbinary', 'image'):
        return models.BinaryField(null=null, blank=blank)
    
    # Default - JSON болон бусад
    if type_lower in ('uniqueidentifier',):
        return models.CharField(max_length=36, null=null, blank=blank)
    
    # Unknown type - TextField ашиглах
    return models.TextField(null=null, blank=blank)


def create_model_from_view(database_name: str, view_name: str, columns: list) -> type:
    """
    View-ийн мэдээллээс Django model динамикаар үүсгэх
    
    Args:
        database_name: Database нэр
        view_name: View нэр
        columns: Column мэдээллийн жагсаалт
    
    Returns:
        Django Model class
    """
    # Model нэр үүсгэх - schema болон view нэрээс
    safe_db_name = database_name
    safe_view_name = view_name
    model_name = f"{safe_db_name}_{safe_view_name}"
    
    # Table name
    db_table = f"{safe_view_name}"
    
    # Fields үүсгэх
    attrs = {
        '__module__': 'datamigration.models',
        'Meta': type('Meta', (), {
            'db_table': db_table,
            'managed': False,  # Django-д migration үүсгэхгүй байх
            'verbose_name': f'{database_name} - {view_name}',
        })
    }
    
    # ID field нэмэх (Primary key)
    attrs['id'] = models.AutoField(primary_key=True)
    
    # Column бүрийг field болгох
    for col in columns:
        field_name = col['name'].lower()
        # Python keyword болон Django талбар нэрээс зайлсхийх
        if field_name in ('class', 'def', 'return', 'id', 'pk'):
            field_name = f"{field_name}_"
        
        field = mssql_to_django_field(
            col['type'],
            col.get('max_length'),
            col.get('nullable', 'YES')
        )
        attrs[field_name] = field
    
    # __str__ method
    def __str__(self):
        return f"{model_name} #{self.pk}"
    attrs['__str__'] = __str__
    
    # Model үүсгэх
    model_class = type(model_name, (models.Model,), attrs)
    
    return model_class


def register_dynamic_model(model_class: type, app_label: str = 'datamigration'):
    """
    Динамик моделийг Django apps registry-д бүртгэх
    
    Args:
        model_class: Model class
        app_label: App label
    """
    try:
        # App config авах
        app_config = apps.get_app_config(app_label)
        
        # Model нэр
        model_name = model_class.__name__.lower()
        
        # Registry-д байгаа эсэхийг шалгах
        if model_name not in app_config.models:
            # Шинэ модель бүртгэх
            model_class._meta.app_label = app_label
            app_config.models[model_name] = model_class
            apps.all_models[app_label][model_name] = model_class
            
            return True
        else:
            # Өмнө нь бүртгэгдсэн
            return False
            
    except Exception as e:
        logger.error(f"Model бүртгэх алдаа: {str(e)}")
        return False
