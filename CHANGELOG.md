# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- SaaS roadmap: Google login, Stripe subscriptions (monthly), coupon codes, and Render deployment (see `PLAN.md`).
- Fresh Django SaaS-first scaffold with separate apps (`accounts`, `billing`, `devices`, `lessons`).
- Docker Compose local development stack (Django + Postgres).
- Admin-managed coupon codes (Stripe Promotion Codes or Coupon IDs) applied to Checkout sessions with redemption limits.
- Phase 7 production hardening:
  - HTTPS security headers: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS (1 year, include subdomains, preload).
  - `CSRF_TRUSTED_ORIGINS` from `DJANGO_CSRF_TRUSTED_ORIGINS` env var (required for Render HTTPS POST forms).
  - `SECRET_KEY` startup guard: raises `RuntimeError` if the default dev key is used with `DEBUG=0`.
  - Structured console logging (`LOGGING` config) with verbose formatter for Render log viewer.
  - All security settings are gated on `DEBUG=False` so local dev is unaffected.
- Phase 5 billing implementation:
  - Stripe SDK dependency (`stripe==7.13.0`).
  - Billing endpoints: `/billing/subscribe/`, `/billing/checkout/`, `/billing/portal/`, `/billing/webhook/`.
  - Stripe models: `StripeCustomer`, `StripeSubscription`, `StripeEvent` + migration `billing.0002_stripe_models`.
  - Billing templates for subscribe/success/cancel flows.
  - Subscription CTA in dashboard + subscription nav link.
  - Webhook idempotency tracking and subscription sync in admin.

### Changed
- **Architecture pivot**: replaced Chrome Extension with Python desktop app (`desktop/`).
  - Chrome extension approach abandoned — Google Meet DOM is too brittle for reliable caption capture.
  - New approach: student takes screenshots (Print Screen) → local OCR (Tesseract) → question detection → send to backend.
  - AI answers displayed only on the web dashboard (paywall), not in the desktop app.
- Phase 1 completed: Google OAuth login (django-allauth), Subscriber profile + settings, and basic dashboard shell.
- Phase 2 completed: Device pairing + security:
  - Device model: `token_hash`, `revoked_at` fields, `revoke()` and `is_active` helpers.
  - `DevicePairingCode.generate()` class method for 8-char hex codes with 10-min expiry.
  - Device token utilities (`devices/tokens.py`): issue and verify opaque `<device_id>:<secret>` tokens.
  - Dashboard views: `/devices/` (list + pairing code), `/devices/pair/` (generate code), `/devices/<id>/revoke/`.
  - API endpoint: `POST /api/devices/pair/` — desktop app exchanges pairing code for device token.
  - **(desktop)** Pairing UI in tkinter app with backend URL config and paired/unpaired states.
- Phase 3 completed: Screenshot capture + OCR + question detection:
  - **(backend)** Device token auth decorator (`devices/auth.py`): `@require_device_token` for API views.
  - **(backend)** `POST /api/captions/` — ingest OCR text with server-side SHA-256 dedupe.
  - **(backend)** `POST /api/questions/` — submit detected questions with AI answering.
  - **(backend)** Lesson model: `meeting_id` + `meeting_date` with unique constraint for auto-create dedup.
  - **(backend)** TranscriptChunk model: `content_hash` with unique constraint for server-side dedupe.
  - **(backend)** Auto-create lesson per meeting title + date; manual lesson selection via `lesson_id` param.
  - **(backend)** Lesson detail view (`/lessons/<id>/`) with transcript + Q&A display.
  - **(backend)** Dashboard lessons list now clickable with chunk/Q&A counts.
  - **(desktop)** Print Screen hotkey listener via `pynput`.
  - **(desktop)** Clipboard screenshot capture via `Pillow.ImageGrab`.
  - **(desktop)** Local OCR via `pytesseract` (Tesseract).
  - **(desktop)** Question detection: interrogative keywords + `?` + math expression patterns.
  - **(desktop)** Activity log in tkinter UI.
