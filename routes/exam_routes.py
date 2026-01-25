"""Examination & results: marks entry, grades, publish, student view."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor

exam_bp = Blueprint("exam_bp", __name__)

ACAD_YEAR = "2024-25"
EXAM_SESSION = "2024-25-S1"
GRADE_MAP = [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C"), (40, "D"), (0, "F")]


def grade_from_total(total):
    if total is None:
        return None
    for thresh, g in GRADE_MAP:
        if total >= thresh:
            return g
    return "F"


@exam_bp.route("/")
@require_login
@require_roles("admin", "faculty")
def index():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.id, s.name, s.code, s.semester, c.name AS course_name, c.id AS course_id
            FROM subjects s
            JOIN courses c ON c.id = s.course_id
            ORDER BY c.name, s.semester
            """
        )
        subjects = cur.fetchall()
    return render_template("exams/index.html", subjects=subjects)


@exam_bp.route("/marks/<int:subject_id>", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def marks_entry(subject_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT s.*, c.name AS course_name, c.id AS course_id FROM subjects s JOIN courses c ON c.id = s.course_id WHERE s.id = %s",
            (subject_id,),
        )
        subj = cur.fetchone()
    if not subj:
        flash("Subject not found.", "danger")
        return redirect(url_for("exam_bp.index"))
    course_id = subj["course_id"]
    semester = subj["semester"]
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT st.id, st.enrollment_no, st.first_name, st.last_name
            FROM students st
            WHERE st.course_id = %s AND st.current_semester = %s
            ORDER BY st.enrollment_no
            """,
            (course_id, semester),
        )
        students = cur.fetchall()
        cur.execute(
            "SELECT student_id, internal_marks, external_marks, total_marks, grade, published FROM marks WHERE subject_id = %s AND exam_session = %s",
            (subject_id, EXAM_SESSION),
        )
        existing = {r["student_id"]: r for r in cur.fetchall()}
    if request.method == "POST":
        for s in students:
            internal = request.form.get(f"internal_{s['id']}")
            external = request.form.get(f"external_{s['id']}")
            if internal is None and external is None:
                continue
            try:
                internal = float(internal) if internal else None
            except (TypeError, ValueError):
                internal = None
            try:
                external = float(external) if external else None
            except (TypeError, ValueError):
                external = None
            total = None
            if internal is not None and external is not None:
                total = internal + external
            elif internal is not None:
                total = internal
            elif external is not None:
                total = external
            grade = grade_from_total(total)
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO marks (student_id, subject_id, internal_marks, external_marks, total_marks, grade, exam_type, exam_session, published)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Internal+External', %s, 0)
                    ON DUPLICATE KEY UPDATE internal_marks=%s, external_marks=%s, total_marks=%s, grade=%s
                    """,
                    (s["id"], subject_id, internal, external, total, grade, EXAM_SESSION, internal, external, total, grade),
                )
        flash("Marks saved.", "success")
        return redirect(url_for("exam_bp.marks_entry", subject_id=subject_id))
    return render_template(
        "exams/marks_entry.html",
        subject=subj,
        students=students,
        existing=existing,
    )


@exam_bp.route("/publish/<int:subject_id>", methods=["POST"])
@require_login
@require_roles("admin", "faculty")
def publish(subject_id):
    action = request.form.get("action")
    pub = 1 if action == "publish" else 0
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE marks SET published = %s WHERE subject_id = %s AND exam_session = %s",
            (pub, subject_id, EXAM_SESSION),
        )
    flash("Results published." if pub else "Results unpublished.", "success")
    return redirect(url_for("exam_bp.marks_entry", subject_id=subject_id))


@exam_bp.route("/my-results")
@require_login
@require_roles("student")
def my_results():
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT m.internal_marks, m.external_marks, m.total_marks, m.grade, m.published,
                   s.name AS subject_name, s.code AS subject_code, s.credits
            FROM marks m
            JOIN subjects s ON s.id = m.subject_id
            WHERE m.student_id = %s AND m.exam_session = %s AND m.published = 1
            ORDER BY s.name
            """,
            (sid, EXAM_SESSION),
        )
        results = cur.fetchall()
        cur.execute(
            "SELECT st.enrollment_no, st.first_name, st.last_name, c.name AS course_name FROM students st JOIN courses c ON c.id = st.course_id WHERE st.id = %s",
            (sid,),
        )
        student = cur.fetchone()
    return render_template("exams/my_results.html", results=results, student=student)
