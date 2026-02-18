# PLAN — Meet Lessons SaaS (Django + Desktop App → Screenshot OCR → AI Q&A)

## Table of contents

- [1) Goal](#1-goal)
- [2) Security & configuration principles](#2-security--configuration-principles)
- [3) SaaS architecture (high level)](#3-saas-architecture-high-level)
- [4) Authentication model](#4-authentication-model)
- [5) Stripe billing (monthly subscription)](#5-stripe-billing-monthly-subscription)
- [6) Data model (multi-tenant)](#6-data-model-multi-tenant)
- [7) Subscriber dashboard scope](#7-subscriber-dashboard-scope)
- [8) Owner (admin) CMS scope](#8-owner-admin-cms-scope)
- [9) Deployment to Render](#9-deployment-to-render)
- [10) Phased implementation plan](#10-phased-implementation-plan)
- [11) Testing](#11-testing)
- [12) Non-goals (for MVP)](#12-non-goals-for-mvp)

Related docs:

- `README.md` — project overview + setup guides
- `ENV.md` — environment variable contract
- `TEST.md` — step-by-step verification checklists
- `CHANGELOG.md` — historical record of changes

## 1) Goal
Build a **single-repo SaaS** that:

- Lets subscribers sign in with **Google**.
- Captures **Google Meet captions** via a **Python desktop app** that takes screenshots and runs **local OCR** (Tesseract).
- Automatically stores OCR text as **Lessons** (auto-create per meeting title + date).
- **Detects questions** in the OCR text (desktop-side) and sends them to the backend for AI answering.
- Backend passes detected questions + lesson transcript context to the **OpenAI API** and returns the answer.
- **Answers are visible on the subscriber dashboard** (streaming tokens via SSE) — this is the paywall.
- The desktop app is a **free capture tool** that shows pairing status and activity log only (no answers).
- Provides a subscriber **dashboard** (settings, lessons, transcripts, Q&A history with streaming AI answers).
- Provides an owner **admin CMS** (you) to manage users, subscriptions, devices, coupons, and content.

Target deployment:

- **Render** for Django Web Service
- **Render Postgres** for database
- **Stripe** for subscriptions (monthly) + coupon codes

## 2) Security & configuration principles

- All server secrets stay in environment variables (Render env vars / `.env` locally).
- No shared secrets shipped in the desktop app.
- The desktop app authenticates via **device pairing** (one-time code) and server-issued tokens.
- Multi-tenant isolation: every row (lesson/transcript/Q&A/device/subscription) is scoped to a user account.
- **AI answers are only visible on the web dashboard** (paywall). The desktop app cannot display answers.

## 3) SaaS architecture (high level)

### 3.1 Backend (Django)
- Auth: Google OAuth sign-in.
- Billing: Stripe Checkout + Webhooks.
- Dashboard: lessons, transcripts, Q&A with streaming AI answers, settings, billing status.
- Admin CMS: Django Admin with curated models.
- **API endpoints** consumed by the desktop app:
  - `POST /api/devices/pair/` — exchange pairing code for device token
  - `POST /api/captions/` — ingest OCR text from screenshots
  - `POST /api/questions/` — submit detected question + context → returns AI answer
  - `GET /api/questions/<id>/stream/` — SSE stream of AI answer tokens (for dashboard)

### 3.2 Desktop app (Python + tkinter)

The `desktop/` folder contains the Python desktop capture tool.

Desktop app responsibilities:
- Listen for **Print Screen** hotkey (global keyboard listener via `pynput`).
- Grab screenshot from clipboard (`Pillow.ImageGrab`).
- Run **local OCR** via Tesseract (`pytesseract`) — no API cost, ~200ms per image.
- **Question detection**: scan OCR text for WH-start questions (`what`, `when`, `where`, `who`, `why`, `how`, `which`, etc.; with or without `?`) and math expressions (including fractions like `1/4 x 1/5`), while filtering URL/UI OCR noise.
- Send full OCR text to `POST /api/captions/` for transcript storage.
- Send detected questions to `POST /api/questions/` for AI answering.
- Show **pairing status** and **activity log** only (no AI answers — those are on the dashboard).
- Periodically re-validate device token (~30s) and auto-unpair when backend access is revoked (e.g., subscription inactive).
- One-time pairing flow (subscriber copies a pairing code from the web dashboard).

### 3.3 Real-time Q&A flow
1. Student opens Google Meet with CC/subtitles enabled.
2. Student presses **Print Screen** → desktop app grabs the screenshot.
3. Desktop app runs local OCR (Tesseract, ~200ms).
4. Desktop app detects questions via WH-start patterns and math expressions (including fractions), and filters URL/UI OCR noise.
5. Desktop app sends OCR text to `POST /api/captions/` (transcript storage).
6. Desktop app sends detected questions to `POST /api/questions/` (AI answering).
7. Backend retrieves transcript context for the lesson.
8. Backend calls OpenAI API with: question + transcript context + grade-level prompt.
9. Backend stores the answer and returns it in the API response.
10. **Dashboard** displays the answer via SSE streaming (`GET /api/questions/<id>/stream/`).
11. Target: answer visible within **5 seconds** of question submission.

## 4) Authentication model

### 4.1 Subscriber login
- Users log in on the web app via **Sign in with Google**.

### 4.2 Desktop app pairing (no secrets in the app)
- Subscriber signs in on the dashboard and generates a short-lived pairing code.
- Desktop app accepts the pairing code once.
- Backend issues a device token.
- Desktop app stores the token locally (`~/.meet_lessons/config.json`).
- Desktop app uses that token for all API requests (`X-Device-Token` header).

## 5) Stripe billing (monthly subscription)

### 5.1 Product & Price
- Create a single Stripe Price:
  - Monthly subscription

We will compute "equivalent" weekly/daily pricing for display/marketing only (no separate weekly/daily subscriptions).

### 5.2 Checkout flow
- Subscriber clicks "Upgrade" in dashboard.
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
Coupon codes are admin-managed and backed by Stripe.

Best-practice approach:

- Use Stripe **Coupons + Promotion Codes** as the billing source of truth.
- Store a local `CouponCode` record that maps:
  - `code` (what the user types)
  - `stripe_promotion_code_id` (`promo_...`)
  - `active`, `max_redemptions`, `expires_at`
- Validate the code before creating the Checkout Session.
- Increment redemption usage via webhook (idempotent) after successful checkout.

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
  - title, meeting_id, meeting_date
- `TranscriptChunk`
  - lesson FK
  - speaker, text, content_hash, captured_at
- `QuestionAnswer`
  - lesson FK nullable
  - question, answer, model, latency_ms
- `CouponCode`
  - code, stripe promotion code id, active, expiry, max redemptions, redeemed count

## 7) Subscriber dashboard scope

- Subscription status + upgrade/manage billing
- Settings:
  - grade level (e.g. Grade 3)
  - max sentences (1–2)
- Lessons:
  - view auto-created lessons (from desktop app captures)
  - view transcript and Q&A history with **streaming AI answers**
- Pair desktop app:
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
- Lock monorepo structure (`backend/`, `desktop/`)
- Environment variable contract documented

### Phase 1 — Multi-tenant accounts + dashboard shell (Completed)
- Google OAuth login ✓
- Subscriber profile + settings (grade level, max sentences) ✓
- Basic dashboard pages (templates) ✓

### Phase 2 — Device pairing + security (Completed)
- **(backend)** Pairing code generation in dashboard ✓
- **(backend)** `POST /api/devices/pair/` endpoint ✓
- **(backend)** Device token issue, verify, revoke ✓
- **(backend)** Dashboard UI: devices list + revoke ✓
- **(desktop)** Pairing UI in tkinter app ✓

### Phase 3 — Screenshot capture + OCR + question detection (Completed)
- **(backend)** `POST /api/captions/` endpoint — receive + store OCR text ✓
- **(backend)** Server-side dedupe via content_hash ✓
- **(backend)** Auto-create lesson per meeting title + date ✓
- **(desktop)** Print Screen hotkey listener (pynput) ✓
- **(desktop)** Clipboard screenshot capture (Pillow ImageGrab) ✓
- **(desktop)** Local OCR via Tesseract (pytesseract) ✓
- **(desktop)** Question detection (WH-start + optional `?` + math/fractions + URL/UI filtering) ✓
- **(desktop)** Send captions and questions to backend API ✓
- **(desktop)** Activity log in tkinter UI ✓

### Phase 4 — AI answering (Completed)
- **(backend)** `POST /api/questions/` calls OpenAI API synchronously ✓
- **(backend)** Retrieves transcript chunks for the lesson as context ✓
- **(backend)** Builds prompt with question + transcript + grade-level setting ✓
- **(backend)** Persists `QuestionAnswer` record with answer, model, latency ✓
- **(backend)** `GET /api/questions/<id>/stream/` SSE endpoint for dashboard ✓
- **(backend)** Dashboard lesson detail page with SSE streaming Q&A display ✓
- **(backend)** `EventSource` JS renders answer tokens live ✓

### Phase 5 — Stripe subscriptions (monthly) (Completed)
- Flat monthly plan: $15.00 USD ✓
- Stripe Checkout Session creation ✓
- Stripe webhook handler + subscription sync ✓
- Entitlement checks on AI answering ✓
- Auto-revoke paired devices on `/devices/` when subscription is inactive/ended ✓
- Billing subscribe page UX emphasizes importance with pricing clarity, trust signals, and next steps ✓
- Billing portal session flow ✓

### Phase 6 — Coupons (admin CMS) (Completed)
- `CouponCode` model + Django Admin (maps local code → Stripe Promotion Code ID or Coupon ID) ✓
- Coupon code field on `/billing/subscribe/` applied during Stripe Checkout Session creation ✓
- Validation rules: active flag, expiry timestamp, max redemptions (tracked via webhook) ✓

### Phase 7 — Render production hardening
- Proper `ALLOWED_HOSTS`, HTTPS settings
- Static files strategy
- DB migrations on deploy
- Admin hardening and logging

### Phase 8 — Dashboard realtime UX (Django templates, pre-Next.js)
- Add "Latest Q&A" panel on `/` (dashboard home) so students can see newest Q&A immediately.
- Add lightweight API endpoint (session-auth) for latest Q&A feed per user.
- Add JavaScript polling/SSE on dashboard home to update latest Q&A without manual refresh.
- Ensure first detected question/answer appears at once on the page.

### Phase 9 — Frontend migration to Next.js (post-core completion)
- Migrate user-facing pages to Next.js after core backend/deployment phases are stable.
- Keep Django as API/admin service while Next.js handles subscriber UI.
- Preserve current API contract and parity for lessons, transcripts, Q&A streaming, settings, devices, and billing views.

## 11) Testing

This document intentionally stays high-level.

For step-by-step verification (device pairing, OCR capture, AI answering, Stripe subscriptions, coupon codes, and revocation behavior), use:

- `TEST.md`

## 12) Non-goals (for MVP)

- Chrome extension (abandoned — Google Meet DOM too brittle)
- Audio capture / speech-to-text from raw audio
- Multi-language OCR support
- Offline/local AI models
- Showing AI answers in the desktop app (paywall: answers only on dashboard)
