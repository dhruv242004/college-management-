"""AI College Assistant Chatbot engine.

Hybrid rule-based + database-aware assistant with optional LLM fallback.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from database import db_cursor


@dataclass
class ChatbotResponse:
    reply: str
    intent: str
    source: str  # "rule", "db", "llm", "fallback"
    metadata: Dict[str, Any]


class ChatbotEngine:
    """Hybrid chatbot engine for college domain."""

    def __init__(self) -> None:
        self._init_llm()

    def _init_llm(self) -> None:
        """Best-effort OpenAI client setup."""
        self._llm_client = None
        self._llm_model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            return
        try:
            import openai  # type: ignore

            openai.api_key = api_key
            self._llm_client = openai
        except Exception:
            self._llm_client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_response(self, user: Dict[str, Any], message: str) -> Dict[str, Any]:
        """Main entrypoint. Returns JSON-serializable dict."""
        text = (message or "").strip()
        if not text:
            return {
                "reply": "Please type a question so I can help you.",
                "intent": "empty",
                "source": "rule",
                "metadata": {},
            }

        intent = self._classify_intent(text)
        role = (user.get("role_name") or "").lower()
        sid = user.get("extra_id") if role == "student" else None

        # Level 2 – database-integrated answers for students
        if role == "student" and sid:
            if intent == "attendance":
                res = self._answer_attendance(sid)
            elif intent == "fees_status":
                res = self._answer_fees_status(sid)
            elif intent == "marks":
                res = self._answer_marks_summary(sid)
            elif intent == "exam_schedule":
                res = self._answer_exam_schedule(sid)
            elif intent == "timetable":
                res = self._answer_today_timetable(sid)
            elif intent == "course_info":
                res = self._answer_course_info(sid)
            elif intent == "profile":
                res = self._answer_profile_info(sid)
            elif intent == "notices":
                res = self._answer_notices()
            elif intent == "admission_help":
                res = self._answer_admission_help()
            elif intent == "greeting":
                res = self._answer_greeting(user)
            else:
                res = self._answer_faq_or_fallback(text, user)
        else:
            # Non-student or not linked → rule-based only
            if intent == "admission_help":
                res = self._answer_admission_help()
            elif intent == "notices":
                res = self._answer_notices()
            elif intent == "greeting":
                res = self._answer_greeting(user)
            else:
                res = self._answer_faq_or_fallback(text, user)

        return {
            "reply": res.reply,
            "intent": res.intent,
            "source": res.source,
            "metadata": res.metadata,
        }

    # ------------------------------------------------------------------
    # Intent classification (Level 1 – rule-based NLP)
    # ------------------------------------------------------------------
    def _classify_intent(self, text: str) -> str:
        t = text.lower()

        if any(k in t for k in ["attendance", "present", "absent", "proxy"]):
            return "attendance"
        if any(k in t for k in ["fee", "fees", "payment", "dues", "balance"]):
            return "fees_status"
        if any(k in t for k in ["mark", "result", "grade", "score", "cgpa", "sgpa"]):
            return "marks"
        if "exam" in t and any(k in t for k in ["date", "schedule", "time", "timetable", "paper"]):
            return "exam_schedule"
        if any(k in t for k in ["timetable", "class", "lecture", "today", "schedule"]):
            return "timetable"
        if any(k in t for k in ["course", "duration", "department", "degree"]):
            return "course_info"
        if any(k in t for k in ["profile", "enrollment", "my info", "who am i"]):
            return "profile"
        if any(k in t for k in ["notice", "announcement", "circular", "news"]):
            return "notices"
        if any(k in t for k in ["admission", "apply", "eligibility", "course", "how to join"]):
            return "admission_help"
        if any(k in t for k in ["hi", "hello", "hey", "namaste", "good morning", "good evening"]):
            return "greeting"
        return "faq_or_fallback"

    # ------------------------------------------------------------------
    # Level 2 – database-backed answers
    # ------------------------------------------------------------------
    def _answer_attendance(self, student_id: int) -> ChatbotResponse:
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT COUNT(*) AS c FROM attendance WHERE student_id = %s AND status = 'P'",
                (student_id,),
            )
            present_row = cur.fetchone() or {"c": 0}
            cur.execute(
                "SELECT COUNT(*) AS c FROM attendance WHERE student_id = %s",
                (student_id,),
            )
            total_row = cur.fetchone() or {"c": 0}
        present = int(present_row["c"])
        total = int(total_row["c"])
        pct = round(present * 100 / total) if total else 0

        if total == 0:
            reply = (
                "I don’t see any attendance records for you yet. "
                "Once faculty start marking attendance, I’ll show your percentage here."
            )
        else:
            status_line = "You are currently eligible for exams." if pct >= 75 else (
                "Your attendance is below 75%. Please attend more classes to stay exam-eligible."
            )
            reply = (
                f"Your current attendance is {pct}% "
                f"({present} out of {total} classes marked present). {status_line}"
            )

        return ChatbotResponse(
            reply=reply,
            intent="attendance",
            source="db",
            metadata={"present": present, "total": total, "percentage": pct},
        )

    def _answer_fees_status(self, student_id: int) -> ChatbotResponse:
        with db_cursor() as (conn, cur):
            # Get student's course & semester
            cur.execute(
                "SELECT course_id, current_semester, enrollment_no FROM students WHERE id = %s",
                (student_id,),
            )
            stu = cur.fetchone()
            if not stu:
                return ChatbotResponse(
                    reply="I could not find your student record in the system.",
                    intent="fees_status",
                    source="db",
                    metadata={},
                )
            course_id = stu["course_id"]
            semester = stu["current_semester"]
            enrollment_no = stu["enrollment_no"]

            # Total fee for this course + semester (all academic years)
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0) AS total_fee
                FROM fee_structure
                WHERE course_id = %s AND semester = %s
                """,
                (course_id, semester),
            )
            fs = cur.fetchone() or {"total_fee": 0}
            total_fee = float(fs["total_fee"] or 0)

            # Total paid by this student for matching fee structures
            cur.execute(
                """
                SELECT COALESCE(SUM(fp.amount_paid), 0) AS paid
                FROM fee_payments fp
                JOIN fee_structure fs ON fs.id = fp.fee_structure_id
                WHERE fp.student_id = %s AND fs.course_id = %s AND fs.semester = %s
                """,
                (student_id, course_id, semester),
            )
            pr = cur.fetchone() or {"paid": 0}
            paid = float(pr["paid"] or 0)

        due = max(total_fee - paid, 0.0)
        if total_fee == 0:
            reply = (
                "I couldn’t find a configured fee structure for your course and semester yet. "
                "Please contact the accounts section for details."
            )
        elif due <= 0.01:
            reply = (
                f"Your fees for the current semester appear to be fully paid. "
                f"Total fee was ₹{total_fee:,.2f} against enrollment {enrollment_no}."
            )
        elif paid == 0:
            reply = (
                f"Your total fee for the current semester is ₹{total_fee:,.2f}, "
                f"and I don’t see any payments recorded yet. "
                "Please pay before the due date mentioned in your fee receipt."
            )
        else:
            reply = (
                f"Your total fee for the current semester is ₹{total_fee:,.2f}. "
                f"You have paid ₹{paid:,.2f} so far. Pending amount: ₹{due:,.2f}."
            )

        return ChatbotResponse(
            reply=reply,
            intent="fees_status",
            source="db",
            metadata={"total_fee": total_fee, "paid": paid, "due": due},
        )

    def _answer_marks_summary(self, student_id: int) -> ChatbotResponse:
        from routes.exam_routes import EXAM_SESSION  # lazy import to avoid cycles

        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT s.name AS subject_name,
                       s.code AS subject_code,
                       m.total_marks,
                       m.grade
                FROM marks m
                JOIN subjects s ON s.id = m.subject_id
                WHERE m.student_id = %s AND m.exam_session = %s AND m.published = TRUE
                ORDER BY s.name
                """,
                (student_id, EXAM_SESSION),
            )
            rows = cur.fetchall()

        if not rows:
            reply = (
                "I couldn’t find any published results for you yet. "
                "Once faculty publish results, I’ll be able to summarize your marks."
            )
            return ChatbotResponse(
                reply=reply,
                intent="marks",
                source="db",
                metadata={"results": []},
            )

        lines = []
        for r in rows[:6]:
            subj = r["subject_name"]
            code = r["subject_code"]
            total = r["total_marks"]
            grade = r["grade"] or "-"
            if total is None:
                lines.append(f"• {subj} ({code}): grade {grade}")
            else:
                lines.append(f"• {subj} ({code}): {total:.1f} marks, grade {grade}")

        reply = "Here is a quick summary of your latest published results:\n" + "\n".join(lines)
        if len(rows) > 6:
            reply += f"\n…and {len(rows) - 6} more subjects. Visit the Results page for full details."

        return ChatbotResponse(
            reply=reply,
            intent="marks",
            source="db",
            metadata={"subjects_count": len(rows)},
        )

    def _answer_exam_schedule(self, student_id: int) -> ChatbotResponse:
        """Upcoming exams for the student's course/semester, if exams table exists."""
        # This query is defensive – if the exams table is missing, it will fail gracefully.
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT course_id, current_semester FROM students WHERE id = %s",
                (student_id,),
            )
            stu = cur.fetchone()
            if not stu:
                return ChatbotResponse(
                    reply="I could not find your student record to look up exam dates.",
                    intent="exam_schedule",
                    source="db",
                    metadata={},
                )
            course_id = stu["course_id"]
            semester = stu["current_semester"]

            try:
                cur.execute(
                    """
                    SELECT e.exam_date,
                           e.start_time,
                           e.end_time,
                           s.name AS subject_name,
                           s.code AS subject_code,
                           e.exam_type
                    FROM exams e
                    JOIN subjects s ON s.id = e.subject_id
                    WHERE e.course_id = %s
                      AND s.semester = %s
                      AND e.exam_date >= CURRENT_DATE
                    ORDER BY e.exam_date, e.start_time
                    LIMIT 8
                    """,
                    (course_id, semester),
                )
                rows = cur.fetchall()
            except Exception:
                rows = []

        if not rows:
            reply = (
                "I don’t see any upcoming exams scheduled for your course and semester yet. "
                "Please check the Exams section or contact your department."
            )
            return ChatbotResponse(
                reply=reply,
                intent="exam_schedule",
                source="db",
                metadata={"exams": []},
            )

        lines = []
        for r in rows:
            date_str = r["exam_date"].strftime("%d %b %Y")
            time_str = f"{r['start_time'].strftime('%H:%M')}–{r['end_time'].strftime('%H:%M')}"
            subj = r["subject_name"]
            code = r["subject_code"]
            etype = r["exam_type"]
            lines.append(f"• {date_str}, {time_str}: {subj} ({code}) – {etype}")

        reply = "Here are your upcoming exam dates:\n" + "\n".join(lines)

        return ChatbotResponse(
            reply=reply,
            intent="exam_schedule",
            source="db",
            metadata={"count": len(rows)},
        )

    def _answer_today_timetable(self, student_id: int) -> ChatbotResponse:
        """Fetch current day's classes for the student."""
        from datetime import datetime
        day_of_week = datetime.now().isoweekday()  # 1 (Mon) to 7 (Sun)
        
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT course_id, current_semester FROM students WHERE id = %s",
                (student_id,),
            )
            stu = cur.fetchone()
            if not stu:
                return ChatbotResponse(reply="Student record not found.", intent="timetable", source="db", metadata={})
            
            cur.execute(
                """
                SELECT tt.start_time, tt.end_time, s.name AS subject_name, tt.room,
                       f.first_name, f.last_name
                FROM timetable tt
                JOIN subjects s ON s.id = tt.subject_id
                JOIN faculty f ON f.id = tt.faculty_id
                WHERE tt.course_id = %s AND tt.semester = %s AND tt.day_of_week = %s
                ORDER BY tt.start_time
                """,
                (stu["course_id"], stu["current_semester"], day_of_week)
            )
            rows = cur.fetchall()

        if not rows:
            day_name = datetime.now().strftime("%A")
            return ChatbotResponse(
                reply=f"You have no classes scheduled for today ({day_name}). Enjoy your day!",
                intent="timetable",
                source="db",
                metadata={}
            )

        lines = []
        for r in rows:
            time_range = f"{r['start_time'].strftime('%H:%M')} - {r['end_time'].strftime('%H:%M')}"
            faculty = f"{r['first_name']} {r['last_name']}"
            lines.append(f"• {time_range}: {r['subject_name']} in {r['room']} (Faculty: {faculty})")
        
        reply = "Here is your schedule for today:\n" + "\n".join(lines)
        return ChatbotResponse(reply=reply, intent="timetable", source="db", metadata={"count": len(rows)})

    def _answer_course_info(self, student_id: int) -> ChatbotResponse:
        """Details about student's course and department."""
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT c.name AS course_name, c.code AS course_code, c.duration_years,
                       d.name AS dept_name
                FROM students s
                JOIN courses c ON c.id = s.course_id
                JOIN departments d ON d.id = c.department_id
                WHERE s.id = %s
                """,
                (student_id,)
            )
            info = cur.fetchone()
        
        if not info:
            return ChatbotResponse(reply="Could not find your course details.", intent="course_info", source="db", metadata={})
        
        reply = (
            f"You are enrolled in **{info['course_name']}** ({info['course_code']}) "
            f"under the **{info['dept_name']}** department. "
            f"The total duration of this course is {info['duration_years']} years."
        )
        return ChatbotResponse(reply=reply, intent="course_info", source="db", metadata=info)

    def _answer_profile_info(self, student_id: int) -> ChatbotResponse:
        """Student profile snapshot."""
        with db_cursor() as (conn, cur):
            cur.execute(
                "SELECT enrollment_no, first_name, last_name, email, phone, current_semester FROM students WHERE id = %s",
                (student_id,)
            )
            p = cur.fetchone()
        
        if not p:
            return ChatbotResponse(reply="Profile not found.", intent="profile", source="db", metadata={})
        
        reply = (
            f"**Profile Details:**\n"
            f"• Name: {p['first_name']} {p['last_name']}\n"
            f"• Enrollment No: {p['enrollment_no']}\n"
            f"• Current Semester: {p['current_semester']}\n"
            f"• Email: {p['email']}\n"
            f"• Phone: {p['phone'] or 'Not provided'}"
        )
        return ChatbotResponse(reply=reply, intent="profile", source="db", metadata=p)

    def _answer_notices(self) -> ChatbotResponse:
        with db_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT title, category, created_at
                FROM notices
                WHERE is_published = TRUE
                ORDER BY created_at DESC
                LIMIT 5
                """
            )
            rows = cur.fetchall()

        if not rows:
            reply = "There are no active notices at the moment. Please check again later."
        else:
            lines = []
            for r in rows:
                date_str = r["created_at"].strftime("%d %b %Y")
                lines.append(f"• [{r['category']}] {r['title']} ({date_str})")
            reply = "Here are the latest college notices:\n" + "\n".join(lines)

        return ChatbotResponse(
            reply=reply,
            intent="notices",
            source="db",
            metadata={"count": len(rows)},
        )

    # ------------------------------------------------------------------
    # Level 1 – canned rule-based answers
    # ------------------------------------------------------------------
    def _answer_greeting(self, user: Dict[str, Any]) -> ChatbotResponse:
        name = user.get("username") or "there"
        reply = (
            f"Hello {name}! I’m your AI College Assistant. You can ask me about your "
            "attendance, fees, results, exam dates, or admission-related queries."
        )
        return ChatbotResponse(
            reply=reply,
            intent="greeting",
            source="rule",
            metadata={},
        )

    def _answer_admission_help(self) -> ChatbotResponse:
        reply = (
            "For new admissions:\n"
            "• Use the online registration form to create your student account.\n"
            "• Choose your course based on eligibility (12th marks / entrance exam, as applicable).\n"
            "• Keep scanned copies of your marksheets, ID proof, and photos ready.\n"
            "• After online submission, visit the college with originals for document verification.\n"
            "• For exact dates, fees, and eligibility, please refer to the official college website "
            "or the Notices section in this portal."
        )
        return ChatbotResponse(
            reply=reply,
            intent="admission_help",
            source="rule",
            metadata={},
        )

    # ------------------------------------------------------------------
    # Level 3 – LLM fallback
    # ------------------------------------------------------------------
    def _answer_faq_or_fallback(self, text: str, user: Dict[str, Any]) -> ChatbotResponse:
        """Try to answer FAQs via LLM; fall back to a helpful default."""
        # Quick rule-based FAQ snippets
        lower = text.lower()
        if "college timing" in lower or "college time" in lower:
            reply = (
                "Regular college timings are typically 9:00 AM to 4:00 PM, "
                "but please refer to your timetable for exact class hours."
            )
            return ChatbotResponse(
                reply=reply,
                intent="faq_or_fallback",
                source="rule",
                metadata={},
            )

        if self._llm_client is None:
            fallback = (
                "I’m not sure about that yet, but I can help with:\n"
                "• Your attendance, fees, and results\n"
                "• Upcoming exam dates (if scheduled)\n"
                "• Notices and admission guidance\n"
                "Try asking, for example: “What is my attendance?” or “Show my fee status”."
            )
            return ChatbotResponse(
                reply=fallback,
                intent="faq_or_fallback",
                source="fallback",
                metadata={"llm_enabled": False},
            )

        try:
            prompt = self._build_llm_prompt(text, user)
            completion = self._llm_client.ChatCompletion.create(  # type: ignore[attr-defined]
                model=self._llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant for a college management system. "
                            "Answer briefly (2–4 sentences) and stay within general academic, "
                            "admission, or campus information. Do NOT invent specific marks, "
                            "fees, or personal data – those are handled by the application."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=256,
            )
            reply = completion.choices[0].message["content"].strip()  # type: ignore[index]
            source = "llm"
            meta = {"llm_enabled": True}
        except Exception:
            reply = (
                "I’m having trouble reaching the AI service right now. "
                "You can still ask me about your attendance, fees, results, exams, or notices."
            )
            source = "fallback"
            meta = {"llm_enabled": True, "llm_error": True}

        return ChatbotResponse(
            reply=reply,
            intent="faq_or_fallback",
            source=source,
            metadata=meta,
        )

    def _build_llm_prompt(self, text: str, user: Dict[str, Any]) -> str:
        """Include light context without leaking PII."""
        role = user.get("role_name") or "unknown"
        enrollment = ""
        if role == "student":
            with db_cursor() as (conn, cur):
                cur.execute(
                    "SELECT enrollment_no FROM students WHERE id = %s",
                    (user.get("extra_id"),),
                )
                row = cur.fetchone()
                if row:
                    enrollment = row["enrollment_no"]

        context_bits = [
            f"User role: {role}",
        ]
        if enrollment:
            context_bits.append(f"Student enrollment: {enrollment}")
        context = "\n".join(context_bits)
        return f"{context}\n\nQuestion: {text}"


# Singleton instance that routes can import
default_chatbot_engine = ChatbotEngine()

