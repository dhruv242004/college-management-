-- College Management System - PostgreSQL Schema

-- ---------------------------------------------------------------------------
-- ROLES
-- ---------------------------------------------------------------------------
CREATE TABLE roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_roles_name ON roles(name);

INSERT INTO roles (name) VALUES ('admin'), ('faculty'), ('student'), ('accountant');

-- ---------------------------------------------------------------------------
-- USERS
-- ---------------------------------------------------------------------------
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    role_id INTEGER NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    username VARCHAR(100) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE RESTRICT
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_role ON users(role_id);

-- ---------------------------------------------------------------------------
-- DEPARTMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE departments (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_dept_code ON departments(code);

-- ---------------------------------------------------------------------------
-- COURSES
-- ---------------------------------------------------------------------------
CREATE TABLE courses (
    id SERIAL PRIMARY KEY,
    department_id INTEGER NOT NULL,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    duration_years INTEGER NOT NULL DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT,
    UNIQUE (department_id, code)
);

CREATE INDEX idx_course_dept ON courses(department_id);

-- ---------------------------------------------------------------------------
-- SUBJECTS
-- ---------------------------------------------------------------------------
CREATE TABLE subjects (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    name VARCHAR(150) NOT NULL,
    code VARCHAR(30) NOT NULL,
    semester INTEGER NOT NULL,
    credits INTEGER NOT NULL DEFAULT 4,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT,
    UNIQUE (course_id, semester, code)
);

CREATE INDEX idx_subject_course ON subjects(course_id);
CREATE INDEX idx_subject_semester ON subjects(semester);

-- ---------------------------------------------------------------------------
-- STUDENTS
-- ---------------------------------------------------------------------------
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE,
    enrollment_no VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    date_of_birth DATE,
    gender VARCHAR(1) CHECK (gender IN ('M','F','O')),
    address TEXT,
    photo_path VARCHAR(255),
    course_id INTEGER NOT NULL,
    current_semester INTEGER NOT NULL DEFAULT 1,
    admission_date DATE,
    is_verified BOOLEAN DEFAULT FALSE,
    photo_change_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE RESTRICT
);

CREATE INDEX idx_students_enrollment ON students(enrollment_no);
CREATE INDEX idx_students_course ON students(course_id);
CREATE INDEX idx_students_semester ON students(current_semester);
CREATE INDEX idx_students_name ON students(first_name, last_name);

-- ---------------------------------------------------------------------------
-- FACULTY
-- ---------------------------------------------------------------------------
CREATE TABLE faculty (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE,
    emp_id VARCHAR(50) NOT NULL UNIQUE,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    email VARCHAR(255) NOT NULL,
    phone VARCHAR(20),
    department_id INTEGER NOT NULL,
    designation VARCHAR(100),
    joined_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (department_id) REFERENCES departments(id) ON DELETE RESTRICT
);

CREATE INDEX idx_faculty_emp ON faculty(emp_id);
CREATE INDEX idx_faculty_dept ON faculty(department_id);

-- ---------------------------------------------------------------------------
-- FACULTY-SUBJECT ASSIGNMENT
-- ---------------------------------------------------------------------------
CREATE TABLE faculty_subject_assignment (
    id SERIAL PRIMARY KEY,
    faculty_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (faculty_id, subject_id, course_id, semester, academic_year)
);

CREATE INDEX idx_fsa_faculty ON faculty_subject_assignment(faculty_id);
CREATE INDEX idx_fsa_subject ON faculty_subject_assignment(subject_id);

-- ---------------------------------------------------------------------------
-- ATTENDANCE
-- ---------------------------------------------------------------------------
CREATE TABLE attendance (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    att_date DATE NOT NULL,
    status VARCHAR(1) NOT NULL DEFAULT 'P' CHECK (status IN ('P','A','L')),
    remarks VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    UNIQUE (student_id, subject_id, att_date)
);

CREATE INDEX idx_att_student ON attendance(student_id);
CREATE INDEX idx_att_subject ON attendance(subject_id);
CREATE INDEX idx_att_date ON attendance(att_date);
CREATE INDEX idx_att_faculty ON attendance(faculty_id);

