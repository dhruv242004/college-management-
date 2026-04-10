"""Attendance: mark, view, reports, validation (no duplicate) + QR-based system."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from auth import require_login, require_roles, get_current_user
from database import db_cursor
from qr_service import QRAttendanceService
import json

attendance_bp = Blueprint("attendance_bp", __name__)
qr_service = QRAttendanceService()

ACAD_YEAR = "2024-25"


@attendance_bp.route("/")
@require_login
@require_roles("admin", "faculty", "student")
def index():
    """Main attendance index with QR and traditional options."""
    user = get_current_user()
    role = user.get("role_name")
    fid = user.get("extra_id") if role == "faculty" else None
    
    # Students see a simplified view
    if role == "student":
        return render_template("attendance/index.html")
        
    is_faculty_assigned = True
    with db_cursor() as (conn, cur):
        if fid:
            cur.execute(
                """
                SELECT fsa.id, fsa.subject_id, fsa.course_id, fsa.semester, s.name AS subject_name, c.name AS course_name
                FROM faculty_subject_assignment fsa
                JOIN subjects s ON s.id = fsa.subject_id
                JOIN courses c ON c.id = fsa.course_id
                WHERE fsa.faculty_id = %s AND fsa.academic_year = %s
                ORDER BY fsa.semester, s.name
                """,
                (fid, ACAD_YEAR),
            )
            assignments = cur.fetchall()
            if not assignments:
                is_faculty_assigned = False
                cur.execute(
                    """
                    SELECT s.id AS subject_id, c.id AS course_id, s.semester, s.name AS subject_name, c.name AS course_name
                    FROM subjects s
                    JOIN courses c ON c.id = s.course_id
                    ORDER BY c.name, s.semester
                    """
                )
                assignments = cur.fetchall()
        else:
            cur.execute(
                """
                SELECT s.id AS subject_id, c.id AS course_id, s.semester, s.name AS subject_name, c.name AS course_name
                FROM subjects s
                JOIN courses c ON c.id = s.course_id
                ORDER BY c.name, s.semester
                """
            )
            assignments = cur.fetchall()
    return render_template("attendance/index.html", assignments=assignments, is_faculty=bool(fid), is_faculty_assigned=is_faculty_assigned)


# ============================================================================
# QR-BASED ATTENDANCE ROUTES
# ============================================================================

@attendance_bp.route("/qr/generate", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def qr_generate():
    """Generate QR code for marking attendance (Admins & Faculty)."""
    user = get_current_user()
    fid = user.get("extra_id") if user.get("role_name") == "faculty" else None
    role = user.get("role_name")
    
    if request.method == "POST":
        subject_id = request.form.get("subject_id", type=int)
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("semester", type=int)
        duration = request.form.get("duration", default=10, type=int)
        
        if not subject_id or not course_id or not semester:
            flash("Missing required fields: subject, course, or semester", "danger")
            return redirect(url_for("attendance_bp.qr_generate"))
        
        # Get faculty IP (optional geolocation)
        faculty_ip = request.remote_addr
        
        # If admin, we need a faculty ID for the session. Use the first one or None if not available.
        effective_fid = fid
        if role == "admin" and not effective_fid:
            with db_cursor() as (conn, cur):
                cur.execute("SELECT id FROM faculty LIMIT 1")
                res = cur.fetchone()
                effective_fid = res['id'] if res else None
        
        if not effective_fid:
            flash("No faculty record found to associate with this session.", "danger")
            return redirect(url_for("attendance_bp.qr_generate"))
        
        try:
            session_data = qr_service.generate_session(
                faculty_id=effective_fid,
                subject_id=subject_id,
                course_id=course_id,
                semester=semester,
                duration_minutes=duration,
                ip_address=faculty_ip
            )
            
            # Get additional session info for display
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    SELECT s.name AS subject_name, c.name AS course_name, 
                           CONCAT(f.first_name, ' ', f.last_name) AS faculty_name
                    FROM subjects s
                    JOIN courses c ON c.id = s.course_id
                    JOIN faculty f ON f.id = %s
                    WHERE s.id = %s
                    """,
                    (effective_fid, subject_id)
                )
                session_info = cur.fetchone()
                
                if session_info:
                    session_data.update({
                        'subject_name': session_info['subject_name'],
                        'course_name': session_info['course_name'],
                        'faculty_name': session_info['faculty_name'],
                        'date': date.today().strftime('%Y-%m-%d'),
                        'semester': semester
                    })
            
            return render_template(
                "attendance/qr_display.html",
                session=session_data,
                subject_id=subject_id
            )
        except Exception as e:
            flash(f"Error generating QR code: {str(e)}", "danger")
            return redirect(url_for("attendance_bp.qr_generate"))
    
    # Show QR generation form
    is_faculty_assigned = True
    with db_cursor() as (conn, cur):
        # Default: Get assignments for faculty
        if role == "faculty":
            cur.execute(
                """
                SELECT fsa.id, fsa.subject_id, fsa.course_id, fsa.semester, 
                       s.name AS subject_name, c.name AS course_name
                FROM faculty_subject_assignment fsa
                JOIN subjects s ON s.id = fsa.subject_id
                JOIN courses c ON c.id = fsa.course_id
                WHERE fsa.faculty_id = %s AND fsa.academic_year = %s
                ORDER BY fsa.semester, s.name
                """,
                (fid, ACAD_YEAR),
            )
            assignments = cur.fetchall()
            
            # If no assignments found for faculty, fetch ALL subjects as fallback
            if not assignments:
                is_faculty_assigned = False
                cur.execute(
                    """
                    SELECT s.id AS subject_id, c.id AS course_id, s.semester, 
                           s.name AS subject_name, c.name AS course_name
                    FROM subjects s
                    JOIN courses c ON c.id = s.course_id
                    ORDER BY c.name, s.semester
                    """
                )
                assignments = cur.fetchall()
        else:
            # Admin view: Get all subjects
            cur.execute(
                """
                SELECT s.id AS subject_id, c.id AS course_id, s.semester, 
                       s.name AS subject_name, c.name AS course_name
                FROM subjects s
                JOIN courses c ON c.id = s.course_id
                ORDER BY c.name, s.semester
                """
            )
            assignments = cur.fetchall()
    
    return render_template("attendance/qr_generate.html", assignments=assignments, is_faculty_assigned=is_faculty_assigned)


