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

### Fixed
- Static assets (admin CSS/JS) failing with MIME type errors: added WhiteNoise, configured `STATICFILES_STORAGE`, and run `collectstatic` at container start.

### Documentation
- Expanded README with tutorials: Google OAuth setup, DJANGO_SECRET_KEY generation, Django Admin setup, and static files troubleshooting notes.

## [0.1.0] - 2026-02-11

### Added
- Initial monorepo structure and project documentation.
