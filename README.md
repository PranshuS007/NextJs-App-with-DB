# Still Studio Yoga Website

Minimalist multi-page yoga website with a calming sage and beige theme, class information, blog content, contact page, and Stripe Checkout flow.

## Run locally

```bash
pip install -r requirements.txt
python scripts/migrate.py
python scripts/seed.py
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Configuration

Create a `.env` file locally with:

```bash
DATABASE_URL=postgresql://username:password@localhost:5432/still_studio
STRIPE_SECRET_KEY=<your_stripe_secret_key>
STRIPE_WEBHOOK_SECRET=<your_stripe_webhook_secret>
STRIPE_CURRENCY=usd
SMTP_HOST=<your_smtp_host>
SMTP_PORT=587
SMTP_USERNAME=<your_smtp_username>
SMTP_PASSWORD=<your_smtp_password>
SMTP_USE_TLS=true
EMAIL_FROM=<your_sender_email>
COOKIE_SECURE=<optional: true/false, defaults to Secure only over HTTPS>
```

**Important:** `DATABASE_URL` is required and must be set via environment variable or `.env` file. Do not hardcode credentials in the application.

**Session cookie:** the auth cookie is marked `Secure` automatically when the site is served over HTTPS and left unmarked over plain HTTP (local dev, LAN). If TLS terminates at a reverse proxy, set `COOKIE_SECURE=true` so the app still marks it Secure.

## Security

This application includes security fixes for critical vulnerabilities. See [SECURITY_FIXES.md](./SECURITY_FIXES.md) for details on:

- Database credential handling
- Password reset token protection
- Session cookie security
- Remaining high-priority security recommendations

Before deploying to production, review the security checklist in [SECURITY_FIXES.md](./SECURITY_FIXES.md).
