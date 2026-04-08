## College Management System

Role-based College Management System built with **Flask**, **MySQL**, **HTML/CSS/JavaScript**, and **Bootstrap 5**, featuring:

- Modern **3D / glassmorphism UI**
- **Auto-generated enrollment numbers**
- **QR-based attendance system** with security & analytics
- Separate dashboards for **Admin**, **Faculty**, **Student**, and **Accountant**

This README consolidates all previous docs (`QUICKSTART.md`, `QUICK_REFERENCE.md`, `QR_ATTENDANCE_GUIDE.md`, `IMPLEMENTATION_SUMMARY.md`, `API_REFERENCE.md`, `CHANGES_SUMMARY.md`, `BACKGROUND_COLOR_REDESIGN.md`, `ATTENDANCE_FEES_STYLING_FIX.md`, `QUICK_SETUP.md`) into a **single file**.

---

### Contents

1. [Features](#features)
2. [Tech Stack](#tech-stack)
3. [Quick Start (30 seconds)](#quick-start-30-seconds)
4. [Full Setup & Useful Commands](#full-setup--useful-commands)
5. [Enrollment Number System](#enrollment-number-system)
6. [QR Attendance System](#qr-attendance-system)
7. [UI Theme & Design](#ui-theme--design)
8. [Project Structure](#project-structure)
9. [Database Design](#database-design)
10. [Deployment & Maintenance Checklist](#deployment--maintenance-checklist)
11. [Default Logins & Roles](#default-logins--roles)
12. [License](#license)

---

### Features

- **Authentication & Security**
  - Login via username/email or **enrollment number** (students)
  - Werkzeug password hashing, Flask sessions
  - Role-based access control (Admin, Faculty, Student, Accountant)
  - CSRF-safe forms and basic protections against SQLi/XSS

- **Student Management**
  - Auto-generated enrollment numbers (course + year + sequence)
  - CRUD operations, photos, personal & academic details
  - Course/semester/department assignment and search

- **Faculty & Academic**
  - Faculty CRUD and subject/class assignment
  - Departments, courses, subjects (per semester with credits)
  - Timetable for course-wise, faculty-wise, and student views

- **Attendance**
  - Classic date-wise attendance by faculty
  - **QR-based attendance** with:
    - Time-limited QR sessions
    - Encrypted tokens
    - Device/IP/geolocation logging
    - Fraud detection dashboard
    - Analytics (charts & trends)

- **Exams & Results**
  - Internal / external marks, auto totals and grades
  - Publish/unpublish controls
  - Read-only result views for students

- **Fees**
  - Fee structure per course/semester
  - Paid/pending tracking, receipts, due dates
  - Accountant and admin access

- **Notices & Reports**
  - Notices (Exam, Event, Holiday, General, Academic)
  - Reports for attendance, results, fees, students
  - CSV export for student lists

- **Modern UI**
  - 3D animated cards, glass panels, gradients
  - Dark theme with blue/purple accents
  - Animated dashboard statistics and charts

---

### Tech Stack

- **Backend**: Python 3.x, Flask 3.x
- **Database**: MySQL 8.x
- **Auth**: Werkzeug `generate_password_hash` / `check_password_hash`, Flask sessions
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Chart.js

---

### Quick Start (30 seconds)

1. **Start MySQL**

```bash
# Windows
net start MySQL80
```

2. **Install dependencies**

```bash
cd "College Management System"
pip install -r requirements.txt
```

3. **Create database & seed admin**

```bash
mysql -u root -p < schema.sql
python seed_admin.py
```

4. **Run the app**

```bash
python app.py
```

Open `http://localhost:5000` and log in with:

- **Admin username**: `admin`
- **Password**: `admin123` (change in production)

If login loops back to the login page, see **“Login issues”** in the next section.

---

### Full Setup & Useful Commands

#### Prerequisites

- Python **3.10+**
- MySQL **8.x**
- `pip`

#### Environment & dependencies

```bash
cd "College Management System"
pip install -r requirements.txt
```

#### Database setup

```bash
mysql -u root -p < schema.sql
python seed_admin.py
```

Update `config.py` with your DB settings:

- `MYSQL_HOST` (default: `localhost`)
- `MYSQL_USER` (default: `root`)
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE` (default: `college_management`)
- `MYSQL_PORT` (default: `3306`)

#### Run / stop application

```bash
python app.py        # start
Ctrl + C             # stop
```

Open in browser: `http://localhost:5000`

#### Common database commands

```bash
mysql -u root -p college_management
SELECT enrollment_no, first_name, email FROM students;
SELECT username, email, role_id FROM users;
```

#### Login issues (looping back to login)

- Check the alert on the login page:
  - **“Database error…”** → MySQL down or schema missing  
    Fix: start MySQL, run `mysql -u root -p < schema.sql`, then `python seed_admin.py`.
  - **“Invalid username or password”** → Wrong or missing admin user  
    Fix: run `python seed_admin.py` again.
- Verify `config.py` has correct MySQL credentials and database name.

---

### Enrollment Number System

Students get **auto-generated enrollment numbers** based on course and year.

- **Format**: `{COURSE_CODE}{YEAR}{SEQUENCE}`
  - Examples: `BCA2025001`, `BCA2025002`, `MCA2025001`
- Generated during registration and stored as `students.enrollment_no`
- Used as:
  - Student identifier in the database
  - Default **username** for student login

Algorithm (simplified):

```python
1. Read course code (e.g. BCA)
2. Read current year (e.g. 2025)
3. Prefix = "BCA2025"
4. Find highest existing enrollment starting with prefix
5. Increment last sequence → BCA2025001, BCA2025002, ...
```

Benefits:

- No manual enrollment entry
- Consistent format across system
- Easy to search and filter by course/year

---

### QR Attendance System

The system includes a **secure, production-ready QR-based attendance module** for real-time attendance with fraud detection.

#### Overview

- Faculty generates **time-limited QR codes** per lecture
- Students scan QR using their device camera or enter a token
- System validates:
  - QR token (encrypted and time-limited)
  - Duplicate scans
  - IP / device / optional geolocation
- Admin can monitor **fraud attempts** and analytics

#### Key backend components

- `qr_service.py`
  - Generates encrypted QR tokens
  - Manages sessions and expiry
  - Validates scans and marks attendance
- `security_service.py`
  - Optional geolocation verification
  - IP whitelist and device fingerprinting
  - Fraud/audit logging and anomaly detection
- `routes/attendance_routes.py`
  - Faculty, student, and admin endpoints for QR attendance

#### Important database tables (from `schema.sql`)

- `attendance_sessions`
  - One row per QR session (class)
  - Fields: `session_id`, `faculty_id`, `subject_id`, `course_id`, `semester`, `date`, `start_time`, `expiry_time`, `qr_token`, `token_hash`, `status`, `latitude`, `longitude`, `ip_address`
- `attendance_records`
  - Individual student scans with device info
  - Prevents duplicates via unique `(session_id, student_id)`
- `attendance_audit_log`
  - Stores suspicious events and security logs
- `ip_whitelist`, `face_verification`
  - Optional IP-range and face recognition support

#### Core flows by role

- **Faculty**
  - `GET /attendance/qr/generate` – form to choose subject/course/semester + duration
  - `POST /attendance/qr/generate` – creates QR session and shows QR with countdown
  - `GET /attendance/qr/session/<session_id>` – live session view
  - `GET /attendance/qr/api/session/<id>/status` – AJAX status (remaining time, count)
  - `GET /attendance/qr/api/session/<id>/attendance` – AJAX list of students
  - `POST /attendance/qr/api/session/<id>/close` – close the session

- **Student**
  - `GET /attendance/qr/scan` – camera-based QR scanner with manual token fallback
  - `POST /attendance/qr/scan` – submits token (+ optional geolocation) to mark attendance
  - `GET /attendance/my` – view personal attendance summary

- **Admin**
  - `GET /attendance/fraud-detection` – fraud attempts and security events
  - `GET /attendance/analytics` – global analytics dashboard

#### Security highlights

- Encrypted, time-limited QR tokens using `itsdangerous`
- Unique `(session_id, student_id)` to block duplicate attendance
- Logs IP, user-agent, and optional latitude/longitude for each scan
- Optional:
  - Geofence around campus (via `COLLEGE_LATITUDE` / `COLLEGE_LONGITUDE`)
  - Campus IP ranges via `ip_whitelist`
  - Face recognition integration

Configuration lives in `config.py`, for example:

```python
QR_VALIDITY_MINUTES = 10
QR_MIN_DURATION = 5
QR_MAX_DURATION = 30
COLLEGE_LATITUDE = 28.6139
COLLEGE_LONGITUDE = 77.2090
GEOFENCE_RADIUS_KM = 1.0
REQUIRE_GEOLOCATION = False
REQUIRE_IP_WHITELIST = False
REQUIRE_FACE_VERIFICATION = False
```

---

### UI Theme & Design

The UI uses a **dark, glassmorphic, 3D-inspired design**:

- Dark cards: `rgba(15, 23, 42, 0.8)`
- Slate backgrounds: `rgba(30, 41, 59, 0.6)`
- Primary accent: `#6366f1` (indigo)
- Text: soft gray `#cbd5e1` (instead of pure white)
- Purple highlights: `#a5b4fc`

Enhancements (from design docs):

- **Login & dashboard**
  - 3D animated cards, floating shapes, gradients, glow effects
  - Role-based dashboard cards with tilt and hover animations
- **Attendance & fees pages**
  - Dark themed tables with subtle row backgrounds
  - Chart.js configured with indigo/purple palette and readable grid lines
  - Color-coded values (green for paid, orange for pending, etc.)

These styles are mainly defined in `static/css/style.css` and used across templates in `templates/`.

---

### Deployment (Render / PostgreSQL)

1. **Connect to GitHub**: Link your repository to a Render **Web Service**.
2. **Environment Variables**: Set the following in the Render dashboard:
   - `FLASK_ENV`: `production`
   - `DATABASE_URL`: Your Render PostgreSQL External/Internal Database URL
   - `SECRET_KEY`: A random secure string
3. **Build Command**: `pip install -r requirements.txt`
4. **Start Command**: `gunicorn --worker-class eventlet -w 1 -b 0.0.0.0:$PORT app:app`

**Note**: The system automatically detects PostgreSQL when `DATABASE_URL` is present and switches from MySQL to PostgreSQL.

---

### Project Structure

```text
├── app.py                 # Flask app, dashboard, blueprint registration
├── config.py              # Configuration (DB, QR, security, college info)
├── college_config.py      # College branding & highlight stats
├── database.py            # MySQL connection, db_cursor context manager
├── auth.py                # Login, logout, session, role decorators
├── seed_admin.py          # Create default admin user
├── qr_service.py          # QR generation & validation
├── security_service.py    # Advanced security & fraud detection
├── schema.sql             # MySQL schema (tables, FKs, indexes)
├── requirements.txt
├── routes/
│   ├── auth_routes.py
│   ├── student_routes.py
│   ├── faculty_routes.py
│   ├── academic_routes.py
│   ├── attendance_routes.py
│   ├── exam_routes.py
│   ├── fees_routes.py
│   ├── notice_routes.py
│   ├── timetable_routes.py
│   ├── reports_routes.py
│   └── chat_routes.py          # if enabled
├── templates/              # Jinja2 HTML templates
│   ├── auth/
│   ├── attendance/
│   ├── fees/
│   ├── students/
│   ├── timetable/
│   └── dashboard.html
└── static/
    ├── css/style.css
    ├── js/
    └── uploads/
```

---

### Database Design

- **Core tables**
  - `roles`, `users`
  - `departments`, `courses`, `subjects`
  - `students`, `faculty`, `faculty_subject_assignment`
  - `attendance` (classic), `attendance_sessions`, `attendance_records`
  - `marks`, `fee_structure`, `fee_payments`
  - `notices`, `timetable`

- **Constraints & indexing**
  - Primary keys and foreign keys across all relations
  - Unique constraints (e.g. `students.enrollment_no`, one attendance per student/subject/date)
  - Indexes on frequently filtered columns (course, semester, subject, dates)

The QR attendance schema is described in more detail in the **QR Attendance System** section above.

---

### Deployment & Maintenance Checklist

Before deployment:

- [ ] Install dependencies: `pip install -r requirements.txt`
- [ ] Apply schema: `mysql -u root -p < schema.sql`
- [ ] Configure `config.py` (DB, QR, security, college location)
- [ ] Run `python seed_admin.py` and change default admin password

Test flows:

- [ ] Admin login and dashboard
- [ ] Student registration + enrollment generation
- [ ] Student login with enrollment number
- [ ] Classic attendance and QR attendance
- [ ] Fees, exams, notices, timetable views
- [ ] QR generation, scan, expiry, and fraud logs

Ongoing maintenance:

- Regular database backups (`mysqldump`)
- Monitor QR fraud/audit logs
- Review performance and indexes

---

### Default Logins & Roles

| Role   | Username | Password  |
|--------|----------|-----------|
| Admin  | admin    | admin123  |

Create additional faculty/students via Admin screens or direct SQL inserts as needed.

---

### License

MIT
"# college_management" 
