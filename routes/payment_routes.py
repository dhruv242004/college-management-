from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor
import uuid
from datetime import date
import razorpay
from config import config

# Initialize Razorpay Client
razorpay_client = razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))

payment_bp = Blueprint("payment_bp", __name__)


def ensure_payments_table():
    with db_cursor() as (conn, cur):
        # PostgreSQL syntax (works for local too if we use SERIAL)
        # Check if we are on PostgreSQL
        is_pg = hasattr(conn, 'cursor_factory')
        if is_pg:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id SERIAL PRIMARY KEY,
                    student_id INTEGER NOT NULL,
                    order_id VARCHAR(100) NOT NULL UNIQUE,
                    payment_id VARCHAR(100),
                    amount DECIMAL(10,2) NOT NULL,
                    status VARCHAR(20) NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
        else:
            # MySQL fallback
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payments (
                    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
                    student_id INT UNSIGNED NOT NULL,
                    order_id VARCHAR(100) NOT NULL UNIQUE,
                    payment_id VARCHAR(100) NULL,
                    amount DECIMAL(10,2) NOT NULL,
                    status ENUM('pending','success','failed') NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_payments_student (student_id),
                    INDEX idx_payments_status (status)
                ) ENGINE=InnoDB
                """
            )


@payment_bp.route("/create-order", methods=["POST"])
@require_login
@require_roles("student")
def create_order():
    try:
        ensure_payments_table()
        sid = get_current_user().get("extra_id")
        if not sid:
            return jsonify({"error": "Student profile not linked"}), 400
        
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT course_id, current_semester FROM students WHERE id = %s",
                (sid,),
            )
            st = cur.fetchone()
        if not st:
            return jsonify({"error": "Student record not found"}), 404
            
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT id, amount FROM fee_structure
                WHERE course_id = %s AND semester = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (st["course_id"], st["current_semester"]),
            )
            structure = cur.fetchone()
        if not structure:
            return jsonify({"error": "No fee structure found for your current semester"}), 400
            
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT COALESCE(SUM(amount_paid),0) AS paid FROM fee_payments WHERE student_id = %s AND fee_structure_id = %s",
                (sid, structure["id"]),
            )
            paid_row = cur.fetchone()
            
        total_amount = float(structure["amount"])
        paid_amount = float(paid_row["paid"]) if paid_row else 0.0
        pending_amount = max(0.0, total_amount - paid_amount)
        
        if pending_amount <= 0.01:
            return jsonify({"error": "No pending amount. Your fees are already fully paid."}), 400
            
        # Create internal order
        internal_order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"
        
        # Create Razorpay Order
        razorpay_order = razorpay_client.order.create({
            "amount": int(pending_amount * 100), # Amount in paise
            "currency": "INR",
            "receipt": internal_order_id,
            "payment_capture": 1
        })
        
        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO payments (student_id, order_id, amount, status) VALUES (%s, %s, %s, %s)",
                (sid, internal_order_id, pending_amount, "pending"),
            )
            
        return jsonify({
            "order_id": internal_order_id,
            "razorpay_order_id": razorpay_order['id'],
            "amount": pending_amount,
            "checkout_url": url_for("payment_bp.razorpay_checkout", order_id=internal_order_id, rzp_order_id=razorpay_order['id'])
        })
    except Exception as e:
        print(f"DEBUG: Create order failed: {str(e)}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@payment_bp.route("/razorpay-checkout/<order_id>")
@require_login
@require_roles("student")
def razorpay_checkout(order_id):
    rzp_order_id = request.args.get("rzp_order_id")
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
        payment = cur.fetchone()
        
    if not payment:
        flash("Order not found", "danger")
        return redirect(url_for("fees_bp.my_fees"))
        
    sid = get_current_user().get("extra_id")
    if payment["student_id"] != sid:
        flash("Unauthorized access", "danger")
        return redirect(url_for("fees_bp.my_fees"))
        
    return render_template(
        "fees/razorpay_checkout.html", 
        payment=payment, 
        razorpay_order_id=rzp_order_id,
        razorpay_amount=int(payment["amount"] * 100),
        key_id=config.RAZORPAY_KEY_ID
    )


@payment_bp.route("/verify-razorpay-payment")
@require_login
@require_roles("student")
def verify_razorpay_payment():
    try:
        payment_id = request.args.get("razorpay_payment_id")
        order_id = request.args.get("razorpay_order_id")
        signature = request.args.get("razorpay_signature")
        internal_order_id = request.args.get("internal_order_id")
        
        # Verify signature
        params_dict = {
            'razorpay_order_id': order_id,
            'razorpay_payment_id': payment_id,
            'razorpay_signature': signature
        }
        
        try:
            razorpay_client.utility.verify_payment_signature(params_dict)
        except Exception as e:
            print(f"Signature verification failed: {e}")
            flash("Payment verification failed. Invalid signature.", "danger")
            return redirect(url_for("fees_bp.my_fees"))

        # If verified, update database
        with db_cursor() as (conn, cur):
            cur.execute("SELECT * FROM payments WHERE order_id = %s", (internal_order_id,))
            pay_row = cur.fetchone()
            
        if not pay_row:
            flash("Internal order records not found", "danger")
            return redirect(url_for("fees_bp.my_fees"))
            
        sid = get_current_user().get("extra_id")
        
        with db_cursor() as (conn, cur):
            # 1. Update internal payments table
            cur.execute(
                "UPDATE payments SET status = 'success', payment_id = %s WHERE id = %s",
                (payment_id, pay_row["id"]),
            )
            
            # 2. Add to fee_payments (the actual ledger)
            cur.execute("SELECT course_id, current_semester FROM students WHERE id = %s", (sid,))
            st = cur.fetchone()
            
            cur.execute(
                """
                SELECT id FROM fee_structure
                WHERE course_id = %s AND semester = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (st["course_id"], st["current_semester"]),
            )
            structure = cur.fetchone()
            
            if structure:
                receipt_no = f"RCP-RZP-{uuid.uuid4().hex[:8].upper()}"
                cur.execute(
                    """
                    INSERT INTO fee_payments (student_id, fee_structure_id, amount_paid, payment_date, payment_mode, receipt_no, remarks)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (sid, structure["id"], pay_row["amount"], date.today(), "Razorpay Online", receipt_no, f"RZP:{payment_id}"),
                )
            conn.commit()

        flash("Payment successful!", "success")
        return redirect(url_for("payment_bp.payment_success", order_id=internal_order_id))
        
    except Exception as e:
        print(f"Verification process error: {e}")
        flash(f"Error during payment verification: {str(e)}", "danger")
        return redirect(url_for("fees_bp.my_fees"))


@payment_bp.route("/mock-checkout/<order_id>")
@require_login
@require_roles("student")
def mock_checkout(order_id):
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
        payment = cur.fetchone()
        
    if not payment:
        flash("Order not found", "danger")
        return redirect(url_for("fees_bp.my_fees"))
        
    sid = get_current_user().get("extra_id")
    if payment["student_id"] != sid:
        flash("Unauthorized access", "danger")
        return redirect(url_for("fees_bp.my_fees"))
        
    return render_template("fees/mock_checkout.html", payment=payment)


@payment_bp.route("/process-mock-payment", methods=["POST"])
@require_login
@require_roles("student")
def process_mock_payment():
    try:
        order_id = request.form.get("order_id")
        action = request.form.get("action") # success or failure
        
        with db_cursor() as (conn, cur):
            cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
            pay_row = cur.fetchone()
            
        if not pay_row:
            flash("Order not found", "danger")
            return redirect(url_for("fees_bp.my_fees"))
            
        sid = get_current_user().get("extra_id")
        if pay_row["student_id"] != sid:
            flash("Unauthorized", "danger")
            return redirect(url_for("fees_bp.my_fees"))
            
        if action == "success":
            payment_id = f"PAY-MOCK-{uuid.uuid4().hex[:10].upper()}"
            
            with db_cursor() as (conn, cur):
                # Update payment status
                cur.execute(
                    "UPDATE payments SET status = 'success', payment_id = %s WHERE id = %s",
                    (payment_id, pay_row["id"]),
                )
                
                # Get student info for fee_payments
                cur.execute(
                    "SELECT course_id, current_semester FROM students WHERE id = %s",
                    (sid,),
                )
                st = cur.fetchone()
                
                # Get fee structure
                cur.execute(
                    """
                    SELECT id FROM fee_structure
                    WHERE course_id = %s AND semester = %s
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (st["course_id"], st["current_semester"]),
                )
                structure = cur.fetchone()
                
                if structure:
                    receipt_no = f"RCP-SIM-{uuid.uuid4().hex[:8].upper()}"
                    cur.execute(
                        """
                        INSERT INTO fee_payments (student_id, fee_structure_id, amount_paid, payment_date, payment_mode, receipt_no, remarks)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (sid, structure["id"], pay_row["amount"], date.today(), "Simulated Gateway", receipt_no, order_id),
                    )
            
            return redirect(url_for("payment_bp.payment_success", order_id=order_id))
        else:
            with db_cursor() as (conn, cur):
                cur.execute("UPDATE payments SET status = 'failed' WHERE id = %s", (pay_row["id"],))
            return redirect(url_for("payment_bp.payment_failed", order_id=order_id))
    except Exception as e:
        print(f"DEBUG: Process mock payment failed: {str(e)}")
        flash(f"Payment processing error: {str(e)}", "danger")
        return redirect(url_for("fees_bp.my_fees"))


@payment_bp.route("/payment-success")
@require_login
@require_roles("student")
def payment_success():
    order_id = request.args.get("order_id")
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
        pay_row = cur.fetchone()
    if not pay_row:
        flash("Payment not found", "danger")
        return redirect(url_for("fees_bp.my_fees"))
    sid = get_current_user().get("extra_id")
    if sid != pay_row["student_id"]:
        flash("Access denied", "danger")
        return redirect(url_for("fees_bp.my_fees"))
    
    receipt = None
    with db_cursor() as (conn, cur):
        cur.execute(
            "SELECT receipt_no FROM fee_payments WHERE student_id = %s ORDER BY id DESC LIMIT 1",
            (sid,),
        )
        row = cur.fetchone()
        receipt = row["receipt_no"] if row else None
        
    return render_template("fees/payment_success.html", payment=pay_row, receipt_no=receipt)


@payment_bp.route("/payment-failed")
@require_login
@require_roles("student")
def payment_failed():
    order_id = request.args.get("order_id")
    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
        pay_row = cur.fetchone()
    sid = get_current_user().get("extra_id")
    if pay_row and sid != pay_row["student_id"]:
        flash("Access denied", "danger")
        return redirect(url_for("fees_bp.my_fees"))
    return render_template("fees/payment_failed.html", order_id=order_id)
