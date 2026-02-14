# Meet Lessons — AI-Powered Q&A from Google Meet Screenshots

A **Django + Python Desktop App** that captures **Google Meet captions via screenshots**, runs **local OCR**, detects questions, and answers them using the **OpenAI API** — tailored to the student's grade level. AI answers stream live on the web dashboard (the paywall).

This repository is organized as a **single monorepo**:

- `backend/`: Django (accounts/billing/devices/lessons/AI), Postgres, admin CMS
- `desktop/`: Python desktop app (screenshot capture, OCR, question detection, device pairing)

## Product overview

- **Subscribers** sign in with **Google**, manage settings (grade level / answer length), and view lessons, transcripts, and Q&A on the **web dashboard**.
- The **desktop app** captures screenshots (Print Screen hotkey), runs **local OCR** (Tesseract), and **detects questions** (interrogative keywords, `?`, math expressions).
- OCR text is sent to the backend as transcript chunks; detected questions are sent for AI answering.
- The backend calls **OpenAI** with the question + lesson transcript context + grade-level prompt.
- **AI answers stream live** on the subscriber dashboard via SSE — this is the **paywall**.
- The desktop app is a **free capture tool** — it shows pairing status and activity log only, never AI answers.

## Current implementation status

| Phase | Status |
|---|---|
| 0 — Repo hygiene & foundations | Completed |
| 1 — Multi-tenant accounts + dashboard shell | Completed |
| 2 — Device pairing + security | Completed |
| 3 — Screenshot capture + OCR + question detection | Completed |
| 4 — AI answering (streaming) | Completed |
| 5 — Stripe subscriptions | Planned |
| 6 — Coupons (admin CMS) | Planned |
| 7 — Render production hardening | Planned |

See `PLAN.md` for the full phased roadmap.

## Local development (Ubuntu + Docker Desktop)

### 1) Prerequisites

- **Docker** and **Docker Compose**
- **Python 3.10+** (for the desktop app)
- **Tesseract OCR** installed on the system:

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

### 2) Configure environment

Create a `.env` in the repo root (copy from `.env.example`) and set at minimum:

- `DJANGO_SECRET_KEY` — generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- `DEVICE_TOKEN_SECRET` — generate with: `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`
- `OPENAI_API_KEY` — required for AI answering

Create `desktop/.env` (copy from `desktop/.env.example`):

- `MEET_LESSONS_URL=http://localhost:8000` (local backend URL for desktop app)

### 3) Google OAuth setup (optional for local dev)

This project uses **django-allauth**. Google OAuth is optional for local development (you can use `createsuperuser`), but required for the SaaS login flow.

1. Go to Google Cloud Console → **APIs & Services** → **Credentials** → **Create OAuth client ID** (Web application)
2. Set authorized redirect URI: `http://localhost:8000/accounts/google/login/callback/`
3. Copy Client ID and Secret into `.env`:
   - `GOOGLE_CLIENT_ID=...`
   - `GOOGLE_CLIENT_SECRET=...`

### 4) Start the backend

```bash
docker compose up --build
```

The container automatically runs `migrate`, `collectstatic`, and `seed_site` on startup.

Create an admin user:

```bash
docker compose run --rm web python manage.py createsuperuser
```

Open:

- **Dashboard**: `http://localhost:8000/`
- **Admin**: `http://localhost:8000/admin/`

### 5) Set up the desktop app

```bash
cd desktop
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

The desktop app window opens with:
- **Device Pairing** section
- **Screenshot Capture** section with activity log
- Capture controls disabled until paired (paywall enforcement)

### 6) Pair the desktop app

**Step 1 — Generate a pairing code on the dashboard:**

1. Log in at `http://localhost:8000/` (Google OAuth or superuser)
2. Click **Devices** in the navbar (or go to `http://localhost:8000/devices/`)
3. Click **Generate pairing code**
4. An 8-character code appears (e.g. `5074D63A`) — you have **10 minutes** to use it

**Step 2 — Enter the code in the desktop app:**

1. Enter the pairing code in the **Pairing code** field
2. Click **Pair Device**
3. You should see: **"✓ Paired (device ...)"**

**Step 3 — Verify on the dashboard:**

1. Go to `http://localhost:8000/devices/`
2. Your device should appear in the list (label: "Desktop App")

### 7) Capture screenshots

1. Open **Google Meet** and enable **CC/subtitles**
2. Press **Print Screen** (or click "Capture Now" in the desktop app)
3. The app will:
   - Grab the screenshot from clipboard
   - Run OCR (~200ms)
   - Detect questions
   - Send text + questions to the backend
4. View AI answers on the **dashboard** → click the lesson → see Q&A with streaming answers

### 8) Troubleshooting

| Problem | Fix |
|---|---|
| "Network error" when pairing | Ensure Docker is running and `MEET_LESSONS_URL` in `desktop/.env` is correct |
| OCR returns no text | Ensure Tesseract is installed: `tesseract --version` |
| No image in clipboard | Press Print Screen first, or use "Capture Now" button |
| "Pairing code expired" | Generate a new code on `/devices/` |
| CORS error | Set `DJANGO_DEBUG=1` in `.env` and restart Docker |

### 9) Revoking / unpairing

- **From the dashboard:** Go to `/devices/`, click **Revoke** on any device.
- **From the desktop app:** Click **Unpair** to clear the stored token locally.

## Django Admin setup

```bash
docker compose run --rm web python manage.py createsuperuser
```

- Visit `http://localhost:8000/admin/`
- Sites framework is auto-configured by `seed_site` on startup
- Manage pricing: `Billing → Billing plans`
- Manage coupons: `Billing → Coupon codes`

## Engineering highlights (portfolio)

- **Desktop + Web SaaS architecture**: free capture tool + paid dashboard with AI answers
- **Local OCR** (Tesseract): no per-user API cost, fast (~200ms), works offline
- **OpenAI streaming**: SSE endpoint streams answer tokens live to the dashboard
- **Device pairing**: secure token-based auth without shipping secrets in the client
- **Multi-tenant isolation**: all data scoped to authenticated user
- **Server-side dedupe**: SHA-256 content hashing prevents duplicate transcript chunks
- Clear roadmap and deliverables (see `PLAN.md`)
