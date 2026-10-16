"""Additional edge-case checks surfaced while investigating the codebase."""
import os
from datetime import timedelta

import pytest

from conftest import client, fake_db as _db
from tests.fake_db import now

from fastapi.testclient import TestClient

import main


def register(email, password="password123"):
    return client.post("/api/auth/register", json={"email": email, "password": password})


def login(email, password="password123"):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def cookies(resp):
    for part in resp.headers.get("set-cookie", "").split(";"):
        part = part.strip()
        if part.startswith("still_session="):
            return {"Cookie": part}
    return {}


def test_expired_session_is_cleaned_up():
    register("expired@example.com")
    token = _db["sessions"][-1]["token"]
    session = _db["sessions"][-1]
    session["expires_at"] = now() - timedelta(minutes=1)
    before = len(_db["sessions"])
    me = client.get("/api/auth/me", headers={"Cookie": f"still_session={token}"})
    assert me.status_code == 200
    assert me.json()["user"] is None
    assert len(_db["sessions"]) == before - 1


def test_book_cancelled_occurrence_rejected():
    register("c@example.com")
    hdrs = cookies(login("c@example.com"))
    occ = _db["class_occurrences"][1]  # a scheduled one
    occ["status"] = "cancelled"
    r = client.post("/api/bookings", json={"occurrence_id": occ["id"]}, headers=hdrs)
    assert r.status_code == 400
    assert "cancelled" in r.json()["detail"].lower()
    occ["status"] = "scheduled"


def test_cancel_waitlisted_booking_gives_up_spot_to_nobody():
    # occ 4: max_size 3, room for 3 confirmed + waitlist
    occ_id = _db.next_id("class_occurrences")
    _db["class_occurrences"].append({
        "id": occ_id, "class_session_id": 1,
        "starts_at": now() + timedelta(days=2),
        "ends_at": now() + timedelta(days=2, hours=1),
        "timezone": "America/Los_Angeles", "max_size": 1, "status": "scheduled",
        "cancelled_by": None, "cancelled_at": None, "cancellation_reason": None,
        "created_at": now(),
    })
    register("w1@example.com"); h1 = cookies(login("w1@example.com"))
    register("w2@example.com"); h2 = cookies(login("w2@example.com"))
    r1 = client.post("/api/bookings", json={"occurrence_id": occ_id}, headers=h1)
    assert r1.json()["booking"]["status"] == "confirmed"
    r2 = client.post("/api/bookings", json={"occurrence_id": occ_id}, headers=h2)
    assert r2.json()["booking"]["status"] == "waitlisted"

    my = client.get("/api/bookings/me", headers=h2).json()["bookings"]
    wl = [b for b in my if b["occurrence_id"] == occ_id][0]
    cancel = client.post(f"/api/bookings/{wl['id']}/cancel", json={}, headers=h2)
    assert cancel.status_code == 200
    my2 = client.get("/api/bookings/me", headers=h2).json()["bookings"]
    assert [b for b in my2 if b["occurrence_id"] == occ_id][0]["status"] == "cancelled"
    # no promotion happened; the confirmed booking is untouched
    my1 = client.get("/api/bookings/me", headers=h1).json()["bookings"]
    assert [b for b in my1 if b["occurrence_id"] == occ_id][0]["status"] == "confirmed"


def test_my_bookings_lists_every_state():
    register("states@example.com")
    hdrs = cookies(login("states@example.com"))
    assert client.post("/api/bookings", json={"occurrence_id": 1}, headers=hdrs).status_code == 200
    assert client.post("/api/bookings", json={"occurrence_id": 2}, headers=hdrs).status_code == 200
    rows = client.get("/api/bookings/me", headers=hdrs).json()["bookings"]
    statuses = {r["status"] for r in rows}
    assert "confirmed" in statuses
    assert len(rows) == 2


def test_schedule_counts_reflect_bookings():
    register("counts@example.com")
    hdrs = cookies(login("counts@example.com"))
    assert client.post("/api/bookings", json={"occurrence_id": 2}, headers=hdrs).status_code == 200
    data = client.get("/api/classes").json()["schedule"]
    occ2 = next(item for item in data if item["occurrence_id"] == 2)
    assert occ2["spots_remaining"] == occ2["max_size"] - 1
    assert occ2["waitlist_count"] == 0


def test_pricing_money_formatting():
    r = client.get("/api/pricing")
    plans = {p["slug"]: p["price"] for p in r.json()["plans"]}
    assert plans == {"drop-in": "$22", "five-pack": "$95", "ten-pack": "$170"}


def test_checkout_with_stripe_configured():
    import api.stripe as stripe_mod

    register("pay2@example.com")
    hdrs = cookies(login("pay2@example.com"))

    class FakeStripe:
        api_key = ""

        class checkout:
            class Session:
                @classmethod
                def create(cls, **kwargs):
                    session = cls.__new__(cls)
                    session.url = "https://checkout.stripe.com/test"
                    return session

    saved = stripe_mod.stripe_sdk
    stripe_mod.settings.stripe_secret_key = "sk_test_123"
    stripe_mod.stripe_sdk = FakeStripe()
    try:
        r = client.post("/api/checkout", json={"plan": "drop-in"}, headers=hdrs)
        assert r.status_code == 200, r.text
        assert r.json()["url"] == "https://checkout.stripe.com/test"
        r_bad = client.post("/api/checkout", json={"plan": "bogus"}, headers=hdrs)
        assert r_bad.status_code == 400  # unknown plan now reaches the DB check
        fresh = TestClient(main.app)
        r_bad2 = fresh.post("/api/checkout", json={"plan": "drop-in"})
        assert r_bad2.status_code == 401
    finally:
        stripe_mod.stripe_sdk = saved
        stripe_mod.settings.stripe_secret_key = ""


# --------------------------------------------------------------------------
# Regression tests for the bug fixes
# --------------------------------------------------------------------------

def test_session_cookie_not_secure_over_http():
    register("relaxed@example.com")
    r = client.post("/api/auth/login", json={"email": "relaxed@example.com", "password": "password123"})
    set_cookie = r.headers.get("set-cookie", "")
    assert "still_session=" in set_cookie
    assert "Secure" not in set_cookie


def test_session_cookie_secure_over_https():
    register("securecookie@example.com")
    https = TestClient(main.app, base_url="https://testserver")
    https.post("/api/auth/register", json={"email": "securecookie@example.com", "password": "password123"})
    r = https.post("/api/auth/login", json={"email": "securecookie@example.com", "password": "password123"})
    assert "Secure" in r.headers.get("set-cookie", "")


def test_security_headers_present():
    r = client.get("/")
    headers = r.headers
    assert headers.get("x-content-type-options") == "nosniff"
    assert headers.get("x-frame-options") == "DENY"
    assert headers.get("referrer-policy") == "strict-origin-when-cross-origin"
    assert "strict-transport-security" not in headers  # HSTS only over HTTPS
    https = TestClient(main.app, base_url="https://testserver")
    r2 = https.get("/")
    assert r2.headers.get("strict-transport-security", "").startswith("max-age=31536000")


def test_static_cache_is_bounded():
    r = client.get("/static/css/style.css")
    assert r.status_code == 200
    cache = r.headers.get("cache-control", "")
    assert "max-age=3600" in cache
    assert "immutable" not in cache
