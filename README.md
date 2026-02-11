# Meet Lessons — SaaS (Django + Google Meet Captions → Lessons → AI Q&A)

A production-minded **Django SaaS** that turns **Google Meet live captions** into structured **Lessons** stored in Postgres, then answers questions using those lessons via the **OpenAI API**.

This repository is organized as a **single monorepo**:

- `backend/`: Django (web UI + API), Postgres integration, Stripe webhooks
- `extension/`: Chrome Extension (MV3) that reads Google Meet captions from the DOM

## Product overview

- **Subscribers** sign in with **Google**, manage settings (grade level / answer length), and view lessons, transcripts, and Q&A.
- The **Chrome extension** reads Meet captions and sends them to the backend.
- The backend creates a lesson per meeting (title + date) by default, or routes captions to a user-selected lesson.
- The AI answers are optimized for speed and clarity (default: short grade-appropriate responses).

## SaaS features (planned)

- **Authentication**: Google OAuth for subscribers
- **Billing**: Stripe subscriptions
  - Daily / weekly / monthly plans
  - Coupon codes (admin-managed)
- **Multi-tenant data isolation**: all lesson data is scoped to the authenticated user
- **Admin CMS** (owner): manage users, subscriptions, devices, and coupon codes
- **Deployment**: Render + Render Postgres

See `PLAN.md` for the full phased roadmap.

## Current implementation status

The codebase currently contains an early scaffold for:

- Django backend (web UI + API)
- Chrome extension (MV3)
- Docker Compose local development stack

The authentication and billing layers will be refactored to the SaaS model in `PLAN.md` (Google login, Stripe checkout/webhooks, extension pairing).

## Local development (Ubuntu + Docker Desktop)

### 1) Configure environment

Create a `.env` in the repo root (copy from `.env.example`) and set at minimum:

- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`

### 2) Start services

```bash
docker compose up --build
```

Then run migrations:

```bash
docker compose run --rm web python manage.py migrate
```

Create an admin user:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Open:

- Web UI: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`

## Chrome Extension (Ubuntu + Windows 11)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

## Engineering highlights (portfolio)

- Separation of concerns between web UI, API endpoints, and extension ingestion
- Security-first model (server-owned secrets, planned device pairing, planned Stripe webhook source-of-truth)
- Clear roadmap and deliverables (see `PLAN.md`)
