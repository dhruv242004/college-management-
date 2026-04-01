"""Faculty management: CRUD, assign subjects, view students."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user, hash_password
from database import db_cursor

faculty_bp = Blueprint("faculty_bp", __name__)


@faculty_bp.route("/")
@require_login
@require_roles("admin")
def list_faculty():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT f.id, f.emp_id, f.first_name, f.last_name, f.email, f.designation, f.user_id,
                   d.name AS dept_name, d.code AS dept_code
            FROM faculty f
            JOIN departments d ON d.id = f.department_id
            ORDER BY f.emp_id
            """
        )
        rows = cur.fetchall()
    return render_template("faculty/list.html", faculty_list=rows)


@faculty_bp.route("/<int:fid>")
@require_login
@require_roles("admin", "faculty")
def profile(fid):
    user = get_current_user()
    if user.get("role_name") == "faculty" and user.get("extra_id") != fid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT f.*, d.name AS dept_name, d.code AS dept_code
            FROM faculty f
            JOIN departments d ON d.id = f.department_id
            WHERE f.id = %s
            """,
            (fid,),
        )
        faculty = cur.fetchone()
    if not faculty:
        flash("Faculty not found.", "danger")
        return redirect(url_for("faculty_bp.list_faculty") if user.get("role_name") == "admin" else url_for("dashboard"))
    return render_template("faculty/profile.html", faculty=faculty)


@faculty_bp.route("/<int:fid>/update-profile", methods=["GET", "POST"])
@require_login
@require_roles("faculty")
def update_profile(fid):
    user = get_current_user()
    if user.get("extra_id") != fid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM faculty WHERE id = %s", (fid,))
        faculty = cur.fetchone()
    if not faculty:
        flash("Faculty not found.", "danger")
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        phone = (request.form.get("phone") or "").strip() or None
        designation = (request.form.get("designation") or "").strip() or None
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE faculty SET phone = %s, designation = %s WHERE id = %s",
                (phone, designation, fid),
            )
        flash("Profile updated.", "success")
        return redirect(url_for("faculty_bp.profile", fid=fid))
    return render_template("faculty/update_profile.html", faculty=faculty)


@faculty_bp.route("/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add():
    if request.method == "POST":
        emp_id = (request.form.get("emp_id") or "").strip()
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        dept_id = request.form.get("department_id", type=int)
        designation = (request.form.get("designation") or "").strip() or None
        joined = request.form.get("joined_date") or None
        create_login = request.form.get("create_login") == "1"
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not emp_id or not first_name or not last_name or not email or not dept_id:
            flash("Emp ID, name, email, and department are required.", "danger")
            return redirect(url_for("faculty_bp.add"))
        if create_login and (not username or not password):
            flash("Username and password required when creating login.", "danger")
            return redirect(url_for("faculty_bp.add"))
        user_id = None
        if create_login:
            with db_cursor() as (conn, cur):
                is_pg = hasattr(conn, 'cursor_factory')
                if is_pg:
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s) RETURNING id",
                        (email, username, hash_password(password)),
                    )
                    user_id = cur.fetchone()['id']
                else:
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s)",
                        (email, username, hash_password(password)),
                    )
                    user_id = cur.lastrowid
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO faculty (user_id, emp_id, first_name, last_name, email, phone, department_id, designation, joined_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (user_id, emp_id, first_name, last_name, email, phone or None, dept_id, designation, joined),
            )
        flash("Faculty added.", "success")
        return redirect(url_for("faculty_bp.list_faculty"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM departments ORDER BY name")
        depts = cur.fetchall()
    return render_template("faculty/form.html", faculty=None, departments=depts)


@faculty_bp.route("/<int:fid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def edit(fid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM faculty WHERE id = %s", (fid,))
        fac = cur.fetchone()
    if not fac:
        flash("Faculty not found.", "danger")
        return redirect(url_for("faculty_bp.list_faculty"))
    if request.method == "POST":
        emp_id = (request.form.get("emp_id") or "").strip()
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        dept_id = request.form.get("department_id", type=int)
        designation = (request.form.get("designation") or "").strip() or None
        joined = request.form.get("joined_date") or None
        if not emp_id or not first_name or not last_name or not email or not dept_id:
            flash("Emp ID, name, email, and department are required.", "danger")
            return redirect(url_for("faculty_bp.edit", fid=fid))
        user_id = fac.get("user_id")
        if not user_id:
            create_login = request.form.get("create_login") == "1"
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if create_login and (not username or not password):
                flash("Username and password required when creating login.", "danger")
                return redirect(url_for("faculty_bp.edit", fid=fid))
            if create_login:
                with db_cursor() as (conn, cur):
                    is_pg = hasattr(conn, 'cursor_factory')
                    if is_pg:
                        cur.execute(
                            "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s) RETURNING id",
                            (email, username, hash_password(password)),
                        )
                        user_id = cur.fetchone()['id']
                    else:
                        cur.execute(
                            "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s)",
                            (email, username, hash_password(password)),
                        )
                        user_id = cur.lastrowid
                    cur.execute("UPDATE faculty SET user_id = %s WHERE id = %s", (user_id, fid))
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                UPDATE faculty SET emp_id=%s, first_name=%s, last_name=%s, email=%s, phone=%s,
                    department_id=%s, designation=%s, joined_date=%s
                WHERE id = %s
                """,
                (emp_id, first_name, last_name, email, phone or None, dept_id, designation, joined, fid),
            )
        msg = "Faculty updated."
        if user_id and not fac.get("user_id"):
            msg += " Login created."
        flash(msg, "success")
        return redirect(url_for("faculty_bp.list_faculty"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM departments ORDER BY name")
        depts = cur.fetchall()
    return render_template("faculty/form.html", faculty=fac, departments=depts)


@faculty_bp.route("/<int:fid>/delete", methods=["POST"])
@require_login
@require_roles("admin")
def delete(fid):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM faculty WHERE id = %s", (fid,))
        if cur.rowcount == 0:
            flash("Faculty not found.", "danger")
        else:
            flash("Faculty deleted.", "success")
    return redirect(url_for("faculty_bp.list_faculty"))


@faculty_bp.route("/<int:fid>/create-login", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def create_login(fid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM faculty WHERE id = %s", (fid,))
        faculty = cur.fetchone()
    if not faculty:
        flash("Faculty not found.", "danger")
        return redirect(url_for("faculty_bp.list_faculty"))
    if faculty.get("user_id"):
        flash("Faculty already has a login.", "info")
        return redirect(url_for("faculty_bp.profile", fid=fid))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("faculty_bp.create_login", fid=fid))
        with db_cursor() as (conn, cur):
            is_pg = hasattr(conn, 'cursor_factory')
            if is_pg:
                cur.execute(
                    "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s) RETURNING id",
                    (faculty["email"], username, hash_password(password)),
                )
                uid = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO users (role_id, email, username, password_hash) VALUES (2, %s, %s, %s)",
                    (faculty["email"], username, hash_password(password)),
                )
                uid = cur.lastrowid
            cur.execute("UPDATE faculty SET user_id = %s WHERE id = %s", (uid, fid))
        flash(f"Login created. Faculty can sign in with {username} / (password as entered).", "success")
        return redirect(url_for("faculty_bp.profile", fid=fid))
    return render_template("faculty/create_login.html", faculty=faculty)


@faculty_bp.route("/<int:fid>/assign", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def assign_subjects(fid):
    user = get_current_user()
    if user.get("role_name") == "faculty" and user.get("extra_id") != fid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM faculty WHERE id = %s", (fid,))
        fac = cur.fetchone()
    if not fac:
        flash("Faculty not found.", "danger")
        return redirect(url_for("faculty_bp.list_faculty") if user.get("role_name") == "admin" else url_for("dashboard"))
    is_faculty_view = user.get("role_name") == "faculty"
    if request.method == "POST" and not is_faculty_view:
        subject_id = request.form.get("subject_id", type=int)
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("semester", type=int)
        acad_year = (request.form.get("academic_year") or "2024-25").strip()
        if not subject_id or not course_id or not semester:
            flash("Subject, course, and semester are required.", "danger")
            return redirect(url_for("faculty_bp.assign_subjects", fid=fid))
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO faculty_subject_assignment (faculty_id, subject_id, course_id, semester, academic_year)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (fid, subject_id, course_id, semester, acad_year),
            )
        flash("Assignment added.", "success")
        return redirect(url_for("faculty_bp.assign_subjects", fid=fid))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT fsa.id, fsa.semester, fsa.academic_year, s.name AS subject_name, s.code AS subject_code,
                   c.name AS course_name
            FROM faculty_subject_assignment fsa
            JOIN subjects s ON s.id = fsa.subject_id
            JOIN courses c ON c.id = fsa.course_id
            WHERE fsa.faculty_id = %s
            ORDER BY fsa.academic_year DESC, fsa.semester
            """,
            (fid,),
        )
        assignments = cur.fetchall()
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
        cur.execute(
            "SELECT id, name, code, course_id, semester FROM subjects ORDER BY course_id, semester, code"
        )
        subjects = cur.fetchall()
    return render_template(
        "faculty/assign.html",
        faculty=fac,
        assignments=assignments,
        courses=courses,
        subjects=subjects,
        is_faculty_view=is_faculty_view,
    )


@faculty_bp.route("/<int:fid>/students")
@require_login
@require_roles("admin", "faculty")
def assigned_students(fid):
    user = get_current_user()
    if user.get("role_name") == "faculty" and user.get("extra_id") != fid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT DISTINCT s.id, s.enrollment_no, s.first_name, s.last_name, s.email, s.current_semester,
                   c.name AS course_name, fsa.subject_id, sub.name AS subject_name
            FROM faculty_subject_assignment fsa
            JOIN students s ON s.course_id = fsa.course_id AND s.current_semester = fsa.semester
            JOIN courses c ON c.id = s.course_id
            JOIN subjects sub ON sub.id = fsa.subject_id
            WHERE fsa.faculty_id = %s
            ORDER BY s.enrollment_no
            """,
            (fid,),
        )
        students = cur.fetchall()
        cur.execute("SELECT * FROM faculty WHERE id = %s", (fid,))
        fac = cur.fetchone()
    if not fac:
        flash("Faculty not found.", "danger")
        return redirect(url_for("faculty_bp.list_faculty"))
    return render_template("faculty/assigned_students.html", faculty=fac, students=students)
