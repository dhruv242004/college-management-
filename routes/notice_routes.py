"""Notice board & announcements."""
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor

notice_bp = Blueprint("notice_bp", __name__)


@notice_bp.route("/")
@require_login
def list_notices():
    user = get_current_user()
    role = user.get("role_name", "")
    category = request.args.get("category")
    with db_cursor() as (conn, cur):
        sql = """
            SELECT n.id, n.title, n.content, n.category, n.target_role, n.created_at, u.username
            FROM notices n
            JOIN users u ON u.id = n.user_id
            WHERE n.is_published = 1
        """
        params = []
        if category:
            sql += " AND n.category = %s"
            params.append(category)
        sql += " ORDER BY n.created_at DESC"
        cur.execute(sql, params or ())
        notices = cur.fetchall()
    return render_template("notices/list.html", notices=notices, category=category)


@notice_bp.route("/add", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def add():
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        category = request.form.get("category") or "General"
        target = request.form.get("target_role") or None
        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("notice_bp.add"))
        uid = get_current_user()["id"]
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO notices (user_id, title, content, category, target_role) VALUES (%s, %s, %s, %s, %s)",
                (uid, title, content, category, target),
            )
        flash("Notice added.", "success")
        return redirect(url_for("notice_bp.list_notices"))
    return render_template("notices/form.html", notice=None)


@notice_bp.route("/<int:nid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def edit(nid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM notices WHERE id = %s", (nid,))
        notice = cur.fetchone()
    if not notice:
        flash("Notice not found.", "danger")
        return redirect(url_for("notice_bp.list_notices"))
    if request.method == "POST":
        title = (request.form.get("title") or "").strip()
        content = (request.form.get("content") or "").strip()
        category = request.form.get("category") or "General"
        target = request.form.get("target_role") or None
        if not title or not content:
            flash("Title and content are required.", "danger")
            return redirect(url_for("notice_bp.edit", nid=nid))
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE notices SET title = %s, content = %s, category = %s, target_role = %s WHERE id = %s",
                (title, content, category, target, nid),
            )
        flash("Notice updated.", "success")
        return redirect(url_for("notice_bp.list_notices"))
    return render_template("notices/form.html", notice=notice)


@notice_bp.route("/<int:nid>/delete", methods=["POST"])
@require_login
@require_roles("admin", "faculty")
def delete(nid):
    with db_cursor() as (conn, cur):
        cur.execute("DELETE FROM notices WHERE id = %s", (nid,))
        if cur.rowcount == 0:
            flash("Notice not found.", "danger")
        else:
            flash("Notice deleted.", "success")
    return redirect(url_for("notice_bp.list_notices"))
