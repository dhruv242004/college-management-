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
    """Initialize database schema."""
    pass
