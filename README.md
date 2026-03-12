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

### Authentication & Billing
- Google OAuth login (django-allauth)
- Stripe monthly subscriptions (Checkout + webhooks + customer portal)
- Coupon codes (admin-managed, backed by Stripe Promotion Codes or Coupon IDs)
- Entitlement checks for AI answering when billing is enabled

### Desktop App
- **Mode Selection**: Switch between Recitation (homework help) and Lesson (study documents) modes
- **Lesson Dropdown**: Select from uploaded lessons in Lesson mode
- **Session Context**: Maintains last 10 captions for conversational flow in Recitation mode
- **Session-based Grouping**: Each app session creates a new lesson (unique session ID)
- Device pairing (`POST /api/devices/pair/`) with revocation
- Screenshot OCR ingestion + server-side dedupe
- **Smart Question Detection**: Sends entire screenshot text as one question to AI
  - Handles multiple-choice questions (a., b., c. options)
  - Works with or without punctuation (Google Meet often omits `?`)
  - AI understands any text format (questions, statements, prompts)
  - URL/UI noise filtering (e.g., `docs.google.com/.../edit?` is ignored)
- Desktop paywall behavior: capture blocked while unpaired
- Devices auto-revoke on `/devices/` when subscription is inactive
- Desktop auto-unpairs if the backend revokes access (including periodic ~30s token re-validation)

### Document Ingestion (Lesson Mode)
- **Web dashboard upload**: Drag-and-drop interface for images and PDFs
- **OCR processing**: PyMuPDF for PDFs, Tesseract for images (JPG, PNG, WEBP, TIFF)
- **AI lesson naming**: OpenAI API generates concise titles from transcribed content
- **Rate limiting**: 50 uploads per day per user (prevents abuse)
- **File limits**: Max 100 files per upload, 100MB total, 10MB per file
- **No server storage**: Files processed in memory only, transcribed text saved to database
- **Source type filtering**: Dashboard tabs separate Recitations vs Lessons
- **Cost-effective**: OCR is free (local), AI naming ~$0.0001 per lesson

### AI & Dashboard
- Subscriber settings (max sentences, AI persona, AI description)
- **AI Persona & Description**: Customize AI behavior for recitation mode (e.g., "You are a grade 3 student")
- **Mode-specific AI behavior**:
  - **Recitation mode**: Uses persona + description + session context for homework help
  - **Lesson mode**: Uses tutor mode to explain uploaded document content
- **Markdown Rendering**: AI answers display with proper formatting (bold, italic, code blocks)
- AI answers stored and streamed in dashboard (SSE)
- Dual content types: Recitations (live capture) and Lessons (uploaded documents)
- **Smart context handling**:
  - Recitation: Uses session context (last 10 captions from desktop app)
  - Lesson: Uses full transcript with page numbers
- **Delete functionality**: Single and bulk delete for lessons with confirmation dialogs
- **Select All checkbox**: Bulk select all lessons for deletion
- **Formatted transcripts**: Preserves line breaks and paragraphs from original documents

