# PLAN — Meet Lessons SaaS (Django + Google Meet Captions → Lessons → AI Q&A)

## 1) Goal
Build a **single-repo SaaS** that:

- Lets subscribers sign in with **Google**.
- Captures **Google Meet live captions** using a **Chrome Extension (MV3)**.
- Automatically stores captions as **Lessons** (auto-create per meeting title + date) or to a manually selected lesson.
- **Detects questions** in the caption stream (extension-side) and sends them to the backend for AI answering.
- Backend passes detected questions + lesson transcript context to the **OpenAI API** and **streams the answer** via SSE.
- Answers are visible in real time on the **subscriber dashboard** (streaming tokens) and in the **extension popup** (quick-glance view).
- Provides a subscriber **dashboard** (settings, lessons, transcripts, Q&A history).
- Provides an owner **admin CMS** (you) to manage users, subscriptions, devices, coupons, and content.

Target deployment:

- **Render** for Django Web Service
- **Render Postgres** for database
- **Stripe** for subscriptions (monthly) + coupon codes

## 2) Security & configuration principles

- All server secrets stay in environment variables (Render env vars / `.env` locally).
- No shared secrets shipped in the extension.
- The extension authenticates via **device pairing** (one-time code) and server-issued tokens.
- Multi-tenant isolation: every row (lesson/transcript/Q&A/device/subscription) is scoped to a user account.

## 3) SaaS architecture (high level)

### 3.1 Backend (Django)
- Auth: Google OAuth sign-in.
- Billing: Stripe Checkout + Webhooks.
- Dashboard: lessons, transcripts, Q&A, settings, billing status.
- Admin CMS: Django Admin with curated models.
- **API endpoints** consumed by the extension:
  - `POST /api/devices/pair/` — exchange pairing code for device token
  - `POST /api/captions/` — ingest raw caption events
  - `POST /api/questions/` — submit detected question + context
  - `GET /api/questions/<id>/stream/` — SSE stream of AI answer tokens

### 3.2 Chrome extension (MV3)

The `extension/` folder lives in this monorepo and contains a starter scaffold. The backend provides the API contract above.

Extension responsibilities:
- Content script reads captions from the Meet DOM.
- **Question detection**: accumulates captions in a sliding buffer; detects questions via interrogative keywords (`what`, `when`, `where`, `who`, `why`, `how`, `is`, `are`, `do`, `does`, `did`, `can`, `could`, `will`, `would`, `should`) and/or trailing `?`. This is necessary because Google Meet captions often omit punctuation.
- Background service worker posts detected questions (with context) to the backend API.
- Background service worker posts raw caption events to the backend API for transcript storage.
- **Popup**: displays the latest AI answer for the active meeting (quick-glance).
- One-time pairing flow (subscriber copies a pairing code from the web dashboard).

### 3.3 Real-time Q&A flow
1. Extension content script accumulates captions in a sliding buffer.
2. Extension detects questions via interrogative keyword matching and/or trailing `?`.
3. Extension sends `POST /api/questions/` with: question text, recent caption context, lesson ID.
4. Backend retrieves transcript chunks for the lesson as additional context.
5. Backend calls OpenAI API (streaming mode) with: question + transcript + grade-level prompt.
6. Backend streams answer tokens via **SSE** (`GET /api/questions/<id>/stream/`).
7. Dashboard renders tokens live; extension popup shows latest Q&A.
8. After stream completes, backend persists the full `QuestionAnswer` record.

## 4) Authentication model

### 4.1 Subscriber login
- Users log in on the web app via **Sign in with Google**.

### 4.2 Extension pairing (no secrets in extension)
- Subscriber signs in on the dashboard and generates a short-lived pairing code.
- Extension options page accepts the pairing code once.
- Backend issues a device credential (refresh token / device token).
- Extension uses that credential to obtain short-lived access tokens.

## 5) Stripe billing (monthly subscription)

### 5.1 Product & Price
- Create a single Stripe Price:
  - Monthly subscription

We will compute “equivalent” weekly/daily pricing for display/marketing only (no separate weekly/daily subscriptions).

### 5.2 Checkout flow
- Subscriber clicks “Upgrade” in dashboard.
- Backend creates a Stripe Checkout Session for the Monthly plan.
- After payment, Stripe redirects back to the dashboard.

