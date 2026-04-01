import os
import uuid
from flask import Blueprint, render_template, request, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from auth import require_login, get_current_user
from database import db_cursor
from config import config
from chatbot_engine import default_chatbot_engine

chat_bp = Blueprint("chat_bp", __name__)


def chat_allowed_file(filename):
    ext = filename.rsplit(".", 1)[1].lower() if "." in filename else ""
    return ext in {"png", "jpg", "jpeg", "gif", "pdf", "doc", "docx"}


def get_user_conversations(user_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT c.id, c.type, c.title,
                   (SELECT u.username FROM chat_conversation_members cm2 
                    JOIN users u ON u.id = cm2.user_id 
                    WHERE cm2.conversation_id = c.id AND cm2.user_id <> %s 
                    LIMIT 1) AS other_username,
                   MAX(m.created_at) AS last_message_at
            FROM chat_conversations c
            JOIN chat_conversation_members cm ON cm.conversation_id = c.id
            LEFT JOIN chat_messages m ON m.conversation_id = c.id
            WHERE cm.user_id = %s
            GROUP BY c.id, c.type, c.title
            ORDER BY last_message_at DESC, c.id DESC
            """,
            (user_id, user_id),
        )
        rows = cur.fetchall()
        # Post-process for display title if private
        for r in rows:
            if r["type"] == "private" and not r["title"]:
                r["title"] = r["other_username"] or f"Chat {r['id']}"
    return rows


@chat_bp.route("/")
@require_login
def index():
    user = get_current_user()
    uid = user.get("id")
    conversations = get_user_conversations(uid)
    return render_template("chat/index.html", conversations=conversations)


@chat_bp.route("/api/conversations", methods=["GET"])
@require_login
def list_conversations():
    uid = get_current_user().get("id")
    rows = get_user_conversations(uid)
    return jsonify({"conversations": rows})


@chat_bp.route("/api/targets", methods=["GET"])
@require_login
def list_chat_targets():
    """Return allowed private-chat targets for the current user.

    - If faculty: students from courses/semesters assigned via faculty_subject_assignment.
    - If student: faculty teaching the student's course and semester.
    """
    try:
        user = get_current_user()
        role = user.get("role_name")
        targets = []
        with db_cursor() as (conn, cur):
            if role == "faculty":
                fid = user.get("extra_id")
                if not fid:
                    return jsonify({"targets": []})
                cur.execute(
                    """
                    SELECT DISTINCT u.id AS user_id,
                           CONCAT(s.first_name, ' ', s.last_name) AS full_name,
                           s.enrollment_no,
                           c.name AS course_name,
                           s.current_semester AS semester
                    FROM faculty_subject_assignment fsa
                    JOIN students s
                      ON s.course_id = fsa.course_id
                     AND s.current_semester = fsa.semester
                    JOIN courses c ON c.id = s.course_id
                    JOIN users u ON u.id = s.user_id
                    WHERE fsa.faculty_id = %s
                    ORDER BY full_name
                    """,
                    (fid,),
                )
                rows = cur.fetchall()
                for r in rows:
                    targets.append(
                        {
                            "user_id": r["user_id"],
                            "display_name": f'{r["full_name"]} ({r["enrollment_no"]})',
                            "detail": f'{r["course_name"]} – Sem {r["semester"]}',
                        }
                    )
            elif role == "student":
                sid = user.get("extra_id")
                if not sid:
                    return jsonify({"targets": []})
                cur.execute(
                    """
                    SELECT DISTINCT u.id AS user_id,
                           CONCAT(f.first_name, ' ', f.last_name) AS full_name,
                           f.emp_id,
                           d.name AS dept_name
                    FROM students s
                    JOIN faculty_subject_assignment fsa
                      ON fsa.course_id = s.course_id
                     AND fsa.semester = s.current_semester
                    JOIN faculty f ON f.id = fsa.faculty_id
                    JOIN departments d ON d.id = f.department_id
                    JOIN users u ON u.id = f.user_id
                    WHERE s.id = %s
                    ORDER BY full_name
                    """,
                    (sid,),
                )
                rows = cur.fetchall()
                for r in rows:
                    targets.append(
                        {
                            "user_id": r["user_id"],
                            "display_name": f'{r["full_name"]} ({r["emp_id"]})',
                            "detail": r["dept_name"],
                        }
                    )
            else:
                return jsonify({"targets": []})
        return jsonify({"targets": targets})
    except Exception as e:
        print(f"DEBUG: list_chat_targets error: {str(e)}")
        return jsonify({"error": str(e)}), 500


@chat_bp.route("/api/conversations/start", methods=["POST"])
@require_login
def start_conversation():
    user = get_current_user()
    uid = user.get("id")
    conv_type = request.json.get("type")
    target_user_id = request.json.get("target_user_id")
    subject_id = request.json.get("subject_id")
    course_id = request.json.get("course_id")
    semester = request.json.get("semester")
    title = request.json.get("title") or None
    if conv_type not in {"private", "class", "group"}:
        return jsonify({"error": "Invalid type"}), 400
    with db_cursor() as (conn, cur):
        if conv_type == "private":
            if not target_user_id:
                return jsonify({"error": "target_user_id required"}), 400
            cur.execute(
                """
                SELECT c.id
                FROM chat_conversations c
                JOIN chat_conversation_members cm1 ON cm1.conversation_id = c.id
                JOIN chat_conversation_members cm2 ON cm2.conversation_id = c.id
                WHERE c.type = 'private' AND cm1.user_id = %s AND cm2.user_id = %s
                """,
                (uid, target_user_id),
            )
            row = cur.fetchone()
            if row:
                return jsonify({"conversation_id": row["id"], "created": False})
        # Use RETURNING for PostgreSQL, lastrowid for MySQL
        is_pg = hasattr(conn, 'cursor_factory')
        
        if is_pg:
            cur.execute(
                """
                INSERT INTO chat_conversations (type, subject_id, course_id, semester, title, created_by)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (conv_type, subject_id, course_id, semester, title, uid),
            )
            conv_id = cur.fetchone()['id']
        else:
            cur.execute(
                """
                INSERT INTO chat_conversations (type, subject_id, course_id, semester, title, created_by)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (conv_type, subject_id, course_id, semester, title, uid),
            )
            conv_id = cur.lastrowid
        cur.execute(
            "INSERT INTO chat_conversation_members (conversation_id, user_id, role_in_conversation) VALUES (%s, %s, %s)",
            (conv_id, uid, user.get("role_name")),
        )
        if conv_type == "private":
            cur.execute(
                "INSERT INTO chat_conversation_members (conversation_id, user_id, role_in_conversation) VALUES (%s, %s, %s)",
                (conv_id, target_user_id, None),
            )
        elif conv_type == "class":
            if not course_id or not semester:
                return jsonify({"error": "course_id and semester required"}), 400
            cur.execute(
                "SELECT id FROM students WHERE course_id = %s AND current_semester = %s",
                (course_id, semester),
            )
            students = cur.fetchall()
            for s in students:
                cur.execute(
                    "INSERT INTO chat_conversation_members (conversation_id, user_id, role_in_conversation) VALUES (%s, %s, %s)",
                    (conv_id, s["user_id"], "student"),
                )
        conn.commit()
    return jsonify({"conversation_id": conv_id, "created": True})


@chat_bp.route("/api/conversations/<int:conv_id>/messages", methods=["GET"])
@require_login
def get_messages(conv_id):
    uid = get_current_user().get("id")
    before_id = request.args.get("before_id", type=int)
    limit = request.args.get("limit", type=int) or 50
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM chat_conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, uid),
        )
        if not cur.fetchone():
            return jsonify({"error": "Forbidden"}), 403
        params = [conv_id]
        sql = """
            SELECT m.id, m.sender_id, u.username, u.role_id,
                   m.content, m.message_type, m.file_id, m.status,
                   m.created_at, m.edited_at, m.deleted_at,
                   f.original_name AS file_name, f.stored_path AS file_path, f.mime_type
            FROM chat_messages m
            JOIN users u ON u.id = m.sender_id
            LEFT JOIN chat_files f ON f.id = m.file_id
            WHERE m.conversation_id = %s
        """
        if before_id:
            sql += " AND m.id < %s"
            params.append(before_id)
        sql += " ORDER BY m.id DESC LIMIT %s"
        params.append(limit)
        cur.execute(sql, tuple(params))
        rows = cur.fetchall()
    rows.reverse()
    return jsonify({"messages": rows})


@chat_bp.route("/api/messages/search", methods=["GET"])
@require_login
def search_messages():
    uid = get_current_user().get("id")
    conv_id = request.args.get("conversation_id", type=int)
    q = (request.args.get("q") or "").strip()
    if not conv_id or not q:
        return jsonify({"messages": []})
    like = f"%{q}%"
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT 1 FROM chat_conversation_members WHERE conversation_id = %s AND user_id = %s",
            (conv_id, uid),
        )
        if not cur.fetchone():
            return jsonify({"error": "Forbidden"}), 403
        cur.execute(
            """
            SELECT m.id, m.sender_id, u.username,
                   m.content, m.message_type, m.created_at
            FROM chat_messages m
            JOIN users u ON u.id = m.sender_id
            WHERE m.conversation_id = %s AND m.content LIKE %s
            ORDER BY m.created_at DESC
            LIMIT 50
            """,
            (conv_id, like),
        )
        rows = cur.fetchall()
    return jsonify({"messages": rows})


@chat_bp.route("/upload", methods=["POST"])
@require_login
def upload_file():
    user = get_current_user()
    uid = user.get("id")
    if "file" not in request.files:
        return jsonify({"error": "No file"}), 400
    f = request.files["file"]
    if not f or not f.filename:
        return jsonify({"error": "No file"}), 400
    if not chat_allowed_file(f.filename):
        return jsonify({"error": "Invalid file type"}), 400
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.seek(0)
    if size > 5 * 1024 * 1024:
        return jsonify({"error": "File too large"}), 400
    ext = f.filename.rsplit(".", 1)[1].lower()
    fn = f"chat_{uuid.uuid4().hex[:16]}.{ext}"
    os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)
    path = os.path.join(config.UPLOAD_FOLDER, fn)
    f.save(path)
    stored = f"uploads/{fn}"
    mime = f.mimetype
    with db_cursor() as (conn, cur):
        is_pg = hasattr(conn, 'cursor_factory')
        if is_pg:
            cur.execute(
                """
                INSERT INTO chat_files (stored_path, original_name, mime_type, size_bytes, uploaded_by)
                VALUES (%s, %s, %s, %s, %s) RETURNING id
                """,
                (stored, f.filename, mime, size, uid),
            )
            file_id = cur.fetchone()['id']
        else:
            cur.execute(
                """
                INSERT INTO chat_files (stored_path, original_name, mime_type, size_bytes, uploaded_by)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (stored, f.filename, mime, size, uid),
            )
            file_id = cur.lastrowid
        conn.commit()
    return jsonify({"file_id": file_id, "url": f"/static/{stored}", "name": f.filename, "mime": mime})


@chat_bp.route("/assistant", methods=["POST"])
@require_login
def assistant_chat():
    """AI College Assistant endpoint (JSON).

    Expects: {"message": "..."}
    Returns: {"reply": "...", "intent": "...", "source": "...", "metadata": {...}}
    """
    user = get_current_user()
    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": "Message is required."}), 400
    try:
        result = default_chatbot_engine.get_response(user, message)
        return jsonify(result)
    except Exception as e:
        # Keep error message generic for clients
        return jsonify({"error": "Sorry, something went wrong while answering. Please try again."}), 500

