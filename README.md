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

## Chrome Extension setup + device pairing

### 3) Install the extension

1. Open **Google Chrome** (or any Chromium-based browser like Edge, Brave)
2. Navigate to `chrome://extensions`
3. Toggle **Developer mode** ON (top-right switch)
4. Click **Load unpacked**
5. Browse to the `extension/` folder inside this repo and select it
6. The extension should appear in the list as **Meet Lessons**

> **Tip:** Pin the extension to your toolbar — click the puzzle icon in Chrome's toolbar, then click the pin icon next to "Meet Lessons".

### 4) Pair the extension with your account

The extension needs a one-time pairing code to connect to your backend. No passwords or secrets are stored in the extension — only a server-issued device token.

**Step 1 — Generate a pairing code on the dashboard:**

1. Make sure the backend is running (`docker compose up --build`)
2. Log in at `http://localhost:8000/` (Google OAuth or superuser)
3. Click **Devices** in the navbar (or go to `http://localhost:8000/devices/`)
4. Click **Generate pairing code**
5. An 8-character code appears (e.g. `5074D63A`) with a live countdown — you have **10 minutes** to use it

**Step 2 — Enter the code in the extension:**

1. Right-click the Meet Lessons extension icon → **Options** (or click the extension → gear icon)
2. Confirm the **Backend URL** is `http://localhost:8000` and click **Save URL**
3. Enter the pairing code from step 1 into the **Pairing code** field
4. Click **Pair device**
5. You should see: ✅ **"Device paired successfully!"** and the UI switches to a "Paired" state

**Step 3 — Verify on the dashboard:**

1. Go back to `http://localhost:8000/devices/`
2. Your device should appear in the list (label: "Chrome Extension")
3. The pairing code is now used and no longer shown

### 5) Troubleshooting extension pairing

| Problem | Fix |
|---|---|
| "Network error" when pairing | Ensure Docker is running and backend URL is correct (`http://localhost:8000`) |
| CORS error in console | Set `DJANGO_DEBUG=1` in `.env` (enables `CORS_ALLOW_ALL_ORIGINS`) and restart |
| "Invalid pairing code" | Code is case-insensitive but must match exactly; check it hasn't expired (10 min) |
| "Pairing code expired or already used" | Generate a new code on `/devices/` |
| Extension not visible in Chrome | Ensure Developer mode is ON; check for errors on `chrome://extensions` |

### 6) Revoking / unpairing

- **From the dashboard:** Go to `/devices/`, click **Revoke** on any device. The extension will no longer be able to make API calls with that token.
- **From the extension:** Open extension options, click **Unpair device**. This clears the stored token locally. You'll need a new pairing code to reconnect.

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