@attendance_bp.route("/qr/session/<session_id>")
@require_login
@require_roles("faculty")
def qr_session_display(session_id):
    """Display active QR session with live attendance count."""
    user = get_current_user()
    fid = user.get("extra_id")
    
    session_info = qr_service.get_session_details(session_id)
    if not session_info or session_info['faculty_id'] != fid:
        flash("Unauthorized or session not found", "danger")
        return redirect(url_for("attendance_bp.qr_generate"))
    
    return render_template(
        "attendance/qr_session.html",
        session=session_info,
        session_id=session_id
    )


@attendance_bp.route("/qr/scan", methods=["GET", "POST"])
@require_login
@require_roles("student")
def qr_scan():
    """Student: Scan QR code to mark attendance."""
    user = get_current_user()
    sid = user.get("extra_id")
    
    if request.method == "POST":
        token = request.form.get("qr_token") or request.get_json().get("qr_token")
        
        if not token:
            return jsonify({"success": False, "message": "No QR token provided"}), 400
        
        # Get device info
        device_info = request.headers.get('User-Agent', '')
        student_ip = request.remote_addr
        
        # Get geolocation from request (if available from JavaScript)
        location_data = request.get_json() or {}
        latitude = location_data.get('latitude')
        longitude = location_data.get('longitude')
        accuracy = location_data.get('accuracy')
        
        success, message, details = qr_service.validate_and_mark_attendance(
            qr_token=token,
            student_id=sid,
            ip_address=student_ip,
            device_info=device_info,
            latitude=latitude,
            longitude=longitude,
            accuracy=accuracy
        )
        
        return jsonify({
            "success": success,
            "message": message,
            "details": details
        })
    
    return render_template("attendance/qr_scan.html")


@attendance_bp.route("/otp/mark", methods=["POST"])
@require_login
@require_roles("student")
def otp_mark():
    """Student: Mark attendance using a unique code (OTP)."""
    user = get_current_user()
    sid = user.get("extra_id")
    
    data = request.get_json() or {}
    otp_code = data.get("otp_code")
    
    if not otp_code:
        return jsonify({"success": False, "message": "Attendance code is required"}), 400
    
    # High-level security: IP and User-Agent logging
    device_info = request.headers.get('User-Agent', '')
    student_ip = request.remote_addr
    
    # Optional geolocation
    latitude = data.get('latitude')
    longitude = data.get('longitude')
    accuracy = data.get('accuracy')
    
    success, message, details = qr_service.validate_otp_and_mark_attendance(
        otp_code=otp_code,
        student_id=sid,
        ip_address=student_ip,
        device_info=device_info,
        latitude=latitude,
        longitude=longitude,
        accuracy=accuracy
    )
    
    return jsonify({
        "success": success,
        "message": message,
        "details": details
    })


