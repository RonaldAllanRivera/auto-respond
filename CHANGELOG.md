# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- SaaS roadmap: Google login, Stripe subscriptions (monthly), coupon codes, and Render deployment (see `PLAN.md`).
- Fresh Django SaaS-first scaffold with separate apps (`accounts`, `billing`, `devices`, `lessons`).
- Chrome Extension (MV3) scaffold with pairing-code configuration (device pairing planned).
- Docker Compose local development stack (Django + Postgres).

### Changed
- Phase 1 completed and verified: Google OAuth login (django-allauth), Subscriber profile + settings, and basic dashboard shell. `PLAN.md` updated and `TEST.md` added.
- Phase 2: Extension pairing + device security:
  - Device model: added `token_hash`, `revoked_at` fields, `revoke()` and `is_active` helpers.
  - `DevicePairingCode.generate()` class method for 8-char hex codes with 10-min expiry.
  - Device token utilities (`devices/tokens.py`): issue and verify opaque `<device_id>:<secret>` tokens.
  - Dashboard views: `/devices/` (list + pairing code), `/devices/pair/` (generate code), `/devices/<id>/revoke/`.
  - API endpoint: `POST /api/devices/pair/` — extension exchanges pairing code for device token.
  - Extension options page: full pairing flow (enter code → call API → store token → show paired state).
  - Extension background.js: authenticated `apiFetch` helper using `X-Device-Token` header.
  - Tailwind-styled devices dashboard template with pairing code display and device list.
- Phase 3: Meet captions ingestion + question detection (backend):
  - Device token auth decorator (`devices/auth.py`): `@require_device_token` for API views.
  - `POST /api/captions/` — ingest caption events with server-side SHA-256 dedupe.
  - `POST /api/questions/` — submit detected questions (answer placeholder for Phase 4).
  - Lesson model: added `meeting_id` + `meeting_date` with unique constraint for auto-create dedup.
  - TranscriptChunk model: added `content_hash` with unique constraint for server-side dedupe.
  - Auto-create lesson per meeting ID + date; manual lesson selection via `lesson_id` param.
  - Admin updated with new fields and filters.

### Fixed
- Static assets (admin CSS/JS) failing with MIME type errors: added WhiteNoise, configured `STATICFILES_STORAGE`, and run `collectstatic` at container start.
- Pairing code expiry display: replaced static UTC timestamp with a dynamic JavaScript countdown timer (timezone-agnostic).
- Migration dependency: fixed missing `0002_billingplan` reference; renumbered lesson migrations to `0002`/`0003`.

### Documentation
- Expanded README with tutorials: Google OAuth setup, DJANGO_SECRET_KEY generation, Django Admin setup, and static files troubleshooting notes.
- README: updated title to "AI-Powered Q&A from Google Meet Captions"; added phase status table.
- PLAN.md: added real-time Q&A flow (Section 3.3), keyword-based question detection, API endpoint contract, and **(backend)**/**(extension)** ownership tags on all phase items.
- PLAN.md: reordered phases — core functionality (pairing, captions, AI) before SaaS monetization (Stripe, coupons).
- PLAN.md: removed streaming from non-goals (now a core feature); added multi-language and offline AI as non-goals.
- TEST.md: added Phase 2 (device pairing) and Phase 3 (caption/question API) testing sections with curl examples.

## [0.1.0] - 2026-02-11

### Added
- Initial monorepo structure and project documentation.
