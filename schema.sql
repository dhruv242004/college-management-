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

-- Admin user created via app seed (run: python seed_admin.py)
