"""QR-based attendance service: generate, validate, and manage sessions."""
import uuid
import json
import hashlib
import qrcode
import io
import base64
import random
import string
from datetime import datetime, timedelta
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
from database import db_cursor
from config import config
from PIL import Image, ImageDraw


class QRAttendanceService:
    """Service for generating and validating QR codes for attendance."""

    def __init__(self):
        """Initialize with Flask secret key for token generation."""
        self.serializer = URLSafeTimedSerializer(config.SECRET_KEY)
        self.algorithm = "sha256"

    def generate_session(self, faculty_id, subject_id, course_id, semester, duration_minutes=10, 
                        latitude=None, longitude=None, ip_address=None):
        """
        Generate a new attendance session with QR code.
        
        Args:
            faculty_id: Faculty member creating the session
            subject_id: Subject ID for this class
            course_id: Course ID
            semester: Semester
            duration_minutes: QR validity in minutes (default 10)
            latitude, longitude: Faculty location
            ip_address: Faculty IP address
        
        Returns:
            dict: Session info with QR code image, token, and expiry details
        """
        # Generate unique identifiers
        session_id = str(uuid.uuid4())
        current_time = datetime.utcnow()
        expiry_time = current_time + timedelta(minutes=duration_minutes)
        
        # Create encrypted token with timestamp
        token_data = {
            'session_id': session_id,
            'faculty_id': faculty_id,
            'subject_id': subject_id,
            'timestamp': current_time.isoformat(),
            'expiry': expiry_time.isoformat()
        }
        
        # Serialize token
        qr_token = self.serializer.dumps(token_data)
        token_hash = self._hash_token(qr_token)
        
        # Generate QR code
        qr_image = self._generate_qr_image(qr_token)
        qr_base64 = self._qr_to_base64(qr_image)
        
        # Generate OTP code (High Security: 6-digit alphanumeric)
        otp_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        otp_expiry = current_time + timedelta(minutes=duration_minutes)
        
        # Store session in database
        with db_cursor() as (conn, cur):
            # Get session date and time
            session_date = current_time.date()
            
            try:
                cur.execute(
                    """
                    INSERT INTO attendance_sessions 
                    (session_id, faculty_id, subject_id, course_id, semester, 
                     date, start_time, expiry_time, qr_token, token_hash, 
                     otp_code, otp_expiry, status, latitude, longitude, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id, faculty_id, subject_id, course_id, semester,
                        session_date, current_time, expiry_time, qr_token, token_hash,
                        otp_code, otp_expiry, 'active', latitude, longitude, ip_address
                    )
                )
                conn.commit()
                
                # Log to audit
                self._log_event(
                    session_id, None, 'session_created', 
                    'QR session created', ip_address, None
                )
                
            except Exception as e:
                conn.rollback()
                raise RuntimeError(f"Failed to create session: {str(e)}")
        
        return {
            'session_id': session_id,
            'qr_image': qr_base64,
            'token': qr_token,
            'start_time': current_time.isoformat(),
            'expiry_time': expiry_time.isoformat(),
            'duration_minutes': duration_minutes,
            'otp_code': otp_code,
            'faculty_id': faculty_id,
            'subject_id': subject_id
        }

    def validate_and_mark_attendance(self, qr_token, student_id, ip_address=None, 
                                    device_info=None, browser_info=None,
                                    latitude=None, longitude=None, accuracy=None):
        """
        Validate QR token and mark attendance.
        
        Args:
            qr_token: QR token from scanned code
            student_id: Student scanning the QR
            ip_address: Student's IP address
            device_info: Device information (User-Agent)
            browser_info: Browser information
            latitude, longitude: Student's location
            accuracy: GPS accuracy in meters
        
        Returns:
            tuple: (success, message, session_id or error_details)
        """
        try:
            # Decode token
            token_data = self.serializer.loads(qr_token, max_age=605)  # 10min + 5sec buffer
            
        except SignatureExpired:
            self._log_event(None, student_id, 'token_expired', 
                          'QR token expired', ip_address, device_info)
            return False, "QR code has expired", None
            
        except BadSignature:
            self._log_event(None, student_id, 'invalid_token', 
                          'Invalid or tampered QR token', ip_address, device_info)
            return False, "Invalid QR code", None
        
        session_id = token_data.get('session_id')
        
        # Get session from database
        with db_cursor() as (conn, cur):
            # Check session exists and is active
            cur.execute(
                """
                SELECT s.id, s.faculty_id, s.subject_id, s.date, 
                       s.start_time, s.expiry_time, s.status
                FROM attendance_sessions s
                WHERE s.session_id = %s
                """,
                (session_id,)
            )
            
            session = cur.fetchone()
            if not session:
                self._log_event(None, student_id, 'session_not_found', 
                              'Session does not exist', ip_address, device_info)
                return False, "Session not found", None
            
            # Check session is still active
            if session['status'] != 'active':
                self._log_event(session_id, student_id, 'session_inactive', 
                              f'Session status: {session["status"]}', ip_address, device_info)
                return False, f"Session is {session['status']}", None
            
            # Check expiry time
            if datetime.utcnow() > session['expiry_time']:
                # Mark session as expired
                cur.execute(
                    "UPDATE attendance_sessions SET status = 'expired' WHERE id = %s",
                    (session['id'],)
                )
                conn.commit()
                self._log_event(session_id, student_id, 'session_expired_db', 
                              'Attendance time expired', ip_address, device_info)
                return False, "Attendance window has closed", None
            
            # Check for duplicate attendance
            cur.execute(
                """
                SELECT id FROM attendance_records 
                WHERE session_id = %s AND student_id = %s
                """,
                (session['id'], student_id)
            )
            
            if cur.fetchone():
                # Log as flagged - duplicate attempt
                self._log_event(session_id, student_id, 'duplicate_scan', 
                              'Duplicate attendance attempt', ip_address, device_info, 
                              flagged=True)
                return False, "You have already marked attendance for this session", None
            
            # Verify student is in the course
            cur.execute(
                """
                SELECT s.id FROM students s
                WHERE s.id = %s AND s.course_id = (
                    SELECT course_id FROM attendance_sessions WHERE id = %s
                )
                """,
                (student_id, session['id'])
            )
            
            if not cur.fetchone():
                self._log_event(session_id, student_id, 'student_not_in_course', 
                              'Student not enrolled in this course', ip_address, device_info,
                              flagged=True)
                return False, "You are not enrolled in this course", None
            
            # All checks passed - mark attendance
            try:
                cur.execute(
                    """
                    INSERT INTO attendance_records 
                    (session_id, student_id, scan_time, ip_address, device_info, 
                     browser_info, latitude, longitude, accuracy, status)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, 'verified')
                    """,
                    (
                        session['id'], student_id, ip_address, device_info, browser_info,
                        latitude, longitude, accuracy
                    )
                )
                
                # Also mark in legacy attendance table for compatibility
                cur.execute(
                    """
                    INSERT INTO attendance 
                    (student_id, subject_id, faculty_id, att_date, status)
                    VALUES (%s, %s, %s, %s, 'P')
                    ON CONFLICT (student_id, subject_id, att_date) DO UPDATE SET status = 'P'
                    """,
                    (
                        student_id, session['subject_id'], session['faculty_id'], session['date']
                    )
                )
                
                conn.commit()
                
                # Log success
                self._log_event(session_id, student_id, 'attendance_marked', 
                              'Attendance successfully marked', ip_address, device_info)
                
                return True, "Attendance marked successfully", {
                    'session_id': session_id,
                    'student_id': student_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                
            except Exception as e:
                conn.rollback()
                self._log_event(session_id, student_id, 'marking_error', 
                              str(e), ip_address, device_info, flagged=True)
                return False, f"Error marking attendance: {str(e)}", None

    def validate_otp_and_mark_attendance(self, otp_code, student_id, ip_address=None,
                                       device_info=None, browser_info=None,
                                       latitude=None, longitude=None, accuracy=None):
        """
        Validate OTP code and mark attendance with high-level security checks.
        """
        otp_code = (otp_code or "").strip().upper()
        if not otp_code:
            return False, "OTP code is required", None

        with db_cursor() as (conn, cur):
            # 1. Find active session with this OTP
            cur.execute(
                """
                SELECT s.id, s.session_id, s.faculty_id, s.subject_id, s.date, 
                       s.start_time, s.expiry_time, s.status, s.otp_expiry,
                       s.course_id, s.semester
                FROM attendance_sessions s
                WHERE s.otp_code = %s AND s.status = 'active'
                ORDER BY s.created_at DESC LIMIT 1
                """,
                (otp_code,)
            )
            session = cur.fetchone()

            if not session:
                self._log_event(None, student_id, 'invalid_otp', 
                              f'Invalid OTP attempt: {otp_code}', ip_address, device_info, flagged=True)
                return False, "Invalid attendance code", None

            # 2. Security Check: OTP Expiry
            if datetime.utcnow() > session['otp_expiry']:
                self._log_event(session['id'], student_id, 'otp_expired', 
                              'OTP code expired', ip_address, device_info)
                return False, "Attendance code has expired", None

            # 3. Security Check: Rate Limiting (prevent brute force)
            cur.execute(
                """
                SELECT COUNT(*) as attempts FROM attendance_audit_log
                WHERE student_id = %s AND event_type = 'invalid_otp'
                AND created_at > CURRENT_TIMESTAMP - INTERVAL '15 minutes'
                """,
                (student_id,)
            )
            if cur.fetchone()['attempts'] >= 5:
                return False, "Too many failed attempts. Please try again later.", None

            # 4. Security Check: Duplicate attendance
            cur.execute(
                "SELECT id FROM attendance_records WHERE session_id = %s AND student_id = %s",
                (session['id'], student_id)
            )
            if cur.fetchone():
                return False, "Attendance already marked for this session", None

            # 5. Security Check: Enrollment
            cur.execute(
                "SELECT id FROM students WHERE id = %s AND course_id = %s AND current_semester = %s",
                (student_id, session['course_id'], session['semester'])
            )
            if not cur.fetchone():
                return False, "You are not enrolled in this course/semester", None

            # 6. Mark Attendance
            try:
                cur.execute(
                    """
                    INSERT INTO attendance_records 
                    (session_id, student_id, scan_time, ip_address, device_info, 
                     browser_info, latitude, longitude, accuracy, status)
                    VALUES (%s, %s, NOW(), %s, %s, %s, %s, %s, %s, 'verified')
                    """,
                    (
                        session['id'], student_id, ip_address, device_info, browser_info,
                        latitude, longitude, accuracy
                    )
                )
                
                cur.execute(
                    """
                    INSERT INTO attendance (student_id, subject_id, faculty_id, att_date, status)
                    VALUES (%s, %s, %s, %s, 'P')
                    ON CONFLICT (student_id, subject_id, att_date) DO UPDATE SET status = 'P'
                    """,
                    (student_id, session['subject_id'], session['faculty_id'], session['date'])
                )
                conn.commit()
                
                self._log_event(session['id'], student_id, 'attendance_marked_otp', 
                              'Attendance marked via OTP', ip_address, device_info)
                
                return True, "Attendance marked successfully", {"session_id": session['session_id']}
            except Exception as e:
                conn.rollback()
                return False, f"System error: {str(e)}", None

    def get_session_details(self, session_id):
        """Get session details and attendance count."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT s.session_id, s.faculty_id, s.subject_id, s.date,
                       s.start_time, s.expiry_time, s.status,
                       f.first_name, f.last_name,
                       sub.name AS subject_name,
                       COUNT(ar.id) AS attendance_count
                FROM attendance_sessions s
                LEFT JOIN faculty f ON s.faculty_id = f.id
                LEFT JOIN subjects sub ON s.subject_id = sub.id
                LEFT JOIN attendance_records ar ON s.id = ar.session_id
                WHERE s.session_id = %s
                GROUP BY s.id
                """,
                (session_id,)
            )
            return cur.fetchone()

    def get_active_sessions(self, limit=10):
        """Get currently active sessions."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT s.session_id, s.faculty_id, s.subject_id, s.date,
                       s.start_time, s.expiry_time,
                       f.first_name, f.last_name,
                       sub.name AS subject_name,
                       COUNT(ar.id) AS attendance_count
                FROM attendance_sessions s
                LEFT JOIN faculty f ON s.faculty_id = f.id
                LEFT JOIN subjects sub ON s.subject_id = sub.id
                LEFT JOIN attendance_records ar ON s.id = ar.session_id
                WHERE s.status = 'active' AND s.expiry_time > NOW()
                GROUP BY s.id
                ORDER BY s.start_time DESC
                LIMIT %s
                """,
                (limit,)
            )
            return cur.fetchall()

    def get_session_attendance(self, session_db_id):
        """Get all attendance records for a session."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT ar.id, ar.student_id, ar.scan_time, ar.ip_address,
                       ar.latitude, ar.longitude, ar.status,
                       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                       s.enrollment_no
                FROM attendance_records ar
                JOIN students s ON ar.student_id = s.id
                WHERE ar.session_id = %s
                ORDER BY ar.scan_time ASC
                """,
                (session_db_id,)
            )
            return cur.fetchall()

    def close_session(self, session_id, faculty_id):
        """Close/complete a session (no more scans allowed)."""
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT id, faculty_id FROM attendance_sessions WHERE session_id = %s",
                (session_id,)
            )
            session = cur.fetchone()
            
            if not session:
                return False, "Session not found"
            
            if session['faculty_id'] != faculty_id:
                return False, "Unauthorized"
            
            try:
                cur.execute(
                    "UPDATE attendance_sessions SET status = 'completed' WHERE id = %s",
                    (session['id'],)
                )
                conn.commit()
                
                self._log_event(session_id, None, 'session_closed', 
                              'Session closed by faculty', None, None)
                
                return True, "Session closed successfully"
            except Exception as e:
                conn.rollback()
                return False, str(e)

    def _generate_qr_image(self, data):
        """Generate QR code image from data."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        return img

    def _qr_to_base64(self, img):
        """Convert PILImage to base64 string for embedding in HTML."""
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"

    def _hash_token(self, token):
        """Hash token for storage (never store plain tokens)."""
        return hashlib.sha256(token.encode()).hexdigest()

    def _log_event(self, session_id, student_id, event_type, action, 
                   ip_address=None, user_agent=None, flagged=False, details=None):
        """Log attendance events for audit trail."""
        try:
            with db_cursor() as (conn, cur):
                # Get session DB ID if we have session_id string
                session_db_id = None
                if session_id and isinstance(session_id, str):
                    cur.execute(
                        "SELECT id FROM attendance_sessions WHERE session_id = %s",
                        (session_id,)
                    )
                    result = cur.fetchone()
                    session_db_id = result['id'] if result else None
                else:
                    session_db_id = session_id
                
                cur.execute(
                    """
                    INSERT INTO attendance_audit_log 
                    (session_id, student_id, event_type, action, ip_address, 
                     user_agent, flagged, details)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_db_id, student_id, event_type, action, 
                        ip_address, user_agent, flagged,
                        json.dumps(details) if details else None
                    )
                )
                conn.commit()
        except Exception as e:
            print(f"Error logging event: {str(e)}")

    def get_fraud_attempts(self, days=7):
        """Get flagged/suspicious attendance events."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT aal.id, aal.session_id, aal.student_id, aal.event_type,
                       aal.action, aal.ip_address, aal.created_at,
                       CONCAT(s.first_name, ' ', s.last_name) AS student_name,
                       s.enrollment_no
                FROM attendance_audit_log aal
                LEFT JOIN students s ON aal.student_id = s.id
                WHERE aal.flagged = TRUE AND aal.created_at >= CURRENT_TIMESTAMP - INTERVAL '1 day' * %s
                ORDER BY aal.created_at DESC
                """,
                (days,)
            )
            return cur.fetchall()