-- ---------------------------------------------------------------------------
-- MARKS
-- ---------------------------------------------------------------------------
CREATE TABLE marks (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    internal_marks DECIMAL(5,2),
    external_marks DECIMAL(5,2),
    total_marks DECIMAL(5,2),
    grade VARCHAR(5),
    exam_type VARCHAR(50),
    exam_session VARCHAR(30),
    published BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    UNIQUE (student_id, subject_id, exam_session)
);

CREATE INDEX idx_marks_student ON marks(student_id);
CREATE INDEX idx_marks_subject ON marks(subject_id);
CREATE INDEX idx_marks_published ON marks(published);

-- ---------------------------------------------------------------------------
-- FEE STRUCTURE
-- ---------------------------------------------------------------------------
CREATE TABLE fee_structure (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    due_date DATE,
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    UNIQUE (course_id, semester, academic_year)
);

CREATE INDEX idx_fee_course ON fee_structure(course_id);

-- ---------------------------------------------------------------------------
-- FEE PAYMENTS
-- ---------------------------------------------------------------------------
CREATE TABLE fee_payments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    fee_structure_id INTEGER NOT NULL,
    amount_paid DECIMAL(10,2) NOT NULL,
    payment_date DATE NOT NULL,
    payment_mode VARCHAR(50),
    receipt_no VARCHAR(50) UNIQUE,
    remarks VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (fee_structure_id) REFERENCES fee_structure(id) ON DELETE RESTRICT
);

CREATE INDEX idx_fp_student ON fee_payments(student_id);
CREATE INDEX idx_fp_structure ON fee_payments(fee_structure_id);
CREATE INDEX idx_fp_date ON fee_payments(payment_date);

-- ---------------------------------------------------------------------------
-- NOTICES
-- ---------------------------------------------------------------------------
CREATE TABLE notices (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(20) NOT NULL DEFAULT 'General' CHECK (category IN ('Exam','Event','Holiday','General','Academic')),
    target_role VARCHAR(50),
    is_published BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_notices_category ON notices(category);
CREATE INDEX idx_notices_created ON notices(created_at);

-- ---------------------------------------------------------------------------
-- TIMETABLE
-- ---------------------------------------------------------------------------
CREATE TABLE timetable (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    faculty_id INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    room VARCHAR(50),
    academic_year VARCHAR(20) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE
);

CREATE INDEX idx_tt_course ON timetable(course_id);
CREATE INDEX idx_tt_faculty ON timetable(faculty_id);
CREATE INDEX idx_tt_day ON timetable(day_of_week);

-- ---------------------------------------------------------------------------
-- ATTENDANCE SESSIONS
-- ---------------------------------------------------------------------------
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
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'expired', 'completed')),
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
);

CREATE INDEX idx_session_id_key ON attendance_sessions(session_id);
CREATE INDEX idx_session_faculty ON attendance_sessions(faculty_id);
CREATE INDEX idx_session_subject ON attendance_sessions(subject_id);
CREATE INDEX idx_session_expiry ON attendance_sessions(expiry_time);
CREATE INDEX idx_session_status ON attendance_sessions(status);
CREATE INDEX idx_session_date ON attendance_sessions(date);

-- ---------------------------------------------------------------------------
-- ATTENDANCE RECORDS
-- ---------------------------------------------------------------------------
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
    status VARCHAR(20) DEFAULT 'verified' CHECK (status IN ('verified', 'flagged', 'rejected')),
    reason VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES attendance_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE (session_id, student_id)
);

CREATE INDEX idx_record_session ON attendance_records(session_id);
CREATE INDEX idx_record_student ON attendance_records(student_id);
CREATE INDEX idx_record_scan_time ON attendance_records(scan_time);
CREATE INDEX idx_record_status ON attendance_records(status);

-- ---------------------------------------------------------------------------
-- IP WHITELIST
-- ---------------------------------------------------------------------------
CREATE TABLE ip_whitelist (
    id SERIAL PRIMARY KEY,
    ip_range_start VARCHAR(45) NOT NULL,
    ip_range_end VARCHAR(45) NOT NULL,
    description VARCHAR(255),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_ip_active ON ip_whitelist(is_active);

-- ---------------------------------------------------------------------------
-- FACE VERIFICATION DATA
-- ---------------------------------------------------------------------------
CREATE TABLE face_verification (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    face_encoding BYTEA NOT NULL,
    image_path VARCHAR(255),
    captured_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    verified BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE (student_id)
);

CREATE INDEX idx_student_verified ON face_verification(student_id, verified);

-- ---------------------------------------------------------------------------
-- ATTENDANCE AUDIT LOG
-- ---------------------------------------------------------------------------
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
);

