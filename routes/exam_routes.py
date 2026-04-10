"""Examination & results: marks entry, grades, publish, student view."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from auth import require_login, require_roles, get_current_user
from database import db_cursor
from datetime import datetime
import json

exam_bp = Blueprint("exam_bp", __name__)

ACAD_YEAR = "2024-25"
EXAM_SESSION = "2024-25-S1"
GRADE_MAP = [(90, "A+"), (80, "A"), (70, "B+"), (60, "B"), (50, "C"), (40, "D"), (0, "F")]


def grade_from_total(total):
    if total is None:
        return None
    for thresh, g in GRADE_MAP:
        if total >= thresh:
            return g
    return "F"


@exam_bp.route("/")
@require_login
@require_roles("admin", "faculty", "student")
def index():
    user = get_current_user()
    role = user.get("role_name")
    
    if role == "student":
        return redirect(url_for("exam_bp.student_exams"))
        
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT s.id, s.name, s.code, s.semester, c.name AS course_name, c.id AS course_id
            FROM subjects s
            JOIN courses c ON c.id = s.course_id
            ORDER BY c.name, s.semester
            """
        )
        subjects = cur.fetchall()
        
        # Also fetch online exams created by this faculty
        fid = user.get("extra_id") if role == "faculty" else None
        if fid:
            cur.execute(
                """
                SELECT oe.*, s.name AS subject_name, s.code AS subject_code
                FROM online_exams oe
                JOIN subjects s ON s.id = oe.subject_id
                WHERE oe.faculty_id = %s
                ORDER BY oe.start_time DESC
                """,
                (fid,)
            )
            online_exams = cur.fetchall()
        else:
            cur.execute(
                """
                SELECT oe.*, s.name AS subject_name, s.code AS subject_code
                FROM online_exams oe
                JOIN subjects s ON s.id = oe.subject_id
                ORDER BY oe.start_time DESC
                """
            )
            online_exams = cur.fetchall()
            
    return render_template("exams/index.html", subjects=subjects, online_exams=online_exams)


# --- Online Examination Routes ---

