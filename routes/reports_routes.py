"""Reports & analytics: student list, attendance, results, fees pending."""
from flask import Blueprint, render_template, request, send_file
from io import BytesIO
import csv
from auth import require_login, require_roles
from database import db_cursor

reports_bp = Blueprint("reports_bp", __name__)

ACAD_YEAR = "2024-25"


@reports_bp.route("/")
@require_login
@require_roles("admin", "faculty", "accountant")
def index():
    return render_template("reports/index.html")


@reports_bp.route("/students")
@require_login
@require_roles("admin", "faculty", "accountant")
def students_report():
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    export = request.args.get("export")  # csv | pdf
    sql = """
        SELECT s.enrollment_no, s.first_name, s.last_name, s.email, s.current_semester,
               c.name AS course_name, c.code AS course_code, d.name AS dept_name
        FROM students s
        JOIN courses c ON c.id = s.course_id
        JOIN departments d ON d.id = c.department_id
        WHERE 1=1
    """
    params = []
    if course_id:
        sql += " AND s.course_id = %s"
        params.append(course_id)
    if semester:
        sql += " AND s.current_semester = %s"
        params.append(semester)
    sql += " ORDER BY c.name, s.current_semester, s.enrollment_no"
    with db_cursor() as (conn, cur):
        cur.execute(sql, params or ())
        rows = cur.fetchall()
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    if export == "csv":
        buf = BytesIO()
        w = csv.writer(buf)
        w.writerow(["Enrollment", "First Name", "Last Name", "Email", "Semester", "Course", "Department"])
        for r in rows:
            w.writerow([
                r["enrollment_no"],
                r["first_name"],
                r["last_name"],
                r["email"],
                r["current_semester"],
                r["course_name"],
                r["dept_name"],
            ])
        buf.seek(0)
        return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="students_report.csv")
    return render_template(
        "reports/students.html",
        rows=rows,
        courses=courses,
        course_id=course_id,
        semester=semester,
    )


@reports_bp.route("/attendance")
@require_login
@require_roles("admin", "faculty")
def attendance_report():
    course_id = request.args.get("course_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    parts = []
    params = []
    if course_id:
        parts.append("st.course_id = %s")
        params.append(course_id)
    if subject_id:
        parts.append("a.subject_id = %s")
        params.append(subject_id)
    where = " AND " + " AND ".join(parts) if parts else ""
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT st.enrollment_no, st.first_name, st.last_name, st.current_semester, c.name AS course_name,
                   sub.name AS subject_name,
                   COUNT(a.id) AS total, SUM(CASE WHEN a.status = 'P' THEN 1 ELSE 0 END) AS present
            FROM students st
            JOIN courses c ON c.id = st.course_id
            JOIN attendance a ON a.student_id = st.id
            JOIN subjects sub ON sub.id = a.subject_id
            WHERE 1=1
            """ + where + """
            GROUP BY st.id, st.enrollment_no, st.first_name, st.last_name, st.current_semester, c.name, sub.id, sub.name
            ORDER BY st.enrollment_no, sub.name
            """,
            params or (),
        )
        rows = cur.fetchall()
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
        cur.execute("SELECT id, name, code FROM subjects ORDER BY name")
        subjects = cur.fetchall()
    return render_template(
        "reports/attendance.html",
        rows=rows,
        courses=courses,
        subjects=subjects,
        course_id=course_id,
        subject_id=subject_id,
    )


@reports_bp.route("/results")
@require_login
@require_roles("admin", "faculty")
def results_report():
    course_id = request.args.get("course_id", type=int)
    subject_id = request.args.get("subject_id", type=int)
    session_name = request.args.get("exam_session") or "2024-25-S1"
    sql = """
        SELECT st.enrollment_no, st.first_name, st.last_name, st.current_semester, c.name AS course_name,
               sub.name AS subject_name, sub.code AS subject_code, m.internal_marks, m.external_marks, m.total_marks, m.grade, m.created_at
        FROM students st
        JOIN courses c ON c.id = st.course_id
        JOIN marks m ON m.student_id = st.id
        JOIN subjects sub ON sub.id = m.subject_id
        WHERE m.exam_session = %s AND m.published = TRUE
    """
    params = [session_name]
    if course_id:
        sql += " AND st.course_id = %s"
        params.append(course_id)
    if subject_id:
        sql += " AND m.subject_id = %s"
        params.append(subject_id)
    sql += " ORDER BY st.enrollment_no, sub.name"
    with db_cursor() as (conn, cur):
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
        cur.execute("SELECT id, name, code FROM subjects ORDER BY name")
        subjects = cur.fetchall()
    return render_template(
        "reports/results.html",
        rows=rows,
        courses=courses,
        subjects=subjects,
        course_id=course_id,
        subject_id=subject_id,
    )


@reports_bp.route("/fees-pending")
@require_login
@require_roles("admin", "accountant")
def fees_pending_report():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT st.enrollment_no, st.first_name, st.last_name, st.current_semester, c.name AS course_name,
                   fs.amount, fs.due_date, fs.semester, fs.academic_year,
                   COALESCE(SUM(fp.amount_paid), 0) AS paid,
                   (fs.amount - COALESCE(SUM(fp.amount_paid), 0)) AS pending
            FROM students st
            JOIN courses c ON c.id = st.course_id
            JOIN fee_structure fs ON fs.course_id = st.course_id AND fs.semester = st.current_semester AND fs.academic_year = %s
            LEFT JOIN fee_payments fp ON fp.student_id = st.id AND fp.fee_structure_id = fs.id
            GROUP BY st.id, st.enrollment_no, st.first_name, st.last_name, st.current_semester, c.name, fs.id, fs.amount, fs.due_date, fs.semester, fs.academic_year
            HAVING (fs.amount - COALESCE(SUM(fp.amount_paid), 0)) > 0
            ORDER BY fs.due_date, st.enrollment_no
            """,
            (ACAD_YEAR,),
        )
        rows = cur.fetchall()
    return render_template("reports/fees_pending.html", rows=rows)
