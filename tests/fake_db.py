"""In-memory fake for the psycopg layer used by the app.

Handles exactly the SQL statements the app issues (matched by normalized text),
with the same row shapes (dict rows), datetime semantics, and uniqueness
constraints the real PostgreSQL schema enforces. This lets us exercise the
FastAPI endpoints end-to-end without a database server.
"""
from datetime import datetime, timedelta, timezone

import psycopg

# re-usable error type the app catches
UniqueViolation = psycopg.errors.UniqueViolation


def now():
    return datetime.now(timezone.utc)


class FakeCursor:
    def __init__(self, db, conn):
        self.db = db
        self.conn = conn
        self._result = None
        self._row_index = 0

    def execute(self, sql, params=None):
        params = params if params is not None else {}
        handler = self._route(sql)
        self._result = handler(params) if callable(handler) else handler
        self._row_index = 0
        return self

    def _route(self, sql):
        s = " ".join(sql.split())
        if "INSERT INTO users" in s:
            return self._insert_user
        if "INSERT INTO sessions" in s:
            return self._insert_session
        if "INSERT INTO password_reset_tokens" in s:
            return lambda p: self._insert_reset_token(p)
        if "INSERT INTO bookings" in s:
            return self._insert_booking
        if "INSERT INTO contact_messages" in s:
            return lambda p: self._insert_contact(p)
        if "INSERT INTO newsletter_signups" in s:
            return lambda p: self._insert_newsletter(p)
        if "INSERT INTO email_notifications" in s:
            return self._insert_email_notification
        if "UPDATE users SET password_hash" in s:
            return lambda p: self._set_user_password(p)
        if "UPDATE password_reset_tokens SET used_at" in s:
            return lambda p: self._mark_reset_used(p)
        if "UPDATE email_notifications" in s:
            return self._update_email_notification
        if "DELETE FROM sessions WHERE token" in s:
            return lambda p: self._delete_session(p)
        if "DELETE FROM sessions WHERE user_id" in s:
            return lambda p: self._delete_user_sessions(p)
        if "SELECT id, email, role, password_hash" in s:
            return lambda p: self._find_user_by_email(p)
        if "SELECT id FROM users" in s:
            return lambda p: self._find_user_id(p)
        if "SELECT users.id, users.email, users.role, sessions.expires_at" in s:
            return self._find_session
        if "SELECT token, user_id, expires_at, used_at" in s:
            return self._find_reset_token
        if "SELECT co.id, co.starts_at" in s and "FOR UPDATE" in s:
            return self._load_occurrence
        if "SELECT COUNT(*) AS count" in s:
            return self._count_confirmed
        if "SELECT COALESCE(MAX(waitlist_position)" in s:
            return self._next_waitlist_position
        if "WHERE b.class_occurrence_id = %s AND b.status = 'waitlisted'" in s:
            return self._next_waitlisted
        if "SET status = 'confirmed', waitlist_position = NULL" in s:
            return self._promote_booking
        if "JOIN class_occurrences co ON co.id = b.class_occurrence_id" in s and "WHERE b.user_id" in s:
            return self._my_bookings
        if "SELECT b.id, b.status, b.class_occurrence_id" in s and "FOR UPDATE OF b, co" in s:
            return self._cancel_booking_row
        if "SET status = 'cancelled', cancelled_at" in s and "WHERE id" in s:
            return self._cancel_booking
        if "UPDATE class_occurrences" in s and "SET status = 'cancelled'" in s:
            return self._cancel_occurrence
        if "SELECT b.id, b.user_id, u.email" in s and "status IN ('confirmed', 'waitlisted')" in s:
            return self._affected_bookings
        if "UPDATE bookings" in s and "status = 'class_cancelled'" in s:
            return self._bulk_class_cancel
        if "FROM class_occurrences co" in s and "COUNT(b.id) FILTER" in s:
            return self._class_rows
        if "FROM yoga_styles" in s:
            return self._styles
        if "FROM pricing_plans" in s and "WHERE slug" not in s:
            return self._pricing
        if "FROM blog_posts bp" in s and "LIMIT 2" in s:
            return self._home_posts
        if "FROM blog_posts bp" in s:
            return self._blog_posts
        if "FROM pricing_plans" in s and "WHERE slug = %(slug)s" in s:
            return self._plan_by_slug
        raise AssertionError("Unhandled SQL statement: %s" % s[:160])

    # ------------------------------------------------------------------ users
    def _insert_user(self, params):
        email = params[0]
        if any(u["email"] == email for u in self.db["users"]):
            raise UniqueViolation(
                'duplicate key value violates unique constraint "users_email_key"'
            )
        user = {
            "id": self.db.next_id("users"),
            "email": email,
            "password_hash": params[1],
            "role": "member",
            "created_at": now(),
        }
        self.db["users"].append(user)
        return [{"id": user["id"], "email": user["email"], "role": user["role"]}]

    def _find_user_by_email(self, params):
        for user in self.db["users"]:
            if user["email"] == params[0]:
                return [user]
        return []

    def _find_user_id(self, params):
        for user in self.db["users"]:
            if user["email"] == params[0]:
                return [{"id": user["id"]}]
        return []

    def _set_user_password(self, params):
        for user in self.db["users"]:
            if user["id"] == params[1]:
                user["password_hash"] = params[0]
                return []

    # ---------------------------------------------------------------- sessions
    def _insert_session(self, params):
        token, user_id, expires_at = params
        self.db["sessions"].append({
            "token": token,
            "user_id": user_id,
            "expires_at": expires_at,
            "created_at": now(),
        })
        return []

    def _find_session(self, params):
        for s in self.db["sessions"]:
            if s["token"] == params[0]:
                for u in self.db["users"]:
                    if u["id"] == s["user_id"]:
                        return [{
                            "id": u["id"],
                            "email": u["email"],
                            "role": u["role"],
                            "expires_at": s["expires_at"],
                        }]
        return []

    def _delete_session(self, params):
        self.db["sessions"] = [s for s in self.db["sessions"] if s["token"] != params[0]]
        return []

    def _delete_user_sessions(self, params):
        self.db["sessions"] = [s for s in self.db["sessions"] if s["user_id"] != params[0]]
        return []

    # ------------------------------------------------------ password resets
    def _insert_reset_token(self, params):
        token, user_id, expires_at = params
        self.db["password_reset_tokens"].append({
            "token": token,
            "user_id": user_id,
            "expires_at": expires_at,
            "used_at": None,
            "created_at": now(),
        })
        return []

    def _find_reset_token(self, params):
        for r in self.db["password_reset_tokens"]:
            if r["token"] == params[0]:
                return [dict(r)]
        return []

    def _mark_reset_used(self, params):
        for r in self.db["password_reset_tokens"]:
            if r["token"] == params[0]:
                r["used_at"] = now()
        return []

    # ------------------------------------------------------------- bookings
    def _load_occurrence(self, params):
        for occ in self.db["class_occurrences"]:
            if occ["id"] == params[0]:
                sess = self._session_for(occ["class_session_id"])
                return [{
                    "id": occ["id"],
                    "starts_at": occ["starts_at"],
                    "ends_at": occ["ends_at"],
                    "max_size": occ["max_size"],
                    "status": occ["status"],
                    "timezone": occ["timezone"],
                    "title": sess["title"],
                    "cancellation_deadline_hours": sess["cancellation_deadline_hours"],
                }]
        return []

    def _count_confirmed(self, params):
        count = sum(
            1 for b in self.db["bookings"]
            if b["class_occurrence_id"] == params[0] and b["status"] == "confirmed"
        )
        return [{"count": count}]

    def _next_waitlist_position(self, params):
        positions = [
            b["waitlist_position"]
            for b in self.db["bookings"]
            if b["class_occurrence_id"] == params[0] and b["status"] == "waitlisted"
        ]
        return [{"position": (max(positions) if positions else 0) + 1}]

    def _insert_booking(self, params):
        user_id, occurrence_id, status, position = params
        active = [
            b for b in self.db["bookings"]
            if b["user_id"] == user_id
            and b["class_occurrence_id"] == occurrence_id
            and b["status"] in ("confirmed", "waitlisted")
        ]
        if active:
            raise UniqueViolation(
                'duplicate key value violates unique constraint "ux_active_booking_per_user_occurrence"'
            )
        booking = {
            "id": self.db.next_id("bookings"),
            "user_id": user_id,
            "class_occurrence_id": occurrence_id,
            "status": status,
            "waitlist_position": position,
            "cancelled_at": None,
            "cancellation_reason": None,
            "promoted_at": None,
            "created_at": now(),
        }
        self.db["bookings"].append(booking)
        return [{
            "id": booking["id"],
            "status": booking["status"],
            "waitlist_position": booking["waitlist_position"],
            "created_at": booking["created_at"],
        }]

    def _next_waitlisted(self, params):
        candidates = [
            b for b in self.db["bookings"]
            if b["class_occurrence_id"] == params[0] and b["status"] == "waitlisted"
        ]
        candidates.sort(key=lambda b: (b["waitlist_position"] or 0, b["created_at"]))
        if not candidates:
            return []
        b = candidates[0]
        user = next(u for u in self.db["users"] if u["id"] == b["user_id"])
        return [{"id": b["id"], "user_id": b["user_id"], "email": user["email"]}]

    def _promote_booking(self, params):
        for b in self.db["bookings"]:
            if b["id"] == params[0]:
                b["status"] = "confirmed"
                b["waitlist_position"] = None
                b["promoted_at"] = now()
                return [{"id": b["id"], "status": b["status"]}]
        return []

    def _my_bookings(self, params):
        rows = []
        for b in self.db["bookings"]:
            if b["user_id"] != params[0]:
                continue
            occ = next(o for o in self.db["class_occurrences"] if o["id"] == b["class_occurrence_id"])
            sess = self._session_for(occ["class_session_id"])
            rows.append({
                "id": b["id"],
                "status": b["status"],
                "waitlist_position": b["waitlist_position"],
                "created_at": b["created_at"],
                "cancelled_at": b["cancelled_at"],
                "occurrence_id": occ["id"],
                "starts_at": occ["starts_at"],
                "ends_at": occ["ends_at"],
                "timezone": occ["timezone"],
                "class_status": occ["status"],
                "title": sess["title"],
                "cancellation_deadline_hours": sess["cancellation_deadline_hours"],
            })
        rows.sort(key=lambda r: r["starts_at"], reverse=True)
        return rows

    def _cancel_booking_row(self, params):
        booking_id, user_id = params
        for b in self.db["bookings"]:
            if b["id"] == booking_id and b["user_id"] == user_id:
                occ = next(o for o in self.db["class_occurrences"] if o["id"] == b["class_occurrence_id"])
                sess = self._session_for(occ["class_session_id"])
                return [{
                    "id": b["id"],
                    "status": b["status"],
                    "class_occurrence_id": occ["id"],
                    "starts_at": occ["starts_at"],
                    "ends_at": occ["ends_at"],
                    "max_size": occ["max_size"],
                    "occurrence_status": occ["status"],
                    "timezone": occ["timezone"],
                    "title": sess["title"],
                    "cancellation_deadline_hours": sess["cancellation_deadline_hours"],
                }]
        return []

    def _cancel_booking(self, params):
        reason, booking_id = params
        for b in self.db["bookings"]:
            if b["id"] == booking_id:
                b["status"] = "cancelled"
                b["cancelled_at"] = now()
                b["cancellation_reason"] = reason
                return [{"id": b["id"], "status": b["status"]}]
        return []

    def _cancel_occurrence(self, params):
        cancelled_by, reason, occurrence_id = params
        for occ in self.db["class_occurrences"]:
            if occ["id"] == occurrence_id:
                occ["status"] = "cancelled"
                occ["cancelled_by"] = cancelled_by
                occ["cancelled_at"] = now()
                occ["cancellation_reason"] = reason
                return [{"id": occ["id"], "status": occ["status"]}]
        return []

    def _affected_bookings(self, params):
        rows = []
        for b in self.db["bookings"]:
            if b["class_occurrence_id"] == params[0] and b["status"] in ("confirmed", "waitlisted"):
                u = next(usr for usr in self.db["users"] if usr["id"] == b["user_id"])
                rows.append({"id": b["id"], "user_id": b["user_id"], "email": u["email"]})
        return rows

    def _bulk_class_cancel(self, params):
        reason, occurrence_id = params
        for b in self.db["bookings"]:
            if b["class_occurrence_id"] == occurrence_id and b["status"] in ("confirmed", "waitlisted"):
                b["status"] = "class_cancelled"
                b["cancelled_at"] = now()
                b["cancellation_reason"] = reason
        return []

    # ------------------------------------------------------------- content
    def _class_rows(self, params):
        rows = []
        for occ in self.db["class_occurrences"]:
            sess = self._session_for(occ["class_session_id"])
            style = next(y for y in self.db["yoga_styles"] if y["id"] == sess["style_id"])
            instr = next(i for i in self.db["instructors"] if i["id"] == sess["instructor_id"])
            if not sess["is_active"] or occ["starts_at"] < now():
                continue
            confirmed = sum(1 for b in self.db["bookings"]
                            if b["class_occurrence_id"] == occ["id"] and b["status"] == "confirmed")
            waitlisted = sum(1 for b in self.db["bookings"]
                             if b["class_occurrence_id"] == occ["id"] and b["status"] == "waitlisted")
            rows.append({
                "occurrence_id": occ["id"],
                "starts_at": occ["starts_at"],
                "ends_at": occ["ends_at"],
                "timezone": occ["timezone"],
                "max_size": occ["max_size"],
                "status": occ["status"],
                "class_session_id": sess["id"],
                "title": sess["title"],
                "duration_minutes": sess["duration_minutes"],
                "cancellation_deadline_hours": sess["cancellation_deadline_hours"],
                "style": style["name"],
                "level": style["level"],
                "instructor": instr["name"],
                "confirmed_count": confirmed,
                "waitlist_count": waitlisted,
            })
        rows.sort(key=lambda r: r["starts_at"])
        return rows

    def _styles(self, params):
        return [dict(s) for s in self.db["yoga_styles"]]

    def _pricing(self, params):
        rows = [dict(p) for p in self.db["pricing_plans"] if p["is_active"]]
        rows.sort(key=lambda p: (p["display_order"], p["name"]))
        return rows

    def _blog_posts(self, params):
        rows = []
        for p in self.db["blog_posts"]:
            if not p["is_published"]:
                continue
            cat = next(c for c in self.db["blog_categories"] if c["id"] == p["category_id"])
            rows.append({
                "slug": p["slug"],
                "title": p["title"],
                "excerpt": p["excerpt"],
                "body": p["body"],
                "read_time_minutes": p["read_time_minutes"],
                "image_class": p["image_class"],
                "is_featured": p["is_featured"],
                "category": cat["name"],
            })
        rows.sort(key=lambda r: (not r["is_featured"], r["slug"]))
        return rows

    def _home_posts(self, params):
        return self._blog_posts(params)[:2]

    def _plan_by_slug(self, params):
        for p in self.db["pricing_plans"]:
            if p["slug"] == params["slug"] and p["is_active"]:
                return [{
                    "name": p["name"],
                    "description": p["description"],
                    "unit_amount_cents": p["unit_amount_cents"],
                    "currency": p["currency"],
                }]
        return []

    # ------------------------------------------------------- misc inserts
    def _insert_contact(self, params):
        name, email, phone, message = params
        self.db["contact_messages"].append({
            "id": self.db.next_id("contact_messages"),
            "name": name,
            "email": email,
            "phone": phone,
            "message": message,
            "created_at": now(),
        })
        return []

    def _insert_newsletter(self, params):
        email = params[0]
        if not any(n["email"] == email for n in self.db["newsletter_signups"]):
            self.db["newsletter_signups"].append({
                "id": self.db.next_id("newsletter_signups"),
                "email": email,
                "created_at": now(),
            })
        return []

    def _insert_email_notification(self, params):
        user_id, email, subject, body = params
        notification = {
            "id": self.db.next_id("email_notifications"),
            "user_id": user_id,
            "email": email,
            "subject": subject,
            "body": body,
            "status": "pending",
            "error": None,
            "sent_at": None,
            "created_at": now(),
        }
        self.db["email_notifications"].append(notification)
        return [{"id": notification["id"]}]

    def _update_email_notification(self, params):
        # UPDATE ... SET status = 'sent', sent_at = NOW() WHERE id = %s  -> (id,)
        # UPDATE ... SET status = 'pending', error = %s WHERE id = %s    -> (error, id)
        if len(params) == 1:
            status, error, nid = "sent", None, params[0]
        else:
            status, error, nid = "pending", params[0], params[1]
        for n in self.db["email_notifications"]:
            if n["id"] == nid:
                n["status"] = status
                n["error"] = error
                if status == "sent":
                    n["sent_at"] = now()
        return []

    # -------------------------------------------------------------- helpers
    def _session_for(self, class_session_id):
        for s in self.db["class_sessions"]:
            if s["id"] == class_session_id:
                return s
        raise KeyError(class_session_id)

    def fetchone(self):
        if not self._result or self._row_index >= len(self._result):
            return None
        row = self._result[self._row_index]
        self._row_index += 1
        return row

    def fetchall(self):
        if not self._result:
            return []
        rows = self._result
        self._row_index = len(rows)
        return rows

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return FakeCursor(self.db, self)

    def commit(self):
        pass

    def rollback(self):
        pass

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeDb:
    def __init__(self):
        self._counters = {}
        self.store = {
            "users": [], "sessions": [], "password_reset_tokens": [],
            "instructors": [], "yoga_styles": [], "class_sessions": [],
            "class_occurrences": [], "bookings": [], "pricing_plans": [],
            "blog_categories": [], "blog_posts": [], "contact_messages": [],
            "newsletter_signups": [], "email_notifications": [],
        }

    def next_id(self, table):
        self._counters[table] = self._counters.get(table, 0) + 1
        return self._counters[table]

    def __getitem__(self, table):
        return self.store[table]

    def __setitem__(self, table, value):
        self.store[table] = value

    def connect(self, *args, **kwargs):
        return FakeConn(self)

    def reset(self):
        for table in self.store:
            self.store[table] = []
        self._counters = {}


