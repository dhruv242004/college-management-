"""Timetable: course-wise, faculty-wise, student view."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor

timetable_bp = Blueprint("timetable_bp", __name__)

ACAD_YEAR = "2024-25"
DAYS = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


@timetable_bp.route("/")
@require_login
@require_roles("admin", "faculty")
def index():
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
        cur.execute(
            "SELECT id, emp_id, first_name, last_name FROM faculty ORDER BY emp_id"
        )
        faculty = cur.fetchall()
    return render_template("timetable/index.html", courses=courses, faculty=faculty)


@timetable_bp.route("/course/<int:course_id>")
@require_login
def course_timetable(course_id):
    semester = request.args.get("semester", type=int) or 1
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses WHERE id = %s",
            (course_id,),
        )
        course = cur.fetchone()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("timetable_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT tt.id, tt.day_of_week, TIME_FORMAT(tt.start_time, '%H:%i') as start_time, TIME_FORMAT(tt.end_time, '%H:%i') as end_time, tt.room, tt.semester,
                   s.name AS subject_name, s.code AS subject_code, f.first_name AS fac_first, f.last_name AS fac_last
            FROM timetable tt
            JOIN subjects s ON s.id = tt.subject_id
            JOIN faculty f ON f.id = tt.faculty_id
            WHERE tt.course_id = %s AND tt.semester = %s AND tt.academic_year = %s
            ORDER BY tt.day_of_week, tt.start_time
            """,
            (course_id, semester, ACAD_YEAR),
        )
        slots = cur.fetchall()
    return render_template(
        "timetable/course.html",
        course=course,
        slots=slots,
        semester=semester,
        days=DAYS,
    )


@timetable_bp.route("/faculty/<int:fid>")
@require_login
@require_roles("admin", "faculty")
def faculty_timetable(fid):
    user = get_current_user()
    if user.get("role_name") == "faculty" and user.get("extra_id") != fid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, emp_id, first_name, last_name FROM faculty WHERE id = %s", (fid,))
        fac = cur.fetchone()
    if not fac:
        flash("Faculty not found.", "danger")
        return redirect(url_for("timetable_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT tt.id, tt.day_of_week, TIME_FORMAT(tt.start_time, '%H:%i') as start_time, TIME_FORMAT(tt.end_time, '%H:%i') as end_time, tt.room, tt.semester,
                   s.name AS subject_name, c.name AS course_name
            FROM timetable tt
            JOIN subjects s ON s.id = tt.subject_id
            JOIN courses c ON c.id = tt.course_id
            WHERE tt.faculty_id = %s AND tt.academic_year = %s
            ORDER BY tt.day_of_week, tt.start_time
            """,
            (fid, ACAD_YEAR),
        )
        slots = cur.fetchall()
    return render_template(
        "timetable/faculty.html",
        faculty=fac,
        slots=slots,
        days=DAYS,
    )


@timetable_bp.route("/my")
@require_login
@require_roles("student")
def my_timetable():
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT course_id, current_semester FROM students WHERE id = %s",
            (sid,),
        )
        row = cur.fetchone()
    if not row:
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))
    course_id = row["course_id"]
    semester = row["current_semester"]
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses WHERE id = %s",
            (course_id,),
        )
        course = cur.fetchone()
        cur.execute(
            """
            SELECT tt.day_of_week, TIME_FORMAT(tt.start_time, '%H:%i') as start_time, TIME_FORMAT(tt.end_time, '%H:%i') as end_time, tt.room,
                   s.name AS subject_name, f.first_name AS fac_first, f.last_name AS fac_last
            FROM timetable tt
            JOIN subjects s ON s.id = tt.subject_id
            JOIN faculty f ON f.id = tt.faculty_id
            WHERE tt.course_id = %s AND tt.semester = %s AND tt.academic_year = %s
            ORDER BY tt.day_of_week, tt.start_time
            """,
            (course_id, semester, ACAD_YEAR),
        )
        slots = cur.fetchall()
    return render_template(
        "timetable/my.html",
        course=course,
        slots=slots,
        semester=semester,
        days=DAYS,
    )


@timetable_bp.route("/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add():
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        faculty_id = request.form.get("faculty_id", type=int)
        semester = request.form.get("semester", type=int)
        day = request.form.get("day_of_week", type=int)
        start = request.form.get("start_time")
        end = request.form.get("end_time")
        room = (request.form.get("room") or "").strip() or None
        if not all([course_id, subject_id, faculty_id, semester, day, start, end]):
            flash("Course, subject, faculty, semester, day, and times are required.", "danger")
            return redirect(url_for("timetable_bp.add"))
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO timetable (course_id, subject_id, faculty_id, semester, day_of_week, start_time, end_time, room, academic_year)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (course_id, subject_id, faculty_id, semester, day, start, end, room, ACAD_YEAR),
            )
        flash("Timetable entry added.", "success")
        return redirect(url_for("timetable_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
        cur.execute("SELECT id, name, code, course_id, semester FROM subjects ORDER BY course_id, semester")
        subjects = cur.fetchall()
        cur.execute("SELECT id, emp_id, first_name, last_name FROM faculty ORDER BY emp_id")
        faculty = cur.fetchall()
    return render_template(
        "timetable/form.html",
        courses=courses,
        subjects=subjects,
        faculty=faculty,
    )
