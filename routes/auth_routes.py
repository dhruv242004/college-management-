"""Authentication routes: login, logout, student registration."""
import os
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import date
from werkzeug.utils import secure_filename

from auth import login_user, logout_user, get_current_user, require_login, hash_password
from database import db_cursor
from config import config
from id_card_service import default_id_card_service

auth_bp = Blueprint("auth_bp", __name__)


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in config.ALLOWED_EXTENSIONS


def get_next_enrollment_for_course(course_code: str) -> str:
    """
    Generate next enrollment number for a course.
    Format: COURSECODE + YEAR + SEQUENCE (e.g., BCA2025001, MCA2025002)
    """
    current_year = date.today().year
    prefix = f"{course_code.upper()}{current_year}"
    
    with db_cursor() as (conn, cur):
        # Get the highest enrollment number for this course prefix
        cur.execute(
            """
            SELECT enrollment_no FROM students 
            WHERE enrollment_no LIKE %s 
            ORDER BY enrollment_no DESC 
            LIMIT 1
            """,
            (f"{prefix}%",)
        )
        row = cur.fetchone()
    
    if not row:
        return f"{prefix}001"
    
    try:
        # Extract the sequence number from the last enrollment
        last_enrollment = row["enrollment_no"]
        sequence = int(last_enrollment[len(prefix):]) + 1
        return f"{prefix}{sequence:03d}"
    except (ValueError, IndexError):
        return f"{prefix}001"


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("dashboard"))
    
    # Fetch recent notices for display on login page
    notices = []
    try:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT title, category FROM notices 
                WHERE is_published = TRUE 
                ORDER BY created_at DESC 
                LIMIT 5
                """
            )
            notices = cur.fetchall()
    except Exception:
        pass  # Ignore errors fetching notices
    
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("auth/login.html", notices=notices)
        try:
            ok, msg, user = login_user(username, password)
        except Exception as e:
            err = str(e)[:150] + "…" if len(str(e)) > 150 else str(e)
            flash(
                "Database connection error. Please check your connection settings. " + err,
                "danger",
            )
            return render_template("auth/login.html", notices=notices)
        if not ok:
            flash(msg, "danger")
            return render_template("auth/login.html", notices=notices)
        session["user"] = user
        session.permanent = True
        session.modified = True
        flash(msg, "success")
        next_url = request.args.get("next") or request.form.get("next") or url_for("dashboard")
        return redirect(next_url)
    return render_template("auth/login.html", notices=notices)


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth_bp.login"))


@auth_bp.route("/register", methods=["GET", "POST"])
def student_register():
    """Student self-registration with course-wise enrollment number generation."""
    if get_current_user():
        return redirect(url_for("dashboard"))
    
    # Fetch available courses
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
    
    if request.method == "POST":
        first_name = (request.form.get("first_name") or "").strip()
        last_name = (request.form.get("last_name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        phone = (request.form.get("phone") or "").strip()
        dob = request.form.get("date_of_birth") or None
        gender = request.form.get("gender") or None
        blood_group = (request.form.get("blood_group") or "").strip().upper()
        try:
            course_id = int(request.form.get("course_id") or 0)
        except (TypeError, ValueError):
            course_id = 0
        password = request.form.get("password") or ""
        confirm_password = request.form.get("confirm_password") or ""
        
        # Validation
        errors = []
        if not first_name:
            errors.append("First name is required.")
        if not last_name:
            errors.append("Last name is required.")
        if not email:
            errors.append("Email is required.")
        if not course_id:
            errors.append("Please select a course.")
        if not dob:
            errors.append("Date of birth is required.")
        if not gender:
            errors.append("Gender is required.")
        if not blood_group:
            errors.append("Blood group is required (for your ID card and safety).")
        if not password:
            errors.append("Password is required.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if password != confirm_password:
            errors.append("Passwords do not match.")
        
        if errors:
            for error in errors:
                flash(error, "danger")
            return render_template("auth/register.html", courses=courses)
        
        # Handle Photo Upload
        photo_path = None
        if "photo" in request.files:
            f = request.files["photo"]
            if f and f.filename and allowed_file(f.filename):
                ext = f.filename.rsplit(".", 1)[1].lower()
                fn = f"student_{uuid.uuid4().hex[:12]}.{ext}"
                target_dir = os.path.join(config.UPLOAD_FOLDER)
                os.makedirs(target_dir, exist_ok=True)
                path = os.path.join(target_dir, fn)
                f.save(path)
                photo_path = f"uploads/{fn}"
        
        if not photo_path:
            flash("Profile photo is compulsory for registration.", "danger")
            return render_template("auth/register.html", courses=courses)
        
        # Check if email already exists
        with db_cursor() as (conn, cur):
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                flash("Email is already registered. Please use a different email or login.", "danger")
                return render_template("auth/register.html", courses=courses)
        
        # Get course code for enrollment generation
        course_code = None
        for c in courses:
            if c["id"] == course_id:
                course_code = c["code"]
                break
        
        if not course_code:
            flash("Invalid course selected.", "danger")
            return render_template("auth/register.html", courses=courses)
        
        # Create user and student records
        try:
            # Generate course-wise enrollment number
            enrollment_no = get_next_enrollment_for_course(course_code)
            
            with db_cursor() as (conn, cur):
                is_pg = hasattr(conn, 'cursor_factory')
                
                # Ensure username (enrollment) is not already taken
                cur.execute("SELECT id FROM users WHERE username = %s", (enrollment_no.lower(),))
                if cur.fetchone():
                    flash("Generated enrollment username already exists. Please contact admin.", "danger")
                    return render_template("auth/register.html", courses=courses)
                
                # Create user account (role_id=3 for student)
                if is_pg:
                    cur.execute(
                        """
                        INSERT INTO users (role_id, email, username, password_hash) 
                        VALUES (3, %s, %s, %s) RETURNING id
                        """,
                        (email, enrollment_no.lower(), hash_password(password))
                    )
                    user_id = cur.fetchone()["id"]
                else:
                    cur.execute(
                        """
                        INSERT INTO users (role_id, email, username, password_hash) 
                        VALUES (3, %s, %s, %s)
                        """,
                        (email, enrollment_no.lower(), hash_password(password))
                    )
                    user_id = cur.lastrowid
                
                # Create student profile
                cur.execute(
                    """
                    INSERT INTO students (
                        user_id, enrollment_no, first_name, last_name, 
                        email, phone, date_of_birth, gender, 
                        photo_path, course_id, current_semester, admission_date
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id, enrollment_no, first_name, last_name,
                        email, phone or None, dob, gender,
                        photo_path, course_id, 1, date.today()
                    )
                )
                
                # IMPORTANT: Must commit before calling ensure_card_record 
                # because it uses its own connection
                conn.commit()
                
                # Initial card record (blood group added from form)
                cur.execute("SELECT id FROM students WHERE enrollment_no = %s", (enrollment_no,))
                sid = cur.fetchone()["id"]
                default_id_card_service.ensure_card_record(sid, blood_group=blood_group)
                
                # Final commit for the ID card record (handled inside ensure_card_record, but good to be safe)
                conn.commit()
            
            flash(f"Registration successful! Your enrollment number is: {enrollment_no}. Please wait for admin approval before logging in.", "success")
            return redirect(url_for("auth_bp.login"))
        
        except Exception as e:
            flash(f"Registration failed. Please try again. Error: {str(e)[:100]}", "danger")
            return render_template("auth/register.html", courses=courses)
    
    return render_template("auth/register.html", courses=courses)
