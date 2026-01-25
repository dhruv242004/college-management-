"""Authentication routes: login, logout."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, session

from auth import login_user, logout_user, get_current_user, require_login

auth_bp = Blueprint("auth_bp", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if get_current_user():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        if not username or not password:
            flash("Username and password are required.", "danger")
            return render_template("auth/login.html")
        try:
            ok, msg, user = login_user(username, password)
        except Exception as e:
            err = str(e)[:120] + "…" if len(str(e)) > 120 else str(e)
            flash(
                "Database error. Ensure MySQL is running, then run: mysql -u root -p < schema.sql and python seed_admin.py. " + err,
                "danger",
            )
            return render_template("auth/login.html")
        if not ok:
            flash(msg, "danger")
            return render_template("auth/login.html")
        session["user"] = user
        session.permanent = True
        session.modified = True
        flash(msg, "success")
        next_url = request.args.get("next") or request.form.get("next") or url_for("dashboard")
        return redirect(next_url)
    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth_bp.login"))
