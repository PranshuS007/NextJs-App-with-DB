from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from psycopg.errors import UniqueViolation

from api.auth_pg import require_user
from db import get_conn, serialize_row
from email_service import queue_and_send

router = APIRouter(prefix="/api", tags=["bookings"])


class BookingRequest(BaseModel):
    occurrence_id: int


class CancelBookingRequest(BaseModel):
    reason: str = ""


class InstructorCancelRequest(BaseModel):
    reason: str = "Class cancelled by instructor."


def format_occurrence(row):
    local_start = row["starts_at"].astimezone(ZoneInfo(row["timezone"]))
    return f"{row['title']} on {local_start.strftime('%A, %B %d at %I:%M %p %Z')}"


def booking_subject(status):
    if status == "confirmed":
        return "Your Still Studio class is confirmed"
    if status == "waitlisted":
        return "You are on the Still Studio waitlist"
    return "Still Studio booking update"


def booking_body(user, occurrence, status):
    class_text = format_occurrence(occurrence)
    if status == "confirmed":
        return f"Your spot is confirmed for {class_text}. We look forward to practicing with you."
    return f"You have been added to the waitlist for {class_text}. We will email you if a spot opens."


def cancellation_window_open(occurrence):
    deadline = occurrence["starts_at"] - timedelta(hours=occurrence["cancellation_deadline_hours"])
    return datetime.now(timezone.utc) <= deadline


def load_occurrence_for_update(cur, occurrence_id):
    cur.execute(
        """
        SELECT co.id, co.starts_at, co.ends_at, co.max_size, co.status, co.timezone,
               cs.title, cs.cancellation_deadline_hours
        FROM class_occurrences co
        JOIN class_sessions cs ON cs.id = co.class_session_id
        WHERE co.id = %s
        FOR UPDATE OF co
        """,
        (occurrence_id,),
    )
    occurrence = cur.fetchone()
    if occurrence is None:
        raise HTTPException(status_code=404, detail="Class was not found.")
    if occurrence["status"] != "scheduled":
        raise HTTPException(status_code=400, detail="This class has been cancelled.")
    if occurrence["starts_at"] <= datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This class has already started.")
    return occurrence


def promote_waitlisted(cur, occurrence):
    cur.execute(
        """
        SELECT b.id, b.user_id, u.email
        FROM bookings b
        JOIN users u ON u.id = b.user_id
        WHERE b.class_occurrence_id = %s AND b.status = 'waitlisted'
        ORDER BY b.waitlist_position, b.created_at
        LIMIT 1
        FOR UPDATE OF b SKIP LOCKED
        """,
        (occurrence["id"],),
    )
    booking = cur.fetchone()
    if booking is None:
        return None
    cur.execute(
        """
        UPDATE bookings
        SET status = 'confirmed', waitlist_position = NULL, promoted_at = NOW()
        WHERE id = %s
        RETURNING id, status
        """,
        (booking["id"],),
    )
    promoted = cur.fetchone()
    body = f"A spot opened for {format_occurrence(occurrence)}. Your waitlist booking has been promoted and confirmed."
    queue_and_send(cur, booking["email"], "Your Still Studio waitlist spot is confirmed", body, booking["user_id"])
    return promoted


