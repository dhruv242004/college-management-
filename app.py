"""College Management System - Flask application."""
import os
import datetime
from flask import Flask, redirect, url_for, render_template, request
from config import config
from auth import get_current_user, require_login, require_roles
from database import db_cursor, init_db
from flask_socketio import SocketIO, join_room, leave_room, emit

app = Flask(__name__)
# Initialize database schema/migrations
try:
    init_db()
except Exception as e:
    print(f"Database initialization failed: {e}")
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["PERMANENT_SESSION_LIFETIME"] = config.PERMANENT_SESSION_LIFETIME
app.config["SESSION_COOKIE_HTTPONLY"] = config.SESSION_COOKIE_HTTPONLY
app.config["SESSION_COOKIE_SAMESITE"] = config.SESSION_COOKIE_SAMESITE

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

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
from routes.chat_routes import chat_bp
from routes.payment_routes import payment_bp
from routes.admin_routes import admin_bp

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
app.register_blueprint(chat_bp, url_prefix="/chat")
app.register_blueprint(payment_bp)
app.register_blueprint(admin_bp, url_prefix="/admin")


@socketio.on("connect")
def handle_connect():
    user = get_current_user()
    if not user:
        return
    uid = user.get("id")
    # Auto-join all conversation rooms for this user
    with db_cursor() as (conn, cur):
        cur.execute("SELECT conversation_id FROM chat_conversation_members WHERE user_id = %s", (uid,))
        convs = cur.fetchall()
        for c in convs:
            join_room(f"conv_{c['conversation_id']}")


@socketio.on("join_conversation")
def handle_join_conversation(data):
    user = get_current_user()
    if not user:
        return
    conv_id = data.get("conversation_id")
    if not conv_id:
        return
    uid = user.get("id")
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM chat_conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, uid),
        )
        if not cur.fetchone():
            return
    room = f"conv_{conv_id}"
    join_room(room)
    # Mark user as online in this conversation room
    emit("user_online", {"user_id": uid}, room=room, include_self=False)


@socketio.on("send_message")
def handle_send_message(data):
    user = get_current_user()
    if not user:
        return
    uid = user.get("id")
    conv_id = data.get("conversation_id")
    content = (data.get("content") or "").strip()
    message_type = data.get("message_type") or "text"
    file_id = data.get("file_id")
    if not conv_id:
        return
    if message_type == "text" and not content:
        return
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM chat_conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, uid),
        )
        if not cur.fetchone():
            return
        is_pg = hasattr(conn, 'cursor_factory')
        if is_pg:
            cur.execute(
                """
                INSERT INTO chat_messages (conversation_id, sender_id, content, message_type, file_id, status)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (conv_id, uid, content or None, message_type, file_id, "sent"),
            )
            mid = cur.fetchone()['id']
        else:
            cur.execute(
                """
                INSERT INTO chat_messages (conversation_id, sender_id, content, message_type, file_id, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (conv_id, uid, content or None, message_type, file_id, "sent"),
            )
            mid = cur.lastrowid
        cur.execute(
            """
            INSERT INTO chat_message_status (message_id, user_id, status)
            VALUES (%s, %s, %s)
            ON CONFLICT (message_id, user_id) DO UPDATE SET 
                status = EXCLUDED.status, 
                status_at = CURRENT_TIMESTAMP
            """,
            (mid, uid, "read"),
        )
        cur.execute(
            "SELECT user_id FROM chat_conversation_members WHERE conversation_id = %s AND user_id <> %s",
            (conv_id, uid),
        )
        others = cur.fetchall()
        for row in others:
            cur.execute(
                """
                INSERT INTO chat_message_status (message_id, user_id, status)
                VALUES (%s, %s, %s)
                ON CONFLICT (message_id, user_id) DO UPDATE SET 
                    status_at = CURRENT_TIMESTAMP
                """,
                (mid, row["user_id"], "sent"),
            )
        cur.execute(
            """
            SELECT m.id, m.conversation_id, m.sender_id, u.username,
                   m.content, m.message_type, m.file_id, m.status,
                   m.created_at, f.original_name, f.stored_path
            FROM chat_messages m
            JOIN users u ON u.id = m.sender_id
            LEFT JOIN chat_files f ON f.id = m.file_id
            WHERE m.id = %s
            """,
            (mid,),
        )
        msg = cur.fetchone()
        conn.commit()
    room = f"conv_{conv_id}"
    payload = {
        "id": msg["id"],
        "conversation_id": msg["conversation_id"],
        "sender_id": msg["sender_id"],
        "sender_name": msg["username"],
        "content": msg["content"],
        "message_type": msg["message_type"],
        "file_id": msg["file_id"],
        "file_name": msg["original_name"],
        "file_url": f"/static/{msg['stored_path']}" if msg["stored_path"] else None,
        "status": msg["status"],
        "created_at": msg["created_at"].strftime("%H:%M"),
        "is_me": False,
    }
    # Send to others in the room
    emit("new_message", payload, room=room, include_self=False)
    # Send to self with is_me: True
    payload["is_me"] = True
    emit("new_message", payload, to=request.sid)


@socketio.on("typing")
def handle_typing(data):
    user = get_current_user()
    if not user:
        return
    conv_id = data.get("conversation_id")
    if not conv_id:
        return
    uid = user.get("id")
    is_typing = bool(data.get("is_typing"))
    room = f"conv_{conv_id}"
    emit("typing", {"conversation_id": conv_id, "user_id": uid, "is_typing": is_typing}, room=room, include_self=False)


@socketio.on("mark_read")
def handle_mark_read(data):
    user = get_current_user()
    if not user:
        return
    uid = user.get("id")
    conv_id = data.get("conversation_id")
    message_id = data.get("message_id")
    if not conv_id or not message_id:
        return
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM chat_conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, uid),
        )
        if not cur.fetchone():
            return
        cur.execute(
            """
            UPDATE chat_message_status
            SET status = 'read', status_at = NOW()
            WHERE message_id = %s AND user_id = %s
            """,
            (message_id, uid),
        )
        conn.commit()
    room = f"conv_{conv_id}"
    emit("message_read", {"message_id": message_id, "user_id": uid}, room=room, include_self=False)


