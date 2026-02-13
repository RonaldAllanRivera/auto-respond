# PLAN — Meet Lessons SaaS (Django + Google Meet Captions → Lessons → AI Q&A)

## 1) Goal
Build a **single-repo SaaS** that:

- Lets subscribers sign in with **Google**.
- Captures **Google Meet live captions** using a **Chrome Extension (MV3)**.
- Automatically stores captions as **Lessons** (auto-create per meeting title + date) or to a manually selected lesson.
- Provides a subscriber **dashboard** (settings, lessons, transcripts, Q&A).
- Provides an owner **admin CMS** (you) to manage users, subscriptions, devices, coupons, and content.
- Answers questions **at once** (fast) using the selected lesson transcript, with a fallback “grade-level answer” setting.

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
- API used by extension:
  - Pairing endpoints
  - Captions ingest endpoint

### 3.2 Chrome extension (MV3)
- Content script reads captions from the Meet DOM.
- Background service worker posts caption events to Django.
- One-time pairing flow (subscriber copies a pairing code from the web dashboard).

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

### Phase 2 — Stripe subscriptions (monthly)
- Stripe Checkout Session creation
- Stripe webhook handler + subscription sync
- Entitlement checks on caption ingest and answering

### Phase 3 — Coupons (admin CMS)
- `Coupon` model + Django Admin
- Apply coupon code in checkout flow
- Validation rules (active, expiry, redemption limits)

### Phase 4 — Extension pairing + device security
- Pairing code generation in dashboard
- Pairing endpoint for extension
- Device tokens, revoke devices

### Phase 5 — Meet captions ingestion
- Caption reader hardening (selectors + fallback scanning)
- Dedupe + cooldown client-side and server-side
- Auto-create lesson per meeting title + date
- Manual lesson selection support

### Phase 6 — Lessons upload + OCR (optional)
- Upload screenshots
- OCR pipeline
- Store OCR transcript chunks in lessons

### Phase 7 — AI answering (fast, answer-at-once)
- Retrieve latest/top chunks for a lesson
- Prompt for grade-level concise answers
- Persist Q&A history

### Phase 8 — Render production hardening
- Proper `ALLOWED_HOSTS`, HTTPS settings
- Static files strategy
- DB migrations on deploy
- Admin hardening and logging

## 11) Non-goals (for MVP)

- Streaming answers (SSE/WebSockets)
- Audio capture
- Full extension overlay UI (dashboard is enough)
