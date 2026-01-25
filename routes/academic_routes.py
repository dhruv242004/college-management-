"""Departments, courses, subjects management."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles
from database import db_cursor

academic_bp = Blueprint("academic_bp", __name__)


# ---------- Departments ----------
@academic_bp.route("/departments")
@require_login
@require_roles("admin")
def list_departments():
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code, created_at FROM departments ORDER BY name"
        )
        rows = cur.fetchall()
    return render_template("academic/departments.html", departments=rows)


@academic_bp.route("/departments/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add_department():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        if not name or not code:
            flash("Name and code are required.", "danger")
            return redirect(url_for("academic_bp.add_department"))
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO departments (name, code) VALUES (%s, %s)",
                (name, code),
            )
        flash("Department added.", "success")
        return redirect(url_for("academic_bp.list_departments"))
    return render_template("academic/department_form.html", department=None)


@academic_bp.route("/departments/<int:did>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def edit_department(did):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM departments WHERE id = %s", (did,))
        dept = cur.fetchone()
    if not dept:
        flash("Department not found.", "danger")
        return redirect(url_for("academic_bp.list_departments"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip().upper()
        if not name or not code:
            flash("Name and code are required.", "danger")
            return redirect(url_for("academic_bp.edit_department", did=did))
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE departments SET name = %s, code = %s WHERE id = %s",
                (name, code, did),
            )
        flash("Department updated.", "success")
        return redirect(url_for("academic_bp.list_departments"))
    return render_template("academic/department_form.html", department=dept)


@academic_bp.route("/departments/<int:did>/delete", methods=["POST"])
@require_login
@require_roles("admin")
def delete_department(did):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM departments WHERE id = %s", (did,))
        if cur.rowcount == 0:
            flash("Department not found or in use.", "danger")
        else:
            flash("Department deleted.", "success")
    return redirect(url_for("academic_bp.list_departments"))


# ---------- Courses ----------
@academic_bp.route("/courses")
@require_login
@require_roles("admin", "faculty")
def list_courses():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT c.id, c.name, c.code, c.duration_years, d.name AS dept_name, d.code AS dept_code
            FROM courses c
            JOIN departments d ON d.id = c.department_id
            ORDER BY d.name, c.name
            """
        )
        rows = cur.fetchall()
    return render_template("academic/courses.html", courses=rows)


@academic_bp.route("/courses/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add_course():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip()
        dept_id = request.form.get("department_id", type=int)
        duration = request.form.get("duration_years", type=int) or 3
        if not name or not code or not dept_id:
            flash("Name, code, and department are required.", "danger")
            return redirect(url_for("academic_bp.add_course"))
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO courses (name, code, department_id, duration_years) VALUES (%s, %s, %s, %s)",
                (name, code, dept_id, duration),
            )
        flash("Course added.", "success")
        return redirect(url_for("academic_bp.list_courses"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM departments ORDER BY name")
        depts = cur.fetchall()
    return render_template("academic/course_form.html", course=None, departments=depts)


@academic_bp.route("/courses/<int:cid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def edit_course(cid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM courses WHERE id = %s", (cid,))
        course = cur.fetchone()
    if not course:
        flash("Course not found.", "danger")
        return redirect(url_for("academic_bp.list_courses"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip()
        dept_id = request.form.get("department_id", type=int)
        duration = request.form.get("duration_years", type=int) or 3
        if not name or not code or not dept_id:
            flash("Name, code, and department are required.", "danger")
            return redirect(url_for("academic_bp.edit_course", cid=cid))
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE courses SET name = %s, code = %s, department_id = %s, duration_years = %s WHERE id = %s",
                (name, code, dept_id, duration, cid),
            )
        flash("Course updated.", "success")
        return redirect(url_for("academic_bp.list_courses"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM departments ORDER BY name")
        depts = cur.fetchall()
    return render_template("academic/course_form.html", course=course, departments=depts)


@academic_bp.route("/courses/<int:cid>/delete", methods=["POST"])
@require_login
@require_roles("admin")
def delete_course(cid):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM courses WHERE id = %s", (cid,))
        if cur.rowcount == 0:
            flash("Course not found or in use.", "danger")
        else:
            flash("Course deleted.", "success")
    return redirect(url_for("academic_bp.list_courses"))


# ---------- Subjects ----------
@academic_bp.route("/subjects")
@require_login
@require_roles("admin", "faculty")
def list_subjects():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.id, s.name, s.code, s.semester, s.credits, c.name AS course_name, c.code AS course_code
            FROM subjects s
            JOIN courses c ON c.id = s.course_id
            ORDER BY c.name, s.semester, s.code
            """
        )
        rows = cur.fetchall()
    return render_template("academic/subjects.html", subjects=rows)


@academic_bp.route("/subjects/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add_subject():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip()
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("semester", type=int) or 1
        credits = request.form.get("credits", type=int) or 4
        if not name or not code or not course_id:
            flash("Name, code, and course are required.", "danger")
            return redirect(url_for("academic_bp.add_subject"))
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO subjects (name, code, course_id, semester, credits) VALUES (%s, %s, %s, %s, %s)",
                (name, code, course_id, semester, credits),
            )
        flash("Subject added.", "success")
        return redirect(url_for("academic_bp.list_subjects"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT c.id, c.name, c.code FROM courses c ORDER BY c.name"
        )
        courses = cur.fetchall()
    return render_template("academic/subject_form.html", subject=None, courses=courses)


@academic_bp.route("/subjects/<int:sid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def edit_subject(sid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM subjects WHERE id = %s", (sid,))
        subject = cur.fetchone()
    if not subject:
        flash("Subject not found.", "danger")
        return redirect(url_for("academic_bp.list_subjects"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        code = (request.form.get("code") or "").strip()
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("semester", type=int) or 1
        credits = request.form.get("credits", type=int) or 4
        if not name or not code or not course_id:
            flash("Name, code, and course are required.", "danger")
            return redirect(url_for("academic_bp.edit_subject", sid=sid))
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE subjects SET name = %s, code = %s, course_id = %s, semester = %s, credits = %s WHERE id = %s",
                (name, code, course_id, semester, credits, sid),
            )
        flash("Subject updated.", "success")
        return redirect(url_for("academic_bp.list_subjects"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    return render_template("academic/subject_form.html", subject=subject, courses=courses)


@academic_bp.route("/subjects/<int:sid>/delete", methods=["POST"])
@require_login
@require_roles("admin")
def delete_subject(sid):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM subjects WHERE id = %s", (sid,))
        if cur.rowcount == 0:
            flash("Subject not found or in use.", "danger")
        else:
            flash("Subject deleted.", "success")
    return redirect(url_for("academic_bp.list_subjects"))
