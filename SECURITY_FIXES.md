# Security Fixes

## Overview
This document tracks critical security vulnerabilities that have been identified and fixed in the Still Studio Yoga application.

---

## Fixed Issues

### 1. Hardcoded Database Credentials (CRITICAL)

**Status:** ✅ FIXED

**File:** `config/settings.py`

**Issue:**
The PostgreSQL connection string was hardcoded with default credentials:
```python
database_url: str = "postgresql://postgres:postgres@localhost:5432/still_studio"
```

**Risk:**
- Credentials exposed in source code
- If code is committed to version control or deployed, attackers gain direct database access
- Default credentials are easily guessable

**Fix Applied:**
Removed the hardcoded default value. `database_url` is now required and must be provided via environment variable or `.env` file:
```python
database_url: str
```

**How to Use:**
Create a `.env` file in the project root (already documented in README.md):
```
DATABASE_URL=postgresql://username:password@localhost:5432/still_studio
```

**Verification:**
- Application will fail to start if `DATABASE_URL` is not set
- No credentials are hardcoded in the codebase

---

### 2. Password Reset Token Exposed in API Response (CRITICAL)

**Status:** ✅ FIXED

**File:** `api/auth_pg.py`

**Issue:**
The `/api/auth/forgot-password` endpoint returned the password reset token and URL directly in the JSON response:
```python
return {"message": message, "reset_url": reset_url}
```

**Risk:**
- Token visible in browser developer tools
- Token logged in server access logs
- Token exposed in browser history
- Token visible in referrer headers
- Anyone with access to logs or network traffic can reset any user's password

**Fix Applied:**
1. Removed `reset_url` from the API response
2. Added email delivery of the reset link via the existing `queue_and_send()` function
3. Updated response message to indicate the link was sent via email

**Before:**
```python
reset_url = f"{str(request.base_url)}forgot-password?token={token}"
return {"message": message, "reset_url": reset_url}
```

**After:**
```python
reset_url = f"{str(request.base_url)}forgot-password?token={token}"
queue_and_send(
    cur,
    email,
    "Reset your password",
    f"Use the link below to reset your password. It expires in {RESET_MINUTES} minutes.\n\n{reset_url}",
    user_id=user["id"],
)
return {"message": message}
```

**Verification:**
- API response no longer contains `reset_url`
- Password reset link is sent via email only
- Frontend `auth.js` gracefully handles the missing `reset_url` (falls back to plain message text)

---

### 3. Missing Secure Flag on Session Cookie (HIGH)

**Status:** ✅ FIXED

**File:** `api/auth_pg.py`

**Issue:**
The session cookie was missing the `secure=True` flag:
```python
response.set_cookie(
    "still_session",
    token,
    max_age=SESSION_DAYS * 24 * 60 * 60,
    httponly=True,
    samesite="lax",
)
```

**Risk:**
- Session cookie transmitted over HTTP (unencrypted)
- Man-in-the-middle (MITM) attacks can intercept session tokens
- Attacker can hijack user sessions

**Fix Applied:**
Added a `secure` flag that is applied automatically when the site is served over HTTPS, e.g.:
```python
secure = settings.cookie_secure if settings.cookie_secure is not None else request.url.scheme == "https"
response.set_cookie(..., secure=secure, ...)
```
`COOKIE_SECURE=true` can be set explicitly when TLS terminates at a proxy so the app only ever sees plain HTTP internally. Over plain HTTP (local development, LAN deployments) the cookie is NOT marked `Secure`, otherwise browsers silently discard it and login/register appear broken.

**Verification:**
- Over HTTPS the cookie is set with the `Secure` flag
- Over HTTP the cookie is set without the flag so the documented `http://127.0.0.1:8000` dev flow works

---

## Fixed During Follow-up (Oct 2026)

### Frontend forgot-password dead path
`static/js/routes/auth.js` still referenced `data.reset_url`, which the API no longer returns, and injected it into `innerHTML` if it ever did. The handler now renders only the server message via `textContent`.

### One-year immutable static cache
`main.py` sent `Cache-Control: public, max-age=31536000, immutable` for all `/static/` assets, but the site does not fingerprint asset filenames, so CSS/JS fixes would be invisible to visitors (and `--reload` developers) for up to a year. Bounded to `public, max-age=3600`.

### Home page class order
`static/js/routes/home.js` reversed the "This week at Still" list, showing upcoming classes in reverse chronological order. Restored the chronological order the original design used.

---

## Remaining High-Priority Issues

The following issues were identified but not yet fixed. They should be addressed before production deployment:

### Missing CSRF Protection
- **File:** `main.py`
- **Risk:** Cross-site request forgery attacks
- **Recommendation:** Add `CsrfMiddleware` from Starlette

### Remaining Security Headers
- **File:** `main.py`
- **Status:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` and HTTPS-only `Strict-Transport-Security` are now set by `add_security_headers`.
- **Missing:**
  - `Content-Security-Policy` (requires an audit of inline styles/scripts, external fonts, the OpenStreetMap iframe, and Unsplash images before adding)
  - `X-XSS-Protection` (deprecated; browsers ignore it)

### Missing Rate Limiting
- **File:** `api/auth_pg.py`
- **Risk:** Brute force attacks on login and password reset
- **Recommendation:** Implement rate limiting on `/login`, `/register`, `/forgot-password`

### Missing Account Lockout
- **File:** `api/auth_pg.py`
- **Risk:** Brute force attacks
- **Recommendation:** Lock account after N failed login attempts

### Weak Password Requirements
- **File:** `api/auth_pg.py`
- **Current:** Minimum 8 characters only
- **Recommendation:** Require uppercase, lowercase, numbers, and special characters

---

## Testing

To verify the fixes:

1. **Database URL requirement:**
   ```bash
   # Should fail without DATABASE_URL set
   python -c "from config.settings import settings"
   ```

2. **Password reset email delivery:**
   - Submit forgot-password form
   - Verify API response does NOT contain `reset_url`
   - Verify email is queued/sent with reset link

3. **Session cookie security:**
   - In production (HTTPS), verify cookie is set with `Secure` flag
   - In development (HTTP), cookie is set without the flag so the documented `http://127.0.0.1:8000` flow works

4. **Automated regression suite** (no database required; runs against an in-memory fake):
   ```bash
   pip install pytest
   python -m pytest tests/ -q
   ```
   Covers registration/login/logout, password reset, booking/waitlist promotion, instructor class cancellation, checkout, Stripe webhook, security headers, and cookie flags.

---

## Deployment Checklist

- [x] Set `DATABASE_URL` environment variable in production
- [x] Configure SMTP settings for email delivery
- [x] Enable HTTPS/TLS for all traffic
- [x] Add security headers middleware
- [ ] Add `Content-Security-Policy` after auditing inline styles/scripts, external fonts, the OpenStreetMap iframe, and Unsplash images
- [ ] Implement CSRF protection
- [ ] Implement rate limiting on auth endpoints
- [ ] Implement account lockout mechanism
- [ ] Audit and pin dependency versions
- [ ] Set up security event logging
- [ ] Disable API documentation endpoints in production

---

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [FastAPI Security](https://fastapi.tiangolo.com/tutorial/security/)
- [Starlette Middleware](https://www.starlette.io/middleware/)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)

---

**Last Updated:** October 16, 2026
**Status:** 3 critical/high issues fixed + follow-up fixes; CSRF, rate limiting, account lockout, and CSP still pending