@attendance_bp.route("/qr/api/session/<session_id>/status")
@require_login
@require_roles("faculty")
def qr_session_status(session_id):
    """Get live session status and attendance count (AJAX)."""
    user = get_current_user()
    fid = user.get("extra_id")
    
    session_info = qr_service.get_session_details(session_id)
    if not session_info or session_info['faculty_id'] != fid:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Calculate remaining time
    expiry_time = datetime.fromisoformat(session_info['expiry_time'])
    remaining_seconds = max(0, int((expiry_time - datetime.utcnow()).total_seconds()))
    
    return jsonify({
        "session_id": session_id,
        "status": session_info['status'],
        "attendance_count": session_info['attendance_count'],
        "remaining_seconds": remaining_seconds,
        "subject_name": session_info['subject_name'],
        "faculty_name": f"{session_info['first_name']} {session_info['last_name']}",
        "start_time": session_info['start_time'],
        "expiry_time": session_info['expiry_time']
    })


@attendance_bp.route("/qr/api/session/<session_id>/attendance")
@require_login
@require_roles("faculty")
def qr_get_attendance(session_id):
    """Get all attendance records for a session (AJAX)."""
    user = get_current_user()
    fid = user.get("extra_id")
    
    session_info = qr_service.get_session_details(session_id)
    if not session_info or session_info['faculty_id'] != fid:
        return jsonify({"error": "Unauthorized"}), 403
    
    # Get DB session ID
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id FROM attendance_sessions WHERE session_id = %s", (session_id,))
        result = cur.fetchone()
        session_db_id = result['id'] if result else None
    
    if not session_db_id:
        return jsonify({"error": "Session not found"}), 404
    
    attendance_records = qr_service.get_session_attendance(session_db_id)
    
    return jsonify({
        "attendance": [dict(record) if hasattr(record, 'items') else record for record in attendance_records],
        "total_count": len(attendance_records)
    })


@attendance_bp.route("/qr/api/session/<session_id>/close", methods=["POST"])
@require_login
@require_roles("faculty")
def qr_close_session(session_id):
    """Close an attendance session (prevent further scans)."""
    user = get_current_user()
    fid = user.get("extra_id")
    
    success, message = qr_service.close_session(session_id, fid)
    
    return jsonify({
        "success": success,
        "message": message
    })


# ============================================================================
# TRADITIONAL ATTENDANCE MARKING (Legacy Support)
# ============================================================================

@attendance_bp.route("/mark", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def mark():
    """Mark attendance manually (traditional method)."""
    user = get_current_user()
    fid = user.get("extra_id") if user.get("role_name") == "faculty" else None
    subject_id = request.args.get("subject_id", type=int)
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    att_date = request.args.get("date") or request.form.get("att_date") or str(date.today())
    if not all([subject_id, course_id, semester]):
        flash("Subject, course, and semester are required.", "danger")
        return redirect(url_for("attendance_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM subjects WHERE id = %s",
            (subject_id,),
        )
        subj = cur.fetchone()
        cur.execute(
            """
            SELECT s.id, s.enrollment_no, s.first_name, s.last_name
            FROM students s
            WHERE s.course_id = %s AND s.current_semester = %s
            ORDER BY s.enrollment_no
            """,
            (course_id, semester),
        )
        students = cur.fetchall()
        cur.execute(
            """
            SELECT a.student_id, a.status
            FROM attendance a
            WHERE a.subject_id = %s AND a.att_date = %s
            """,
            (subject_id, att_date),
        )
        existing = {r["student_id"]: r["status"] for r in cur.fetchall()}
    if not subj:
        flash("Subject not found.", "danger")
        return redirect(url_for("attendance_bp.index"))
    faculty_id = fid
    if not faculty_id:
        with db_cursor() as (conn, cur):
            cur.execute("SELECT id FROM faculty LIMIT 1")
            r = cur.fetchone()
            faculty_id = r["id"] if r else None
    if not faculty_id:
        flash("No faculty available to mark attendance.", "danger")
        return redirect(url_for("attendance_bp.index"))
    if request.method == "POST":
        if existing:
            flash("Attendance already marked for this date. No duplicate entry.", "warning")
            return redirect(url_for("attendance_bp.mark", subject_id=subject_id, course_id=course_id, semester=semester, date=att_date))
        for s in students:
            key = f"att_{s['id']}"
            status = request.form.get(key)
            if not status:
                continue
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO attendance (student_id, subject_id, faculty_id, att_date, status)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (s["id"], subject_id, faculty_id, att_date, status),
                )
        flash("Attendance saved.", "success")
        return redirect(url_for("attendance_bp.index"))
    return render_template(
        "attendance/mark.html",
        subject=subj,
        students=students,
        att_date=att_date,
        existing=existing,
    )


@attendance_bp.route("/my")
@require_login
@require_roles("student")
def my_attendance():
    """View personal attendance records."""
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.id, s.name, s.code
            FROM subjects s
            JOIN students st ON st.course_id = s.course_id AND st.current_semester = s.semester
            WHERE st.id = %s
            ORDER BY s.semester, s.name
            """,
            (sid,),
        )
        subjects = cur.fetchall()
    rows = []
    for sub in subjects:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT COUNT(*) AS total,
                       SUM(CASE WHEN status = 'P' THEN 1 ELSE 0 END) AS present
                FROM attendance
                WHERE student_id = %s AND subject_id = %s
                """,
                (sid, sub["id"]),
            )
            r = cur.fetchone()
        total = r["total"] or 0
        present = r["present"] or 0
        pct = (present / total * 100) if total else 0
        rows.append(
            {
                "subject": sub,
                "total": total,
                "present": present,
                "percent": round(pct, 1),
            }
        )
    return render_template("attendance/my.html", stats=rows)


