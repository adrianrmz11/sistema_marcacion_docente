from pyodbc import *
from typing import Any, Iterator, List, Dict, Optional, Tuple
import os

Row = Dict[str, Any]

def get_connection() -> Connection:
    conn = connect(f'DRIVER={{Sql Server}};SERVER={os.getenv("DB_HOST")};DATABASE={os.getenv("DB_NAME")};UID={os.getenv("DB_USER")};PWD={os.getenv("DB_PASSWORD")};')
    
    return conn

def fetchone(query, *params):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(query, *params)
    
    result = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    return result

def fetchall(query, *params):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute(query, *params)
    
    result = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return result

def get_cursor() -> Cursor:
    conn = get_connection()
    return conn.cursor()

def close_cursor(cursor: Cursor) -> None:
    if cursor is not None:
        cursor.close()
