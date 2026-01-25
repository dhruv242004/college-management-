"""Authentication, session handling, and role-based authorization."""
import functools
from flask import session, redirect, url_for, request, flash
from werkzeug.security import check_password_hash, generate_password_hash
from database import db_cursor

ROLES = {"admin": 1, "faculty": 2, "student": 3, "accountant": 4}


def login_user(username: str, password: str) -> tuple[bool, str, dict]:
    """
    Authenticate user. Returns (success, message, user_dict).
    user_dict: id, username, email, role_id, role_name, extra_id (student_id/faculty_id).
    """
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.password_hash, u.role_id, r.name AS role_name,
                   s.id AS student_id, f.id AS faculty_id
            FROM users u
            JOIN roles r ON r.id = u.role_id
            LEFT JOIN students s ON s.user_id = u.id
            LEFT JOIN faculty f ON f.user_id = u.id
            WHERE (u.username = %s OR u.email = %s) AND u.is_active = 1
            """,
            (username, username),
        )
        row = cur.fetchone()
    if not row:
        return False, "Invalid username or password.", {}
    if not check_password_hash(row["password_hash"], password):
        return False, "Invalid username or password.", {}
    role = row["role_name"].lower()
    extra = row.get("student_id") or row.get("faculty_id")
    user = {
        "id": row["id"],
        "username": row["username"],
        "email": row["email"],
        "role_id": row["role_id"],
        "role_name": role,
        "extra_id": extra,
    }
    return True, "Login successful.", user


def logout_user():
    """Clear session."""
    session.clear()


def get_current_user():
    """Return current user dict from session or None."""
    return session.get("user")


def require_login(f):
    """Decorator: redirect to login if not authenticated."""

    @functools.wraps(f)
    def inner(*a, **kw):
        if not get_current_user():
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth_bp.login", next=request.url))
        return f(*a, **kw)

    return inner


def require_roles(*allowed):
    """Decorator: require one of the given roles (e.g. 'admin', 'faculty')."""

    def decorator(f):
        @functools.wraps(f)
        def inner(*a, **kw):
            user = get_current_user()
            if not user:
                flash("Please log in to continue.", "warning")
                return redirect(url_for("auth_bp.login", next=request.url))
            if user.get("role_name") not in allowed:
                flash("Access denied.", "danger")
                return redirect(url_for("dashboard"))
            return f(*a, **kw)

        return inner

    return decorator


def hash_password(password: str) -> str:
    return generate_password_hash(password)
