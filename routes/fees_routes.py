"""Fees: structure, payments, receipts, due tracking."""
import uuid
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor

fees_bp = Blueprint("fees_bp", __name__)

ACAD_YEAR = "2025-26"


@fees_bp.route("/")
@require_login
@require_roles("admin", "accountant")
def index():
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT fs.id, fs.course_id, fs.semester, fs.amount, fs.due_date, fs.academic_year,
                   c.name AS course_name, c.code AS course_code
            FROM fee_structure fs
            JOIN courses c ON c.id = fs.course_id
            ORDER BY c.name, fs.semester
            """
        )
        structures = cur.fetchall()
    return render_template("fees/index.html", structures=structures)


@fees_bp.route("/structure/add", methods=["GET", "POST"])
@require_login
@require_roles("admin", "accountant")
def add_structure():
    if request.method == "POST":
        course_id = request.form.get("course_id", type=int)
        semester = request.form.get("semester", type=int)
        amount = request.form.get("amount", type=float)
        due_date = request.form.get("due_date") or None
        acad_year = (request.form.get("academic_year") or ACAD_YEAR).strip()
        if not course_id or not semester or amount is None or amount < 0:
            flash("Course, semester, and amount are required.", "danger")
            return redirect(url_for("fees_bp.add_structure"))
        
        # Check for existing structure
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT id FROM fee_structure WHERE course_id = %s AND semester = %s AND academic_year = %s",
                (course_id, semester, acad_year)
            )
            if cur.fetchone():
                flash(f"Fee structure for Course {course_id}, Sem {semester}, Year {acad_year} already exists.", "warning")
                return redirect(url_for("fees_bp.index"))

            cur.execute(
                "INSERT INTO fee_structure (course_id, semester, amount, due_date, academic_year) VALUES (%s, %s, %s, %s, %s)",
                (course_id, semester, amount, due_date, acad_year),
            )
        flash("Fee structure added.", "success")
        return redirect(url_for("fees_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    
    # Pre-fill from query params (for "No Structure" link)
    pre_course_id = request.args.get("course_id", type=int)
    pre_semester = request.args.get("semester", type=int)
    
    return render_template("fees/structure_form.html", structure=None, courses=courses, pre_course_id=pre_course_id, pre_semester=pre_semester)


@fees_bp.route("/structure/<int:fsid>/edit", methods=["GET", "POST"])
@require_login
@require_roles("admin", "accountant")
def edit_structure(fsid):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM fee_structure WHERE id = %s", (fsid,))
        structure = cur.fetchone()
    if not structure:
        flash("Fee structure not found.", "danger")
        return redirect(url_for("fees_bp.index"))
    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        due_date = request.form.get("due_date") or None
        if amount is None or amount < 0:
            flash("Valid amount is required.", "danger")
            return redirect(url_for("fees_bp.edit_structure", fsid=fsid))
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE fee_structure SET amount = %s, due_date = %s WHERE id = %s",
                (amount, due_date, fsid),
            )
        flash("Fee structure updated.", "success")
        return redirect(url_for("fees_bp.index"))
    with db_cursor() as (conn, cur):
        cur.execute("SELECT id, name, code FROM courses ORDER BY name")
        courses = cur.fetchall()
    return render_template("fees/structure_form.html", structure=structure, courses=courses)


@fees_bp.route("/pay")
@require_login
@require_roles("admin", "accountant")
def pay_list():
    course_id = request.args.get("course_id", type=int)
    semester = request.args.get("semester", type=int)
    status_filter = request.args.get("status")  # paid | pending
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT id, name, code FROM courses ORDER BY name"
        )
        courses = cur.fetchall()
    sql = """
        SELECT st.id, st.enrollment_no, st.first_name, st.last_name, st.course_id, st.current_semester,
               c.name AS course_name
        FROM students st
        JOIN courses c ON c.id = st.course_id
        WHERE 1=1
    """
    params = []
    if course_id:
        sql += " AND st.course_id = %s"
        params.append(course_id)
    if semester:
        sql += " AND st.current_semester = %s"
        params.append(semester)
    sql += " ORDER BY st.enrollment_no"
    with db_cursor() as (conn, cur):
        cur.execute(sql, params or ())
        students = cur.fetchall()
    rows = []
    for s in students:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT fs.id, fs.semester, fs.amount, fs.due_date, fs.academic_year
                FROM fee_structure fs
                WHERE fs.course_id = %s AND fs.semester = %s AND fs.academic_year = %s
                """,
                (s["course_id"], s["current_semester"], ACAD_YEAR),
            )
            fs = cur.fetchone()
        if not fs:
            rows.append({"student": s, "structure": None, "paid": 0, "pending": None, "payments": []})
            continue
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT id, amount_paid, payment_date, receipt_no, payment_mode
                FROM fee_payments
                WHERE student_id = %s AND fee_structure_id = %s
                ORDER BY payment_date DESC
                """,
                (s["id"], fs["id"]),
            )
            payments = cur.fetchall()
        paid = float(sum(p["amount_paid"] for p in payments))
        pending = max(0.0, float(fs["amount"]) - paid)
        if status_filter == "paid" and pending > 0:
            continue
        if status_filter == "pending" and pending <= 0:
            continue
        rows.append(
            {
                "student": s,
                "structure": fs,
                "paid": paid,
                "pending": pending,
                "payments": payments,
            }
        )
    return render_template(
        "fees/pay_list.html",
        courses=courses,
        rows=rows,
        course_id=course_id,
        semester=semester,
        status_filter=status_filter,
    )


@fees_bp.route("/pay/<int:student_id>", methods=["GET", "POST"])
@require_login
@require_roles("admin", "accountant")
def record_payment(student_id):
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT st.*, c.name AS course_name FROM students st JOIN courses c ON c.id = st.course_id WHERE st.id = %s",
            (student_id,),
        )
        student = cur.fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("fees_bp.pay_list"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT fs.* FROM fee_structure fs
            WHERE fs.course_id = %s AND fs.semester = %s AND fs.academic_year = %s
            """,
            (student["course_id"], student["current_semester"], ACAD_YEAR),
        )
        structure = cur.fetchone()
    if not structure:
        flash("No fee structure for this course/semester.", "danger")
        return redirect(url_for("fees_bp.pay_list"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM fee_payments WHERE student_id = %s AND fee_structure_id = %s ORDER BY payment_date DESC",
            (student_id, structure["id"]),
        )
        payments = cur.fetchall()
    paid = float(sum(p["amount_paid"] for p in payments))
    pending = max(0.0, float(structure["amount"]) - paid)
    if request.method == "POST":
        amount = request.form.get("amount", type=float)
        payment_date = request.form.get("payment_date") or str(date.today())
        mode = (request.form.get("payment_mode") or "").strip() or None
        remarks = (request.form.get("remarks") or "").strip() or None
        if not amount or amount <= 0:
            flash("Valid amount is required.", "danger")
            return redirect(url_for("fees_bp.record_payment", student_id=student_id))
        receipt_no = f"RCP-{uuid.uuid4().hex[:8].upper()}"
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                INSERT INTO fee_payments (student_id, fee_structure_id, amount_paid, payment_date, payment_mode, receipt_no, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (student_id, structure["id"], amount, payment_date, mode, receipt_no, remarks),
            )
        flash(f"Payment recorded. Receipt: {receipt_no}", "success")
        return redirect(url_for("fees_bp.record_payment", student_id=student_id))
    return render_template(
        "fees/record_payment.html",
        student=student,
        structure=structure,
        payments=payments,
        paid=paid,
        pending=pending,
    )


@fees_bp.route("/my-fees")
@require_login
@require_roles("student")
def my_fees():
    sid = get_current_user().get("extra_id")
    if not sid:
        flash("Student profile not linked.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT st.*, c.name AS course_name FROM students st JOIN courses c ON c.id = st.course_id WHERE st.id = %s",
            (sid,),
        )
        student = cur.fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("dashboard"))
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT fs.* FROM fee_structure fs
            WHERE fs.course_id = %s AND fs.semester = %s AND fs.academic_year = %s
            """,
            (student["course_id"], student["current_semester"], ACAD_YEAR),
        )
        structure = cur.fetchone()
    if not structure:
        return render_template("fees/my_fees.html", student=student, structure=None, payments=[], paid=0, pending=0)
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT * FROM fee_payments WHERE student_id = %s AND fee_structure_id = %s ORDER BY payment_date DESC",
            (sid, structure["id"]),
        )
        payments = cur.fetchall()
    paid = float(sum(p["amount_paid"] for p in payments))
    pending = max(0.0, float(structure["amount"]) - paid)
    return render_template(
        "fees/my_fees.html",
        student=student,
        structure=structure,
        payments=payments,
        paid=paid,
        pending=pending,
    )


@fees_bp.route("/receipt/<receipt_no>")
@require_login
def receipt(receipt_no):
    user = get_current_user()
    with db_cursor() as (conn, cur):
        cur.execute(
            """
            SELECT fp.*, st.first_name, st.last_name, st.enrollment_no, st.course_id, st.current_semester,
                   c.name AS course_name, fs.academic_year, fs.amount AS total_fee
            FROM fee_payments fp
            JOIN students st ON st.id = fp.student_id
            JOIN courses c ON c.id = st.course_id
            JOIN fee_structure fs ON fs.id = fp.fee_structure_id
            WHERE fp.receipt_no = %s
            """,
            (receipt_no,),
        )
        payment = cur.fetchone()

    if not payment:
        flash("Receipt not found.", "danger")
        return redirect(url_for("dashboard"))

    # Authorization check
    if user["role_name"] == "student":
        if user.get("extra_id") != payment["student_id"]:
            flash("Access denied.", "danger")
            return redirect(url_for("dashboard"))
    elif user["role_name"] not in ["admin", "accountant"]:
        flash("Access denied.", "danger")
        return redirect(url_for("dashboard"))

    return render_template("fees/receipt.html", payment=payment)
