"""MySQL database connection and query helpers."""
import mysql.connector
from mysql.connector import Error
from contextlib import contextmanager
from config import config


def get_connection():
    """Create and return MySQL connection."""
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
    except Error as e:
        raise RuntimeError(f"Database connection failed: {e}")


@contextmanager
def db_cursor(dictionary=True):
    """Context manager for database cursor. Yields (conn, cursor)."""
    conn = get_connection()
    try:
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
    """Initialize database schema. Run schema.sql externally or via CLI."""
    pass  # Schema applied via schema.sql
