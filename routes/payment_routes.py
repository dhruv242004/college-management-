from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from auth import require_login, require_roles, get_current_user
from database import db_cursor
import os

from config import _env_strip
from routes.fees_routes import ACAD_YEAR
import uuid
import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from datetime import date

payment_bp = Blueprint("payment_bp", __name__)


def _razorpay_configured():
    # Read from os.environ so Razorpay keys always match what load_dotenv applied
    kid = _env_strip(os.environ.get("RAZORPAY_KEY_ID"))
    sec = _env_strip(os.environ.get("RAZORPAY_KEY_SECRET"))
    if kid and sec:
        return kid, sec
    return "", ""


def _razorpay_api_post(path, payload):
    key_id, key_secret = _razorpay_configured()
    if not key_id or not key_secret:
        return None, "not_configured"
    auth_b64 = base64.b64encode(f"{key_id}:{key_secret}".encode("utf-8")).decode("ascii")
    url = f"https://api.razorpay.com/v1/{path.lstrip('/')}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"Basic {auth_b64}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
        except Exception:
            err_body = str(e)
        print(f"DEBUG: Razorpay HTTP {e.code}: {err_body}")
        return None, err_body
    except Exception as e:
        print(f"DEBUG: Razorpay request failed: {e}")
        return None, str(e)


def _razorpay_order_error_user_message(err_body):
    """Turn Razorpay API error JSON into a safe, actionable message for the UI."""
    if not err_body or err_body == "not_configured":
        return "Payment gateway unavailable. Please try again later."
    try:
        data = json.loads(err_body) if isinstance(err_body, str) else err_body
        desc = ((data or {}).get("error") or {}).get("description") or ""
    except Exception:
        desc = str(err_body)[:200]
    dlow = desc.lower()
    if "authentication failed" in dlow or "invalid api key" in dlow:
        return (
            "Razorpay rejected your API keys. Open the dashboard in Test mode, "
            "Account & Settings → API Keys, and copy the Key Id and Key Secret into "
            "RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET in .env (no quotes). Restart the server. "
            "Do not mix a test Key Id with a live secret, or vice versa."
        )
    if desc:
        return f"Could not start payment: {desc}"
    return "Payment gateway unavailable. Please try again later."


def _verify_razorpay_payment_signature(order_id, payment_id, signature):
    _, key_secret = _razorpay_configured()
    if not key_secret or not signature:
        return False
    body = f"{order_id}|{payment_id}".encode("utf-8")
    digest = hmac.new(key_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, signature)


def _fee_structure_row(cur, course_id, semester):
    cur.execute(
        """
        SELECT id, amount FROM fee_structure
        WHERE course_id = %s AND semester = %s AND academic_year = %s
        LIMIT 1
        """,
        (course_id, semester, ACAD_YEAR),
    )
    return cur.fetchone()


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
            structure = _fee_structure_row(cur, st["course_id"], st["current_semester"])
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

        key_id, key_secret = _razorpay_configured()
        if key_id and key_secret:
            amount_paise = int(round(pending_amount * 100))
            receipt = f"FEE{uuid.uuid4().hex[:12].upper()}"[:40]
            rp_order, err = _razorpay_api_post(
                "orders",
                {
                    "amount": amount_paise,
                    "currency": "INR",
                    "receipt": receipt,
                    "notes": {"student_id": str(sid), "source": "college_cms_fees"},
                },
            )
            if err or not rp_order:
                return jsonify({"error": _razorpay_order_error_user_message(err)}), 502

            with db_cursor() as (conn, cur):
                cur.execute(
                    "INSERT INTO payments (student_id, order_id, amount, status) VALUES (%s, %s, %s, %s)",
                    (sid, rp_order["id"], pending_amount, "pending"),
                )

            return jsonify(
                {
                    "gateway": "razorpay",
                    "key_id": key_id,
                    "order_id": rp_order["id"],
                    "amount": int(rp_order["amount"]),
                    "currency": rp_order.get("currency") or "INR",
                }
            )

        # Fallback: simulated checkout (no Razorpay keys)
        order_id = f"ORD-{uuid.uuid4().hex[:12].upper()}"

        with db_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO payments (student_id, order_id, amount, status) VALUES (%s, %s, %s, %s)",
                (sid, order_id, pending_amount, "pending"),
            )

        return jsonify(
            {
                "gateway": "mock",
                "order_id": order_id,
                "amount": pending_amount,
                "checkout_url": url_for("payment_bp.mock_checkout", order_id=order_id),
            }
        )
    except Exception as e:
        print(f"DEBUG: Create order failed: {str(e)}")
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500


@payment_bp.route("/verify-payment", methods=["POST"])
@require_login
@require_roles("student")
def verify_payment():
    ensure_payments_table()
    sid = get_current_user().get("extra_id")
    if not sid:
        return jsonify({"error": "Student profile not linked"}), 400

    payload = request.get_json(silent=True) or {}
    order_id = (payload.get("razorpay_order_id") or "").strip()
    payment_id = (payload.get("razorpay_payment_id") or "").strip()
    signature = (payload.get("razorpay_signature") or "").strip()

    if not order_id or not payment_id or not signature:
        return jsonify({"error": "Missing payment details"}), 400

    if not _razorpay_configured()[0]:
        return jsonify({"error": "Payment gateway not configured"}), 503

    if not _verify_razorpay_payment_signature(order_id, payment_id, signature):
        return jsonify({"error": "Invalid payment signature"}), 400

    redirect_url = url_for("payment_bp.payment_success", order_id=order_id)

    with db_cursor() as (conn, cur):
        cur.execute("SELECT * FROM payments WHERE order_id = %s", (order_id,))
        pay_row = cur.fetchone()

        if not pay_row:
            return jsonify({"error": "Order not found"}), 404
        if pay_row["student_id"] != sid:
            return jsonify({"error": "Unauthorized"}), 403

        status = (pay_row.get("status") or "").lower()
        if status == "success":
            return jsonify({"redirect": redirect_url})

        cur.execute("SELECT course_id, current_semester FROM students WHERE id = %s", (sid,))
        st = cur.fetchone()
        if not st:
            return jsonify({"error": "Student record missing"}), 500

        structure = _fee_structure_row(cur, st["course_id"], st["current_semester"])

        cur.execute(
            "UPDATE payments SET status = 'success', payment_id = %s WHERE id = %s AND status = %s",
            (payment_id, pay_row["id"], "pending"),
        )
        if cur.rowcount == 0:
            cur.execute("SELECT status FROM payments WHERE id = %s", (pay_row["id"],))
            again = cur.fetchone()
            if again and (again.get("status") or "").lower() == "success":
                return jsonify({"redirect": redirect_url})
            return jsonify({"error": "Payment could not be confirmed"}), 409

        if structure:
            key_id = _env_strip(os.environ.get("RAZORPAY_KEY_ID"))
            mode = "Razorpay (Test)" if "rzp_test_" in key_id else "Razorpay"
            receipt_no = f"RCP-RZP-{uuid.uuid4().hex[:8].upper()}"
            cur.execute(
                """
                INSERT INTO fee_payments (student_id, fee_structure_id, amount_paid, payment_date, payment_mode, receipt_no, remarks)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    sid,
                    structure["id"],
                    float(pay_row["amount"]),
                    date.today(),
                    mode,
                    receipt_no,
                    f"razorpay_payment:{payment_id}",
                ),
            )

    return jsonify({"redirect": redirect_url})


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
                
                structure = _fee_structure_row(cur, st["course_id"], st["current_semester"])
                
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
