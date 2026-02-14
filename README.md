# Meet Lessons

**AI-assisted Q&A from screenshots using Django + Python desktop OCR.**

Meet Lessons is a full-stack SaaS-style project where a Python desktop client captures screenshots, extracts text locally with Tesseract, detects likely questions, and sends them to a Django backend for AI answering. Answers stream live in the web dashboard via SSE.

---

## Table of contents

- [Project highlights](#project-highlights)
- [Architecture at a glance](#architecture-at-a-glance)
- [Core capabilities](#core-capabilities)
- [Current implementation status](#current-implementation-status)
- [Tech stack](#tech-stack)
- [API contract (desktop ↔ backend)](#api-contract-desktop--backend)
- [Quickstart (local)](#quickstart-local)
- [Validation summary (verified)](#validation-summary-verified)
- [Troubleshooting](#troubleshooting)
- [What’s next](#whats-next)

---

## Project highlights

- **End-to-end product thinking**: desktop client + backend APIs + dashboard UX + admin workflows.
- **Security-conscious architecture**: no shared client secrets; device pairing with server-issued tokens.
- **Cost-aware ML integration**: local OCR (Tesseract) + targeted OpenAI calls only for detected questions.
- **Production-minded reliability**: dedupe, paywall enforcement, SSE streaming, Linux capture fallbacks.
- **Multi-tenant SaaS patterns**: per-user data isolation across lessons, transcripts, devices, and Q&A.

---

## Architecture at a glance

### Monorepo layout

- `backend/` — Django app (accounts, devices, lessons, billing, OpenAI integration)
- `desktop/` — Python tkinter app (capture, OCR, question detection, pairing)

### Data flow

1. User captures text via desktop app (`Print Screen` or clipboard watcher fallback).
2. Desktop app runs local OCR (Tesseract).
3. Desktop app filters OCR noise (URLs/UI junk), detects questions, and submits:
   - `POST /api/captions/`
   - `POST /api/questions/`
4. Backend stores transcript, builds prompt with user settings, calls OpenAI.
5. Dashboard streams answer tokens via `GET /api/questions/<id>/stream/`.

---

## Core capabilities

- Google OAuth login (django-allauth)
- Subscriber settings (grade level, max sentences)
- Device pairing (`POST /api/devices/pair/`) with revocation
- Screenshot OCR ingestion + server-side dedupe
- Question detection:
  - WH-start questions (`what`, `where`, `when`, `how`, etc.)
  - math expressions (including fractions like `1/4 x 1/5`)
  - URL/UI noise filtering (e.g., `docs.google.com/.../edit?` is ignored)
- AI answers stored and streamed in dashboard (SSE)
- Desktop paywall behavior: capture blocked while unpaired

---

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

See `PLAN.md` for detailed phased deliverables.

---

## Tech stack

### Backend
- Django
- PostgreSQL
- django-allauth (Google OAuth)
- WhiteNoise (static files)
- OpenAI API

### Desktop
- Python + tkinter
- Pillow (`ImageGrab`)
- pytesseract + Tesseract OCR
- pynput (global hotkey)

### Infra / DevEx
- Docker Compose
- Render (target deployment)

---

## API contract (desktop ↔ backend)

- `POST /api/devices/pair/` — exchange pairing code for device token
- `POST /api/captions/` — ingest OCR transcript chunks
- `POST /api/questions/` — submit detected question + context, return AI answer
- `GET /api/questions/<id>/stream/` — stream answer tokens via SSE (dashboard)

---

## Quickstart (local)

### 1) Prerequisites

- Docker + Docker Compose
- Python 3.10+
- Tesseract OCR

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr

# macOS
brew install tesseract
```

### 2) Configure environment

Copy `.env.example` → `.env` and set:

- `DJANGO_SECRET_KEY`
- `DEVICE_TOKEN_SECRET`
- `OPENAI_API_KEY`

Copy `desktop/.env.example` → `desktop/.env`:

- `MEET_LESSONS_URL=http://localhost:8000`

### 3) Start backend

```bash
docker compose up --build
docker compose run --rm web python manage.py createsuperuser
```

Open:

- Dashboard: `http://localhost:8000/`
- Admin: `http://localhost:8000/admin/`

### 4) Start desktop app

```bash
cd desktop
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

### 5) Pair device and capture

1. Generate pairing code in dashboard (`/devices/`)
2. Pair in desktop app
3. Capture text from Google Meet or any readable screen
4. Open lesson detail in dashboard and confirm streamed answers

---

## Validation summary (verified)

- Desktop capture pipeline is working end-to-end
- AI answers are visible in dashboard and persisted in Django Admin
- Device pairing, dashboard, admin pages, and auth flows are working

Detailed test checklist: `TEST.md`

---

## Troubleshooting

| Problem | Fix |
|---|---|
| Pairing network errors | Confirm backend is running and `MEET_LESSONS_URL` is correct in `desktop/.env` |
| OCR returns empty text | Confirm `tesseract --version` and capture readable text |
| Print Screen not detected on Linux | Use clipboard watcher flow (`Print Screen` → select → `Ctrl+C`) |
| No AI answer | Confirm `OPENAI_API_KEY` in `.env`, then restart backend |

### Linux dock/icons keep moving (CPU wakeups)

The clipboard watcher polls to support reliable capture on Linux desktops where hotkeys are intercepted. If UI wakeups still feel high, tune:

- `MeetLessonsApp._CLIPBOARD_POLL_MS_MIN`
- `MeetLessonsApp._CLIPBOARD_POLL_MS_MAX`

File: `desktop/main.py`

---

## What’s next

- Stripe subscriptions (Checkout + webhook sync + entitlement checks)
- Coupon management in Admin
- Render production hardening

See `PLAN.md` and `CHANGELOG.md` for ongoing milestones.
