# Still Studio Yoga Website

Minimalist multi-page yoga website with a calming sage and beige theme, class information, blog content, contact page, and Stripe Checkout flow.

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Stripe setup

Create a `.env` file locally with:

```bash
STRIPE_SECRET_KEY=<your_stripe_secret_key>
STRIPE_WEBHOOK_SECRET=<your_stripe_webhook_secret>
STRIPE_CURRENCY=usd
```
