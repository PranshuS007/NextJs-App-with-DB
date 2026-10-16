"""End-to-end API tests for the app running against the in-memory fake DB.

Run:  python -m pytest tests/test_api_flows.py -q
"""
from datetime import datetime, timedelta, timezone

from conftest import client, fake_db as _db


def register(email="a@example.com", password="password123", expect=200):
    resp = client.post("/api/auth/register", json={"email": email, "password": password})
    assert resp.status_code == expect, (resp.status_code, resp.text)
    return resp


def login(email, password, expect=200):
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == expect, (resp.status_code, resp.text)
    return resp


def auth_headers_from(resp):
    set_cookie = resp.headers.get("set-cookie", "")
    # extract still_session=...;
    for part in set_cookie.split(";"):
        part = part.strip()
        if part.startswith("still_session="):
            return {"Cookie": part}
    return {}


def test_pages():
    for path in ["/", "/about", "/classes", "/blog", "/contact", "/login", "/register", "/forgot-password"]:
        resp = client.get(path)
        assert resp.status_code == 200, path


def test_dashboard_redirects_when_logged_out():
    resp = client.get("/dashboard", follow_redirects=False)
    assert resp.status_code in (302, 307)
    assert "/login" in resp.headers["location"]


def test_content_endpoints():
    classes = client.get("/api/classes")
    assert classes.status_code == 200
    data = classes.json()
    assert len(data["styles"]) == 3
    assert len(data["schedule"]) >= 1
    for item in data["schedule"]:
        assert "spots_remaining" in item
        assert item["spots_remaining"] >= 0
        assert item["day"] and item["date"] and item["time"]

    pricing = client.get("/api/pricing")
    assert pricing.status_code == 200
    assert pricing.json()["plans"][0]["price"] == "$22"

    blog = client.get("/api/blog")
    assert blog.status_code == 200
    assert len(blog.json()["posts"]) == 3

    home = client.get("/api/home")
    assert home.status_code == 200
    assert 0 < len(home.json()["classes"]) <= 3 and len(home.json()["posts"]) == 2


def test_contact_and_newsletter():
    assert client.post("/api/contact", json={
        "name": "J", "email": "j@x.com", "message": "hi"
    }).status_code == 200
    assert client.post("/api/contact", json={
        "name": "", "email": "j@x.com", "message": "hi"
    }).status_code == 400
    assert client.post("/api/newsletter", json={"email": "n@x.com"}).status_code == 200


def test_register_and_duplicate():
    register("new@example.com")
    register("new@example.com", expect=400)
    register("pwshort@example.com", "short", expect=400)  # password too short


def test_login_logout_me():
    register("u1@example.com")
    resp = login("u1@example.com", "password123")
    hdrs = auth_headers_from(resp)
    me = client.get("/api/auth/me", headers=hdrs)
    assert me.status_code == 200 and me.json()["user"]["email"] == "u1@example.com"

    bad = login("u1@example.com", "wrongpass", expect=401).status_code
    assert bad == 401

    out = client.post("/api/auth/logout", json={}, headers=hdrs)
    assert out.status_code == 200
    me2 = client.get("/api/auth/me", headers=hdrs)
    assert me2.json()["user"] is None


def test_public_forgot_password_flow():
    # existing user: email queued, no reset_url in response
    register("reset@example.com")
    resp = client.post("/api/auth/forgot-password", json={"email": "reset@example.com"})
    assert resp.status_code == 200
    body = resp.json()
    assert "reset_url" not in body
    assert body["message"]
    # non-existing user: same generic response, no leak
    resp2 = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert resp2.status_code == 200
    assert resp2.json() == body


def test_reset_password_flow():
    register("reset2@example.com")
    old_hash = next(u for u in _db["users"] if u["email"] == "reset2@example.com")["password_hash"]
    client.post("/api/auth/forgot-password", json={"email": "reset2@example.com"})
    token = _db["password_reset_tokens"][-1]["token"]

    resp = client.post("/api/auth/reset-password", json={"token": token, "password": "newpassword1"})
    assert resp.status_code == 200, resp.text
    new_hash = next(u for u in _db["users"] if u["email"] == "reset2@example.com")["password_hash"]
    assert new_hash != old_hash
    # token now spent
    resp2 = client.post("/api/auth/reset-password", json={"token": token, "password": "newpassword1"})
    assert resp2.status_code == 400
    # bogus token
    resp3 = client.post("/api/auth/reset-password", json={"token": "nope", "password": "newpassword1"})
    assert resp3.status_code == 400
    # short password
    resp4 = client.post("/api/auth/reset-password", json={"token": "nope", "password": "short"})
    assert resp4.status_code == 400
    # user can log in with new password
    assert login("reset2@example.com", "newpassword1").status_code == 200


def test_booking_requires_auth():
    resp = client.post("/api/bookings", json={"occurrence_id": 1})
    assert resp.status_code == 401