def seed_default_store(db):
    """Minimal data that mirrors scripts/seed.py."""
    db["instructors"].append({
        "id": db.next_id("instructors"), "name": "Maya Bennett", "bio": None,
        "created_at": now(),
    })
    for name, desc, level, dur, order in [
        ("Hatha", "alignment", "All levels", 60, 1),
        ("Vinyasa", "flow", "Open level", 60, 2),
        ("Yin", "restore", "All levels", 75, 3),
    ]:
        db["yoga_styles"].append({
            "id": db.next_id("yoga_styles"), "name": name, "description": desc,
            "level": level, "duration_minutes": dur, "display_order": order,
        })

    def add_session(style_name, title, dow, start_time, dur, order, max_size=3, deadline=12):
        style = next(s for s in db["yoga_styles"] if s["name"] == style_name)
        db["class_sessions"].append({
            "id": db.next_id("class_sessions"),
            "style_id": style["id"],
            "instructor_id": 1,
            "title": title,
            "day_of_week": dow,
            "start_time": start_time,
            "duration_minutes": dur,
            "is_active": True,
            "display_order": order,
            "max_size": max_size,
            "timezone": "America/Los_Angeles",
            "cancellation_deadline_hours": deadline,
        })

    add_session("Vinyasa", "Morning Vinyasa", 1, "07:00", 60, 1)
    add_session("Hatha", "Grounded Hatha", 2, "17:30", 60, 2)

    def add_occurrence(session_id, starts_at, max_size=None):
        sess = next(s for s in db["class_sessions"] if s["id"] == session_id)
        db["class_occurrences"].append({
            "id": db.next_id("class_occurrences"),
            "class_session_id": session_id,
            "starts_at": starts_at,
            "ends_at": starts_at + timedelta(minutes=sess["duration_minutes"]),
            "timezone": sess["timezone"],
            "max_size": max_size or sess["max_size"],
            "status": "scheduled",
            "cancelled_by": None, "cancelled_at": None, "cancellation_reason": None,
            "created_at": now(),
        })

    t0 = now()
    add_occurrence(1, t0 + timedelta(days=1, hours=2))      # occurrence 1 (soon, max 3)
    add_occurrence(1, t0 + timedelta(days=8, hours=2))      # occurrence 2
    add_occurrence(2, t0 - timedelta(hours=1))              # occurrence 3 (already started)

    for slug, name, desc, cents, featured, order in [
        ("drop-in", "Drop-in", "One class", 2200, False, 1),
        ("five-pack", "5 Class Pack", "Five classes", 9500, True, 2),
        ("ten-pack", "10 Class Pack", "Ten classes", 17000, False, 3),
    ]:
        db["pricing_plans"].append({
            "id": db.next_id("pricing_plans"), "slug": slug, "name": name,
            "description": desc, "unit_amount_cents": cents, "currency": "usd",
            "is_featured": featured, "is_active": True, "display_order": order,
        })

    for name in ["Movement", "Breathwork", "Practice"]:
        db["blog_categories"].append({"id": db.next_id("blog_categories"), "name": name})

    def add_post(cat, slug, title, featured):
        cat_id = next(c for c in db["blog_categories"] if c["name"] == cat)["id"]
        db["blog_posts"].append({
            "id": db.next_id("blog_posts"),
            "category_id": cat_id, "slug": slug, "title": title,
            "excerpt": "excerpt", "body": "para one.\n\npara two.",
            "read_time_minutes": 5, "image_class": "blog-one",
            "is_featured": featured, "is_published": True,
            "published_at": now(),
        })

    add_post("Movement", "simple-morning-stretches", "Simple Morning Stretches", True)
    add_post("Breathwork", "breathing-techniques", "Breathing Techniques", False)
    add_post("Practice", "why-consistency", "Why Consistency", False)
