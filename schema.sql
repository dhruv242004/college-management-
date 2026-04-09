-- College Management System - MySQL Schema
-- Normalized (3NF), Primary Keys, Foreign Keys, Indexes

DROP DATABASE IF EXISTS college_management;
CREATE DATABASE college_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE college_management;

-- ---------------------------------------------------------------------------
-- ROLES
-- ---------------------------------------------------------------------------
CREATE TABLE roles (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_roles_name (name)
) ENGINE=InnoDB;

INSERT INTO roles (name) VALUES ('admin'), ('faculty'), ('student'), ('accountant');

-- ---------------------------------------------------------------------------
-- USERS (unified login)
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    role_id INT UNSIGNED NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT,
    INDEX idx_users_email (email),
    INDEX idx_users_username (username),
    INDEX idx_users_role (role_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- DEPARTMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE departments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_dept_code (code)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- COURSES (per department)
-- ---------------------------------------------------------------------------
CREATE TABLE courses (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    department_id INT UNSIGNED NOT NULL,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    duration_years INT UNSIGNED NOT NULL DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    UNIQUE KEY uk_course_dept_code (department_id, code),
    INDEX idx_course_dept (department_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- SUBJECTS (per course/semester, credits)
-- ---------------------------------------------------------------------------
CREATE TABLE subjects (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id INT UNSIGNED NOT NULL,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    semester INT UNSIGNED NOT NULL,
    credits INT UNSIGNED NOT NULL DEFAULT 4,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT,
    UNIQUE KEY uk_subject_course_sem_code (course_id, semester, code),
    INDEX idx_subject_course (course_id),
    INDEX idx_subject_semester (semester)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- STUDENTS
-- ---------------------------------------------------------------------------
CREATE TABLE students (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NULL UNIQUE,
    enrollment_no VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NULL,
    date_of_birth DATE NULL,
    gender ENUM('M','F','O') NULL,
    address TEXT NULL,
    photo_path VARCHAR(255) NULL,
    course_id INT UNSIGNED NOT NULL,
    current_semester INT UNSIGNED NOT NULL DEFAULT 1,
    admission_date DATE NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    photo_change_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT,
    INDEX idx_students_enrollment (enrollment_no),
    INDEX idx_students_course (course_id),
    INDEX idx_students_semester (current_semester),
    INDEX idx_students_name (first_name, last_name)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- FACULTY
-- ---------------------------------------------------------------------------
CREATE TABLE faculty (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NULL UNIQUE,
    emp_id VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20) NULL,
    department_id INT UNSIGNED NOT NULL,
    designation VARCHAR(100) NULL,
    joined_date DATE NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    INDEX idx_faculty_emp (emp_id),
    INDEX idx_faculty_dept (department_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- FACULTY-SUBJECT ASSIGNMENT (assign subjects & classes to faculty)
-- ---------------------------------------------------------------------------
CREATE TABLE faculty_subject_assignment (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    faculty_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    course_id INT UNSIGNED NOT NULL,
    semester INT UNSIGNED NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE KEY uk_fac_sub_course_sem_yr (faculty_id, subject_id, course_id, semester, academic_year),
    INDEX idx_fsa_faculty (faculty_id),
    INDEX idx_fsa_subject (subject_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- ATTENDANCE
-- ---------------------------------------------------------------------------
CREATE TABLE attendance (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    faculty_id INT UNSIGNED NOT NULL,
    att_date DATE NOT NULL,
    status ENUM('P','A','L') NOT NULL DEFAULT 'P',
    remarks VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    UNIQUE KEY uk_att_student_subject_date (student_id, subject_id, att_date),
    INDEX idx_att_student (student_id),
    INDEX idx_att_subject (subject_id),
    INDEX idx_att_date (att_date),
    INDEX idx_att_faculty (faculty_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- MARKS (internal + external, grades)
-- ---------------------------------------------------------------------------
CREATE TABLE marks (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    internal_marks DECIMAL(5,2) NULL,
    external_marks DECIMAL(5,2) NULL,
    total_marks DECIMAL(5,2) NULL,
    grade VARCHAR(5) NULL,
    exam_type VARCHAR(50) NULL,
    exam_session VARCHAR(30) NULL,
    published TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE KEY uk_marks_student_subject_session (student_id, subject_id, exam_session),
    INDEX idx_marks_student (student_id),
    INDEX idx_marks_subject (subject_id),
    INDEX idx_marks_published (published)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- FEE STRUCTURE (per course/semester)
-- ---------------------------------------------------------------------------
CREATE TABLE fee_structure (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id INT UNSIGNED NOT NULL,
    semester INT UNSIGNED NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    due_date DATE NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE KEY uk_fee_course_sem_yr (course_id, semester, academic_year),
    INDEX idx_fee_course (course_id)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- FEE PAYMENTS (student-wise)
-- ---------------------------------------------------------------------------
CREATE TABLE fee_payments (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL,
    fee_structure_id INT UNSIGNED NOT NULL,
    amount_paid DECIMAL(10,2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_mode VARCHAR(50) NULL,
    receipt_no VARCHAR(50) NULL UNIQUE,
    remarks VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (fee_structure_id) REFERENCES fee_structure(id) ON DELETE RESTRICT,
    INDEX idx_fp_student (student_id),
    INDEX idx_fp_structure (fee_structure_id),
    INDEX idx_fp_date (payment_date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- NOTICES
-- ---------------------------------------------------------------------------
CREATE TABLE notices (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id INT UNSIGNED NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category ENUM('Exam','Event','Holiday','General','Academic') NOT NULL DEFAULT 'General',
    target_role VARCHAR(50) NULL,
    is_published TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_notices_category (category),
    INDEX idx_notices_created (created_at)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- TIMETABLE
-- ---------------------------------------------------------------------------
CREATE TABLE timetable (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    faculty_id INT UNSIGNED NOT NULL,
    semester INT UNSIGNED NOT NULL,
    day_of_week TINYINT UNSIGNED NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room VARCHAR(50) NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    INDEX idx_tt_course (course_id),
    INDEX idx_tt_faculty (faculty_id),
    INDEX idx_tt_day (day_of_week)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- ATTENDANCE SESSIONS (QR-based, time-limited)
-- ---------------------------------------------------------------------------
CREATE TABLE attendance_sessions (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL UNIQUE,
    faculty_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    course_id INT UNSIGNED NOT NULL,
    semester INT UNSIGNED NOT NULL,
    date DATE NOT NULL,
    start_time DATETIME NOT NULL,
    expiry_time DATETIME NOT NULL,
    qr_token VARCHAR(500) NOT NULL,
    token_hash VARCHAR(255) NOT NULL UNIQUE,
    otp_code VARCHAR(10) NULL,
    otp_expiry DATETIME NULL,
    status ENUM('active', 'expired', 'completed') DEFAULT 'active',
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    ip_address VARCHAR(45) NULL,
    session_data JSON NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE KEY uk_session_date_faculty (subject_id, date, faculty_id),
    INDEX idx_session_id (session_id),
    INDEX idx_session_faculty (faculty_id),
    INDEX idx_session_subject (subject_id),
    INDEX idx_session_expiry (expiry_time),
    INDEX idx_session_status (status),
    INDEX idx_session_date (date)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- ATTENDANCE RECORDS (QR-based, with device & IP logging)
-- ---------------------------------------------------------------------------
CREATE TABLE attendance_records (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id INT UNSIGNED NOT NULL,
    student_id INT UNSIGNED NOT NULL,
    scan_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address VARCHAR(45) NULL,
    device_info VARCHAR(500) NULL,
    browser_info VARCHAR(255) NULL,
    latitude DECIMAL(10, 8) NULL,
    longitude DECIMAL(11, 8) NULL,
    accuracy FLOAT NULL,
    status ENUM('verified', 'flagged', 'rejected') DEFAULT 'verified',
    reason VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE KEY uk_record_session_student (session_id, student_id),
    INDEX idx_record_session (session_id),
    INDEX idx_record_student (student_id),
    INDEX idx_record_scan_time (scan_time),
    INDEX idx_record_status (status)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- IP WHITELIST (Campus IP ranges for WiFi restriction)
-- ---------------------------------------------------------------------------
CREATE TABLE ip_whitelist (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    ip_range_start VARCHAR(45) NOT NULL,
    ip_range_end VARCHAR(45) NOT NULL,
    description VARCHAR(255) NULL,
    is_active TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_ip_active (is_active)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- FACE VERIFICATION DATA (For advanced face recognition)
-- ---------------------------------------------------------------------------
CREATE TABLE face_verification (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL,
    face_encoding LONGBLOB NOT NULL,
    image_path VARCHAR(255) NULL,
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified TINYINT(1) DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE KEY uk_student_face (student_id),
    INDEX idx_student_verified (student_id, verified)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- ATTENDANCE AUDIT LOG (Security & Fraud detection)
-- ---------------------------------------------------------------------------
CREATE TABLE attendance_audit_log (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    session_id INT UNSIGNED NULL,
    student_id INT UNSIGNED NULL,
    event_type VARCHAR(50) NOT NULL,
    action VARCHAR(100) NOT NULL,
    ip_address VARCHAR(45) NULL,
    user_agent VARCHAR(500) NULL,
    details JSON NULL,
    flagged TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE SET NULL,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE SET NULL,
    INDEX idx_event_type (event_type),
    INDEX idx_flagged (flagged),
    INDEX idx_created (created_at)
) ENGINE=InnoDB;

CREATE TABLE chat_conversations (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    type ENUM('private','class','group') NOT NULL,
    subject_id INT UNSIGNED NULL,
    course_id INT UNSIGNED NULL,
    semester INT UNSIGNED NULL,
    title VARCHAR(255) NULL,
    created_by INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_chat_type (type),
    INDEX idx_chat_subject (subject_id),
    INDEX idx_chat_course_sem (course_id, semester)
) ENGINE=InnoDB;

CREATE TABLE chat_files (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    stored_path VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100) NULL,
    size_bytes INT UNSIGNED NOT NULL,
    uploaded_by INT UNSIGNED NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_chat_files_uploader (uploaded_by)
) ENGINE=InnoDB;

CREATE TABLE chat_messages (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT UNSIGNED NOT NULL,
    sender_id INT UNSIGNED NOT NULL,
    content TEXT NULL,
    message_type ENUM('text','file') NOT NULL DEFAULT 'text',
    file_id INT UNSIGNED NULL,
    status ENUM('sent','delivered','read') NOT NULL DEFAULT 'sent',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at DATETIME NULL,
    deleted_at DATETIME NULL,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES chat_files(id) ON DELETE SET NULL,
    INDEX idx_chat_msg_conv (conversation_id, created_at),
    INDEX idx_chat_msg_sender (sender_id),
    INDEX idx_chat_msg_status (status)
) ENGINE=InnoDB;

CREATE TABLE chat_conversation_members (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    role_in_conversation VARCHAR(50) NULL,
    last_read_message_id INT UNSIGNED NULL,
    last_read_at DATETIME NULL,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (last_read_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL,
    UNIQUE KEY uk_chat_member (conversation_id, user_id),
    INDEX idx_chat_member_user (user_id)
) ENGINE=InnoDB;

CREATE TABLE chat_message_status (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    message_id INT UNSIGNED NOT NULL,
    user_id INT UNSIGNED NOT NULL,
    status ENUM('sent','delivered','read') NOT NULL DEFAULT 'sent',
    status_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE KEY uk_chat_msg_user (message_id, user_id),
    INDEX idx_chat_status_user (user_id),
    INDEX idx_chat_status_status (status)
) ENGINE=InnoDB;

CREATE TABLE chat_user_presence (
    user_id INT UNSIGNED PRIMARY KEY,
    is_online TINYINT(1) DEFAULT 0,
    last_seen DATETIME NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_chat_presence_online (is_online)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- STUDENT ID CARDS (digital ID with QR)
-- ---------------------------------------------------------------------------
CREATE TABLE student_id_cards (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    student_id INT UNSIGNED NOT NULL UNIQUE,
    enrollment_no VARCHAR(50) NOT NULL,
    card_number VARCHAR(50) NOT NULL UNIQUE,
    qr_token VARCHAR(255) NOT NULL,
    qr_image_path VARCHAR(255) NULL,
    blood_group VARCHAR(10) NULL,
    valid_from DATE NOT NULL,
    valid_till DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    INDEX idx_idcard_enrollment (enrollment_no)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------------
-- EXAMS (exam dates & schedule per subject)
-- ---------------------------------------------------------------------------
CREATE TABLE exams (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    course_id INT UNSIGNED NOT NULL,
    subject_id INT UNSIGNED NOT NULL,
    semester INT UNSIGNED NOT NULL,
    exam_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    exam_type VARCHAR(50) NOT NULL,
    exam_session VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    INDEX idx_exams_course_sem_date (course_id, semester, exam_date),
    INDEX idx_exams_subject (subject_id),
    INDEX idx_exams_session (exam_session)
) ENGINE=InnoDB;

-- Sample exam schedule (can be adjusted per college)
INSERT INTO exams (course_id, subject_id, semester, exam_date, start_time, end_time, exam_type, exam_session)
SELECT
    c.id AS course_id,
    s.id AS subject_id,
    s.semester,
    DATE_ADD(CURDATE(), INTERVAL 7 DAY) AS exam_date,
    '10:00:00' AS start_time,
    '13:00:00' AS end_time,
    'End-Semester' AS exam_type,
    '2024-25-S1' AS exam_session
FROM subjects s
JOIN courses c ON c.id = s.course_id
WHERE s.semester = 1
LIMIT 5;

-- Admin user created via app seed (run: python seed_admin.py)