@exam_bp.route("/create", methods=["GET", "POST"])
@require_login
@require_roles("faculty", "admin")
def create_exam():
    user = get_current_user()
    fid = user.get("extra_id")
    
    with db_cursor() as (conn, cur):
        # Fetch subjects assigned to faculty
        if user.get("role_name") == "faculty":
            cur.execute(
                "SELECT s.id, s.name, s.code FROM subjects s JOIN faculty_subject_assignment fsa ON fsa.subject_id = s.id WHERE fsa.faculty_id = %s",
                (fid,)
            )
        else:
            cur.execute("SELECT id, name, code FROM subjects ORDER BY name")
        subjects = cur.fetchall()

    if request.method == "POST":
        subject_id = request.form.get("subject_id")
        title = request.form.get("title")
        description = request.form.get("description")
        duration = request.form.get("duration")
        min_attendance = request.form.get("min_attendance", 60.0)
        start_time = request.form.get("start_time")
        end_time = request.form.get("end_time")
        
        # Basic validation
        if not all([subject_id, title, start_time, end_time]):
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("exam_bp.create_exam"))

        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO online_exams (faculty_id, subject_id, title, description, duration_minutes, min_attendance_percentage, start_time, end_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (fid, subject_id, title, description, duration, min_attendance, start_time, end_time)
            )
            exam_id = cur.fetchone()["id"]
            
            # Process Questions
            q_texts = request.form.getlist("q_text[]")
            q_types = request.form.getlist("q_type[]")
            q_marks = request.form.getlist("q_marks[]")
            
            for i in range(len(q_texts)):
                q_text = q_texts[i]
                q_type = q_types[i]
                marks = q_marks[i]
                
                options = None
                correct_answer = None
                
                if q_type == "mcq":
                    opts = request.form.getlist(f"q_opts_{i}[]")
                    options = json.dumps(opts)
                    correct_answer = request.form.get(f"q_correct_{i}")
                elif q_type == "true_false":
                    correct_answer = request.form.get(f"q_correct_tf_{i}")
                
                cur.execute(
                    """
                    INSERT INTO exam_questions (exam_id, question_text, question_type, options, correct_answer, marks)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (exam_id, q_text, q_type, options, correct_answer, marks)
                )
            
        flash("Exam created successfully!", "success")
        return redirect(url_for("exam_bp.index"))

    return render_template("exams/create_exam.html", subjects=subjects)


@exam_bp.route("/student-exams")
@require_login
@require_roles("student")
def student_exams():
    sid = get_current_user().get("extra_id")
    with db_cursor() as (conn, cur):
        # Fetch all online exams for the student's course/semester
        cur.execute(
            """
            SELECT oe.*, s.name AS subject_name, s.code AS subject_code,
                   (SELECT status FROM student_exam_attempts WHERE exam_id = oe.id AND student_id = %s) AS attempt_status
            FROM online_exams oe
            JOIN subjects s ON s.id = oe.subject_id
            JOIN students st ON st.course_id = s.course_id AND st.current_semester = s.semester
            WHERE st.id = %s
            ORDER BY oe.start_time DESC
            """,
            (sid, sid)
        )
        exams = cur.fetchall()
    return render_template("exams/student_exams.html", exams=exams)


@exam_bp.route("/attempt/<int:exam_id>", methods=["GET", "POST"])
@require_login
@require_roles("student")
def attempt_exam(exam_id):
    sid = get_current_user().get("extra_id")
    now = datetime.now()
    
    with db_cursor() as (conn, cur):
        # Check eligibility (Attendance 60%)
        cur.execute(
            """
            SELECT oe.*, s.id AS subject_id,
                   (SELECT COUNT(*) FROM attendance WHERE student_id = %s AND subject_id = oe.subject_id) AS total_classes,
                   (SELECT COUNT(*) FROM attendance WHERE student_id = %s AND subject_id = oe.subject_id AND status = 'P') AS present_classes
            FROM online_exams oe
            JOIN subjects s ON s.id = oe.subject_id
            WHERE oe.id = %s
            """,
            (sid, sid, exam_id)
        )
        exam = cur.fetchone()
        
        if not exam:
            flash("Exam not found.", "danger")
            return redirect(url_for("exam_bp.student_exams"))
            
        # Attendance Check
        total = exam["total_classes"] or 0
        present = exam["present_classes"] or 0
        att_percentage = (present / total * 100) if total > 0 else 0
        
        if att_percentage < float(exam["min_attendance_percentage"]):
            flash(f"Ineligible to take this exam. Your attendance is {att_percentage:.1f}%, but {exam['min_attendance_percentage']}% is required.", "warning")
            return redirect(url_for("exam_bp.student_exams"))

        # Check if already submitted
        cur.execute(
            "SELECT status FROM student_exam_attempts WHERE exam_id = %s AND student_id = %s",
            (exam_id, sid)
        )
        attempt = cur.fetchone()
        if attempt and attempt["status"] == "submitted":
            flash("You have already submitted this exam.", "info")
            return redirect(url_for("exam_bp.student_exams"))

        # Check timing
        if now < exam["start_time"]:
            flash("Exam has not started yet.", "info")
            return redirect(url_for("exam_bp.student_exams"))
        if now > exam["end_time"]:
            flash("Exam has already ended.", "danger")
            return redirect(url_for("exam_bp.student_exams"))

        # Fetch Questions
        cur.execute("SELECT * FROM exam_questions WHERE exam_id = %s", (exam_id,))
        questions = cur.fetchall()

    if request.method == "POST":
        with db_cursor() as (conn, cur):
            # Create/Get Attempt
            cur.execute(
                """
                INSERT INTO student_exam_attempts (exam_id, student_id, status)
                VALUES (%s, %s, 'submitted')
                ON CONFLICT (exam_id, student_id) DO UPDATE SET status = 'submitted', submit_time = CURRENT_TIMESTAMP
                RETURNING id
                """,
                (exam_id, sid)
            )
            attempt_id = cur.fetchone()["id"]
            
            total_score = 0
            for q in questions:
                ans = request.form.get(f"q_{q['id']}")
                is_correct = False
                marks_obtained = 0
                
                if q["question_type"] in ["mcq", "true_false"]:
                    if ans == q["correct_answer"]:
                        is_correct = True
                        marks_obtained = q["marks"]
                        total_score += marks_obtained
                
                cur.execute(
                    """
                    INSERT INTO student_answers (attempt_id, question_id, answer_text, is_correct, marks_obtained)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (attempt_id, q["id"], ans, is_correct, marks_obtained)
                )
                
            cur.execute(
                "UPDATE student_exam_attempts SET score = %s WHERE id = %s",
                (total_score, attempt_id)
            )
            
        flash("Exam submitted successfully!", "success")
        return redirect(url_for("exam_bp.student_exams"))

    return render_template("exams/attempt_exam.html", exam=exam, questions=questions)