@router.post("/bookings")
async def create_booking(payload: BookingRequest, request: Request):
    user = require_user(request)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                occurrence = load_occurrence_for_update(cur, payload.occurrence_id)
                cur.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM bookings
                    WHERE class_occurrence_id = %s AND status = 'confirmed'
                    """,
                    (occurrence["id"],),
                )
                confirmed_count = cur.fetchone()["count"]
                if confirmed_count < occurrence["max_size"]:
                    status = "confirmed"
                    waitlist_position = None
                else:
                    status = "waitlisted"
                    cur.execute(
                        """
                        SELECT COALESCE(MAX(waitlist_position), 0) + 1 AS position
                        FROM bookings
                        WHERE class_occurrence_id = %s AND status = 'waitlisted'
                        """,
                        (occurrence["id"],),
                    )
                    waitlist_position = cur.fetchone()["position"]
                cur.execute(
                    """
                    INSERT INTO bookings (user_id, class_occurrence_id, status, waitlist_position)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, status, waitlist_position, created_at
                    """,
                    (user["id"], occurrence["id"], status, waitlist_position),
                )
                booking = cur.fetchone()
                queue_and_send(cur, user["email"], booking_subject(status), booking_body(user, occurrence, status), user["id"])
            conn.commit()
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="You already have an active booking for this class.") from exc
    return {"booking": serialize_row(booking)}


@router.get("/bookings/me")
async def my_bookings(request: Request):
    user = require_user(request)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.status, b.waitlist_position, b.created_at, b.cancelled_at,
                       co.id AS occurrence_id, co.starts_at, co.ends_at, co.timezone, co.status AS class_status,
                       cs.title, cs.cancellation_deadline_hours
                FROM bookings b
                JOIN class_occurrences co ON co.id = b.class_occurrence_id
                JOIN class_sessions cs ON cs.id = co.class_session_id
                WHERE b.user_id = %s
                ORDER BY co.starts_at DESC
                """,
                (user["id"],),
            )
            rows = [serialize_row(row) for row in cur.fetchall()]
    return {"bookings": rows}


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: int, payload: CancelBookingRequest, request: Request):
    user = require_user(request)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.status, b.class_occurrence_id, co.starts_at, co.ends_at, co.max_size, co.status AS occurrence_status,
                       co.timezone, cs.title, cs.cancellation_deadline_hours
                FROM bookings b
                JOIN class_occurrences co ON co.id = b.class_occurrence_id
                JOIN class_sessions cs ON cs.id = co.class_session_id
                WHERE b.id = %s AND b.user_id = %s
                FOR UPDATE OF b, co
                """,
                (booking_id, user["id"]),
            )
            booking = cur.fetchone()
            if booking is None or booking["status"] not in ("confirmed", "waitlisted"):
                raise HTTPException(status_code=404, detail="Active booking was not found.")
            occurrence = {"id": booking["class_occurrence_id"], "starts_at": booking["starts_at"], "ends_at": booking["ends_at"], "max_size": booking["max_size"], "title": booking["title"], "timezone": booking["timezone"], "cancellation_deadline_hours": booking["cancellation_deadline_hours"]}
            if booking["status"] == "confirmed" and not cancellation_window_open(occurrence):
                raise HTTPException(status_code=400, detail="The cancellation window has closed for this class.")
            cur.execute(
                """
                UPDATE bookings
                SET status = 'cancelled', cancelled_at = NOW(), cancellation_reason = %s
                WHERE id = %s
                RETURNING id, status
                """,
                (payload.reason.strip() or None, booking["id"]),
            )
            cancelled = cur.fetchone()
            if booking["status"] == "confirmed":
                promote_waitlisted(cur, occurrence)
            queue_and_send(cur, user["email"], "Your Still Studio booking was cancelled", f"Your booking for {format_occurrence(occurrence)} has been cancelled.", user["id"])
        conn.commit()
    return {"booking": serialize_row(cancelled)}


@router.post("/instructor/classes/{occurrence_id}/cancel")
async def instructor_cancel_class(occurrence_id: int, payload: InstructorCancelRequest, request: Request):
    user = require_user(request)
    if user.get("role") != "instructor":
        raise HTTPException(status_code=403, detail="Instructor access is required.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            occurrence = load_occurrence_for_update(cur, occurrence_id)
            cur.execute(
                """
                UPDATE class_occurrences
                SET status = 'cancelled', cancelled_by = %s, cancelled_at = NOW(), cancellation_reason = %s
                WHERE id = %s
                RETURNING id, status
                """,
                (user["id"], payload.reason.strip(), occurrence["id"]),
            )
            cancelled = cur.fetchone()
            cur.execute(
                """
                SELECT b.id, b.user_id, u.email
                FROM bookings b
                JOIN users u ON u.id = b.user_id
                WHERE b.class_occurrence_id = %s AND b.status IN ('confirmed', 'waitlisted')
                FOR UPDATE OF b
                """,
                (occurrence["id"],),
            )
            affected = cur.fetchall()
            cur.execute(
                """
                UPDATE bookings
                SET status = 'class_cancelled', cancelled_at = NOW(), cancellation_reason = %s
                WHERE class_occurrence_id = %s AND status IN ('confirmed', 'waitlisted')
                """,
                (payload.reason.strip(), occurrence["id"]),
            )
            for booking in affected:
                body = f"{format_occurrence(occurrence)} has been cancelled. Reason: {payload.reason.strip()}"
                queue_and_send(cur, booking["email"], "Your Still Studio class was cancelled", body, booking["user_id"])
        conn.commit()
    return {"class": serialize_row(cancelled), "notified": len(affected)}