def test_booking_lifecycle_and_waitlist():
    register("member1@example.com")
    resp = login("member1@example.com", "password123")
    hdrs = auth_headers_from(resp)

    # unknown occurrence
    assert client.post("/api/bookings", json={"occurrence_id": 9999}, headers=hdrs).status_code == 404
    # past occurrence
    assert client.post("/api/bookings", json={"occurrence_id": 3}, headers=hdrs).status_code == 400

    occ1 = 1  # max_size 3
    b1 = client.post("/api/bookings", json={"occurrence_id": occ1}, headers=hdrs)
    assert b1.status_code == 200, b1.text
    assert b1.json()["booking"]["status"] == "confirmed"

    # duplicate active booking -> 409
    dup = client.post("/api/bookings", json={"occurrence_id": occ1}, headers=hdrs)
    assert dup.status_code == 409

    # fill remaining two spots, then a fourth user is waitlisted
    for i in (2, 3):
        register(f"fill{i}@example.com")
        h = auth_headers_from(login(f"fill{i}@example.com", "password123"))
        r = client.post("/api/bookings", json={"occurrence_id": occ1}, headers=h)
        assert r.status_code == 200 and r.json()["booking"]["status"] == "confirmed"

    register("wait1@example.com")
    h4 = auth_headers_from(login("wait1@example.com", "password123"))
    r4 = client.post("/api/bookings", json={"occurrence_id": occ1}, headers=h4)
    assert r4.status_code == 200
    assert r4.json()["booking"]["status"] == "waitlisted"
    assert r4.json()["booking"]["waitlist_position"] == 1

    register("wait2@example.com")
    h5 = auth_headers_from(login("wait2@example.com", "password123"))
    r5 = client.post("/api/bookings", json={"occurrence_id": occ1}, headers=h5)
    assert r5.json()["booking"]["status"] == "waitlisted"
    assert r5.json()["booking"]["waitlist_position"] == 2

    # member1 cancels -> wait1 promoted to confirmed
    my = client.get("/api/bookings/me", headers=hdrs).json()["bookings"]
    my_confirmed = [b for b in my if b["status"] == "confirmed" and b["occurrence_id"] == occ1]
    booking_id = my_confirmed[0]["id"]
    cancel = client.post(f"/api/bookings/{booking_id}/cancel", json={"reason": ""}, headers=hdrs)
    assert cancel.status_code == 200, cancel.text
    assert cancel.json()["booking"]["status"] == "cancelled"

    me4 = client.get("/api/bookings/me", headers=h4).json()["bookings"]
    promoted = [b for b in me4 if b["occurrence_id"] == occ1][0]
    assert promoted["status"] == "confirmed", promoted

    # cancel is idempotent-guarded: second cancel -> 404
    cancel2 = client.post(f"/api/bookings/{booking_id}/cancel", json={}, headers=hdrs)
    assert cancel2.status_code == 404


def test_instructor_cancel_requires_role():
    register("member1@example.com")
    resp = login("member1@example.com", "password123")
    hdrs = auth_headers_from(resp)
    r = client.post("/api/instructor/classes/1/cancel", json={}, headers=hdrs)
    assert r.status_code == 403


def test_instructor_cancel_class():
    register("teacher@example.com")
    teacher = next(u for u in _db["users"] if u["email"] == "teacher@example.com")
    teacher["role"] = "instructor"
    hdrs = auth_headers_from(login("teacher@example.com", "password123"))

    register("member1@example.com")
    member = auth_headers_from(login("member1@example.com", "password123"))
    assert member, "member login should succeed"

    # class already started -> 400
    r = client.post("/api/instructor/classes/3/cancel", json={}, headers=hdrs)
    assert r.status_code == 400

    # schedule one future occurrence and book a member into it
    from tests.fake_db import now as fake_now
    db_store = _db
    occ_future_id = db_store.next_id("class_occurrences")
    sess = next(s for s in db_store["class_sessions"] if s["id"] == 1)
    starts = fake_now() + timedelta(days=1)
    db_store["class_occurrences"].append({
        "id": occ_future_id, "class_session_id": 1,
        "starts_at": starts, "ends_at": starts + timedelta(hours=1),
        "timezone": sess["timezone"], "max_size": 3, "status": "scheduled",
        "cancelled_by": None, "cancelled_at": None, "cancellation_reason": None,
        "created_at": fake_now(),
    })

    member = auth_headers_from(login("member1@example.com", "password123"))
    member_book = client.post("/api/bookings", json={"occurrence_id": occ_future_id}, headers=member)
    assert member_book.status_code == 200, member_book.text

    cancelled = client.post(f"/api/instructor/classes/{occ_future_id}/cancel", json={}, headers=hdrs)
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["notified"] == 1  # the member's booking was affected


def test_checkout_requires_auth_and_stripe():
    # not logged in
    r = client.post("/api/checkout", json={"plan": "drop-in"})
    assert r.status_code == 401
    # logged in, no stripe key configured
    register("pay@example.com")
    hdrs = auth_headers_from(login("pay@example.com", "password123"))
    r2 = client.post("/api/checkout", json={"plan": "drop-in"}, headers=hdrs)
    assert r2.status_code == 503
    r3 = client.post("/api/checkout", json={"plan": "bogus"}, headers=hdrs)
    assert r3.status_code == 503  # fails before plan lookup


def test_stripe_webhook_unconfigured():
    r = client.post("/api/stripe/webhook")
    assert r.status_code == 200
    assert r.json() == {"received": True, "verified": False}
