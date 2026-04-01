"""Digital Student ID Card service.

Generates and manages digital ID cards with QR codes and verification.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from typing import Any, Dict, Optional, Tuple

import qrcode
from itsdangerous import URLSafeSerializer, BadSignature

from config import config
from database import db_cursor


@dataclass
class StudentIDCard:
    id: int
    student_id: int
    enrollment_no: str
    card_number: str
    qr_token: str
    qr_image_path: Optional[str]
    blood_group: Optional[str]
    valid_from: date
    valid_till: date


class StudentIDCardService:
    """Service for generating digital ID cards and QR codes."""

    def __init__(self) -> None:
        self.serializer = URLSafeSerializer(config.SECRET_KEY, salt="student-id-card")

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------
    def ensure_card_record(
        self,
        student_id: int,
        blood_group: Optional[str] = None,
    ) -> Tuple[StudentIDCard, Dict[str, Any]]:
        """Get or create a student_id_cards row for the given student."""
        with db_cursor() as (conn, cur):
            # Load student with course details
            cur.execute(
                """
                SELECT s.id,
                       s.enrollment_no,
                       s.first_name,
                       s.last_name,
                       s.date_of_birth,
                       s.admission_date,
                       c.id AS course_id,
                       c.name AS course_name,
                       c.code AS course_code,
                       c.duration_years
                FROM students s
                JOIN courses c ON c.id = s.course_id
                WHERE s.id = %s
                """,
                (student_id,),
            )
            stu = cur.fetchone()
            if not stu:
                raise ValueError("Student not found for ID card generation.")

            # Try existing card
            cur.execute(
                "SELECT * FROM student_id_cards WHERE student_id = %s",
                (student_id,),
            )
            card_row = cur.fetchone()

            student_meta = {
                "full_name": f"{stu['first_name']} {stu['last_name']}",
                "course_name": stu["course_name"],
                "course_code": stu["course_code"],
                "date_of_birth": stu["date_of_birth"],
                "admission_date": stu["admission_date"],
            }

            if card_row:
                # Optionally update blood group if newly provided
                if blood_group and not card_row.get("blood_group"):
                    cur.execute(
                        "UPDATE student_id_cards SET blood_group = %s WHERE id = %s",
                        (blood_group, card_row["id"]),
                    )
                    card_row["blood_group"] = blood_group
                return self._row_to_card(card_row), student_meta

            # No existing card → create one
            enrollment_no = stu["enrollment_no"]
            card_number = enrollment_no  # Simple: card number == enrollment

            # Compute validity: from today (or admission date) for duration_years + 1 year buffer
            valid_from = stu["admission_date"] or date.today()
            duration_years = int(stu.get("duration_years") or 3)
            try:
                valid_till = valid_from.replace(year=valid_from.year + duration_years + 1)
            except ValueError:
                # Handle 29 Feb, etc.
                valid_till = date(valid_from.year + duration_years + 1, 12, 31)

            payload = {
                "student_id": student_id,
                "enrollment_no": enrollment_no,
                "card_number": card_number,
            }
            qr_token = self.serializer.dumps(payload)

            is_pg = hasattr(conn, 'cursor_factory')
            if is_pg:
                cur.execute(
                    """
                    INSERT INTO student_id_cards (
                        student_id, enrollment_no, card_number,
                        qr_token, qr_image_path, blood_group,
                        valid_from, valid_till
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                    """,
                    (
                        student_id,
                        enrollment_no,
                        card_number,
                        qr_token,
                        None,
                        blood_group,
                        valid_from,
                        valid_till,
                    ),
                )
                new_id = cur.fetchone()['id']
            else:
                cur.execute(
                    """
                    INSERT INTO student_id_cards (
                        student_id, enrollment_no, card_number,
                        qr_token, qr_image_path, blood_group,
                        valid_from, valid_till
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        student_id,
                        enrollment_no,
                        card_number,
                        qr_token,
                        None,
                        blood_group,
                        valid_from,
                        valid_till,
                    ),
                )
                new_id = cur.lastrowid

            cur.execute(
                "SELECT * FROM student_id_cards WHERE id = %s",
                (new_id,),
            )
            card_row = cur.fetchone()

        return self._row_to_card(card_row), student_meta

    def generate_qr_image(self, data: str, student_id: int) -> str:
        """Generate QR PNG for given data and return relative static path."""
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=8,
            border=2,
        )
        qr.add_data(data)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        # Save under static/uploads/idcards/
        base_dir = config.UPLOAD_FOLDER
        target_dir = os.path.join(base_dir, "idcards")
        os.makedirs(target_dir, exist_ok=True)

        filename = f"idcard_{student_id}.png"
        abs_path = os.path.join(target_dir, filename)
        img.save(abs_path, format="PNG")

        # Path relative to static root
        rel_path = os.path.join("uploads", "idcards", filename).replace("\\", "/")
        with db_cursor() as (conn, cur):
            cur.execute(
                "UPDATE student_id_cards SET qr_image_path = %s WHERE student_id = %s",
                (rel_path, student_id),
            )
        return rel_path

    def get_card_with_student(self, student_id: int) -> Tuple[Optional[StudentIDCard], Optional[Dict[str, Any]]]:
        """Fetch card + basic student info if card exists."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT c.*, s.first_name, s.last_name, s.enrollment_no,
                       s.date_of_birth, s.photo_path,
                       s.course_id, s.current_semester,
                       c2.name AS course_name, c2.code AS course_code
                FROM student_id_cards c
                JOIN students s ON s.id = c.student_id
                JOIN courses c2 ON c2.id = s.course_id
                WHERE c.student_id = %s
                """,
                (student_id,),
            )
            row = cur.fetchone()
            if not row:
                return None, None

            card = self._row_to_card(row)
            meta = {
                "full_name": f"{row['first_name']} {row['last_name']}",
                "enrollment_no": row["enrollment_no"],
                "date_of_birth": row["date_of_birth"],
                "photo_path": row.get("photo_path"),
                "course_name": row["course_name"],
                "course_code": row["course_code"],
                "semester": row["current_semester"],
            }
            return card, meta

    def verify_token(self, token: str) -> Tuple[bool, Optional[StudentIDCard], Optional[Dict[str, Any]], str]:
        """Verify QR token and return card + limited public student data."""
        try:
            payload = self.serializer.loads(token)
        except BadSignature:
            return False, None, None, "Invalid or tampered verification code."

        student_id = payload.get("student_id")
        enrollment_no = payload.get("enrollment_no")
        if not student_id or not enrollment_no:
            return False, None, None, "Verification data is incomplete."

        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT c.*, s.first_name, s.last_name,
                       s.enrollment_no, s.photo_path,
                       c2.name AS course_name, c2.code AS course_code
                FROM student_id_cards c
                JOIN students s ON s.id = c.student_id
                JOIN courses c2 ON c2.id = s.course_id
                WHERE c.student_id = %s AND c.enrollment_no = %s
                """,
                (student_id, enrollment_no),
            )
            row = cur.fetchone()
            if not row:
                return False, None, None, "No matching ID card found for this code."

            card = self._row_to_card(row)
            public_meta = {
                "full_name": f"{row['first_name']} {row['last_name']}",
                "enrollment_no": row["enrollment_no"],
                "course_name": row["course_name"],
                "course_code": row["course_code"],
                "photo_path": row.get("photo_path"),
            }
            return True, card, public_meta, ""

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _row_to_card(self, row: Dict[str, Any]) -> StudentIDCard:
        return StudentIDCard(
            id=row["id"],
            student_id=row["student_id"],
            enrollment_no=row["enrollment_no"],
            card_number=row["card_number"],
            qr_token=row["qr_token"],
            qr_image_path=row.get("qr_image_path"),
            blood_group=row.get("blood_group"),
            valid_from=row["valid_from"],
            valid_till=row["valid_till"],
        )


# Shared singleton for routes
default_id_card_service = StudentIDCardService()

