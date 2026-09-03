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
Added `secure=True` flag to enforce HTTPS-only transmission:
```python
response.set_cookie(
    "still_session",
    token,
    max_age=SESSION_DAYS * 24 * 60 * 60,
    httponly=True,
    secure=True,
    samesite="lax",
)
```

**Verification:**
- Session cookie will only be transmitted over HTTPS
- In development (HTTP), the cookie will not be set; ensure HTTPS in production

---

## Remaining High-Priority Issues

The following issues were identified but not yet fixed. They should be addressed before production deployment:

### Missing CSRF Protection
- **File:** `main.py`
- **Risk:** Cross-site request forgery attacks
- **Recommendation:** Add `CsrfMiddleware` from Starlette

### Missing Security Headers
- **File:** `main.py`
- **Risk:** XSS, clickjacking, MIME-type sniffing
- **Missing Headers:**
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `X-XSS-Protection: 1; mode=block`
  - `Strict-Transport-Security`
  - `Content-Security-Policy`

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
   - In development (HTTP), cookie will not be set (expected behavior)

---

## Deployment Checklist

- [ ] Set `DATABASE_URL` environment variable in production
- [ ] Configure SMTP settings for email delivery
- [ ] Enable HTTPS/TLS for all traffic
- [ ] Implement CSRF middleware
- [ ] Add security headers middleware
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

**Last Updated:** August 25, 2026
**Status:** 3 critical/high issues fixed; 5+ medium/low issues pending