CREATE INDEX idx_event_type ON attendance_audit_log(event_type);
CREATE INDEX idx_flagged ON attendance_audit_log(flagged);
CREATE INDEX idx_created ON attendance_audit_log(created_at);

-- ---------------------------------------------------------------------------
-- CHAT CONVERSATIONS
-- ---------------------------------------------------------------------------
CREATE TABLE chat_conversations (
    id SERIAL PRIMARY KEY,
    type VARCHAR(10) NOT NULL CHECK (type IN ('private','class','group')),
    subject_id INTEGER,
    course_id INTEGER,
    semester INTEGER,
    title VARCHAR(255),
    created_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE SET NULL,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_type ON chat_conversations(type);
CREATE INDEX idx_chat_subject ON chat_conversations(subject_id);
CREATE INDEX idx_chat_course_sem ON chat_conversations(course_id, semester);

-- ---------------------------------------------------------------------------
-- CHAT FILES
-- ---------------------------------------------------------------------------
CREATE TABLE chat_files (
    id SERIAL PRIMARY KEY,
    stored_path VARCHAR(255) NOT NULL,
    original_name VARCHAR(255) NOT NULL,
    mime_type VARCHAR(100),
    size_bytes INTEGER NOT NULL,
    uploaded_by INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploaded_by) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_files_uploader ON chat_files(uploaded_by);

-- ---------------------------------------------------------------------------
-- CHAT MESSAGES
-- ---------------------------------------------------------------------------
CREATE TABLE chat_messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    sender_id INTEGER NOT NULL,
    content TEXT,
    message_type VARCHAR(10) NOT NULL DEFAULT 'text' CHECK (message_type IN ('text','file')),
    file_id INTEGER,
    status VARCHAR(10) NOT NULL DEFAULT 'sent' CHECK (status IN ('sent','delivered','read')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    edited_at TIMESTAMP,
    deleted_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (file_id) REFERENCES chat_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_chat_msg_conv ON chat_messages(conversation_id, created_at);
CREATE INDEX idx_chat_msg_sender ON chat_messages(sender_id);
CREATE INDEX idx_chat_msg_status ON chat_messages(status);

-- ---------------------------------------------------------------------------
-- CHAT CONVERSATION MEMBERS
-- ---------------------------------------------------------------------------
CREATE TABLE chat_conversation_members (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role_in_conversation VARCHAR(50),
    last_read_message_id INTEGER,
    last_read_at TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES chat_conversations(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (last_read_message_id) REFERENCES chat_messages(id) ON DELETE SET NULL,
    UNIQUE (conversation_id, user_id)
);

CREATE INDEX idx_chat_member_user ON chat_conversation_members(user_id);

-- ---------------------------------------------------------------------------
-- CHAT MESSAGE STATUS
-- ---------------------------------------------------------------------------
CREATE TABLE chat_message_status (
    id SERIAL PRIMARY KEY,
    message_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'sent' CHECK (status IN ('sent','delivered','read')),
    status_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (message_id) REFERENCES chat_messages(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (message_id, user_id)
);

CREATE INDEX idx_chat_status_user ON chat_message_status(user_id);
CREATE INDEX idx_chat_status_status_val ON chat_message_status(status);

-- ---------------------------------------------------------------------------
-- CHAT USER PRESENCE
-- ---------------------------------------------------------------------------
CREATE TABLE chat_user_presence (
    user_id INTEGER PRIMARY KEY,
    is_online BOOLEAN DEFAULT FALSE,
    last_seen TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX idx_chat_presence_online ON chat_user_presence(is_online);

-- ---------------------------------------------------------------------------
-- STUDENT ID CARDS
-- ---------------------------------------------------------------------------
CREATE TABLE student_id_cards (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL UNIQUE,
    enrollment_no VARCHAR(50) NOT NULL,
    card_number VARCHAR(50) NOT NULL UNIQUE,
    qr_token VARCHAR(255) NOT NULL,
    qr_image_path VARCHAR(255),
    blood_group VARCHAR(10),
    valid_from DATE NOT NULL,
    valid_till DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE INDEX idx_idcard_enrollment ON student_id_cards(enrollment_no);

-- ---------------------------------------------------------------------------
-- EXAMS
-- ---------------------------------------------------------------------------
CREATE TABLE exams (
    id SERIAL PRIMARY KEY,
    course_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    semester INTEGER NOT NULL,
    exam_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    exam_type VARCHAR(50) NOT NULL,
    exam_session VARCHAR(30) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

CREATE INDEX idx_exams_course_sem_date ON exams(course_id, semester, exam_date);
CREATE INDEX idx_exams_subject ON exams(subject_id);
CREATE INDEX idx_exams_session ON exams(exam_session);

-- ---------------------------------------------------------------------------
-- PAYMENTS (Mock Payment Gateway)
-- ---------------------------------------------------------------------------
CREATE TABLE payments (
    id SERIAL PRIMARY KEY,
    student_id INTEGER NOT NULL,
    order_id VARCHAR(100) NOT NULL UNIQUE,
    payment_id VARCHAR(100),
    amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','success','failed')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_payments_student ON payments(student_id);
CREATE INDEX idx_payments_status ON payments(status);

-- ---------------------------------------------------------------------------
-- ONLINE EXAMS
-- ---------------------------------------------------------------------------
CREATE TABLE online_exams (
    id SERIAL PRIMARY KEY,
    faculty_id INTEGER NOT NULL,
    subject_id INTEGER NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL,
    min_attendance_percentage DECIMAL(5,2) DEFAULT 0,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculty(id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(id) ON DELETE CASCADE
);

CREATE INDEX idx_oe_faculty ON online_exams(faculty_id);
CREATE INDEX idx_oe_subject ON online_exams(subject_id);
CREATE INDEX idx_oe_start ON online_exams(start_time);

-- ---------------------------------------------------------------------------
-- EXAM QUESTIONS
-- ---------------------------------------------------------------------------
CREATE TABLE exam_questions (
    id SERIAL PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    question_text TEXT NOT NULL,
    question_type VARCHAR(20) NOT NULL CHECK (question_type IN ('mcq', 'true_false', 'short_answer')),
    options JSONB,
    correct_answer TEXT,
    marks INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE
);

CREATE INDEX idx_eq_exam ON exam_questions(exam_id);

-- ---------------------------------------------------------------------------
-- STUDENT EXAM ATTEMPTS
-- ---------------------------------------------------------------------------
CREATE TABLE student_exam_attempts (
    id SERIAL PRIMARY KEY,
    exam_id INTEGER NOT NULL,
    student_id INTEGER NOT NULL,
    status VARCHAR(20) DEFAULT 'started' CHECK (status IN ('started', 'submitted', 'graded')),
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    submit_time TIMESTAMP,
    score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (exam_id) REFERENCES online_exams(id) ON DELETE CASCADE,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    UNIQUE (exam_id, student_id)
);

CREATE INDEX idx_sea_exam_student ON student_exam_attempts(exam_id, student_id);

-- ---------------------------------------------------------------------------
-- STUDENT ANSWERS
-- ---------------------------------------------------------------------------
CREATE TABLE student_answers (
    id SERIAL PRIMARY KEY,
    attempt_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    answer_text TEXT,
    is_correct BOOLEAN DEFAULT FALSE,
    marks_obtained DECIMAL(5,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attempt_id) REFERENCES student_exam_attempts(id) ON DELETE CASCADE,
    FOREIGN KEY (question_id) REFERENCES exam_questions(id) ON DELETE CASCADE,
    UNIQUE (attempt_id, question_id)
);

-- Sample data for exams (PostgreSQL syntax)
INSERT INTO exams (course_id, subject_id, semester, exam_date, start_time, end_time, exam_type, exam_session)
SELECT
    c.id AS course_id,
    s.id AS subject_id,
    s.semester,
    CURRENT_DATE + INTERVAL '7 days' AS exam_date,
    '10:00:00' AS start_time,
    '13:00:00' AS end_time,
    'End-Semester' AS exam_type,
    '2024-25-S1' AS exam_session
FROM subjects s
JOIN courses c ON c.id = s.course_id
WHERE s.semester = 1
LIMIT 5;