### Live Dashboard (Phase 8)
- **Homepage**: Live Q&A page at `/` for instant access during Google Meet sessions
- **Real-time streaming**: ChatGPT-style word-by-word answer display
- **Auto-reload**: Page refreshes every 5 seconds to check for new questions
- **Latest first**: New questions appear at the top (reverse chronological)
- **Mode selector**: Switch between Recitation (today's session) and Lesson (selected lesson)
- **Optimized OCR**: 30-50% faster processing (resize, grayscale, contrast enhancement)
- **Zero desktop overhead**: All streaming happens on Django side
- **Stable performance**: No worker timeouts, no connection errors

### Desktop App Stability & Performance
- **Instant startup**: < 1 second app launch (10-20x faster than before)
- **Async initialization**: Background threads for pairing validation and lesson loading
- **Local caching**: Lessons cached for 5 minutes, instant display on startup
- **Connection status**: Real-time online/offline indicator (green/red)
- **Retry logic**: 3 automatic retry attempts with exponential backoff on network errors
- **Clear offline feedback**: User-friendly messages when server is unreachable
- **Auto-capture**: Automatically detects new clipboard images (Ctrl+C after Print Screen)
- **Non-blocking UI**: No freezing or shaking during clipboard polling
- **Session-based grouping**: Each app session creates a new lesson with unique ID
- **AI-generated titles**: Lesson names generated from first captured text
- **Long-running stability**: Safe for 4+ hour sessions (~60MB memory, auto-trimming logs)
- **Comprehensive tests**: 19 tests covering capture, UI responsiveness, OCR, detection
- **Bug fixes**: Resolved duplicate capture issue (Print Screen + clipboard watcher conflict)

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
| **Deploy checkpoint** — Render + Neon + OAuth + Stripe | **Completed** |
| **8 — Live Dashboard with Real-Time Streaming** | **Completed** |
| 9 — Frontend migration to Next.js | Planned |
| 10 — Windows desktop installer | Completed |
| **11 — Document Ingestion Pipeline (Backend)** | **Completed** |
| **12 — Dashboard Upload & Editing UI** | **Completed** |
| 13 — AI Persona & send-all architecture | Completed |
| **14 — Desktop App Stability & Auto-Capture** | **Completed** |
| **16 — Desktop App Mode Selection & Lesson UI** | **Completed** |
| **16.7 — Desktop App Async Startup Optimization** | **Completed** |

See `PLAN.md` for detailed phased deliverables.

---

## Tech stack

### Backend
- Django
- PostgreSQL
- django-allauth (Google OAuth)
- WhiteNoise (static files)
- OpenAI API (gpt-4o-mini for AI naming and answers)
- Stripe API
- PyMuPDF (PDF processing)
- Pillow (image processing)
- pytesseract + Tesseract OCR (server-side)

### Desktop
- Python + tkinter
- Pillow (`ImageGrab`)
- pytesseract + Tesseract OCR
- pynput (global hotkey)

### Infra / DevEx
- Docker Compose
- Render (production deployment)

---

## API contract (desktop ↔ backend)

### Desktop App APIs (device token auth)
- `POST /api/devices/pair/` — exchange pairing code for device token
- `POST /api/captions/` — ingest OCR transcript chunks
- `POST /api/questions/` — submit detected question + context, return AI answer
- `GET /api/lessons/list/` — list lessons for selection (filtered by source_type)

### Dashboard APIs (session auth)
- `POST /api/lessons/upload/` — upload images/PDFs for OCR and lesson creation
- `DELETE /api/lessons/<id>/delete/` — delete single lesson with all associated data
- `POST /api/lessons/bulk-delete/` — delete multiple lessons in bulk
- `GET /api/questions/<id>/stream/` — stream answer tokens via SSE

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

- Live Q&A (Homepage): `http://localhost:8000/`
- Lessons Dashboard: `http://localhost:8000/lessons/`
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

This project uses **Stripe Checkout** for monthly subscriptions ($15.00 USD).

Subscription entitlement is enforced on AI answering endpoints when billing is configured.

---

### Part 1: Local development (Test mode)

Use this for local testing with `docker compose`.

#### 1.1 Create a Stripe Product + Price (Test mode)

1. [Stripe Dashboard](https://dashboard.stripe.com/test/products) → **Test mode** (toggle in top-right)
2. **Products** → **Add product**
3. Name: `Meet Lessons Monthly`
4. Pricing:
   - **Recurring** (not one-time)
   - **Monthly** billing period
   - Price: **$15.00 USD**
5. Click **Save product**
6. Copy the **Price ID** (format: `price_...`)

#### 1.2 Configure Django Admin

1. Start local backend: `docker compose up --build`
2. Create superuser: `docker compose exec web python manage.py createsuperuser`
3. Login at `http://localhost:8000/admin/`
4. **Billing → Billing plans** → edit the default plan
5. Set `stripe_monthly_price_id` to your `price_...` from step 1.1
6. Save

#### 1.3 Set local environment variables

In root `.env` file:

```bash
STRIPE_SECRET_KEY=sk_test_...  # From Stripe Dashboard → Developers → API keys
STRIPE_WEBHOOK_SECRET=whsec_...  # From Stripe CLI (see step 1.4)
```

#### 1.4 Set up local webhook forwarding (Stripe CLI)

Stripe webhooks cannot reach `localhost` directly. Use Stripe CLI to forward events:

**Option A: Using Docker Compose (recommended)**

1. Authenticate Stripe CLI (one-time):
   ```bash
   docker compose run --rm stripe-cli login
   ```
2. Start the full stack (includes automatic webhook forwarding):
   ```bash
   docker compose up --build
   ```
3. View webhook logs:
   ```bash
   docker compose logs -f stripe-cli
   ```
4. Copy the `whsec_...` signing secret from the logs into your `.env` as `STRIPE_WEBHOOK_SECRET`
5. Restart: `docker compose up --build`

**Option B: Using Stripe CLI directly**

1. Install Stripe CLI: [https://stripe.com/docs/stripe-cli](https://stripe.com/docs/stripe-cli)
2. Login:
   ```bash
   stripe login
   ```
3. Forward webhooks to local Django:
   ```bash
   stripe listen --forward-to http://localhost:8000/billing/webhook/
   ```
4. Copy the `whsec_...` signing secret into your `.env` as `STRIPE_WEBHOOK_SECRET`
5. Restart backend: `docker compose up --build`

#### 1.5 Test local subscription flow

1. Visit `http://localhost:8000/billing/subscribe/`
2. Click **Subscribe**
3. Use Stripe test card: `4242 4242 4242 4242`, any future expiry, any CVC
4. Complete checkout
5. Verify in Django Admin:
   - **Billing → Stripe events** (should show `checkout.session.completed`, etc.)
   - **Billing → Stripe subscriptions** (should show active subscription)
6. Test entitlement: visit `/devices/` and verify you can generate pairing codes

#### 1.6 Test subscription cancellation

1. Visit `http://localhost:8000/billing/portal/`
2. Cancel subscription
3. Visit `/devices/` → active devices should auto-revoke
4. Try to generate a pairing code → should be blocked

---

### Part 2: Production deployment (Render + Stripe Test mode)

This section covers connecting your **live Render app** (`https://auto-respond-tdp7.onrender.com`) to Stripe webhooks.

**Prerequisites:**
- Render app deployed and accessible
- Stripe Product + Price created (from Part 1, step 1.1)
- Django Admin configured with `stripe_monthly_price_id` (from Part 1, step 1.2)

See the "Deploy to Render" section below for full deployment steps. Once deployed, return here to configure Stripe webhooks for production.

#### 2.1 Create webhook destination in Stripe Dashboard

1. [Stripe Dashboard](https://dashboard.stripe.com/test/workbench/webhooks) → **Test mode** (toggle in top-right)
2. **Workbench** → **Webhooks** → **Add destination**
3. **Step 1 - Select events:**
   - Choose **"Your account"** (receive events from resources in this account)
   - Click **"Selected events"** tab
   - Select these 6 events:
     - ✅ `checkout.session.completed`
     - ✅ `customer.subscription.created`
     - ✅ `customer.subscription.updated`
     - ✅ `customer.subscription.deleted`
     - ✅ `invoice.paid`
     - ✅ `invoice.payment_failed`
   - Click **Continue**

4. **Step 2 - Choose destination type:**
   - Select **"Webhook destination"** (send to a webhook endpoint)
   - Click **Continue**

5. **Step 3 - Configure your destination:**
   - **Destination name:** `Render production webhook` (or any name you prefer)
   - **Endpoint URL:**
     ```
     https://auto-respond-tdp7.onrender.com/billing/webhook/
     ```
     ⚠️ Replace `auto-respond-tdp7` with your actual Render service name
   - **Description (optional):** Leave blank or add notes
   - Click **Create destination**

#### 2.2 Copy the webhook signing secret to Render

1. After creating the destination, click on it to view details
2. Under **Signing secret**, click **Reveal**
3. Copy the secret (format: `whsec_...`)
4. **Render Dashboard** → your Web Service → **Environment**
5. Add or update:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
   (paste the secret you just copied)
6. Click **Save Changes**
7. Render will auto-redeploy (takes ~2-3 minutes)

#### 2.3 Verify webhook is working

1. After Render redeploys, visit your app and complete a test subscription:
   - `https://auto-respond-tdp7.onrender.com/billing/subscribe/`
   - Use test card: `4242 4242 4242 4242`, any future expiry, any CVC
2. Check **Stripe Dashboard** → **Webhooks** → your endpoint → **Events** tab
   - Should show successful deliveries (green checkmarks, 200 OK responses)
3. Check **Django Admin** → **Billing → Stripe events**
   - Should show the received events (`checkout.session.completed`, etc.)
4. Check **Django Admin** → **Billing → Stripe subscriptions**
   - Should show your active subscription with correct status

**Troubleshooting:**
- **500 errors in Stripe webhook events**: Check Render logs for Python exceptions
- **400 errors**: `STRIPE_WEBHOOK_SECRET` is incorrect or missing from Render environment
- **No events appear**: Verify the destination URL matches your Render URL exactly (including `https://`)
- **Subscription not created**: Check that `BillingPlan.stripe_monthly_price_id` is set correctly in Django Admin

#### 2.4 Enable Stripe Customer Portal (optional)

1. [Stripe Dashboard](https://dashboard.stripe.com/test/settings/billing/portal) → **Settings** → **Billing** → **Customer portal**
2. Toggle **Activate test link**
3. Enable **Subscription cancellation** and **Payment method updates**
4. Save

Now users can manage their subscriptions at: `https://auto-respond-tdp7.onrender.com/billing/portal/`

---

### Part 3: Moving to Live mode (production billing)

⚠️ **Only do this when you're ready to charge real customers.**

1. **Stripe Dashboard** → Switch to **Live mode** (toggle in top-right)
2. Create a new Product + Price (same as Part 1, but in Live mode)
3. Update Django Admin → **Billing plans** → `stripe_monthly_price_id` to the **Live** `price_...`
4. Create a **new webhook destination** for Live mode:
   - Follow the same steps as Part 2.1 (Add destination → Select events → Choose Webhook destination → Configure)
   - URL: `https://auto-respond-tdp7.onrender.com/billing/webhook/`
   - Same 6 events as before
   - Copy the **Live mode** signing secret
5. Update Render environment:
   - `STRIPE_SECRET_KEY=sk_live_...` (from Live mode API keys)
   - `STRIPE_WEBHOOK_SECRET=whsec_...` (from Live mode webhook)
6. Test with a real card (you'll be charged $15.00)
7. Refund the test transaction in Stripe Dashboard if needed

**Best practice:** Keep Test mode and Live mode webhook destinations configured separately so you can test changes without affecting live customers.

---

## Coupon codes

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

Database best practice (Render): set **`DATABASE_URL`** using the Render Postgres **Internal Database URL**. Do **not** set `POSTGRES_HOST=localhost/127.0.0.1` on Render.

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
| `STRIPE_WEBHOOK_SECRET` | `whsec_...` (from Render webhook destination — see Step 5) |
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

**Important:** Production webhooks use a **different signing secret** than local Stripe CLI. You must configure a webhook destination in Stripe Dashboard.

**See detailed instructions in the "Stripe subscriptions" section above (Part 2).**

Quick summary:

1. [Stripe Dashboard](https://dashboard.stripe.com/test/workbench/webhooks) → **Test mode**
2. **Workbench** → **Webhooks** → **Add destination**
3. Follow the 3-step wizard:
   - **Step 1:** Select the 6 required events
   - **Step 2:** Choose "Webhook destination"
   - **Step 3:** Enter URL: `https://auto-respond-tdp7.onrender.com/billing/webhook/`
4. Copy the signing secret and add to Render

#### 5.1 Copy the webhook signing secret

1. After creating the destination, click on it to view details
2. Under **Signing secret**, click **Reveal**
3. Copy the secret (format: `whsec_...`)
4. **Render Dashboard** → your Web Service → **Environment**
5. Add or update:
   ```
   STRIPE_WEBHOOK_SECRET=whsec_...
   ```
   (paste the secret you just copied)
6. Click **Save Changes**
7. Render will auto-redeploy

#### 5.3 Verify webhook is working

1. After Render redeploys, visit your app and complete a test subscription:
   - `https://auto-respond-tdp7.onrender.com/billing/subscribe/`
   - Use test card: `4242 4242 4242 4242`
2. Check Stripe Dashboard → **Webhooks** → your endpoint → **Events**
   - Should show successful deliveries (200 OK responses)
3. Check Django Admin → **Billing → Stripe events**
   - Should show the received events
4. Check Django Admin → **Billing → Stripe subscriptions**
   - Should show your active subscription

**Troubleshooting:**
- If webhook shows 500 errors: check Render logs for Python errors
- If webhook shows 400 errors: `STRIPE_WEBHOOK_SECRET` is incorrect or missing
- If no events appear: verify the endpoint URL matches your Render URL exactly

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
   If you're on a **free Render instance** and **Shell is not supported**, create the superuser from your laptop by connecting directly to Render Postgres:

   1. Render Dashboard → your **PostgreSQL** → **Connections**
   2. Copy the **External Database URL** (this is accessible from your machine)
      Example format:
      ```text
      postgres://USER:PASSWORD@HOST:5432/DBNAME
      ```
   3. From your repo root, run:
      ```bash
      DATABASE_URL='paste_external_db_url_here' \
      DJANGO_DEBUG=0 \
      DJANGO_SECRET_KEY='use_the_same_one_on_render' \
      DJANGO_ALLOWED_HOSTS='your-app.onrender.com' \
      DJANGO_CSRF_TRUSTED_ORIGINS='https://your-app.onrender.com' \
      python3 backend/manage.py createsuperuser
      ```
      Notes:
      - Use the same `DJANGO_SECRET_KEY` value you set on Render.
      - If your Render DB requires TLS and the URL doesn’t include it, append `?sslmode=require` to `DATABASE_URL`.
   4. Log in at:
      ```
      https://your-app.onrender.com/admin/
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

### Using Neon Postgres (free, no expiry — recommended over Render Postgres)

Render's free PostgreSQL instance **expires after 30 days**. [Neon](https://neon.tech) is a free, serverless Postgres provider with no expiry and a generous free tier — ideal for small production deployments (1–10 users).

#### Step A — Create a Neon project

1. Sign up at [neon.tech](https://neon.tech) (free, no credit card)
2. **New Project** → name it `meet-lessons`
3. Choose a region closest to your Render service
4. Neon creates a default database and user automatically
5. Go to your project → **Dashboard** → **Connection Details**
6. Select **Connection string** → copy the URL:
   ```text
   postgres://USER:PASSWORD@HOST/DBNAME?sslmode=require
   ```
   > Neon always requires SSL — the `?sslmode=require` is already included.

#### Step B — Update `DATABASE_URL` on Render

1. Render → your **Web Service** → **Environment**
2. Update `DATABASE_URL` to the Neon connection string from Step A
3. Click **Save Changes**
4. Render → **Manual Deploy** → **Deploy latest commit**

Django will run `migrate` on startup and create all tables in the new Neon DB automatically.

#### Step C — Create a superuser against Neon (from your laptop)

Since Render free tier has no Shell, run this locally:

> Note: If your Neon connection string includes `channel_binding=require` (common on some **pooler** URLs), remove that parameter for this local command (or use Neon's **direct** connection string). Some Postgres client stacks may not support it.

```bash
DATABASE_URL='paste_neon_connection_string_here' \
DJANGO_DEBUG=0 \
DJANGO_SECRET_KEY='use_the_same_one_on_render' \
DJANGO_ALLOWED_HOSTS='auto-respond-tdp7.onrender.com' \
DJANGO_CSRF_TRUSTED_ORIGINS='https://auto-respond-tdp7.onrender.com' \
python3 backend/manage.py createsuperuser
```

Then log in at `https://your-app.onrender.com/admin/`.

#### Step D — Delete the Render Postgres instance (optional)

Once Neon is working, you can delete the Render Postgres to free up the slot:

- Render Dashboard → your **PostgreSQL** → **Settings** → **Delete Database**

> **Best practices for Neon free tier:**
> - Free tier: 0.5 GB storage, 1 compute unit, auto-suspend after 5 min inactivity (cold start ~1–2s)
> - Do **not** store large binary files in the DB (use S3/Cloudflare R2 for that)
> - Keep connection pooling in mind if you scale beyond ~10 concurrent users (use Neon's built-in pooler URL)
> - Neon connection string format: `postgres://USER:PASSWORD@HOST/DBNAME?sslmode=require`

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