- Phase 4 completed: AI answering:
  - **(backend)** `POST /api/questions/` now calls OpenAI API synchronously and returns the answer.
  - **(backend)** AI module (`lessons/ai.py`): prompt builder with grade-level + max-sentences settings.
  - **(backend)** `GET /api/questions/<id>/stream/` SSE endpoint for dashboard streaming.
  - **(backend)** Lesson detail template: `EventSource` JS renders answer tokens live.
  - **(backend)** Auto-refresh on lesson detail page to pick up new Q&A from desktop app.
- Desktop app configuration hardening:
  - Removed Backend URL input from tkinter UI.
  - Desktop app now reads backend URL from `desktop/.env` (`MEET_LESSONS_URL`) with production fallback.
  - Added `desktop/.env.example` template for desktop deployments.
- Paywall enforcement in desktop app:
  - Capture is now blocked when device is not paired.
  - Manual capture button stays disabled while unpaired.
  - Hotkey/manual capture attempts while unpaired log: `Not paired — pair your device first to enable capture`.
- Device dashboard copy/data cleanup:
  - `/devices/` page text updated to refer to the desktop app (removed Chrome extension wording).
  - Existing legacy device labels updated from `Chrome Extension` to `Desktop App`.
- Verification updates (2026-02-14):
  - Google login working.
  - Device pairing working.
  - User dashboard working.
  - Admin login and admin pages working.
  - Desktop capture flow working with Linux clipboard watcher fallback.
  - AI answers verified from desktop-submitted questions in dashboard and Django Admin records.

- Phase 5 completed (2026-02-15):
  - Flat monthly Stripe plan standardized at $15.00 USD.
  - Checkout session creation for recurring monthly subscriptions.
  - Webhook signature verification and Stripe event de-duplication.
  - Subscription entitlement enforcement on AI answering endpoints.
  - Device subscription enforcement hardening:
    - `/devices/` auto-revokes active devices when subscription is inactive/ended.
    - Pairing code generation and pairing exchange require active subscription when billing is configured.
  - Billing subscribe page UX refresh:
    - Emphasizes subscription importance with clear status + action-required messaging.
    - Shows pricing details, trust signals, and next-step guidance.
  - django-allauth redirect customization for post-signup/login billing UX.
  - Docker compose updated to pass Stripe env vars to web container.
  - Documentation expanded with Stripe webhook tutorials (local + production).

- Desktop capture reliability + detector hardening:
  - Added clipboard watcher fallback for Linux/DE environments where `Print Screen` is intercepted.
  - Added adaptive clipboard polling backoff to reduce idle UI wakeups/CPU activity.
  - Added periodic (~30s) backend token re-validation to auto-unpair when device access is revoked.
  - Updated detector to ignore URL/browser UI OCR noise (e.g. `docs.google.com/.../edit?`).
  - Question detection now prefers WH-start questions (with optional `?`) and math expressions.
  - Added fraction math detection support (e.g. `1/4 x 1/5`).
  - Improved sentence parsing by treating OCR line breaks as spaces to avoid truncated questions.

### Removed
- Chrome Extension (`extension/` folder) — replaced by Python desktop app.

### Fixed
- Static assets (admin CSS/JS) failing with MIME type errors: added WhiteNoise, configured `STATICFILES_STORAGE`, and run `collectstatic` at container start.
- Pairing code expiry display: replaced static UTC timestamp with a dynamic JavaScript countdown timer (timezone-agnostic).
- Migration dependency: fixed missing `0002_billingplan` reference; renumbered lesson migrations to `0002`/`0003`.

### Documentation
- Complete rewrite of README.md, PLAN.md, ENV.md, TEST.md for desktop app architecture.
- PLAN.md: phases now tagged with **(backend)** / **(desktop)** ownership.
- PLAN.md: Chrome extension listed as non-goal.

## [0.1.0] - 2026-02-11

### Added
- Initial monorepo structure and project documentation.