### 5.3 Webhooks (source of truth)
Handle:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid` / `invoice.payment_failed`

Backend updates local subscription state used for entitlement checks.

### 5.4 Coupon codes
Implement **coupon codes** with an admin-managed CMS.

Recommended approach:

- Use Stripe **Coupons + Promotion Codes** as the billing source of truth.
- Store a local `Coupon` model that maps:
  - `code`
  - `stripe_promotion_code_id`
  - `active`, `max_redemptions`, `expires_at`
- Admin can create/disable coupon codes in Django Admin.
- At checkout creation time, backend applies the promotion code if valid.

### 5.5 Pricing CMS (Admin)

- Add a `BillingPlan` model managed in Django Admin that stores:
  - Monthly price (cents)
  - Monthly discount percent (default: 20%)
  - Stripe Price ID (monthly)
- Backend uses this model to:
  - render pricing on the subscriber dashboard
  - attach the correct Stripe Price ID during Checkout

## 6) Data model (multi-tenant)

- `User` (Django auth)
- `SubscriberProfile`
  - user FK
  - defaults: grade level, max sentences
- `Subscription`
  - user FK
  - stripe customer id, subscription id, status, current period end, plan type
- `Device`
  - user FK
  - label, last_seen_at, token hash, revoked_at
- `Lesson`
  - user FK
  - title, source (`manual`, `meet_auto`), meeting_code, meeting_started_at
- `TranscriptChunk`
  - lesson FK
  - source (`meet_caption`, `ocr_image`, `manual`), speaker, text, captured_at
- `QuestionAnswer`
  - lesson FK nullable
  - question, answer, model, latency
- `Coupon`
  - code, stripe promotion code id, active flags

## 7) Subscriber dashboard scope

- Subscription status + upgrade/manage billing
- Settings:
  - grade level (e.g. Grade 3)
  - max sentences (1–2)
- Lessons:
  - create manual lesson
  - view Meet auto-created lessons
  - view transcript stream and Q&A history
- Pair extension:
  - generate pairing code
  - view connected devices and revoke

## 8) Owner (admin) CMS scope

Use Django Admin as the primary CMS:

- Users / subscriber profiles
- Subscriptions (synced from Stripe)
- Devices (revoke, audit last seen)
- Coupons (create/disable)
- Lessons / transcripts / Q&A

## 9) Deployment to Render

- Render Web Service running Django (Docker or native build)
- Render Postgres
- Environment variables configured in Render dashboard
- Stripe webhook endpoint exposed publicly (Render URL)

## 10) Phased implementation plan

### Phase 0 — Repo hygiene & foundations (Completed)
- Lock monorepo structure (`backend/`, `extension/`)
- Baseline CI checks (format/lint optional)
- Environment variable contract documented

### Phase 1 — Multi-tenant accounts + dashboard shell (Completed)
- Google OAuth login
- Subscriber profile + settings (grade level, max sentences)
- Basic dashboard pages (templates)

Status: Tested and verified (see `TEST.md`).

### Phase 2 — Extension pairing + device security (Completed)
- **(backend)** Pairing code generation in dashboard ✓
- **(backend)** `POST /api/devices/pair/` endpoint ✓
- **(backend)** Device token issue, verify, revoke ✓
- **(backend)** Dashboard UI: devices list + revoke ✓
- **(extension)** Options page: enter pairing code, call API, store token ✓

Status: Fully tested and verified — dashboard pairing + extension pairing confirmed working (see `TEST.md`).

### Phase 3 — Meet captions ingestion + question detection (Completed)
- **(backend)** `POST /api/captions/` endpoint — receive + store caption events ✓
- **(backend)** Server-side dedupe + cooldown ✓
- **(backend)** Auto-create lesson per meeting title + date ✓
- **(backend)** Manual lesson selection support ✓
- **(extension)** Caption reader hardening (selectors + fallback scanning) ✓
- **(extension)** Client-side dedupe + cooldown ✓
- **(extension)** **Question detection** (sliding buffer + interrogative keyword matching + `?` fallback) ✓
- **(extension)** Post captions and detected questions to backend API ✓

Status: Backend verified via curl/Python tests. Extension content.js v2 rewritten with correct Google Meet DOM selectors (`TEjq6e`, `.iTTPOb`, `.zs7s8d.jxFHg`), wait-for-call flow, caption settle timer, and CC toggle detection. Options page now shows live activity log and Q&A section. Dashboard lesson list is clickable with chunk/Q&A counts; lesson detail page shows transcript + Q&A. Requires live Google Meet session to fully test caption capture.

### Phase 4 — AI answering (streaming)
- **(backend)** `POST /api/questions/` endpoint (receives question + context + lesson ID) ✔
- **(backend)** Retrieve transcript chunks for the lesson as context
- **(backend)** Build prompt: question + transcript context + grade-level setting
- **(backend)** Call OpenAI API in **streaming mode**
- **(backend)** **SSE endpoint** (`GET /api/questions/<id>/stream/`) streams answer tokens
- **(backend)** Persist full `QuestionAnswer` record after stream completes
- **(backend)** Dashboard: lesson detail page with Q&A display (template ready) ✔
- **(backend)** Dashboard: `EventSource` JS renders tokens live
- **(extension)** Options page: Q&A display section (ready for Phase 4 answers) ✔
- **(extension)** Popup: consume SSE stream and display latest Q&A

### Phase 5 — Lessons upload + OCR (optional)
- Upload screenshots
- OCR pipeline
- Store OCR transcript chunks in lessons

### Phase 6 — Stripe subscriptions (monthly)
- Stripe Checkout Session creation
- Stripe webhook handler + subscription sync
- Entitlement checks on caption ingest and answering

### Phase 7 — Coupons (admin CMS)
- `Coupon` model + Django Admin
- Apply coupon code in checkout flow
- Validation rules (active, expiry, redemption limits)

### Phase 8 — Render production hardening
- Proper `ALLOWED_HOSTS`, HTTPS settings
- Static files strategy
- DB migrations on deploy
- Admin hardening and logging

## 11) Non-goals (for MVP)

- Audio capture
- Full extension overlay UI (popup for latest Q&A is enough; no floating overlay)
- Multi-language caption support
- Offline/local AI models
