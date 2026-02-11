# Meet Lessons — SaaS (Django + Google Meet Captions → Lessons → AI Q&A)

A production-minded **Django SaaS** that turns **Google Meet live captions** into structured **Lessons** stored in Postgres, then answers questions using those lessons via the **OpenAI API**.

This repository is organized as a **single monorepo**:

- `backend/`: Django (accounts/billing/devices/lessons), Postgres integration, admin CMS models
- `extension/`: Chrome Extension (MV3) scaffold with pairing-code configuration (device pairing planned)

## Product overview

- **Subscribers** sign in with **Google**, manage settings (grade level / answer length), and view lessons, transcripts, and Q&A.
- The **Chrome extension** reads Meet captions and sends them to the backend.
- The backend creates a lesson per meeting (title + date) by default, or routes captions to a user-selected lesson.
- The AI answers are optimized for speed and clarity (default: short grade-appropriate responses).

## SaaS features (planned)

- **Authentication**: Google OAuth for subscribers
- **Billing**: Stripe subscriptions
  - Monthly plan (weekly/daily shown as computed equivalents for display)
  - Coupon codes (admin-managed)
- **Multi-tenant data isolation**: all lesson data is scoped to the authenticated user
- **Admin CMS** (owner): manage users, subscriptions, devices, and coupon codes
- **Pricing CMS** (owner): manage monthly plan config (Stripe Price ID + discount) in Django Admin
- **Deployment**: Render + Render Postgres

See `PLAN.md` for the full phased roadmap.

## Current implementation status

The codebase currently contains a **fresh SaaS-first scaffold** for:

- Django backend with multi-tenant-ready data model (`accounts`, `billing`, `devices`, `lessons`)
- Django Admin registrations for core CMS models (pricing plan, coupons, devices, lessons)
- Chrome extension skeleton with an options page to store a pairing code
- Docker Compose local development stack (Django + Postgres)

Google OAuth, Stripe checkout/webhooks, device pairing endpoints, and caption ingestion are planned next (see `PLAN.md`).

## Local development (Ubuntu + Docker Desktop)

### 1) Configure environment

Create a `.env` in the repo root (copy from `.env.example`) and set at minimum:

- `DJANGO_SECRET_KEY`
- `OPENAI_API_KEY`

Set a device-token signing secret (used for the planned device pairing flow):

- Add `DEVICE_TOKEN_SECRET` to `.env`.
- Generate a strong value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

- Restart Docker so Compose reloads the env file:

```bash
docker compose down
docker compose up --build
```

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
