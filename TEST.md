# Testing Guide (Phase 1)

Status: Phase 1 verified — 2026-02-13

Summary of what was validated:
- Google OAuth login via django-allauth (Google button renders and redirects)
- Subscriber settings form (save + reload)
- Authenticated dashboard shell
- Static assets served via WhiteNoise; Tailwind styling present on public pages

This guide describes how to verify Phase 1 features:
- Google OAuth login (django-allauth)
- Subscriber profile + settings
- Basic dashboard pages (templates)

## 0) Prerequisites

- .env contains:
  - `DJANGO_SECRET_KEY`
  - `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
  - Recommended: `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1`
- Sites framework is configured (Django Admin → Sites → Site 1):
  - Domain: `localhost:8000`
  - Display name: `Localhost`
- Services running and DB migrated:
  - `docker compose up -d web`
  - `docker compose run --rm web python manage.py migrate`

## 1) Test Google OAuth login

1. Visit `http://localhost:8000/accounts/login/`
2. Click the Google provider and complete consent
3. Expected results:
   - Redirects to `/` (dashboard)
   - You are authenticated (navbar shows `Settings` and a `Logout` button)
   - Admin → Users shows your user
   - Admin → Social accounts shows a Google entry for your user

Troubleshooting:
- Redirect URI mismatch: ensure this exact URI is configured in Google Cloud → Credentials → OAuth Client:
  - `http://localhost:8000/accounts/google/login/callback/`
- Loop back to login: confirm Admin → Sites domain is exactly `localhost:8000`
- Google button not visible: ensure `docker-compose.yml` forwards `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to the `web` service, then restart:

  ```bash
  docker compose down
  docker compose up --build
  ```

## 2) Test Subscriber profile + settings

1. Visit `http://localhost:8000/settings/` (must be logged in)
2. Change fields and save:
   - `grade_level` (e.g., "Grade 6")
   - `max_sentences` (e.g., 3)
3. Expected results:
   - Redirects back to `/settings/`
   - Form displays the saved values
   - Admin → Accounts → Subscriber profiles shows a profile for your user (auto-created by signal)

## 3) Test basic dashboard pages (templates)

1. Visit `http://localhost:8000/` while logged in
2. Expected results:
   - "Lessons" dashboard loads
   - With no lessons: shows "No lessons yet."
3. Optional: Create a lesson to see it listed
   - Admin → Lessons → Add Lesson (associate it with your user)
   - Refresh `/` to confirm it appears
4. Auth check:
   - Open an incognito/private window and visit `http://localhost:8000/`
   - Expected: redirected to `/accounts/login/`

## 4) Test logout

1. Click `Logout` in the navbar (POST form)
2. Expected results:
   - Redirects to `/accounts/login/`
   - Visiting `/` or `/settings/` now redirects to login

## 5) Static files sanity check (admin CSS/JS)

1. Open `http://localhost:8000/admin/`
2. Expected: admin styles and sidebar load
3. Direct static check:
   - Visit `http://localhost:8000/static/admin/css/base.css` → returns CSS content

If broken:
- Rebuild and restart the web container (WhiteNoise + collectstatic is configured):
  ```bash
  docker compose build web
  docker compose up -d web
  ```

## Quick commands reference

- Start services (build):
  ```bash
  docker compose up --build
  ```
- Migrate DB:
  ```bash
  docker compose run --rm web python manage.py migrate
  ```
- Create admin (superuser):
  ```bash
  docker compose run --rm web python manage.py createsuperuser
  ```
- Tail logs (web):
  ```bash
  docker compose logs -f web
  ```

## What’s next (Phase 2 preview)

- Add Stripe monthly subscription flow:
  - Checkout Session endpoint (uses Billing Plan’s Stripe Price ID from Admin)
  - Webhook handler to sync subscription status
  - Entitlement checks for caption ingest and Q&A
