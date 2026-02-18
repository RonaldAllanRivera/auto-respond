# Environment Variables

This document defines the environment variable contract for local development and Render deployment.

## Local development (Docker Compose)

Copy `.env.example` to `.env` and set values.

Scope note:

- `/.env` (repo root) is for **backend + Docker Compose** variables.
- `/desktop/.env` is for **desktop app** variables.

Required for running the backend locally:

- `DJANGO_SECRET_KEY`

Recommended (required once AI answering is enabled):

- `OPENAI_API_KEY`

Recommended for local dev:

- `DJANGO_DEBUG=1`
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`

Required in production (Render):

- `DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-service>.onrender.com`
  - Comma-separated list of trusted origins for CSRF (required for POST forms over HTTPS).
  - Example: `https://meetlessons.onrender.com`

Recommended for device pairing:

- `DEVICE_TOKEN_SECRET`

## Static files

Static assets are served via WhiteNoise in the container. No additional environment variables are required.

Database variables (Docker Compose defaults are provided):

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Production (Render)

Recommended settings:

- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=<your-service>.onrender.com`

You should also configure database variables from Render Postgres.

## OpenAI

- `OPENAI_API_KEY`: required
- `OPENAI_MODEL`: default `gpt-4o-mini`
- `OPENAI_TIMEOUT_SECONDS`: default `15`

## SaaS variables

### Google OAuth

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`

Notes:

- See README.md for required redirect URI(s) and the Django Sites domain configuration for allauth.

### Stripe

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Notes:

- `STRIPE_SECRET_KEY` is required when testing billing locally.
- `STRIPE_WEBHOOK_SECRET` is required for webhook signature verification.
- For local development, this value usually comes from Stripe CLI forwarding output (`whsec_...`).

Local webhook forwarding (Docker Stripe CLI):

```bash
docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest listen --forward-to http://localhost:8000/billing/webhook/
```

Webhook endpoint used by Django:

- `http://localhost:8000/billing/webhook/`

Pricing notes:

- This project uses a **flat monthly subscription of $15.00 USD**.
- The Stripe **Price ID** for that plan is configured via the Django Admin Billing Plan CMS (stored in the database), not via environment variables.
- Coupon codes are also configured via Django Admin (`CouponCode`) and map to a Stripe Promotion Code ID or Coupon ID (Stripe may display shorter IDs depending on UI/version).
- Device policy when billing is configured: users without an active subscription cannot pair devices, and active devices are auto-revoked on `/devices/`.

Security notes:

- Never commit real Stripe secret keys or webhook secrets to git.
- Rotate secrets immediately if they are accidentally exposed.

## Device pairing

The desktop app uses **device pairing + server-issued device tokens** for desktop-app-to-backend requests.

- `DEVICE_TOKEN_SECRET`

## Desktop app environment (`desktop/.env`)

Copy `desktop/.env.example` to `desktop/.env` and set:

- `MEET_LESSONS_URL`
  - Local dev: `http://localhost:8000`
  - Production desktop build: your Render URL (e.g. `https://<service>.onrender.com`)

Notes:

- The desktop app no longer exposes a Backend URL input field in the UI.
- The desktop app reads `MEET_LESSONS_URL` from `desktop/.env`.
- No additional desktop environment variables are required for screenshot watcher/detection tuning; current tuning is code-level in `desktop/main.py`.
- On Linux, the desktop app includes a clipboard watcher fallback so capture still works when `Print Screen` is intercepted by the desktop environment.
- The desktop app periodically re-validates its device token (~30s) and will auto-unpair if the backend revokes the token or the subscription becomes inactive.
- Question detection is intentionally strict: WH-start questions + math expressions (including fractions), with URL/UI OCR noise filtered out.
