"""Database connection helper supporting both PostgreSQL (Production) and MySQL (Local)."""
import os
from contextlib import contextmanager
from config import config

# Import drivers based on availability and config
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except ImportError:
    psycopg2 = None

try:
    import mysql.connector
except ImportError:
    mysql.connector = None

def get_connection():
    """Create and return a database connection (PostgreSQL or MySQL)."""
    # 1. Try PostgreSQL (Standard for Render)
    if config.DATABASE_URL:
        if not psycopg2:
            raise RuntimeError("psycopg2 is not installed. Required for PostgreSQL.")
        try:
            # Handle Render's 'postgres://' vs 'postgresql://' if needed
            url = config.DATABASE_URL
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            conn = psycopg2.connect(url)
            conn.autocommit = False
            return conn
        except Exception as e:
            raise RuntimeError(f"PostgreSQL connection failed: {e}")

    # 2. Fallback to MySQL (Local development)
    if mysql.connector:
        try:
            conn = mysql.connector.connect(
                host=config.MYSQL_HOST,
                user=config.MYSQL_USER,
                password=config.MYSQL_PASSWORD,
                database=config.MYSQL_DATABASE,
                port=config.MYSQL_PORT,
                autocommit=False,
            )
            return conn
        except Exception as e:
            raise RuntimeError(f"MySQL connection failed: {e}")
    
    raise RuntimeError("No database driver or configuration found.")

@contextmanager
def db_cursor(dictionary=True):
    """Context manager for database cursor. Yields (conn, cursor)."""
    conn = get_connection()
    try:
        # Check if it's a PostgreSQL connection
        if hasattr(conn, 'cursor_factory'):
            # PostgreSQL
            if dictionary:
                cur = conn.cursor(cursor_factory=RealDictCursor)
            else:
                cur = conn.cursor()
        else:
            # MySQL
            cur = conn.cursor(dictionary=dictionary)
            
        yield conn, cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

def init_db():
    """Initialize database schema and handle simple migrations."""
    # 1. Check for 'is_verified' in 'students'
    has_is_verified = False
    with db_cursor(dictionary=True) as (conn, cur):
        # We check information_schema for the column. 
        # Using lowercase for table and column names as they are usually stored that way.
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE LOWER(table_name) = 'students' AND LOWER(column_name) = 'is_verified'
        """)
        has_is_verified = cur.fetchone() is not None
    
    if not has_is_verified:
        with db_cursor(dictionary=False) as (conn, cur):
            print("Migration: Adding 'is_verified' column to 'students' table...")
            try:
                # PostgreSQL/MySQL compatible ALTER TABLE
                cur.execute("ALTER TABLE students ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
                print("Migration: 'is_verified' added successfully.")
            except Exception as e:
                print(f"Migration: Error adding 'is_verified': {e}")
                
    # 2. Check for 'photo_change_count' in 'students'
    has_photo_count = False
    with db_cursor(dictionary=True) as (conn, cur):
        cur.execute("""
            SELECT 1 FROM information_schema.columns 
            WHERE LOWER(table_name) = 'students' AND LOWER(column_name) = 'photo_change_count'
        """)
        has_photo_count = cur.fetchone() is not None
        
    if not has_photo_count:
        with db_cursor(dictionary=False) as (conn, cur):
            print("Migration: Adding 'photo_change_count' column to 'students' table...")
            try:
                cur.execute("ALTER TABLE students ADD COLUMN photo_change_count INTEGER DEFAULT 0")
                print("Migration: 'photo_change_count' added successfully.")
            except Exception as e:
                print(f"Migration: Error adding 'photo_change_count': {e}")
