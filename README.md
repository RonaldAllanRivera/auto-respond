# Meet Lessons — AI-Powered Q&A from Google Meet Captions

A **Django + Chrome Extension** app that listens to **Google Meet live captions**, detects questions in real time, and answers them using the **OpenAI API** — tailored to the student's grade level. Answers stream live to the web dashboard and the extension popup.

This repository is organized as a **single monorepo**:

- `backend/`: Django (accounts/billing/devices/lessons), Postgres integration, admin CMS models
- `extension/`: Chrome Extension (MV3) starter scaffold

## Product overview

- **Subscribers** sign in with **Google**, manage settings (grade level / answer length), and view lessons, transcripts, and Q&A.
- The **Chrome extension** reads Meet captions, **detects questions** (via interrogative keywords like *what*, *when*, *how*, etc., since Meet captions often omit `?`), and sends them to the backend.
- The backend creates a lesson per meeting (title + date) by default, or routes captions to a user-selected lesson.
- Detected questions are answered by the **OpenAI API** using lesson transcript context.
- **Answers stream in real time** on the subscriber dashboard and in the extension popup.
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

| Phase | Status |
|---|---|
| 0 — Repo hygiene & foundations | Completed |
| 1 — Multi-tenant accounts + dashboard shell | Completed & verified |
| 2 — Extension pairing + device security | Completed (backend + extension scaffold) |
| 3 — Meet captions ingestion + question detection | Backend completed; extension items pending |
| 4 — AI answering (streaming) | `POST /api/questions/` done; SSE + OpenAI next |

The codebase currently contains:

- **Backend**: Django with Google OAuth, device pairing API, caption ingestion API (`POST /api/captions/`, `POST /api/questions/`), server-side dedupe, auto-create lessons per meeting, admin CMS, Docker Compose stack
- **Extension**: Starter scaffold with options page (pairing flow) and background service worker (authenticated API helper)

Next up: AI answering with OpenAI streaming + SSE endpoint (Phase 4 backend). See `PLAN.md` for the full roadmap with **(backend)** / **(extension)** tags.

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

Set a strong Django secret key (required):

- Add `DJANGO_SECRET_KEY` to `.env`.
- Generate a strong value:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

- Restart Docker so Compose reloads the env file:

```bash
docker compose down
docker compose up --build
```

### 1.1) Google OAuth setup (get `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET`)

This project uses **django-allauth**. Google OAuth is optional for local development (you can still use `createsuperuser`), but required for the SaaS login flow.

1) Create an OAuth Client in Google Cloud

- Go to the Google Cloud Console: `https://console.cloud.google.com/`
- Create or select a project.
- Go to **APIs & Services**
  - **OAuth consent screen**
    - Choose **External** (or Internal if you’re on Google Workspace)
    - Fill in the app name + support email
    - Add yourself as a **Test user** (while the app is in testing)
  - **Credentials** -> **Create Credentials** -> **OAuth client ID**
    - Application type: **Web application**

2) Configure origins + redirect URIs

For local dev:

- Authorized JavaScript origins:
  - `http://localhost:8000`
- Authorized redirect URIs:
  - `http://localhost:8000/accounts/google/login/callback/`

For production, add the same two entries using your Render domain (HTTPS), e.g.

- `https://YOUR-SERVICE.onrender.com`
- `https://YOUR-SERVICE.onrender.com/accounts/google/login/callback/`

3) Copy the credentials into `.env`

Copy the **Client ID** and **Client secret** values into your repo-root `.env`:

- `GOOGLE_CLIENT_ID=...`
- `GOOGLE_CLIENT_SECRET=...`

4) Set Django Sites domain (required by allauth)

This is handled automatically by the `seed_site` management command which runs on container start. It sets Site 1 to `localhost:8000`.

For production, override with:

```bash
docker compose run --rm web python manage.py seed_site --domain=YOUR-SERVICE.onrender.com --name="Production"
```

### 2) Start services

```bash
docker compose up --build
```

The container automatically runs `migrate`, `collectstatic`, and `seed_site` on startup.

Create an admin user:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Open:

- Web UI: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`

Admin login notes:

- There are no default admin credentials.
- Use the username/email and password you set when running `createsuperuser`.

### 1.2) Django Admin setup

1) Log in to Admin

- Visit `http://localhost:8000/admin/`
- Log in with the superuser you created.

2) Configure the Sites framework (required by allauth)

This is auto-seeded on container start (`seed_site` command). To verify or change:

- Go to `Sites` → `Sites` in Admin (`/admin/sites/site/`)
- Site 1 should already have domain `localhost:8000`

For production, run:

```bash
python manage.py seed_site --domain=YOUR-SERVICE.onrender.com --name="Production"
```

3) (Optional) Configure Google Social Application in Admin

If you are NOT setting `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` in `.env`, you can configure them via Admin instead:

- Go to `Social Accounts` → `Social applications`
- Add a new app:
  - Provider: `Google`
  - Name: e.g. `Local Google`
  - Client id / Secret: paste from Google Cloud
  - Add `Site`: select `Localhost (localhost:8000)` and save

4) Manage pricing and coupons

- Billing Plan: `Billing → Billing plans` (store Stripe Monthly Price ID and discount)
- Coupons: `Billing → Coupon codes`

## Chrome Extension (Ubuntu + Windows 11)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder

## How to set up admin

- Create a superuser

```bash
docker compose run --rm web python manage.py createsuperuser
```

- Log in
  - Go to `http://localhost:8000/admin/`
  - Use the username/email and password you set in the previous step

This is also documented above under the Local development section.

## Engineering highlights (portfolio)

- Separation of concerns between web UI, API endpoints, and extension ingestion
- Security-first model (server-owned secrets, planned device pairing, planned Stripe webhook source-of-truth)
- Clear roadmap and deliverables (see `PLAN.md`)
