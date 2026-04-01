"""Student management: CRUD, search, profile."""
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, make_response
from werkzeug.utils import secure_filename
from auth import require_login, require_roles, get_current_user, hash_password
from database import db_cursor
from config import config
from id_card_service import default_id_card_service

students_bp = Blueprint("students_bp", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def next_enrollment():
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT enrollment_no FROM students ORDER BY id DESC LIMIT 1"
        )
        row = cur.fetchone()
    if not row:
        return "ENR0001"
    try:
        n = int(row["enrollment_no"].replace("ENR", "")) + 1
        return f"ENR{n:04d}"
    except ValueError:
        return "ENR0001"


@students_bp.route("/")
@require_login
@require_roles("admin", "faculty", "accountant")
def list_students():
    q = request.args.get("q", "").strip()
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT c.id, c.name, c.code, d.name AS dept_name
            FROM courses c
            JOIN departments d ON d.id = c.department_id
            ORDER BY d.name, c.name
            """
        )
        courses = cur.fetchall()
    sql = """
        SELECT s.id, s.enrollment_no, s.first_name, s.last_name, s.email, s.current_semester, s.user_id,
               c.name AS course_name, c.code AS course_code, d.name AS dept_name
        FROM students s
        JOIN courses c ON c.id = s.course_id
        JOIN departments d ON d.id = c.department_id
        WHERE 1=1
    """
    params = []
    if q:
        sql += " AND (s.first_name LIKE %s OR s.last_name LIKE %s OR s.enrollment_no LIKE %s OR s.email LIKE %s)"
        p = f"%{q}%"
        params.extend([p, p, p, p])
    if course_id:
        sql += " AND s.course_id = %s"
        params.append(course_id)
    if semester:
        sql += " AND s.current_semester = %s"
        params.append(semester)
    sql += " ORDER BY s.enrollment_no"
    with db_cursor() as (conn, cur):
        cur.execute(sql, params or ())
        students = cur.fetchall()
    return render_template(
        "students/list.html",
        students=students,
        courses=courses,
        q=q,
        course_id=course_id,
        semester=semester,
    )


@students_bp.route("/add", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def add():
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        dob = request.form.get("date_of_birth") or None
        gender = request.form.get("gender") or None
        address = (request.form.get("address") or "").strip() or None
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("current_semester", type=int) or 1
        admission_date = request.form.get("admission_date") or None
        if not first_name or not last_name or not email or not course_id:
            flash("First name, last name, email, and course are required.", "danger")
            return redirect(url_for("students_bp.add"))
        create_login = request.form.get("create_login") == "1"
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if create_login and (not username or not password):
            flash("Username and password are required when creating login.", "danger")
            return redirect(url_for("students_bp.add"))
        enrollment_no = next_enrollment()
        photo_path = None
        if "photo" in request.files:
            f = request.files["photo"]
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit(".", 1)[1].lower()
                fn = f"student_{uuid.uuid4().hex[:12]}.{ext}"
                path = os.path.join(config.UPLOAD_FOLDER, fn)
                f.save(path)
                photo_path = f"uploads/{fn}"
        user_id = None
        if create_login:
            with db_cursor() as (conn, cur):
                is_pg = hasattr(conn, 'cursor_factory')
                if is_pg:
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s) RETURNING id",
                        (email, username, hash_password(password)),
                    )
                    user_id = cur.fetchone()['id']
                else:
                    cur.execute(
                        "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s)",
                        (email, username, hash_password(password)),
                    )
                    user_id = cur.lastrowid
        with db_cursor() as (conn, cur):
            is_pg = hasattr(conn, 'cursor_factory')
            if is_pg:
                cur.execute(
                    """
                    INSERT INTO students (user_id, enrollment_no, first_name, last_name, email, phone,
                        date_of_birth, gender, address, photo_path, course_id, current_semester, admission_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        user_id,
                        enrollment_no,
                        first_name,
                        last_name,
                        email,
                        phone or None,
                        dob,
                        gender,
                        address,
                        photo_path,
                        course_id,
                        semester,
                        admission_date,
                    ),
                )
                student_id = cur.fetchone()['id']
            else:
                cur.execute(
                    """
                    INSERT INTO students (user_id, enrollment_no, first_name, last_name, email, phone,
                        date_of_birth, gender, address, photo_path, course_id, current_semester, admission_date)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        enrollment_no,
                        first_name,
                        last_name,
                        email,
                        phone or None,
                        dob,
                        gender,
                        address,
                        photo_path,
                        course_id,
                        semester,
                        admission_date,
                    ),
                )
                student_id = cur.lastrowid
        msg = f"Student added with enrollment {enrollment_no}."
        if create_login:
            msg += f" Login: {username} / (password as entered)."
        flash(msg, "success")
        return redirect(url_for("students_bp.list_students"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    return render_template("students/form.html", student=None, courses=courses)


@students_bp.route("/<int:sid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def edit(sid):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM students WHERE id = %s",
            (sid,),
        )
        student = cur.fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students_bp.list_students"))
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip()
        phone = (request.form.get("phone") or "").strip()
        dob = request.form.get("date_of_birth") or None
        gender = request.form.get("gender") or None
        address = (request.form.get("address") or "").strip() or None
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("current_semester", type=int) or 1
        admission_date = request.form.get("admission_date") or None
        if not first_name or not last_name or not email or not course_id:
            flash("First name, last name, email, and course are required.", "danger")
            return redirect(url_for("students_bp.edit", sid=sid))
        photo_path = student.get("photo_path")
        if "photo" in request.files:
            f = request.files["photo"]
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit(".", 1)[1].lower()
                fn = f"student_{uuid.uuid4().hex[:12]}.{ext}"
                path = os.path.join(config.UPLOAD_FOLDER, fn)
                f.save(path)
                photo_path = f"uploads/{fn}"
        user_id = student.get("user_id")
        if not user_id:
            create_login = request.form.get("create_login") == "1"
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            if create_login and (not username or not password):
                flash("Username and password are required when creating login.", "danger")
                return redirect(url_for("students_bp.edit", sid=sid))
            if create_login:
                with db_cursor() as (conn, cur):
                    is_pg = hasattr(conn, 'cursor_factory')
                    if is_pg:
                        cur.execute(
                            "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s) RETURNING id",
                            (email, username, hash_password(password)),
                        )
                        user_id = cur.fetchone()['id']
                    else:
                        cur.execute(
                            "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s)",
                            (email, username, hash_password(password)),
                        )
                        user_id = cur.lastrowid
                with db_cursor() as (conn, cur):
                    cur.execute("UPDATE students SET user_id = %s WHERE id = %s", (user_id, sid))
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                UPDATE students SET first_name=%s, last_name=%s, email=%s, phone=%s,
                    date_of_birth=%s, gender=%s, address=%s, photo_path=%s,
                    course_id=%s, current_semester=%s, admission_date=%s
                WHERE id = %s
                """,
                (
                    first_name,
                    last_name,
                    email,
                    phone or None,
                    dob,
                    gender,
                    address,
                    photo_path,
                    course_id,
                    semester,
                    admission_date,
                    sid,
                ),
            )
        flash("Student updated." + (" Login created." if user_id and not student.get("user_id") else ""), "success")
        return redirect(url_for("students_bp.list_students"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    return render_template("students/form.html", student=student, courses=courses)


@students_bp.route("/<int:sid>/create-login", methods=["GET", "POST"])
@require_login
@require_roles("admin")
def create_login(sid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM students WHERE id = %s", (sid,))
        student = cur.fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students_bp.list_students"))
    if student.get("user_id"):
        flash("Student already has a login.", "info")
        return redirect(url_for("students_bp.profile", sid=sid))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
            return redirect(url_for("students_bp.create_login", sid=sid))
        with db_cursor() as (conn, cur):
            is_pg = hasattr(conn, 'cursor_factory')
            if is_pg:
                cur.execute(
                    "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s) RETURNING id",
                    (student["email"], username, hash_password(password)),
                )
                uid = cur.fetchone()['id']
            else:
                cur.execute(
                    "INSERT INTO users (role_id, email, username, password_hash) VALUES (3, %s, %s, %s)",
                    (student["email"], username, hash_password(password)),
                )
                uid = cur.lastrowid
            cur.execute("UPDATE students SET user_id = %s WHERE id = %s", (uid, sid))
        flash(f"Login created. Student can sign in with {username} / (password as entered).", "success")
        return redirect(url_for("students_bp.profile", sid=sid))
    return render_template("students/create_login.html", student=student)


@students_bp.route("/<int:sid>/delete", methods=["POST"])
@require_login
@require_roles("admin")
def delete(sid):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM students WHERE id = %s", (sid,))
        if cur.rowcount == 0:
            flash("Student not found.", "danger")
        else:
            flash("Student deleted.", "success")
    return redirect(url_for("students_bp.list_students"))


@students_bp.route("/<int:sid>")
@require_login
@require_roles("admin", "faculty", "student", "accountant")
def profile(sid):
    user = get_current_user()
    if user.get("role_name") == "student" and user.get("extra_id") != sid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.*, c.name AS course_name, c.code AS course_code,
                   d.name AS dept_name, d.code AS dept_code
            FROM students s
            JOIN courses c ON c.id = s.course_id
            JOIN departments d ON d.id = c.department_id
            WHERE s.id = %s
            """,
            (sid,),
        )
        student = cur.fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("students_bp.list_students"))
    return render_template("students/profile.html", student=student)


@students_bp.route("/<int:sid>/id-card")
@require_login
@require_roles("admin", "faculty", "student", "accountant")
def id_card(sid):
    """View digital ID card (HTML) – owners + staff."""
    user = get_current_user()
    if user.get("role_name") == "student" and user.get("extra_id") != sid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    # Ensure card exists (blood group is optional here; mainly handled at registration)
    try:
        card, student_meta = default_id_card_service.ensure_card_record(sid)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("students_bp.profile", sid=sid))

    # Build verification URL and QR image
    verify_url = url_for("students_bp.id_card_verify", token=card.qr_token, _external=True)
    qr_rel_path = default_id_card_service.generate_qr_image(verify_url, sid)
    qr_image_url = url_for("static", filename=qr_rel_path)

    # Load richer student info for the card UI
    card2, full_meta = default_id_card_service.get_card_with_student(sid)
    if card2:
        card = card2
    meta = full_meta or student_meta

    return render_template(
        "students/id_card.html",
        card=card,
        student=meta,
        qr_image_url=qr_image_url,
        pdf_mode=False,
    )


@students_bp.route("/<int:sid>/id-card/pdf")
@require_login
@require_roles("admin", "faculty", "student", "accountant")
def id_card_pdf(sid):
    """Download digital ID card as PDF."""
    user = get_current_user()
    if user.get("role_name") == "student" and user.get("extra_id") != sid:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    # Ensure card and QR exist
    try:
        card, _ = default_id_card_service.ensure_card_record(sid)
    except ValueError as e:
        flash(str(e), "danger")
        return redirect(url_for("students_bp.profile", sid=sid))

    verify_url = url_for("students_bp.id_card_verify", token=card.qr_token, _external=True)
    qr_rel_path = default_id_card_service.generate_qr_image(verify_url, sid)
    qr_image_url = url_for("static", filename=qr_rel_path)
    card2, meta = default_id_card_service.get_card_with_student(sid)
    if card2:
        card = card2

    try:
        from weasyprint import HTML  # type: ignore
    except ImportError:
        flash("PDF generation is not available. Please install WeasyPrint to enable this feature.", "danger")
        return redirect(url_for("students_bp.id_card", sid=sid))

    html_str = render_template(
        "students/id_card.html",
        card=card,
        student=meta,
        qr_image_url=qr_image_url,
        pdf_mode=True,
    )

    pdf = HTML(string=html_str, base_url=request.url_root).write_pdf()
    filename = f"ID_{meta.get('enrollment_no', 'student')}.pdf" if meta else "ID_card.pdf"
    resp = make_response(pdf)
    resp.headers["Content-Type"] = "application/pdf"
    resp.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


@students_bp.route("/id-card/verify/<token>")
def id_card_verify(token):
    """Public verification endpoint – used when QR is scanned."""
    ok, card, public_meta, error = default_id_card_service.verify_token(token)
    if not ok or not card or not public_meta:
        return render_template(
            "students/id_card_verify.html",
            success=False,
            error_message=error or "Invalid verification link.",
            card=None,
            student=None,
        )

    return render_template(
        "students/id_card_verify.html",
        success=True,
        error_message="",
        card=card,
        student=public_meta,
    )