@attendance_bp.route("/report")
@require_login
@require_roles("admin", "faculty")
def report():
    """Generate attendance reports."""
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    subject_id = request.args.get("subject_id", type=int)
    month = request.args.get("month")
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses ORDER BY name"
        )
        courses = cur.fetchall()
        cur.execute(
            "SELECT id, name, code, course_id, semester FROM subjects ORDER BY course_id, semester"
        )
        subjects = cur.fetchall()
    filters = []
    params = []
    if course_id:
        filters.append("st.course_id = %s")
        params.append(course_id)
    if semester:
        filters.append("st.current_semester = %s")
        params.append(semester)
    if subject_id:
        filters.append("a.subject_id = %s")
        params.append(subject_id)
    if month:
        filters.append("TO_CHAR(a.att_date, 'YYYY-MM') = %s")
        params.append(month)
    where = " AND " + " AND ".join(filters) if filters else ""
    with db_cursor() as (conn, cur):
        cur.execute(
            f"""
            SELECT st.id, st.enrollment_no, st.first_name, st.last_name, st.course_id, st.current_semester,
                   sub.name AS subject_name, sub.id AS subject_id,
                   COUNT(a.id) AS total, SUM(CASE WHEN a.status = 'P' THEN 1 ELSE 0 END) AS present
            FROM students st
            LEFT JOIN attendance a ON a.student_id = st.id
            LEFT JOIN subjects sub ON sub.id = a.subject_id
            WHERE 1=1 {where}
            GROUP BY st.id, st.enrollment_no, st.first_name, st.last_name, st.course_id, st.current_semester, sub.id, sub.name
            ORDER BY st.enrollment_no, sub.name
            """,
            params or (),
        )
        report_rows = cur.fetchall()
    return render_template(
        "attendance/report.html",
        courses=courses,
        subjects=subjects,
        report=report_rows,
        course_id=course_id,
        semester=semester,
        subject_id=subject_id,
        month=month,
    )


# ============================================================================
# SECURITY & ANALYTICS ROUTES
# ============================================================================

@attendance_bp.route("/fraud-detection")
@require_login
@require_roles("admin")
def fraud_detection():
    """View suspicious attendance attempts."""
    fraud_logs = qr_service.get_fraud_attempts(days=7)
    
    return render_template(
        "attendance/fraud_detection.html",
        fraud_logs=fraud_logs
    )


@attendance_bp.route("/analytics")
@require_login
@require_roles("admin", "faculty")
def analytics():
    """Attendance analytics and statistics."""
    user = get_current_user()
    is_faculty = user.get("role_name") == "faculty"
    fid = user.get("extra_id") if is_faculty else None
    
    with db_cursor() as (conn, cur):
        if is_faculty and fid:
            # Faculty-specific analytics
            cur.execute(
                """
                SELECT s.name AS subject_name, s.id,
                       COUNT(DISTINCT ar.student_id) AS total_students,
                       COUNT(ar.id) AS total_scans,
                       COUNT(DISTINCT a.att_date) AS class_count
                FROM attendance_sessions asess
                JOIN subjects s ON asess.subject_id = s.id
                LEFT JOIN attendance_records ar ON ar.session_id = asess.id
                LEFT JOIN attendance a ON a.subject_id = s.id AND a.status = 'P'
                WHERE asess.faculty_id = %s
                GROUP BY s.id, s.name
                """,
                (fid,)
            )
        else:
            # Admin: all analytics
            cur.execute(
                """
                SELECT s.name AS subject_name, s.id,
                       COUNT(DISTINCT ar.student_id) AS total_students,
                       COUNT(ar.id) AS total_scans,
                       COUNT(DISTINCT a.att_date) AS class_count
                FROM attendance_sessions asess
                JOIN subjects s ON asess.subject_id = s.id
                LEFT JOIN attendance_records ar ON ar.session_id = asess.id
                LEFT JOIN attendance a ON a.subject_id = s.id AND a.status = 'P'
                GROUP BY s.id, s.name
                """
            )
        
        analytics_data = cur.fetchall()
    
    return render_template(
        "attendance/analytics.html",
        analytics=analytics_data
    )

