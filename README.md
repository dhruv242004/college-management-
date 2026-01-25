# College Management System

A role-based College Management System built with **Flask**, **MySQL**, **HTML/CSS/JavaScript**, and **Bootstrap 5**. It supports **Admin**, **Faculty**, **Student**, and **Accountant** roles with separate dashboards, session-based auth, and restricted access.

## Features

- **Authentication**: Secure login (username/email + password), Werkzeug password hashing, session management, role-based authorization, logout & session expiry
- **Student management**: Add/update/delete, auto-generated enrollment, profile (photo, personal + academic), course/semester/department, search
- **Faculty management**: CRUD, assign subjects & classes, view assigned students, upload internal marks, attendance access
- **Academic**: Departments, courses (per department), subjects (per semester, credits), relational design with FKs
- **Attendance**: Faculty marks date-wise, no duplicate entry, student view & percentage, monthly/subject-wise reports
- **Exams & results**: Subject-wise marks (internal + external), auto total & grade, publish/unpublish, student read-only view
- **Fees**: Fee structure per course/semester, paid/pending, receipts, due-date tracking, admin & accountant access
- **Notices**: Admin/faculty post; students view; categories (Exam, Event, Holiday, General, Academic)
- **Timetable**: Course-wise, faculty-wise, student timetable view
- **Reports**: Students by course/semester, attendance, results, fees pending; CSV export for students

## Tech Stack

- **Backend**: Python 3.x, Flask 3.x
- **Database**: MySQL 8.x
- **Auth**: Werkzeug `generate_password_hash` / `check_password_hash`, Flask session
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons, Chart.js (attendance)

## Setup

### 1. Prerequisites

- Python 3.10+
- MySQL 8.x
- pip

### 2. Clone & install

```bash
cd "College Management System"
pip install -r requirements.txt
```

### 3. Database

Create database and load schema:

```bash
mysql -u root -p < schema.sql
```

Update `config.py` (or env) with your MySQL settings:

- `MYSQL_HOST` (default: localhost)
- `MYSQL_USER` (default: root)
- `MYSQL_PASSWORD`
- `MYSQL_DATABASE` (default: college_management)
- `MYSQL_PORT` (default: 3306)

### 4. Seed admin

```bash
python seed_admin.py
```

Creates admin user: **username** `admin`, **password** `admin123`. Change in production.

### 5. Run

```bash
python app.py
```

Open **http://127.0.0.1:5000**. Log in as `admin` / `admin123`.

### Login stuck / always shows login page

1. **Check the red alert** on the login page after submitting. It will show either:
   - **"Database error..."** → MySQL is not running, or schema/DB not set up. Start MySQL, run `mysql -u root -p < schema.sql`, then `python seed_admin.py`.
   - **"Invalid username or password"** → Admin user missing or wrong credentials. Run `python seed_admin.py` to create `admin` / `admin123`.
2. Ensure `config.py` (or env) has correct **MYSQL_HOST**, **MYSQL_USER**, **MYSQL_PASSWORD**, **MYSQL_DATABASE**.

## Project structure

```
├── app.py              # Flask app, dashboard, blueprint registration
├── config.py           # Configuration
├── database.py         # MySQL connection, db_cursor context manager
├── auth.py             # Login, logout, session, role decorators
├── seed_admin.py       # Create default admin
├── schema.sql          # MySQL schema (tables, FKs, indexes)
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
│   └── reports_routes.py
├── templates/          # Jinja2 HTML
└── static/
    ├── css/style.css
    ├── js/main.js
    └── uploads/        # Student photos
```

## Database design

- **Tables**: `roles`, `users`, `departments`, `courses`, `subjects`, `students`, `faculty`, `faculty_subject_assignment`, `attendance`, `marks`, `fee_structure`, `fee_payments`, `notices`, `timetable`
- **Constraints**: Primary keys, foreign keys, unique keys (e.g. enrollment_no, att student+subject+date)
- **Normalization**: 3NF; indexes on commonly filtered columns

## SQL usage

- **CRUD**: INSERT/UPDATE/DELETE for students, faculty, courses, subjects, fees, notices, timetable, etc.
- **JOINs**: Students with course/department; faculty with department; attendance/results/fees with students, subjects, courses; reports use JOINs throughout.

## Default login

| Role    | Username | Password  |
|---------|----------|-----------|
| Admin   | admin    | admin123  |

Create faculty/student logins via Admin (e.g. faculty form “Create login”, or link existing students to users).

## License

MIT.
