# Meet Lessons

**AI-assisted Q&A from screenshots using Django + Python desktop OCR.**

Meet Lessons is a full-stack SaaS-style project where a Python desktop client captures screenshots, extracts text locally with Tesseract, detects likely questions, and sends them to a Django backend for AI answering. Answers stream live in the web dashboard via SSE.

---

## Table of contents

- [Project highlights](#project-highlights)
- [Architecture at a glance](#architecture-at-a-glance)
- [Core capabilities](#core-capabilities)
- [Current implementation status](#current-implementation-status)
- [Tech stack](#tech-stack)
- [API contract (desktop ↔ backend)](#api-contract-desktop--backend)
- [Quickstart (local)](#quickstart-local)
- [Stripe subscriptions (setup guide)](#stripe-subscriptions-setup-guide)
- [Deploy to Render (production)](#deploy-to-render-production)
- [Validation summary (verified)](#validation-summary-verified)
- [Troubleshooting](#troubleshooting)
- [What’s next](#whats-next)

---

## Project highlights

- **End-to-end product thinking**: desktop client + backend APIs + dashboard UX + admin workflows.
- **Security-conscious architecture**: no shared client secrets; device pairing with server-issued tokens.
- **Cost-aware ML integration**: local OCR (Tesseract) + targeted OpenAI calls only for detected questions.
- **Production-minded reliability**: dedupe, paywall enforcement, SSE streaming, Linux capture fallbacks.
- **Multi-tenant SaaS patterns**: per-user data isolation across lessons, transcripts, devices, and Q&A.

---

## Architecture at a glance

### Monorepo layout

- `backend/` — Django app (accounts, devices, lessons, billing, OpenAI integration)
- `desktop/` — Python tkinter app (capture, OCR, question detection, pairing)

### Data flow

1. User captures text via desktop app (`Print Screen` or clipboard watcher fallback).
2. Desktop app runs local OCR (Tesseract).
3. Desktop app filters OCR noise (URLs/UI junk), detects questions, and submits:
   - `POST /api/captions/`
   - `POST /api/questions/`
4. Backend stores transcript, builds prompt with user settings, calls OpenAI.
5. Dashboard streams answer tokens via `GET /api/questions/<id>/stream/`.

---

## Core capabilities

- Google OAuth login (django-allauth)
- Subscriber settings (grade level, max sentences)
- Device pairing (`POST /api/devices/pair/`) with revocation
- Screenshot OCR ingestion + server-side dedupe
- Question detection:
  - WH-start questions (`what`, `where`, `when`, `how`, etc.)
  - math expressions (including fractions like `1/4 x 1/5`)
  - URL/UI noise filtering (e.g., `docs.google.com/.../edit?` is ignored)
- AI answers stored and streamed in dashboard (SSE)
- Desktop paywall behavior: capture blocked while unpaired
- Stripe monthly subscriptions (Checkout + webhooks + customer portal)
- Coupon codes (admin-managed, backed by Stripe Promotion Codes or Coupon IDs)
- Entitlement checks for AI answering when billing is enabled
- Devices auto-revoke on `/devices/` when subscription is inactive
- Desktop auto-unpairs if the backend revokes access (including periodic ~30s token re-validation)

---

## Current implementation status

| Phase | Status |
|---|---|
| 0 — Repo hygiene & foundations | Completed |
| 1 — Multi-tenant accounts + dashboard shell | Completed |
| 2 — Device pairing + security | Completed |
| 3 — Screenshot capture + OCR + question detection | Completed |
| 4 — AI answering (streaming) | Completed |
| 5 — Stripe subscriptions | Completed |
| 6 — Coupons (admin CMS) | Completed |
| 7 — Render production hardening | Completed |
| 8 — Dashboard realtime UX | Planned |
| 9 — Frontend migration to Next.js | Planned |
| 10 — Windows desktop installer | Completed |

See `PLAN.md` for detailed phased deliverables.

---

## Tech stack

### Backend
- Django
- PostgreSQL
- django-allauth (Google OAuth)
- WhiteNoise (static files)
- OpenAI API
- Stripe API

### Desktop
- Python + tkinter
- Pillow (`ImageGrab`)
- pytesseract + Tesseract OCR
- pynput (global hotkey)

### Infra / DevEx
- Docker Compose
- Render (target deployment)

---

## API contract (desktop ↔ backend)

- `POST /api/devices/pair/` — exchange pairing code for device token
- `POST /api/captions/` — ingest OCR transcript chunks
- `POST /api/questions/` — submit detected question + context, return AI answer
- `GET /api/questions/<id>/stream/` — stream answer tokens via SSE (dashboard)

---

## Quickstart (local)

### 1) Prerequisites

- Docker + Docker Compose
- Python 3.10+
- Tesseract OCR

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

### 2) Configure environment

Copy `.env.example` → `.env` and set:

- `DJANGO_SECRET_KEY`
- `DEVICE_TOKEN_SECRET`
- `OPENAI_API_KEY`
- `STRIPE_SECRET_KEY` (required when testing billing)

Copy `desktop/.env.example` → `desktop/.env`:

- `MEET_LESSONS_URL=http://localhost:8000`

### 3) Start backend

```bash
docker compose up --build
docker compose run --rm web python manage.py createsuperuser
```

Open:

- Dashboard: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`

### 4) Start desktop app

```bash
cd desktop
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

### 5) Pair device and capture

1. Generate pairing code in dashboard (`/devices/`)
2. Pair in desktop app
3. Capture text from Google Meet or any readable screen
4. Open lesson detail in dashboard and confirm streamed answers

---

## Stripe subscriptions (setup guide)

This project uses **Stripe Checkout (subscription mode)** for recurring payments, a **Stripe webhook** to sync subscription status, and the **Stripe customer portal** for managing/canceling.

Current billing offer:

- **Flat rate: $15.00/month** (single monthly plan)

### Recommended workflow (best practice)

1. Use **Stripe Test mode** for development and end-to-end verification.
2. Switch to **Live mode** only after:
   - webhooks are verified in production
   - you’ve tested cancel/payment-failed flows
   - your production domain + HTTPS are configured

### Required env vars

In root `.env` (backend):

- `STRIPE_SECRET_KEY=sk_test_...`
- `STRIPE_WEBHOOK_SECRET=whsec_...`

### Create a Product + recurring Price

In Stripe Dashboard (Test mode):

1. Create a **Product**
2. Create a **Recurring Price** (monthly, flat rate **$15.00 USD**)
3. Copy the **Price ID** (`price_...`)
4. In Django Admin, set it on the `BillingPlan` record:
   - Admin → Billing → Billing plans → id=1 → `stripe_monthly_price_id=price_...`

### Local webhook forwarding (Stripe CLI)

The local webhook endpoint in this app is:

- `http://localhost:8000/billing/webhook/`

Docker Compose now includes a `stripe-cli` service that forwards webhooks to Django automatically.

One-time auth setup:

```bash
docker compose run --rm stripe-cli login
```

Then start the stack normally (includes webhook forwarding):

```bash
docker compose up --build
```

View Stripe listener logs:

```bash
docker compose logs -f stripe-cli
```

Use Stripe CLI to forward webhooks to your local Docker backend:

```bash
stripe login
stripe listen --forward-to http://localhost:8000/billing/webhook/
```

If Stripe CLI is not installed on your host machine, use Docker instead:

```bash
docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest login

docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest listen --forward-to http://localhost:8000/billing/webhook/
```

The CLI will print a signing secret like `whsec_...`.
Copy that into your local `.env` as `STRIPE_WEBHOOK_SECRET`.

### Webhook tutorial (end-to-end)

This app's webhook handler is:

- `POST /billing/webhook/`

It verifies the Stripe signature using `STRIPE_WEBHOOK_SECRET` and de-dupes events in the database.

#### Local development (recommended)

1. Start backend:

```bash
docker compose up --build
```

This starts:

- `db`
- `web`
- `stripe-cli` (automatic local webhook forwarding to `/billing/webhook/`)

2. (Optional) If not using Compose `stripe-cli` service, start Stripe CLI forwarding manually:

```bash
stripe login
stripe listen --forward-to http://localhost:8000/billing/webhook/
```

3. Copy the signing secret printed by Stripe CLI into `.env`:

```bash
STRIPE_WEBHOOK_SECRET=whsec_...
```

4. Restart backend so the new env var is loaded:

```bash
docker compose up --build
```

#### Send test events (Stripe CLI)

In another terminal, you can emit Stripe test events:

```bash
stripe trigger checkout.session.completed
stripe trigger customer.subscription.updated
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
```

Then inspect:

- Docker logs: `docker compose logs --tail=200 web`
- Django Admin tables:
  - Billing → Stripe events
  - Billing → Stripe subscriptions

#### Stripe Dashboard webhook vs Stripe CLI

- Stripe Dashboard webhooks **cannot** call `localhost`.
- For local development, use **Stripe CLI forwarding**.
- For staging/production, you **must manually add** a Dashboard webhook endpoint with a real HTTPS URL:
  - `https://your-domain.com/billing/webhook/`
- Local-only rule:
  - If you are using `stripe listen --forward-to ...`, you do **not** need to add a Dashboard endpoint for localhost.

#### Production webhook setup

Stripe Dashboard → Developers → Webhooks:

1. Add endpoint URL: `https://your-domain.com/billing/webhook/`
2. Subscribe to the events listed below
3. Copy the endpoint signing secret (`whsec_...`) into production env as `STRIPE_WEBHOOK_SECRET`
4. Use a separate endpoint for Test mode and Live mode (best practice)
5. Keep Stripe webhook retries enabled (default) and monitor failed deliveries

#### Common failure modes

- If `web` container crashes with `ModuleNotFoundError: stripe`:
  - rebuild: `docker compose up --build`
- If you see signature verification errors:
  - confirm you copied the correct `whsec_...` for the environment (CLI vs Dashboard, Test vs Live)
- If subscription status never updates:
  - confirm Stripe is actually sending events (CLI shows deliveries)
  - confirm the `BillingPlan.stripe_monthly_price_id` is set to your `price_...`

### Stripe webhook events to enable

Configure your webhook endpoint to send at least:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid`
- `invoice.payment_failed`

### What you need to do next (Stripe + local verification)

1. **Create Stripe Product + Monthly Price** (Test mode), then save `price_...` to Django Admin BillingPlan.
2. **Set local env vars** in root `.env`:
   - `STRIPE_SECRET_KEY=sk_test_...`
   - `STRIPE_WEBHOOK_SECRET=whsec_...` (from Stripe CLI output)
3. **Run local webhook forwarding**:

```bash
stripe listen --forward-to http://localhost:8000/billing/webhook/
```

4. **Verify local subscription flow**:
   - open `/billing/subscribe/`
   - complete Checkout in test mode
   - confirm `StripeEvent` + `StripeSubscription` updated in Django Admin
   - confirm entitlement checks on `/api/questions/`
   - visit `/devices/` while unsubscribed and confirm active devices auto-revoke
5. **Before production cutover**:
   - add Dashboard webhook endpoint: `https://your-domain.com/billing/webhook/`
   - enable minimum events:
     - `checkout.session.completed`
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `invoice.payment_failed`
   - set production `STRIPE_WEBHOOK_SECRET` from Dashboard endpoint secret (not CLI secret)
   - repeat one full subscription test in production/Test endpoint before enabling Live billing

### Customer portal

Stripe Dashboard → Settings → Billing → Customer portal:

- Enable portal
- Enable subscription cancellation and payment method updates (recommended)

### Coupon codes

Coupon codes are managed in Django Admin (`CouponCode`) and applied to Stripe Checkout.

This app supports storing either:

- a Stripe **Promotion Code ID** (commonly `promo_...`) or
- a Stripe **Coupon ID** (commonly `coupon_...`)

Depending on Stripe UI/version, you may also see shorter IDs. If you paste one of those, the backend will validate it against Stripe when `STRIPE_SECRET_KEY` is configured.

#### Option A (recommended): Create a Promotion Code in Stripe (tutorial)

Use this if you want a user-facing code (like `SAVE100`) with Stripe-managed rules.

1. Stripe Dashboard (Test mode) → **Product catalog → Coupons**.
2. Open your coupon (example: `SAVE100`).
3. In the coupon page, scroll to **Promotion codes**.
4. Click the **+** button to create a Promotion Code.
5. Set the **Code** to what the user should type at checkout (example: `SAVE100`).
6. Save, then copy the **Promotion Code ID**.
7. In Django Admin → Billing → Coupon codes:
   - `code`: the user-facing code (example: `SAVE100`)
   - `stripe_promotion_code_id`: paste the Promotion Code ID

Note: if you do not create a Promotion Code, the coupon will show “No promotion codes” and you’ll only have the Coupon ID.

### Device access policy tied to subscription

When billing is configured:

- Users without an active subscription cannot generate or use pairing codes.
- Visiting `/devices/` auto-revokes active paired devices when subscription is inactive/ended.
- Reactivating subscription requires generating a new pairing code and re-pairing desktop device(s).

Desktop behavior:

- The desktop app periodically re-validates its device token (~30s) and will auto-unpair if the backend revokes the token or the subscription becomes inactive.

### Subscription UX

Best-practice user flow:

1. User signs up / logs in
2. User visits `/billing/subscribe/`
3. Checkout creates subscription
4. Webhook syncs subscription state
5. AI answering endpoints enforce entitlement when billing is configured

---

## Deploy to Render (production)

This project is designed to deploy on [Render](https://render.com) as a **Web Service** (Docker) + **PostgreSQL** managed database.

### Prerequisites

- GitHub repo pushed to `main`
- Render account (free tier works for testing)
- Stripe account (Test mode keys)
- Google OAuth credentials (for production domain)
- OpenAI API key

---

### Step 1 — Create a PostgreSQL database on Render

1. Render Dashboard → **New** → **PostgreSQL**
2. Name it `meet-lessons-db`
3. Choose the free plan
4. Click **Create Database**
5. Once created, copy the **Internal Database URL** (used in Step 3)

---

### Step 2 — Create a Web Service on Render

1. Render Dashboard → **New** → **Web Service**
2. Connect your GitHub repo (`auto-respond`)
3. Settings:
   - **Branch:** `main`
   - **Runtime:** `Docker`
   - **Dockerfile path:** `./backend/Dockerfile`
   - **Docker context:** `./backend`
   - **Region:** choose closest to your users
4. Click **Create Web Service** (don't deploy yet — set env vars first)

---

### Step 3 — Set environment variables on Render

In your Web Service → **Environment** tab, add all of the following:

| Variable | Value |
|---|---|
| `DJANGO_SECRET_KEY` | Generate a strong random key (50+ chars) |
| `DJANGO_DEBUG` | `0` |
| `DJANGO_ALLOWED_HOSTS` | `your-app.onrender.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | `https://your-app.onrender.com` |
| `DATABASE_URL` | Paste the **Internal Database URL** from Step 1 |
| `DEVICE_TOKEN_SECRET` | Generate a strong random key |
| `OPENAI_API_KEY` | `sk-...` |
| `OPENAI_MODEL` | `gpt-4o-mini` |
| `OPENAI_TIMEOUT_SECONDS` | `15` |
| `GOOGLE_CLIENT_ID` | From Google Cloud Console |
| `GOOGLE_CLIENT_SECRET` | From Google Cloud Console |
| `STRIPE_SECRET_KEY` | `sk_test_...` (Test mode) |
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (from Render webhook endpoint — see Step 5) |
| `DEFAULT_GRADE_LEVEL` | `3` |
| `DEFAULT_MAX_SENTENCES` | `2` |
| `DESKTOP_DOWNLOAD_URL` | `https://github.com/RonaldAllanRivera/auto-respond/releases/download/v1.0.6/MeetLessonsInstaller.exe` |

> **Generate a secret key (Linux/macOS):**
> ```bash
> python3 -c "import secrets; print(secrets.token_urlsafe(50))"
> ```

Run this again for `DEVICE_TOKEN_SECRET` — it's the same command, just generates a fresh independent key:

Run it **twice total** — one output per secret. Never reuse the same value for both. They're independent signing keys used for different purposes:

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Django session/cookie/CSRF signing |
| `DEVICE_TOKEN_SECRET` | Desktop device token signing (HMAC) |
---

### Step 4 — Configure Google OAuth for production

1. [Google Cloud Console](https://console.cloud.google.com/) → your OAuth app → **Credentials**
2. Under **Authorized redirect URIs**, add:
   ```
   https://your-app.onrender.com/accounts/google/login/callback/
   ```
3. Save
4. In Django Admin (after first deploy): **Sites** → change `example.com` to `your-app.onrender.com`
5. **Social Applications** → update the Google app's `Client ID` and `Secret Key` to match production credentials

---

### Step 5 — Configure Stripe webhook for production

1. Stripe Dashboard → **Developers** → **Webhooks** → **Add endpoint**
2. Endpoint URL:
   ```
   https://your-app.onrender.com/billing/webhook/
   ```
3. Subscribe to events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.paid`
   - `invoice.payment_failed`
4. Copy the **Signing secret** (`whsec_...`) → set as `STRIPE_WEBHOOK_SECRET` in Render env

---

### Step 6 — Deploy

1. Render → your Web Service → **Manual Deploy** → **Deploy latest commit**
2. Watch the build logs — the container runs:
   - `python manage.py migrate --noinput`
   - `python manage.py collectstatic --noinput`
   - Gunicorn starts on port 8000
3. Once green, visit `https://your-app.onrender.com/`

---

### Step 7 — Post-deploy setup

1. Create a superuser via Render **Shell** tab:
   ```bash
   python manage.py createsuperuser
   ```
2. Django Admin → **Sites** → set domain to `your-app.onrender.com`
3. Django Admin → **Social Applications** → update Google OAuth credentials
4. Django Admin → **Billing → Billing plans** → set `stripe_monthly_price_id` to your `price_...`
5. Django Admin → **Stripe Customer Portal** → enable in Stripe Dashboard (Settings → Billing → Customer portal)

---

### Step 8 — Smoke test

- [ ] Visit `https://your-app.onrender.com/` — redirects to login
- [ ] Google login works
- [ ] `/devices/` shows **Download for Windows** button linking to the GitHub Release
- [ ] Pair a device using the desktop app (`MeetLessonsInstaller.exe`)
- [ ] Subscribe via `/billing/subscribe/` (Stripe test card `4242 4242 4242 4242`)
- [ ] Capture a question → answer streams in dashboard
- [ ] Cancel subscription → device auto-revokes on `/devices/`

---

### Updating the desktop download URL (future releases)

When you publish a new installer version:
1. Push a new tag: `git tag v1.x.x && git push origin v1.x.x`
2. GitHub Actions builds and publishes `MeetLessonsInstaller.exe` automatically
3. Update `DESKTOP_DOWNLOAD_URL` on Render to the new release URL
4. Redeploy (or Render auto-deploys on push)

---

## Validation summary (verified)

- Desktop capture pipeline is working end-to-end
- AI answers are visible in dashboard and persisted in Django Admin
- Device pairing, dashboard, admin pages, and auth flows are working
- Stripe Checkout + webhook sync verified in local test mode

Detailed test checklist: `TEST.md`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Pairing network errors | Confirm backend is running and `MEET_LESSONS_URL` is correct in `desktop/.env` |
| OCR returns empty text | Confirm `tesseract --version` and capture readable text |
| Print Screen not detected on Linux | Use clipboard watcher flow (`Print Screen` → select → `Ctrl+C`) |
| No AI answer | Confirm `OPENAI_API_KEY` in `.env`, then restart backend |

### Linux dock/icons keep moving (CPU wakeups)

The clipboard watcher polls to support reliable capture on Linux desktops where hotkeys are intercepted. If UI wakeups still feel high, tune:

- `MeetLessonsApp._CLIPBOARD_POLL_MS_MIN`
- `MeetLessonsApp._CLIPBOARD_POLL_MS_MAX`

File: `desktop/main.py`

---

## What’s next

- Phase 8: Dashboard realtime UX (latest Q&A panel, SSE/polling on home)
- Phase 9: Frontend migration to Next.js (post-core)

See `PLAN.md` and `CHANGELOG.md` for ongoing milestones.
