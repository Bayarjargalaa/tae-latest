"""
MSSQL views-үүдийг PostgreSQL-д импортлох management command
"""
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from datamigration.utils.view_extractor import MSSQLViewExtractor, get_all_databases
from datamigration.utils.dynamic_models import create_model_from_view, mssql_to_django_field
import logging
import time

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'MSSQL-ээс бүх views-ийн өгөгдлийг PostgreSQL-д хадгална'

    def add_arguments(self, parser):
        parser.add_argument(
            '--database',
            type=str,
            help='Тодорхой database-ийн views-үүдийг татах (заагаагүй бол бүгд)'
        )
        parser.add_argument(
            '--view',
            type=str,
            help='Тодорхой view-г татах'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='View тус бүрээс татах мөрийн тоо (тест хийхэд)'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Views-ийн жагсаалтыг харуулаад гарах'
        )
        parser.add_argument(
            '--create-tables',
            action='store_true',
            help='PostgreSQL-д хүснэгтүүд үүсгэх'
        )

    def handle(self, *args, **options):
        target_database = options.get('database')
        target_view = options.get('view')
        limit = options.get('limit')
        list_only = options.get('list')
        create_tables = options.get('create_tables')
        
        self.stdout.write(self.style.SUCCESS('='*70))
        self.stdout.write(self.style.SUCCESS('MSSQL Views -> PostgreSQL Import'))
        self.stdout.write(self.style.SUCCESS('='*70))
        
        # Database-уудын жагсаалт
        databases = get_all_databases()
        
        if target_database:
            if target_database not in databases:
                self.stdout.write(self.style.ERROR(f"Database '{target_database}' not found"))
                return
            databases = [target_database]
        
        if not databases:
            self.stdout.write(self.style.ERROR('MSSQL database not configured (check .env file)'))
            return
        
        self.stdout.write(f'\nProcessing databases: {", ".join(databases)}\n')
        
        total_views = 0
        total_records = 0
        total_created = 0
        total_errors = 0
        
        # Database бүрээр давтах
        for db_name in databases:
            self.stdout.write(self.style.WARNING(f'\nDatabase: {db_name}'))
            self.stdout.write('-' * 70)
            
            try:
                with MSSQLViewExtractor(db_name) as extractor:
                    # Views-ийн жагсаалт авах
                    views = extractor.get_all_views()
                    
                    if not views:
                        self.stdout.write(self.style.WARNING('  No views found'))
                        continue
                    
                    self.stdout.write(f'  Found {len(views)} views')
                    
                    # Жагсаалт харуулаад гарах
                    if list_only:
                        for view in views:
                            self.stdout.write(f'    • {view}')
                        continue
                    
                    # Тодорхой view хайх
                    if target_view:
                        if target_view not in views:
                            self.stdout.write(self.style.WARNING(f"  View '{target_view}' not found"))
                            continue
                        views = [target_view]
                    
                    # View бүрийг боловсруулах
                    for view_name in views:
                        view_started = time.monotonic()
                        try:
                            self.stdout.write(f'\n  View: {view_name}')
                            
                            # Column мэдээлэл авах
                            columns = extractor.get_view_columns(view_name)
                            if not columns:
                                self.stdout.write(self.style.WARNING('    No columns found'))
                                total_errors += 1
                                continue
                            
                            self.stdout.write(f'    Columns: {len(columns)}')
                            
                            # PostgreSQL хүснэгт үүсгэх
                            if create_tables:
                                table_name = self._create_table(db_name, view_name, columns)
                                if table_name:
                                    self.stdout.write(self.style.SUCCESS(f'    Table created: {table_name}'))
                                else:
                                    self.stdout.write(self.style.ERROR('    Table creation error'))
                            
                            # Өгөгдөл татах
                            df = extractor.get_view_data(view_name, limit)
                            
                            if df is None or df.empty:
                                self.stdout.write(self.style.WARNING('    No data'))
                                continue
                            
                            # PostgreSQL-д хадгалах (анхны нэрээр)
                            table_name = view_name  # MSSQL view нэрийг шууд ашиглана
                            records_saved = self._save_to_postgres(df, table_name, columns)
                            
                            if records_saved > 0:
                                total_records += records_saved
                                total_created += 1
                                self.stdout.write(self.style.SUCCESS(f'    {records_saved} records saved'))
                                self._log_sync(view_name, db_name, records_saved, time.monotonic() - view_started)
                                # Хүснэгт дахин үүссэн тул тайлангийн индексүүдийг сэргээнэ (datamigration.opendata_indexes)
                                try:
                                    from datamigration.opendata_indexes import ensure_indexes
                                    indexed = ensure_indexes([table_name])
                                    if indexed:
                                        self.stdout.write(f'    {indexed} index created')
                                    if table_name == 'OpenDataSale':
                                        from shop.services.sales_report import warm_cache
                                        warm_cache()
                                        self.stdout.write('    sales report cache warmed')
                                except Exception as e:
                                    self.stdout.write(self.style.WARNING(f'    Index error: {e}'))
                            else:
                                self.stdout.write(self.style.ERROR('    Save error'))
                                total_errors += 1
                            
                            total_views += 1
                            
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'    Error: {str(e)}'))
                            total_errors += 1
                            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Database connection error: {str(e)}'))
                continue
        
        # Дүгнэлт
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write('='*70)
        self.stdout.write(f'Total views: {total_views}')
        self.stdout.write(f'Successful: {total_created}')
        self.stdout.write(f'Total records: {total_records:,}')
        if total_errors > 0:
            self.stdout.write(self.style.ERROR(f'Errors: {total_errors}'))
        self.stdout.write('='*70)
    
    def _create_table(self, db_name: str, view_name: str, columns: list) -> str:
        """PostgreSQL хүснэгт үүсгэх"""
        try:
            table_name = f"{view_name}"
            
            # DROP хийх (хэрэв байгаа бол)
            with connection.cursor() as cursor:
                cursor.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
            
            # CREATE TABLE SQL үүсгэх
            sql_parts = [f'CREATE TABLE "{table_name}" (']
            sql_parts.append('    id SERIAL PRIMARY KEY,')
            
            for col in columns:
                col_name = col['name']  # Анхны нэрээр нь хадгална
                # Python reserved words-ийг шалгах (case-sensitive)
                if col_name.lower() in ('class', 'def', 'return', 'for', 'if', 'while'):
                    col_name = f"{col_name}_"
                
                pg_type = self._mssql_to_postgres_type(col['type'], col.get('max_length'))
                nullable = '' if col.get('nullable') == 'YES' else ' NOT NULL'
                
                sql_parts.append(f'    "{col_name}" {pg_type}{nullable},')
            
            # Сүүлийн таслалыг арилгах
            sql_parts[-1] = sql_parts[-1].rstrip(',')
            sql_parts.append(');')
            
            sql = '\n'.join(sql_parts)
            
            # Execute
            with connection.cursor() as cursor:
                cursor.execute(sql)
            
            return table_name
            
        except Exception as e:
            logger.error(f"Хүснэгт үүсгэх алдаа: {str(e)}")
            return None
    
    def _mssql_to_postgres_type(self, mssql_type: str, max_length: int = None) -> str:
        """MSSQL type → PostgreSQL type"""
        type_lower = mssql_type.lower()
        
        if type_lower in ('varchar', 'nvarchar', 'char', 'nchar'):
            if max_length and max_length > 0:
                return f'VARCHAR({max_length})'
            return 'TEXT'
        
        if type_lower in ('text', 'ntext'):
            return 'TEXT'
        
        if type_lower in ('int', 'integer'):
            return 'INTEGER'
        
        if type_lower in ('bigint',):
            return 'BIGINT'
        
        if type_lower in ('smallint', 'tinyint'):
            return 'SMALLINT'
        
        if type_lower in ('decimal', 'numeric', 'money', 'smallmoney'):
            return 'DECIMAL(18,2)'
        
        if type_lower in ('float', 'real'):
            return 'REAL'
        
        if type_lower in ('bit',):
            return 'BOOLEAN'
        
        if type_lower in ('date',):
            return 'DATE'
        
        if type_lower in ('time',):
            return 'TIME'
        
        if type_lower in ('datetime', 'datetime2', 'smalldatetime'):
            return 'TIMESTAMP'
        
        if type_lower in ('binary', 'varbinary', 'image'):
            return 'BYTEA'
        
        if type_lower in ('uniqueidentifier',):
            return 'UUID'
        
        return 'TEXT'
    
    def _log_sync(self, table_name, db_name, rows, seconds):
        """Өдөр тутмын синкийг "Өгөгдөл шинэчлэх" хуудасны түүхэнд бүртгэнэ (хүснэгт хэзээ шинэчлэгдсэнийг харуулахад)."""
        try:
            from django.utils import timezone
            from shop.models import OpenDataSyncLog
            OpenDataSyncLog.objects.create(
                table_name=table_name, database=db_name, status=OpenDataSyncLog.STATUS_SUCCESS, rows=rows,
                seconds=round(seconds, 2), message='Хуваарьт синк (import_views)', finished_at=timezone.now(),
            )
        except Exception as e:
            logger.warning(f'Sync log error: {e}')

    def _save_to_postgres(self, df, table_name: str, columns: list) -> int:
        """DataFrame-ийг PostgreSQL-д хадгалах - түр хүснэгтэд COPY-оор бичээд атомаар солино
        (datamigration.sync.write_dataframe; давхардсан Id-г хасна)."""
        try:
            from datamigration.sync import write_dataframe
            return write_dataframe(df, table_name)
        except Exception as e:
            logger.error(f"PostgreSQL-д хадгалах алдаа: {str(e)}")
            return 0
