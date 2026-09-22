"""
MSSQL database холбогдох утилити функцууд
"""
import pyodbc
import pandas as pd
from decouple import config
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MSSQLConnection:
    """MSSQL database-тай холбогдох класс"""
    
    def __init__(self):
        self.server = config('MSSQL_SERVER', default='')
        self.database = config('MSSQL_DATABASE', default='')
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
            self.connection = pyodbc.connect(connection_string)
            logger.info(f"MSSQL-д амжилттай холбогдлоо: {self.server}/{self.database}")
            return True
        except Exception as e:
            logger.error(f"MSSQL холбогдох алдаа: {str(e)}")
            return False
    
    def disconnect(self):
        """Холболтыг таслах"""
        if self.connection:
            self.connection.close()
            logger.info("MSSQL холболт тасарлаа")
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> Optional[pd.DataFrame]:
        """
        SQL query ажиллуулж DataFrame буцаах
        
        Args:
            query: SQL query
            params: Query параметрүүд (optional)
        
        Returns:
            pandas DataFrame эсвэл None (алдаа гарвал)
        """
        try:
            if not self.connection:
                if not self.connect():
                    return None
            
            df = pd.read_sql(query, self.connection, params=params)
            logger.info(f"Query ажилласан: {len(df)} мөр олдлоо")
            return df
        except Exception as e:
            logger.error(f"Query ажиллуулах алдаа: {str(e)}")
            return None
    
    def get_table_data(self, table_name: str, where_clause: str = None) -> Optional[pd.DataFrame]:
        """
        Хүснэгтийн өгөгдлийг татах
        
        Args:
            table_name: Хүснэгтийн нэр
            where_clause: WHERE нөхцөл (optional)
        
        Returns:
            pandas DataFrame
        """
        query = f"SELECT * FROM {table_name}"
        if where_clause:
            query += f" WHERE {where_clause}"
        
        return self.execute_query(query)
    
    def __enter__(self):
        """Context manager support"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager support"""
        self.disconnect()


def fetch_products_from_mssql(table_name: str = 'Products') -> Optional[pd.DataFrame]:
    """
    MSSQL-ээс бүтээгдэхүүний жагсаалт татах
    
    Args:
        table_name: Бүтээгдэхүүний хүснэгтийн нэр
    
    Returns:
        pandas DataFrame
    """
    with MSSQLConnection() as conn:
        return conn.get_table_data(table_name)


def fetch_customers_from_mssql(table_name: str = 'Customers') -> Optional[pd.DataFrame]:
    """
    MSSQL-ээс харилцагчдын жагсаалт татах
    
    Args:
        table_name: Харилцагчийн хүснэгтийн нэр
    
    Returns:
        pandas DataFrame
    """
    with MSSQLConnection() as conn:
        return conn.get_table_data(table_name)


def fetch_employees_from_mssql(table_name: str = 'Employees') -> Optional[pd.DataFrame]:
    """
    MSSQL-ээс ажилчдын жагсаалт татах
    
    Args:
        table_name: Ажилчдын хүснэгтийн нэр
    
    Returns:
        pandas DataFrame
    """
    with MSSQLConnection() as conn:
        return conn.get_table_data(table_name)
