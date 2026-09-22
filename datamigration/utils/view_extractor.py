"""
MSSQL views-үүдийг PostgreSQL-д шилжүүлэх утилити функцууд
"""
import pyodbc
import pandas as pd
from decouple import config
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MSSQLViewExtractor:
    """MSSQL database-аас views-үүдийг татах класс"""
    
    def __init__(self, database_name: str = None):
        self.server = config('MSSQL_SERVER', default='')
        self.database = database_name or config('MSSQL_DATABASE', default='')
        self.username = config('MSSQL_USERNAME', default='')
        self.password = config('MSSQL_PASSWORD', default='')
        self.driver = config('MSSQL_DRIVER', default='ODBC Driver 17 for SQL Server')
        self.connection = None
    
    def connect(self) -> bool:
        """Database-д холбогдох"""
        try:
            connection_string = (
                f"DRIVER={{{self.driver}}};"
                f"SERVER={self.server};"
                f"DATABASE={self.database};"
                f"UID={self.username};"
                f"PWD={self.password};"
                f"TrustServerCertificate=yes;"
            )
            self.connection = pyodbc.connect(connection_string, timeout=30)
            logger.info(f"MSSQL-д холбогдлоо: {self.server}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"MSSQL холбогдох алдаа: {str(e)}")
            return False
    
    def disconnect(self):
        """Холболтыг таслах"""
        if self.connection:
            self.connection.close()
            logger.info("MSSQL холболт тасарлаа")
    
    def get_all_views(self) -> List[str]:
        """
        Database дахь бүх views-ийн нэрсийг авах
        
        Returns:
            List of view names
        """
        try:
            if not self.connection:
                if not self.connect():
                    return []
            
            query = """
                SELECT TABLE_SCHEMA, TABLE_NAME
                FROM INFORMATION_SCHEMA.VIEWS
                WHERE TABLE_SCHEMA NOT IN ('sys', 'INFORMATION_SCHEMA')
                ORDER BY TABLE_SCHEMA, TABLE_NAME
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query)
            
            views = []
            for row in cursor.fetchall():
                schema = row[0]
                view_name = row[1]
                full_name = f"{schema}.{view_name}" if schema != 'dbo' else view_name
                views.append(full_name)
            
            logger.info(f"{len(views)} views олдлоо")
            return views
            
        except Exception as e:
            logger.error(f"Views-ийн жагсаалт авах алдаа: {str(e)}")
            return []
    
    def get_view_data(self, view_name: str, limit: int = None) -> Optional[pd.DataFrame]:
        """
        View-ийн өгөгдлийг татах
        
        Args:
            view_name: View-ийн нэр
            limit: Хязгаарлалт (optional)
        
        Returns:
            pandas DataFrame
        """
        try:
            if not self.connection:
                if not self.connect():
                    return None
            
            # TOP clause нэмэх
            if limit:
                query = f"SELECT TOP {limit} * FROM {view_name}"
            else:
                query = f"SELECT * FROM {view_name}"
            
            logger.info(f"View татаж байна: {view_name}")
            df = pd.read_sql(query, self.connection)
            logger.info(f"  → {len(df)} мөр, {len(df.columns)} багана")
            
            return df
            
        except Exception as e:
            logger.error(f"View '{view_name}' татах алдаа: {str(e)}")
            return None
    
    def get_view_columns(self, view_name: str) -> List[Dict[str, str]]:
        """
        View-ийн column-уудын мэдээлэл авах
        
        Args:
            view_name: View-ийн нэр
        
        Returns:
            List of column info dicts
        """
        try:
            if not self.connection:
                if not self.connect():
                    return []
            
            # Schema болон view нэрийг задлах
            parts = view_name.split('.')
            if len(parts) == 2:
                schema, view = parts
            else:
                schema = 'dbo'
                view = view_name
            
            query = """
                SELECT 
                    COLUMN_NAME,
                    DATA_TYPE,
                    CHARACTER_MAXIMUM_LENGTH,
                    IS_NULLABLE,
                    COLUMN_DEFAULT
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?
                ORDER BY ORDINAL_POSITION
            """
            
            cursor = self.connection.cursor()
            cursor.execute(query, (schema, view))
            
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    'name': row[0],
                    'type': row[1],
                    'max_length': row[2],
                    'nullable': row[3],
                    'default': row[4]
                })
            
            return columns
            
        except Exception as e:
            logger.error(f"View columns авах алдаа: {str(e)}")
            return []
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.disconnect()


def get_all_databases() -> List[str]:
    """
    .env файлаас бүх MSSQL database-уудын нэрийг авах
    
    Returns:
        List of database names
    """
    databases = []
    
    # Үндсэн database
    db1 = config('MSSQL_DATABASE', default='')
    if db1:
        databases.append(db1)
    
    # Хоёр дахь database
    db2 = config('MSSQL_DATABASE2', default='')
    if db2:
        databases.append(db2)
    
    # Нэмэлт databases (MSSQL_DATABASE3, 4, 5...)
    i = 3
    while True:
        db = config(f'MSSQL_DATABASE{i}', default='')
        if not db:
            break
        databases.append(db)
        i += 1
    
    return databases