@socketio.on("edit_message")
def handle_edit_message(data):
    user = get_current_user()
    if not user:
        return
    uid = user.get("id")
    message_id = data.get("message_id")
    content = (data.get("content") or "").strip()
    if not message_id or not content:
        return
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT conversation_id, sender_id FROM chat_messages WHERE id = %s",
            (message_id,),
        )
        msg = cur.fetchone()
        if not msg or msg["sender_id"] != uid:
            return
        cur.execute(
            "UPDATE chat_messages SET content = %s, edited_at = NOW() WHERE id = %s",
            (content, message_id),
        )
        conn.commit()
    room = f"conv_{msg['conversation_id']}"
    emit("message_edited", {"id": message_id, "content": content}, room=room)


@socketio.on("delete_message")
def handle_delete_message(data):
    user = get_current_user()
    if not user:
        return
    uid = user.get("id")
    message_id = data.get("message_id")
    if not message_id:
        return
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT conversation_id, sender_id FROM chat_messages WHERE id = %s",
            (message_id,),
        )
        msg = cur.fetchone()
        if not msg or msg["sender_id"] != uid:
            return
        cur.execute(
            "UPDATE chat_messages SET content = NULL, deleted_at = NOW() WHERE id = %s",
            (message_id,),
        )
        conn.commit()
    room = f"conv_{msg['conversation_id']}"
    emit("message_deleted", {"id": message_id}, room=room)


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
            cur.execute("SELECT COUNT(*) AS c FROM notices WHERE is_published = TRUE")
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
            cur.execute(
                "SELECT COUNT(*) AS c FROM chat_message_status WHERE user_id = %s AND status <> 'read'",
                (user.get("id"),),
            )
            stats["unread_messages"] = cur.fetchone()["c"]
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
                cur.execute(
                    "SELECT COUNT(*) AS c FROM chat_message_status WHERE user_id = %s AND status <> 'read'",
                    (user.get("id"),),
                )
                stats["unread_messages"] = cur.fetchone()["c"]
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
    socketio.run(app, debug=True, host="0.0.0.0", port=5000, allow_unsafe_werkzeug=True)
