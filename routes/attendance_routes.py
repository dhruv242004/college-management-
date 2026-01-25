"""Attendance: mark, view, reports, validation (no duplicate)."""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor

attendance_bp = Blueprint("attendance_bp", __name__)

ACAD_YEAR = "2024-25"


@attendance_bp.route("/")
@require_login
@require_roles("admin", "faculty")
def index():
    user = get_current_user()
    fid = user.get("extra_id") if user.get("role_name") == "faculty" else None
    with db_cursor() as (conn, cur):
        if fid:
            cur.execute(
                """
                SELECT fsa.id, fsa.subject_id, fsa.course_id, fsa.semester, s.name AS subject_name, c.name AS course_name
                FROM faculty_subject_assignment fsa
                JOIN subjects s ON s.id = fsa.subject_id
                JOIN courses c ON c.id = fsa.course_id
                WHERE fsa.faculty_id = %s AND fsa.academic_year = %s
                ORDER BY fsa.semester, s.name
                """,
                (fid, ACAD_YEAR),
            )
        else:
            cur.execute(
                """
                SELECT s.id AS subject_id, c.id AS course_id, s.semester, s.name AS subject_name, c.name AS course_name
                FROM subjects s
                JOIN courses c ON c.id = s.course_id
                ORDER BY c.name, s.semester
                """
            )
        assignments = cur.fetchall()
    return render_template("attendance/index.html", assignments=assignments, is_faculty=bool(fid))


@attendance_bp.route("/mark", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def mark():
    user = get_current_user()
    fid = user.get("extra_id") if user.get("role_name") == "faculty" else None
    subject_id = request.args.get("subject_id", type=int)
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    att_date = request.args.get("date") or request.form.get("att_date") or str(date.today())
    if not all([subject_id, course_id, semester]):
        flash("Subject, course, and semester are required.", "danger")
        return redirect(url_for("attendance_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM subjects WHERE id = %s",
            (subject_id,),
        )
        subj = cur.fetchone()
        cur.execute(
            """
            SELECT s.id, s.enrollment_no, s.first_name, s.last_name
            FROM students s
            WHERE s.course_id = %s AND s.current_semester = %s
            ORDER BY s.enrollment_no
            """,
            (course_id, semester),
        )
        students = cur.fetchall()
        cur.execute(
            """
            SELECT a.student_id, a.status
            FROM attendance a
            WHERE a.subject_id = %s AND a.att_date = %s
            """,
            (subject_id, att_date),
        )
        existing = {r["student_id"]: r["status"] for r in cur.fetchall()}
    if not subj:
        flash("Subject not found.", "danger")
        return redirect(url_for("attendance_bp.index"))
    faculty_id = fid
    if not faculty_id:
        with db_cursor() as (conn, cur):
            cur.execute("SELECT id FROM faculty LIMIT 1")
            r = cur.fetchone()
            faculty_id = r["id"] if r else None
    if not faculty_id:
        flash("No faculty available to mark attendance.", "danger")
        return redirect(url_for("attendance_bp.index"))
    if request.method == "POST":
        if existing:
            flash("Attendance already marked for this date. No duplicate entry.", "warning")
            return redirect(url_for("attendance_bp.mark", subject_id=subject_id, course_id=course_id, semester=semester, date=att_date))
        for s in students:
            key = f"att_{s['id']}"
            status = request.form.get(key)
            if not status:
                continue
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO attendance (student_id, subject_id, faculty_id, att_date, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (s["id"], subject_id, faculty_id, att_date, status),
                )
        flash("Attendance saved.", "success")
        return redirect(url_for("attendance_bp.index"))
    return render_template(
        "attendance/mark.html",
        subject=subj,
        students=students,
        att_date=att_date,
        existing=existing,
    )


@attendance_bp.route("/my")
@require_login
@require_roles("student")
def my_attendance():
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.id, s.name, s.code
            FROM subjects s
            JOIN students st ON st.course_id = s.course_id AND st.current_semester = s.semester
            WHERE st.id = %s
            ORDER BY s.semester, s.name
            """,
            (sid,),
        )
        subjects = cur.fetchall()
    rows = []
    for sub in subjects:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status = 'P' THEN 1 ELSE 0 END) AS present
                FROM attendance
                WHERE student_id = %s AND subject_id = %s
                """,
                (sid, sub["id"]),
            )
            r = cur.fetchone()
        total = r["total"] or 0
        present = r["present"] or 0
        pct = (present / total * 100) if total else 0
        rows.append(
            {
                "subject": sub,
                "total": total,
                "present": present,
                "percent": round(pct, 1),
            }
        )
    return render_template("attendance/my.html", stats=rows)


@attendance_bp.route("/report")
@require_login
@require_roles("admin", "faculty")
def report():
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    subject_id = request.args.get("subject_id", type=int)
    month = request.args.get("month")
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses ORDER BY name"
        )
        courses = cur.fetchall()
        cur.execute(
            "SELECT id, name, code, course_id, semester FROM subjects ORDER BY course_id, semester"
        )
        subjects = cur.fetchall()
    filters = []
    params = []
    if course_id:
        filters.append("st.course_id = %s")
        params.append(course_id)
    if semester:
        filters.append("st.current_semester = %s")
        params.append(semester)
    if subject_id:
        filters.append("a.subject_id = %s")
        params.append(subject_id)
    if month:
        filters.append("DATE_FORMAT(a.att_date, '%%Y-%%m') = %s")
        params.append(month)
    where = " AND " + " AND ".join(filters) if filters else ""
    with db_cursor() as (conn, cur):
        cur.execute(
            f"""
            SELECT st.id, st.enrollment_no, st.first_name, st.last_name, st.course_id, st.current_semester,
                   sub.name AS subject_name, sub.id AS subject_id,
                   COUNT(a.id) AS total, SUM(CASE WHEN a.status = 'P' THEN 1 ELSE 0 END) AS present
            FROM students st
            LEFT JOIN attendance a ON a.student_id = st.id
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            WHERE 1=1 {where}
            GROUP BY st.id, st.enrollment_no, st.first_name, st.last_name, st.course_id, st.current_semester, sub.id, sub.name
            ORDER BY st.enrollment_no, sub.name
            """,
            params or (),
        )
        report_rows = cur.fetchall()
    return render_template(
        "attendance/report.html",
        courses=courses,
        subjects=subjects,
        report=report_rows,
        course_id=course_id,
        semester=semester,
        subject_id=subject_id,
        month=month,
    )
