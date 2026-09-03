from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from db import get_conn
from email_service import queue_and_send

SESSION_DAYS = 14
RESET_MINUTES = 30

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AuthRequest(BaseModel):
    email: str
    password: str


class EmailRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


def now_utc():
    return datetime.now(timezone.utc)


def hash_password(password):
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 260000)
    return f"{salt.hex()}:{digest.hex()}"


def verify_password(password, stored):
    try:
        salt_hex, digest_hex = stored.split(":", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 260000)
        return hmac.compare_digest(digest.hex(), digest_hex)
    except ValueError:
        return False


def public_user(user):
    return {"id": user["id"], "email": user["email"], "role": user.get("role", "member")}


def session_user(request: Request):
    token = request.cookies.get("still_session")
    if not token:
        return None

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT users.id, users.email, users.role, sessions.expires_at
                FROM sessions
                JOIN users ON users.id = sessions.user_id
                WHERE sessions.token = %s
                """,
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            if row["expires_at"] <= now_utc():
                cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
                conn.commit()
                return None
            return row


def require_user(request: Request):
    user = session_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Please log in to reserve a class.")
    return user


def set_session(response: Response, user_id: int):
    token = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(days=SESSION_DAYS)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sessions (token, user_id, expires_at) VALUES (%s, %s, %s)",
                (token, user_id, expires_at),
            )
        conn.commit()
    response.set_cookie(
        "still_session",
        token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="lax",
    )


def clear_session(request: Request, response: Response):
    token = request.cookies.get("still_session")
    if token:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM sessions WHERE token = %s", (token,))
            conn.commit()
    response.delete_cookie("still_session")


@router.post("/register")
async def register(payload: AuthRequest, response: Response):
    email = payload.email.lower().strip()
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id, email, role",
                    (email, hash_password(payload.password)),
                )
                user = cur.fetchone()
            conn.commit()
    except Exception as exc:
        if "users_email_key" in str(exc):
            raise HTTPException(status_code=400, detail="An account with this email already exists.") from exc
        raise

    set_session(response, user["id"])
    return {"user": public_user(user)}


@router.post("/login")
async def login(payload: AuthRequest, response: Response):
    email = payload.email.lower().strip()
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, email, role, password_hash FROM users WHERE email = %s", (email,))
            user = cur.fetchone()

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    set_session(response, user["id"])
    return {"user": public_user(user)}


@router.post("/logout")
async def logout(request: Request, response: Response):
    clear_session(request, response)
    return {"ok": True}


@router.get("/me")
async def me(request: Request):
    user = session_user(request)
    if user is None:
        return {"user": None}
    return {"user": public_user(user)}


@router.post("/forgot-password")
async def forgot_password(payload: EmailRequest, request: Request):
    email = payload.email.lower().strip()
    token = secrets.token_urlsafe(32)
    expires_at = now_utc() + timedelta(minutes=RESET_MINUTES)

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            if user is not None:
                cur.execute(
                    "INSERT INTO password_reset_tokens (token, user_id, expires_at) VALUES (%s, %s, %s)",
                    (token, user["id"], expires_at),
                )
                reset_url = f"{str(request.base_url)}forgot-password?token={token}"
                queue_and_send(
                    cur,
                    email,
                    "Reset your password",
                    f"Use the link below to reset your password. It expires in {RESET_MINUTES} minutes.\n\n{reset_url}",
                    user_id=user["id"],
                )
        conn.commit()

    message = "If that email is registered, a password reset link has been sent."
    return {"message": message}


@router.post("/reset-password")
async def reset_password(payload: ResetPasswordRequest):
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT token, user_id, expires_at, used_at
                FROM password_reset_tokens
                WHERE token = %s
                """,
                (payload.token,),
            )
            reset = cur.fetchone()
            if reset is None or reset["used_at"] is not None or reset["expires_at"] <= now_utc():
                raise HTTPException(status_code=400, detail="Reset link is invalid or expired.")
            cur.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(payload.password), reset["user_id"]),
            )
            cur.execute("UPDATE password_reset_tokens SET used_at = NOW() WHERE token = %s", (payload.token,))
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (reset["user_id"],))
        conn.commit()

    return {"message": "Password updated. You can log in with your new password."}
