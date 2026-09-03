from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import fetch_all, get_conn

router = APIRouter(prefix="/api", tags=["content"])


class ContactMessage(BaseModel):
    name: str
    email: str
    phone: str = ""
    message: str


class NewsletterSignup(BaseModel):
    email: str


def money(cents):
    amount = cents / 100
    return f"${amount:,.0f}" if amount.is_integer() else f"${amount:,.2f}"


def class_rows(limit=None):
    query = """
        SELECT co.id AS occurrence_id, co.starts_at, co.ends_at, co.timezone, co.max_size, co.status,
               cs.id AS class_session_id, cs.title, cs.duration_minutes, cs.cancellation_deadline_hours,
               ys.name AS style, ys.level, i.name AS instructor,
               COUNT(b.id) FILTER (WHERE b.status = 'confirmed') AS confirmed_count,
               COUNT(b.id) FILTER (WHERE b.status = 'waitlisted') AS waitlist_count
        FROM class_occurrences co
        JOIN class_sessions cs ON cs.id = co.class_session_id
        JOIN yoga_styles ys ON ys.id = cs.style_id
        JOIN instructors i ON i.id = cs.instructor_id
        LEFT JOIN bookings b ON b.class_occurrence_id = co.id
        WHERE cs.is_active = TRUE AND co.starts_at >= NOW()
        GROUP BY co.id, cs.id, ys.id, i.id
        ORDER BY co.starts_at
    """
    rows = fetch_all(query)
    if limit:
        rows = rows[:limit]
    for row in rows:
        local_start = row["starts_at"]
        if isinstance(local_start, str):
            from datetime import datetime
            local_start = datetime.fromisoformat(local_start)
        local_start = local_start.astimezone(ZoneInfo(row["timezone"]))
        row["day"] = local_start.strftime("%A")
        row["date"] = local_start.strftime("%b %d")
        row["time"] = local_start.strftime("%I:%M %p").lstrip("0")
        row["spots_remaining"] = max(row["max_size"] - row["confirmed_count"], 0)
    return rows


@router.get("/classes")
async def classes_content():
    styles = fetch_all("SELECT id, name, description, level, duration_minutes FROM yoga_styles ORDER BY display_order, name")
    return {"styles": styles, "schedule": class_rows()}


@router.get("/pricing")
async def pricing_content():
    rows = fetch_all("""
        SELECT slug, name, description, unit_amount_cents, currency, is_featured
        FROM pricing_plans
        WHERE is_active = TRUE
        ORDER BY display_order, name
    """)
    for row in rows:
        row["price"] = money(row["unit_amount_cents"])
    return {"plans": rows}


@router.get("/blog")
async def blog_content():
    posts = fetch_all("""
        SELECT bp.slug, bp.title, bp.excerpt, bp.body, bp.read_time_minutes,
               bp.image_class, bp.is_featured, bc.name AS category
        FROM blog_posts bp
        JOIN blog_categories bc ON bc.id = bp.category_id
        WHERE bp.is_published = TRUE
        ORDER BY bp.is_featured DESC, bp.published_at DESC, bp.id DESC
    """)
    return {"posts": posts}


@router.get("/home")
async def home_content():
    posts = fetch_all("""
        SELECT bp.slug, bp.title, bp.read_time_minutes, bc.name AS category
        FROM blog_posts bp
        JOIN blog_categories bc ON bc.id = bp.category_id
        WHERE bp.is_published = TRUE
        ORDER BY bp.is_featured DESC, bp.published_at DESC, bp.id DESC
        LIMIT 2
    """)
    return {"classes": class_rows(3), "posts": posts}


@router.post("/contact")
async def save_contact_message(payload: ContactMessage):
    if not payload.name.strip() or not payload.email.strip() or not payload.message.strip():
        raise HTTPException(status_code=400, detail="Please complete the required fields.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_messages (name, email, phone, message)
                VALUES (%s, %s, %s, %s)
                """,
                (payload.name.strip(), payload.email.lower().strip(), payload.phone.strip() or None, payload.message.strip()),
            )
        conn.commit()
    return {"message": "Thank you. We will be in touch within two studio days."}


@router.post("/newsletter")
async def save_newsletter_signup(payload: NewsletterSignup):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO newsletter_signups (email)
                VALUES (%s)
                ON CONFLICT (email) DO NOTHING
                """,
                (payload.email.lower().strip(),),
            )
        conn.commit()
    return {"message": "Thank you. A little stillness is on its way."}
