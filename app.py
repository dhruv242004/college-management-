"""College Management System - Flask application."""
import os
import datetime
from flask import Flask, redirect, url_for, render_template
from config import config
from auth import get_current_user, require_login, require_roles
from database import db_cursor

app = Flask(__name__)
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = config.PERMANENT_SESSION_LIFETIME
app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

from routes.auth_routes import auth_bp
from routes.student_routes import students_bp
from routes.faculty_routes import faculty_bp
from routes.academic_routes import academic_bp
from routes.attendance_routes import attendance_bp
from routes.exam_routes import exam_bp
from routes.fees_routes import fees_bp
from routes.notice_routes import notice_bp
from routes.timetable_routes import timetable_bp
from routes.reports_routes import reports_bp

app.register_blueprint(auth_bp, url_prefix="/auth")
app.register_blueprint(students_bp, url_prefix="/students")
app.register_blueprint(faculty_bp, url_prefix="/faculty")
app.register_blueprint(academic_bp, url_prefix="/academic")
app.register_blueprint(attendance_bp, url_prefix="/attendance")
app.register_blueprint(exam_bp, url_prefix="/exams")
app.register_blueprint(fees_bp, url_prefix="/fees")
app.register_blueprint(notice_bp, url_prefix="/notices")
app.register_blueprint(timetable_bp, url_prefix="/timetable")
app.register_blueprint(reports_bp, url_prefix="/reports")


@app.route("/")
def index():
    if get_current_user():
        return redirect(url_for("dashboard"))
    return redirect(url_for("auth_bp.login"))


@app.route("/dashboard")
@require_login
def dashboard():
    user = get_current_user()
    role = user.get("role_name", "")
    stats = {}
    with db_cursor() as (conn, cur):
        if role == "admin":
            cur.execute("SELECT COUNT(*) AS c FROM students")
            stats["students"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM faculty")
            stats["faculty"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM courses")
            stats["courses"] = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM notices WHERE is_published = 1")
            stats["notices"] = cur.fetchone()["c"]
        elif role == "faculty":
            fid = user.get("extra_id")
            if fid:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM faculty_subject_assignment WHERE faculty_id = %s",
                    (fid,),
                )
                stats["assignments"] = cur.fetchone()["c"]
            else:
                stats["assignments"] = 0
        elif role == "student":
            sid = user.get("extra_id")
            if sid:
                cur.execute(
                    "SELECT COUNT(*) AS c FROM attendance WHERE student_id = %s AND status = 'P'",
                    (sid,),
                )
                stats["present"] = cur.fetchone()["c"]
                cur.execute("SELECT COUNT(*) AS c FROM attendance WHERE student_id = %s", (sid,))
                stats["total"] = cur.fetchone()["c"]
            else:
                stats["present"] = stats["total"] = 0
        else:
            cur.execute("SELECT COUNT(*) AS c FROM fee_payments")
            stats["payments"] = cur.fetchone()["c"]
    return render_template(
        "dashboard.html",
        user=user,
        role=role,
        stats=stats,
    )


@app.context_processor
def inject_user():
    return {"current_user": get_current_user()}


@app.template_filter("date")
def date_filter(value, format="%Y-%m-%d"):
    if value == "now":
        return datetime.datetime.now().strftime(format)
    if hasattr(value, "strftime"):
        return value.strftime(format)
    return value


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
