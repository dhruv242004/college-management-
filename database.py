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
            try:
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

    # 3. Ensure Attendance Tables Exist (for QR system)
    with db_cursor(dictionary=False) as (conn, cur):
        # Check attendance_sessions
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance_sessions'")
        if not cur.fetchone():
            print("Migration: Creating attendance_sessions table...")
            cur.execute("""
                CREATE TABLE attendance_sessions (
                    id SERIAL PRIMARY KEY,
                    session_id VARCHAR(36) NOT NULL UNIQUE,
                    faculty_id INTEGER NOT NULL,
                    subject_id INTEGER NOT NULL,
                    course_id INTEGER NOT NULL,
                    semester INTEGER NOT NULL,
                    date DATE NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    expiry_time TIMESTAMP NOT NULL,
                    qr_token VARCHAR(500) NOT NULL,
                    token_hash VARCHAR(255) NOT NULL UNIQUE,
                    otp_code VARCHAR(10),
                    otp_expiry TIMESTAMP,
                    status VARCHAR(20) DEFAULT 'active',
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    ip_address VARCHAR(45),
                    session_data JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
                    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                    UNIQUE (subject_id, date, faculty_id)
                )
            """)

        # Check attendance_records
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance_records'")
        if not cur.fetchone():
            print("Migration: Creating attendance_records table...")
            cur.execute("""
                CREATE TABLE attendance_records (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    scan_time TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    ip_address VARCHAR(45),
                    device_info VARCHAR(500),
                    browser_info VARCHAR(255),
                    latitude DECIMAL(10, 8),
                    longitude DECIMAL(11, 8),
                    accuracy FLOAT,
                    status VARCHAR(20) DEFAULT 'verified',
                    reason VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE (session_id, student_id)
                )
            """)

        # Check attendance_audit_log
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'attendance_audit_log'")
        if not cur.fetchone():
            print("Migration: Creating attendance_audit_log table...")
            cur.execute("""
                CREATE TABLE attendance_audit_log (
                    id SERIAL PRIMARY KEY,
                    session_id INTEGER,
                    student_id INTEGER,
                    event_type VARCHAR(50) NOT NULL,
                    action VARCHAR(100) NOT NULL,
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(500),
                    details JSONB,
                    flagged BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE SET NULL,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL
                )
            """)

        # 4. Ensure Examination Tables Exist
        # online_exams table
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'online_exams'")
        if not cur.fetchone():
            print("Migration: Creating online_exams table...")
            cur.execute("""
                CREATE TABLE online_exams (
                    id SERIAL PRIMARY KEY,
                    faculty_id INTEGER NOT NULL,
                    subject_id INTEGER NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    description TEXT,
                    duration_minutes INTEGER DEFAULT 60,
                    min_attendance_percentage DECIMAL(5, 2) DEFAULT 60.00,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
                    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
                )
            """)

        # exam_questions table
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'exam_questions'")
        if not cur.fetchone():
            print("Migration: Creating exam_questions table...")
            cur.execute("""
                CREATE TABLE exam_questions (
                    id SERIAL PRIMARY KEY,
                    exam_id INTEGER NOT NULL,
                    question_text TEXT NOT NULL,
                    question_type VARCHAR(20) NOT NULL, -- 'text', 'mcq', 'true_false'
                    options JSONB, -- For MCQ: ["Option A", "Option B", ...]
                    correct_answer TEXT, -- For MCQ/TF: the correct value
                    marks INTEGER DEFAULT 1,
                    FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE
                )
            """)

        # student_exam_attempts table
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'student_exam_attempts'")
        if not cur.fetchone():
            print("Migration: Creating student_exam_attempts table...")
            cur.execute("""
                CREATE TABLE student_exam_attempts (
                    id SERIAL PRIMARY KEY,
                    exam_id INTEGER NOT NULL,
                    student_id INTEGER NOT NULL,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    submit_time TIMESTAMP,
                    score DECIMAL(5, 2),
                    status VARCHAR(20) DEFAULT 'in_progress', -- 'in_progress', 'submitted', 'graded'
                    FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE,
                    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
                    UNIQUE (exam_id, student_id)
                )
            """)

        # student_answers table
        cur.execute("SELECT 1 FROM information_schema.tables WHERE table_name = 'student_answers'")
        if not cur.fetchone():
            print("Migration: Creating student_answers table...")
            cur.execute("""
                CREATE TABLE student_answers (
                    id SERIAL PRIMARY KEY,
                    attempt_id INTEGER NOT NULL,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT,
                    is_correct BOOLEAN,
                    marks_obtained DECIMAL(5, 2),
                    FOREIGN KEY (attempt_id) REFERENCES student_exam_attempts(id) ON DELETE CASCADE,
                    FOREIGN KEY (question_id) REFERENCES exam_questions(id) ON DELETE CASCADE,
                    UNIQUE (attempt_id, question_id)
                )
            """)
