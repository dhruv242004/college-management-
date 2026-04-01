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
    
    # Check if we are on PostgreSQL
    is_pg = hasattr(conn, 'cursor_factory')
    time_func = "TO_CHAR(tt.start_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.start_time, '%H:%i')"
    end_time_func = "TO_CHAR(tt.end_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.end_time, '%H:%i')"
    
    with db_cursor() as (conn, cur):
        cur.execute(
            f"""
            SELECT tt.id, tt.day_of_week, {time_func} as start_time, {end_time_func} as end_time, tt.room, tt.semester,
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
    
    # Check if we are on PostgreSQL
    is_pg = hasattr(conn, 'cursor_factory')
    time_func = "TO_CHAR(tt.start_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.start_time, '%H:%i')"
    end_time_func = "TO_CHAR(tt.end_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.end_time, '%H:%i')"

    with db_cursor() as (conn, cur):
        cur.execute(
            f"""
            SELECT tt.id, tt.day_of_week, {time_func} as start_time, {end_time_func} as end_time, tt.room, tt.semester,
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
    
    # Check if we are on PostgreSQL
    is_pg = hasattr(conn, 'cursor_factory')
    time_func = "TO_CHAR(tt.start_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.start_time, '%H:%i')"
    end_time_func = "TO_CHAR(tt.end_time, 'HH24:MI')" if is_pg else "TIME_FORMAT(tt.end_time, '%H:%i')"

    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses WHERE id = %s",
            (course_id,),
        )
        course = cur.fetchone()
        cur.execute(
            f"""
            SELECT tt.day_of_week, {time_func} as start_time, {end_time_func} as end_time, tt.room,
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
@require_roles("admin", "faculty")
def add():
    user = get_current_user()
    is_faculty = user.get("role_name") == "faculty"

    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        subject_id = request.form.get("subject_id", type=int)
        # If faculty, enforce their own faculty id
        if is_faculty:
            faculty_id = user.get("extra_id")
        else:
            faculty_id = request.form.get("faculty_id", type=int)
        semester = request.form.get("semester", type=int)
        day = request.form.get("day_of_week", type=int)
        start = request.form.get("start_time")
        end = request.form.get("end_time")
        room = (request.form.get("room") or "").strip() or None
        if not all([course_id, subject_id, faculty_id, semester, day, start, end]):
            flash("Course, subject, faculty, semester, day, and times are required.", "danger")
            return redirect(url_for("timetable_bp.add"))

        # If faculty posting, ensure they are assigned to this subject
        with db_cursor() as (conn, cur):
            cur.execute("SELECT course_id FROM subjects WHERE id = %s", (subject_id,))
            subj = cur.fetchone()
        if not subj:
            flash("Selected subject not found.", "danger")
            return redirect(url_for("timetable_bp.add"))

        # Ensure subject's course matches provided course_id
        if subj["course_id"] != course_id:
            flash("Selected subject does not belong to the selected course.", "danger")
            return redirect(url_for("timetable_bp.add"))

        if is_faculty:
            with db_cursor() as (conn, cur):
                cur.execute(
                    "SELECT COUNT(*) AS c FROM faculty_subject_assignment WHERE faculty_id = %s AND subject_id = %s AND academic_year = %s",
                    (faculty_id, subject_id, ACAD_YEAR),
                )
                ok = cur.fetchone()["c"]
            if not ok:
                flash("You are not assigned to the selected subject.", "danger")
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

    # GET: prepare lists. If faculty, limit subjects to their assignments and courses accordingly.
    with db_cursor() as (conn, cur):
        if is_faculty:
            fid = user.get("extra_id")
            cur.execute(
                "SELECT s.id, s.name, s.code, s.course_id, s.semester FROM subjects s JOIN faculty_subject_assignment fsa ON fsa.subject_id = s.id WHERE fsa.faculty_id = %s AND fsa.academic_year = %s ORDER BY s.course_id, s.semester",
                (fid, ACAD_YEAR),
            )
            subjects = cur.fetchall()

            # get unique courses from those subjects
            course_ids = list({s['course_id'] for s in subjects})
            if course_ids:
                placeholders = ','.join(['%s'] * len(course_ids))
                cur.execute(
                    f"SELECT id, name, code FROM courses WHERE id IN ({placeholders}) ORDER BY name",
                    tuple(course_ids),
                )
                courses = cur.fetchall()
            else:
                courses = []

            # faculty info for display
            cur.execute("SELECT id, emp_id, first_name, last_name FROM faculty WHERE id = %s", (fid,))
            faculty = [cur.fetchone()]
        else:
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
        is_faculty=is_faculty,
    )
