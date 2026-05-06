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
    # Check if database is seeded by looking for 'admin' user
    is_seeded = False
    with db_cursor(dictionary=False) as (conn, cur):
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
        if cur.fetchone():
            cur.execute("SELECT 1 FROM users WHERE username = 'admin'")
            is_seeded = cur.fetchone() is not None

    if not is_seeded:
        print("Database not seeded or empty. Checking for schema...")
        # Check if tables need to be created first
        with db_cursor(dictionary=False) as (conn, cur):
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'users'")
            tables_exist = cur.fetchone() is not None
        
        if not tables_exist:
            print("Initializing schema from schema_pg.sql...")
            schema_path = os.path.join(os.path.dirname(__file__), 'schema_pg.sql')
            if os.path.exists(schema_path):
                try:
                    with open(schema_path, 'r', encoding='utf-8') as f:
                        schema_sql = f.read()
                    
                    with db_cursor(dictionary=False) as (conn, cur):
                        cur.execute(schema_sql)
                        conn.commit()
                    print("Schema initialized successfully.")
                except Exception as e:
                    print(f"Error initializing schema: {e}")
                    return
            else:
                print(f"Warning: schema_pg.sql not found at {schema_path}")
                return

        # Seed admin and sample data
        print("Seeding database...")
        try:
            from seed_admin import seed_admin
            from seed_data import seed_sample_data
            seed_admin()
            seed_sample_data()
            print("Seeding completed successfully.")
        except Exception as e:
            print(f"Error seeding database: {e}")
        
        return # Skip migrations if we just created/seeded the database

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

    # 2. Check for 'online_exams' tables
    try:
        has_online_exams = False
        with db_cursor(dictionary=False) as (conn, cur):
            cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'online_exams'")
            has_online_exams = cur.fetchone() is not None
        
        if not has_online_exams:
            print("Migration: Creating online exam tables...")
            with db_cursor(dictionary=False) as (conn, cur):
                # We can't easily run the whole schema_pg.sql again, so we just run the specific CREATE TABLEs
                # For simplicity, we'll use the same logic as the schema but adapted for both PG and MySQL if possible
                is_pg = hasattr(conn, 'cursor_factory')
                
                if is_pg:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS online_exams (
                            id SERIAL PRIMARY KEY,
                            faculty_id INTEGER NOT NULL REFERENCES faculty(id) ON DELETE CASCADE,
                            subject_id INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
                            title VARCHAR(255) NOT NULL,
                            description TEXT,
                            duration_minutes INTEGER NOT NULL,
                            min_attendance_percentage DECIMAL(5,2) DEFAULT 0,
                            start_time TIMESTAMP NOT NULL,
                            end_time TIMESTAMP NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS exam_questions (
                            id SERIAL PRIMARY KEY,
                            exam_id INTEGER NOT NULL REFERENCES online_exams(id) ON DELETE CASCADE,
                            question_text TEXT NOT NULL,
                            question_type VARCHAR(20) NOT NULL,
                            options JSONB,
                            correct_answer TEXT,
                            marks INTEGER NOT NULL DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE TABLE IF NOT EXISTS student_exam_attempts (
                            id SERIAL PRIMARY KEY,
                            exam_id INTEGER NOT NULL REFERENCES online_exams(id) ON DELETE CASCADE,
                            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
                            status VARCHAR(20) DEFAULT 'started',
                            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            submit_time TIMESTAMP,
                            score DECIMAL(5,2),
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE (exam_id, student_id)
                        );
                        CREATE TABLE IF NOT EXISTS student_answers (
                            id SERIAL PRIMARY KEY,
                            attempt_id INTEGER NOT NULL REFERENCES student_exam_attempts(id) ON DELETE CASCADE,
                            question_id INTEGER NOT NULL REFERENCES exam_questions(id) ON DELETE CASCADE,
                            answer_text TEXT,
                            is_correct BOOLEAN DEFAULT FALSE,
                            marks_obtained DECIMAL(5,2) DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            UNIQUE (attempt_id, question_id)
                        );
                    """)
                else:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS online_exams (
                            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                            faculty_id INT UNSIGNED NOT NULL,
                            subject_id INT UNSIGNED NOT NULL,
                            title VARCHAR(255) NOT NULL,
                            description TEXT,
                            duration_minutes INTEGER NOT NULL,
                            min_attendance_percentage DECIMAL(5,2) DEFAULT 0,
                            start_time DATETIME NOT NULL,
                            end_time DATETIME NOT NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                            FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                        ) ENGINE=InnoDB;
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS exam_questions (
                            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                            exam_id INT UNSIGNED NOT NULL,
                            question_text TEXT NOT NULL,
                            question_type VARCHAR(20) NOT NULL,
                            options JSON,
                            correct_answer TEXT,
                            marks INTEGER NOT NULL DEFAULT 1,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE
                        ) ENGINE=InnoDB;
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS student_exam_attempts (
                            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                            exam_id INT UNSIGNED NOT NULL,
                            student_id INT UNSIGNED NOT NULL,
                            status VARCHAR(20) DEFAULT 'started',
                            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            submit_time DATETIME NULL,
                            score DECIMAL(5,2) NULL,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE,
                            FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                            UNIQUE KEY uk_exam_student (exam_id, student_id)
                        ) ENGINE=InnoDB;
                    """)
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS student_answers (
                            id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                            attempt_id INT UNSIGNED NOT NULL,
                            question_id INT UNSIGNED NOT NULL,
                            answer_text TEXT NULL,
                            is_correct BOOLEAN DEFAULT FALSE,
                            marks_obtained DECIMAL(5,2) DEFAULT 0,
                            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (attempt_id) REFERENCES student_exam_attempts(id) ON DELETE CASCADE,
                            FOREIGN KEY (question_id) REFERENCES exam_questions(id) ON DELETE CASCADE,
                            UNIQUE KEY uk_attempt_question (attempt_id, question_id)
                        ) ENGINE=InnoDB;
                    """)
                conn.commit()
                print("Migration: Online exam tables created.")
    except Exception as e:
        print(f"Migration error (online_exams): {e}")