@exam_bp.route("/marks/<int:subject_id>", methods=["GET", "POST"])
@require_login
@require_roles("admin", "faculty")
def marks_entry(subject_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT s.*, c.name AS course_name, c.id AS course_id FROM subjects s JOIN courses c ON c.id = s.course_id WHERE s.id = %s",
            (subject_id,),
        )
        subj = cur.fetchone()
    if not subj:
        flash("Subject not found.", "danger")
        return redirect(url_for("exam_bp.index"))
    course_id = subj["course_id"]
    semester = subj["semester"]
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT st.id, st.enrollment_no, st.first_name, st.last_name
            FROM students st
            WHERE st.course_id = %s AND st.current_semester = %s
            ORDER BY st.enrollment_no
            """,
            (course_id, semester),
        )
        students = cur.fetchall()
        cur.execute(
            "SELECT student_id, internal_marks, external_marks, total_marks, grade, published FROM marks WHERE subject_id = %s AND exam_session = %s",
            (subject_id, EXAM_SESSION),
        )
        existing = {r["student_id"]: r for r in cur.fetchall()}
    if request.method == "POST":
        for s in students:
            internal = request.form.get(f"internal_{s['id']}")
            external = request.form.get(f"external_{s['id']}")
            if internal is None and external is None:
                continue
            try:
                internal = float(internal) if internal else None
            except (TypeError, ValueError):
                internal = None
            try:
                external = float(external) if external else None
            except (TypeError, ValueError):
                external = None
            total = None
            if internal is not None and external is not None:
                total = internal + external
            elif internal is not None:
                total = internal
            elif external is not None:
                total = external
            grade = grade_from_total(total)
            with db_cursor() as (conn, cur):
                cur.execute(
                    """
                    INSERT INTO marks (student_id, subject_id, internal_marks, external_marks, total_marks, grade, exam_type, exam_session, published)
                    VALUES (%s, %s, %s, %s, %s, %s, 'Internal+External', %s, FALSE)
                    ON CONFLICT (student_id, subject_id, exam_session) DO UPDATE SET 
                        internal_marks = EXCLUDED.internal_marks, 
                        external_marks = EXCLUDED.external_marks, 
                        total_marks = EXCLUDED.total_marks, 
                        grade = EXCLUDED.grade
                    """,
                    (s["id"], subject_id, internal, external, total, grade, EXAM_SESSION),
                )
        flash("Marks saved.", "success")
        return redirect(url_for("exam_bp.marks_entry", subject_id=subject_id))
    return render_template(
        "exams/marks_entry.html",
        subject=subj,
        students=students,
        existing=existing,
    )


@exam_bp.route("/publish/<int:subject_id>", methods=["POST"])
@require_login
@require_roles("admin", "faculty")
def publish(subject_id):
    action = request.form.get("action")
    pub = (action == "publish")
    with db_cursor() as (conn, cur):
        cur.execute(
            "UPDATE marks SET published = %s WHERE subject_id = %s AND exam_session = %s",
            (pub, subject_id, EXAM_SESSION),
        )
    flash("Results published." if pub else "Results unpublished.", "success")
    return redirect(url_for("exam_bp.marks_entry", subject_id=subject_id))


@exam_bp.route("/my-results")
@require_login
@require_roles("student")
def my_results():
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT m.internal_marks, m.external_marks, m.total_marks, m.grade, m.published,
                   s.name AS subject_name, s.code AS subject_code, s.credits
            FROM marks m
            JOIN subjects s ON s.id = m.subject_id
            WHERE m.student_id = %s AND m.exam_session = %s AND m.published = TRUE
            ORDER BY s.name
            """,
            (sid, EXAM_SESSION),
        )
        results = cur.fetchall()
        cur.execute(
            "SELECT st.enrollment_no, st.first_name, st.last_name, c.name AS course_name FROM students st JOIN courses c ON c.id = st.course_id WHERE st.id = %s",
            (sid,),
        )
        student = cur.fetchone()
    return render_template("exams/my_results.html", results=results, student=student)
