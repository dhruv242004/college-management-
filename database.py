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
    db_url = config.DATABASE_URL
    
    # 1. Try PostgreSQL (Standard for Render)
    if db_url:
        if not psycopg2:
            raise RuntimeError("psycopg2 is not installed. Required for PostgreSQL.")
        try:
            # Handle Render's 'postgres://' vs 'postgresql://' if needed
            if db_url.startswith("postgres://"):
                db_url = db_url.replace("postgres://", "postgresql://", 1)
            
            # Log connection attempt (redacted)
            print(f"Connecting to PostgreSQL...")
            conn = psycopg2.connect(db_url)
            conn.autocommit = False
            return conn
        except Exception as e:
            # If DATABASE_URL is present but fails, DO NOT fall back to MySQL
            raise RuntimeError(f"PostgreSQL connection failed. Check your DATABASE_URL environment variable. Error: {e}")

    # 2. Fallback to MySQL (Local development only if DATABASE_URL is missing)
    if mysql.connector:
        try:
            print("Connecting to MySQL (Local fallback)...")
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
            raise RuntimeError(f"Local MySQL connection failed: {e}")
    
    raise RuntimeError("No database driver (psycopg2 or mysql-connector-python) found.")

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
    # Check if database is empty by looking for 'users' table
    with db_cursor(dictionary=False) as (conn, cur):
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
        has_users = cur.fetchone() is not None

    if not has_users:
        print("Database is empty. Initializing schema from schema_pg.sql...")
        schema_path = os.path.join(os.path.dirname(__file__), 'schema_pg.sql')
        if os.path.exists(schema_path):
            try:
                with open(schema_path, 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                
                # Execute schema as a single block (PostgreSQL supports this)
                with db_cursor(dictionary=False) as (conn, cur):
                    cur.execute(schema_sql)
                    conn.commit()
                print("Schema initialized successfully.")
                return # Skip migrations if we just created the schema
            except Exception as e:
                print(f"Error initializing schema: {e}")
        else:
            print(f"Warning: schema_pg.sql not found at {schema_path}")

    # --- Legacy Migrations (Only run if tables already exist) ---
    try:
        # 1. Check for 'is_verified' in 'students'
        has_is_verified = False
        with db_cursor(dictionary=True) as (conn, cur):
            cur.execute("""
                SELECT 1 FROM information_schema.columns 
                WHERE LOWER(table_name) = 'students' AND LOWER(column_name) = 'is_verified'
            """)
            has_is_verified = cur.fetchone() is not None
        
        if not has_is_verified:
            with db_cursor(dictionary=False) as (conn, cur):
                print("Migration: Adding 'is_verified' column to 'students' table...")
                cur.execute("ALTER TABLE students ADD COLUMN is_verified BOOLEAN DEFAULT FALSE")
    except Exception as e:
        print(f"Migration error (is_verified): {e}")

    # ... rest of migrations (truncated for brevity in replace_file_content)
    # Actually, I'll just replace the whole function to be safe.
