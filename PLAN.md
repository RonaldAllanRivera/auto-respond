# PLAN — Meet Lessons SaaS (Django + Desktop App → Screenshot OCR → AI Q&A)

## 1) Goal
Build a **single-repo SaaS** that:

- Lets subscribers sign in with **Google**.
- Captures **Google Meet captions** via a **Python desktop app** that takes screenshots and runs **local OCR** (Tesseract).
- Automatically stores OCR text as **Lessons** (auto-create per meeting title + date).
- **Detects questions** in the OCR text (desktop-side) and sends them to the backend for AI answering.
- Backend passes detected questions + lesson transcript context to the **OpenAI API** and returns the answer.
- **Answers are visible on the subscriber dashboard** (streaming tokens via SSE) — this is the paywall.
- The desktop app is a **free capture tool** that shows pairing status and activity log only (no answers).
- Provides a subscriber **dashboard** (settings, lessons, transcripts, Q&A history with streaming AI answers).
- Provides an owner **admin CMS** (you) to manage users, subscriptions, devices, coupons, and content.

Target deployment:

- **Render** for Django Web Service
- **Render Postgres** for database
- **Stripe** for subscriptions (monthly) + coupon codes

## 2) Security & configuration principles

- All server secrets stay in environment variables (Render env vars / `.env` locally).
- No shared secrets shipped in the desktop app.
- The desktop app authenticates via **device pairing** (one-time code) and server-issued tokens.
- Multi-tenant isolation: every row (lesson/transcript/Q&A/device/subscription) is scoped to a user account.
- **AI answers are only visible on the web dashboard** (paywall). The desktop app cannot display answers.

## 3) SaaS architecture (high level)

### 3.1 Backend (Django)
- Auth: Google OAuth sign-in.
- Billing: Stripe Checkout + Webhooks.
- Dashboard: lessons, transcripts, Q&A with streaming AI answers, settings, billing status.
- Admin CMS: Django Admin with curated models.
- **API endpoints** consumed by the desktop app:
  - `POST /api/devices/pair/` — exchange pairing code for device token
  - `POST /api/captions/` — ingest OCR text from screenshots
  - `POST /api/questions/` — submit detected question + context → returns AI answer
  - `GET /api/questions/<id>/stream/` — SSE stream of AI answer tokens (for dashboard)

### 3.2 Desktop app (Python + tkinter)

The `desktop/` folder contains the Python desktop capture tool.

Desktop app responsibilities:
- Listen for **Print Screen** hotkey (global keyboard listener via `pynput`).
- Grab screenshot from clipboard (`Pillow.ImageGrab`).
- Run **local OCR** via Tesseract (`pytesseract`) — no API cost, ~200ms per image.
- **Question detection**: scan OCR text for interrogative keywords (`what`, `when`, `where`, `who`, `why`, `how`, `is`, `are`, `do`, `does`, `did`, `can`, `could`, `will`, `would`, `should`), trailing `?`, and math expressions.
- Send full OCR text to `POST /api/captions/` for transcript storage.
- Send detected questions to `POST /api/questions/` for AI answering.
- Show **pairing status** and **activity log** only (no AI answers — those are on the dashboard).
- One-time pairing flow (subscriber copies a pairing code from the web dashboard).

### 3.3 Real-time Q&A flow
1. Student opens Google Meet with CC/subtitles enabled.
2. Student presses **Print Screen** → desktop app grabs the screenshot.
3. Desktop app runs local OCR (Tesseract, ~200ms).
4. Desktop app detects questions via interrogative keywords, `?`, and math patterns.
5. Desktop app sends OCR text to `POST /api/captions/` (transcript storage).
6. Desktop app sends detected questions to `POST /api/questions/` (AI answering).
7. Backend retrieves transcript context for the lesson.
8. Backend calls OpenAI API with: question + transcript context + grade-level prompt.
9. Backend stores the answer and returns it in the API response.
10. **Dashboard** displays the answer via SSE streaming (`GET /api/questions/<id>/stream/`).
11. Target: answer visible within **5 seconds** of question submission.

## 4) Authentication model

### 4.1 Subscriber login
- Users log in on the web app via **Sign in with Google**.

### 4.2 Desktop app pairing (no secrets in the app)
- Subscriber signs in on the dashboard and generates a short-lived pairing code.
- Desktop app accepts the pairing code once.
- Backend issues a device token.
- Desktop app stores the token locally (`~/.meet_lessons/config.json`).
- Desktop app uses that token for all API requests (`X-Device-Token` header).

## 5) Stripe billing (monthly subscription)

### 5.1 Product & Price
- Create a single Stripe Price:
  - Monthly subscription

We will compute "equivalent" weekly/daily pricing for display/marketing only (no separate weekly/daily subscriptions).

### 5.2 Checkout flow
- Subscriber clicks "Upgrade" in dashboard.
- Backend creates a Stripe Checkout Session for the Monthly plan.
- After payment, Stripe redirects back to the dashboard.

### 5.3 Webhooks (source of truth)
Handle:

- `checkout.session.completed`
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `invoice.paid` / `invoice.payment_failed`

Backend updates local subscription state used for entitlement checks.

### 5.4 Coupon codes
Implement **coupon codes** with an admin-managed CMS.

Recommended approach:

- Use Stripe **Coupons + Promotion Codes** as the billing source of truth.
- Store a local `Coupon` model that maps:
  - `code`
  - `stripe_promotion_code_id`
  - `active`, `max_redemptions`, `expires_at`
- Admin can create/disable coupon codes in Django Admin.
- At checkout creation time, backend applies the promotion code if valid.

### 5.5 Pricing CMS (Admin)

- Add a `BillingPlan` model managed in Django Admin that stores:
  - Monthly price (cents)
  - Monthly discount percent (default: 20%)
  - Stripe Price ID (monthly)
- Backend uses this model to:
  - render pricing on the subscriber dashboard
  - attach the correct Stripe Price ID during Checkout

## 6) Data model (multi-tenant)

- `User` (Django auth)
- `SubscriberProfile`
  - user FK
  - defaults: grade level, max sentences
- `Subscription`
  - user FK
  - stripe customer id, subscription id, status, current period end, plan type
- `Device`
  - user FK
  - label, last_seen_at, token hash, revoked_at
- `Lesson`
  - user FK
  - title, meeting_id, meeting_date
- `TranscriptChunk`
  - lesson FK
  - speaker, text, content_hash, captured_at
- `QuestionAnswer`
  - lesson FK nullable
  - question, answer, model, latency_ms
- `Coupon`
  - code, stripe promotion code id, active flags

## 7) Subscriber dashboard scope

- Subscription status + upgrade/manage billing
- Settings:
  - grade level (e.g. Grade 3)
  - max sentences (1–2)
- Lessons:
  - view auto-created lessons (from desktop app captures)
  - view transcript and Q&A history with **streaming AI answers**
- Pair desktop app:
  - generate pairing code
  - view connected devices and revoke

## 8) Owner (admin) CMS scope

Use Django Admin as the primary CMS:

- Users / subscriber profiles
- Subscriptions (synced from Stripe)
- Devices (revoke, audit last seen)
- Coupons (create/disable)
- Lessons / transcripts / Q&A

## 9) Deployment to Render

- Render Web Service running Django (Docker or native build)
- Render Postgres
- Environment variables configured in Render dashboard
- Stripe webhook endpoint exposed publicly (Render URL)

## 10) Phased implementation plan

### Phase 0 — Repo hygiene & foundations (Completed)
- Lock monorepo structure (`backend/`, `desktop/`)
- Environment variable contract documented

### Phase 1 — Multi-tenant accounts + dashboard shell (Completed)
- Google OAuth login ✓
- Subscriber profile + settings (grade level, max sentences) ✓
- Basic dashboard pages (templates) ✓

### Phase 2 — Device pairing + security (Completed)
- **(backend)** Pairing code generation in dashboard ✓
- **(backend)** `POST /api/devices/pair/` endpoint ✓
- **(backend)** Device token issue, verify, revoke ✓
- **(backend)** Dashboard UI: devices list + revoke ✓
- **(desktop)** Pairing UI in tkinter app ✓

### Phase 3 — Screenshot capture + OCR + question detection
- **(backend)** `POST /api/captions/` endpoint — receive + store OCR text
- **(backend)** Server-side dedupe via content_hash
- **(backend)** Auto-create lesson per meeting title + date
- **(desktop)** Print Screen hotkey listener (pynput)
- **(desktop)** Clipboard screenshot capture (Pillow ImageGrab)
- **(desktop)** Local OCR via Tesseract (pytesseract)
- **(desktop)** Question detection (interrogative keywords + `?` + math patterns)
- **(desktop)** Send captions and questions to backend API
- **(desktop)** Activity log in tkinter UI

### Phase 4 — AI answering
- **(backend)** `POST /api/questions/` calls OpenAI API synchronously
- **(backend)** Retrieves transcript chunks for the lesson as context
- **(backend)** Builds prompt with question + transcript + grade-level setting
- **(backend)** Persists `QuestionAnswer` record with answer, model, latency
- **(backend)** `GET /api/questions/<id>/stream/` SSE endpoint for dashboard
- **(backend)** Dashboard lesson detail page with SSE streaming Q&A display
- **(backend)** `EventSource` JS renders answer tokens live

### Phase 5 — Stripe subscriptions (monthly)
- Stripe Checkout Session creation
- Stripe webhook handler + subscription sync
- Entitlement checks on caption ingest and AI answering

### Phase 6 — Coupons (admin CMS)
- `Coupon` model + Django Admin
- Apply coupon code in checkout flow
- Validation rules (active, expiry, redemption limits)

### Phase 7 — Render production hardening
- Proper `ALLOWED_HOSTS`, HTTPS settings
- Static files strategy
- DB migrations on deploy
- Admin hardening and logging

## 11) Testing the desktop app (Phase 2–4)

### 11.1 Prerequisites

**System dependencies:**

```bash
# Ubuntu/Debian
sudo apt install tesseract-ocr xclip

# macOS
brew install tesseract
```

Verify Tesseract is installed:

```bash
tesseract --version
```

**Backend running:**

```bash
docker compose up --build
```

Create a superuser if you don't have one:

```bash
docker compose run --rm web python manage.py createsuperuser
```

**Desktop app dependencies:**

```bash
cd desktop
python -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Desktop app environment:

```bash
cp desktop/.env.example desktop/.env
# local dev
# MEET_LESSONS_URL=http://localhost:8000
```

### 11.2 Phase 2 — Device pairing

**Test: Pair the desktop app with your account**

1. Start the desktop app:
   ```bash
   cd desktop
   .venv/bin/python main.py
   ```
2. Ensure `desktop/.env` has `MEET_LESSONS_URL=http://localhost:8000`.
3. Log in to the dashboard at `http://localhost:8000/` (Google OAuth or superuser).
4. Go to **Devices** (`http://localhost:8000/devices/`).
5. Click **Generate pairing code** — note the 8-character code (e.g. `5074D63A`).
6. In the desktop app, enter the code in the **Pairing code** field.
7. Click **Pair Device**.

Expected:
- Activity log shows: `Pairing with code 5074D63A...` then `Paired successfully! Device ID: xxxxxxxx...`
- Status changes to: `✓ Paired (device xxxxxxxx...)`
- Pairing code entry and Pair button become disabled.
- On the dashboard `/devices/` page, a new device appears (label: "Desktop App").

**Test: Unpair the desktop app**

1. Click **Unpair** in the desktop app.
2. Expected:
   - Activity log shows: `Device unpaired.`
   - Status changes to: `Not paired — enter a pairing code from the dashboard`
   - Pairing code entry and Pair button become enabled again.

**Test: Pairing error cases**

| Action | Expected |
|---|---|
| Click "Pair Device" with empty code | Warning dialog: "Enter a pairing code first." |
| Enter an expired code (wait >10 min) | Activity log: `Pairing failed: ...` + error dialog |
| Enter a wrong/random code | Activity log: `Pairing failed: ...` + error dialog |
| Enter code while backend is down | Activity log: `Pairing failed: ...` (network error) |

### 11.3 Phase 3 — Screenshot capture + OCR + question detection

**Prerequisite:** Desktop app must be paired (complete Phase 2 test first).

**Test: Capture a screenshot with Print Screen**

1. Open **Google Meet** (or any page with text) and enable **CC/subtitles**.
2. Press **Print Screen** on your keyboard.
3. Switch to the desktop app window.

Expected activity log output (in order):
```
Screenshot captured — running OCR...
OCR done (XXXms): [first 100 chars of extracted text]...
Caption sent → lesson 1, chunk 1, new=True
Found N question(s): [first question]...
Question sent → ID 1: [question text]
```

**Test: Manual capture button**

1. Take a screenshot first (Print Screen) so the clipboard has an image.
2. Click **Capture Now (Manual)** in the desktop app.
3. Expected: same activity log output as above.

**Test: Capture with no image in clipboard**

1. Copy some text (not an image) to the clipboard.
2. Click **Capture Now (Manual)**.
3. Expected: `No image in clipboard — capturing screen` then proceeds with full-screen capture.

**Test: Capture while not paired**

1. Click **Unpair** first.
2. Press Print Screen or click **Capture Now**.
3. Expected:
   ```
   Not paired — pair your device first to enable capture
   ```
   - Manual capture button stays disabled while unpaired.

**Test: OCR quality check**

1. Open a page with clear, large text (e.g. Google Meet captions with CC enabled).
2. Press Print Screen.
3. Check the activity log — the OCR text should be readable and match the screen content.
4. If OCR returns no text: ensure Tesseract is installed and the screenshot contains actual text.

**Test: Question detection**

The detector recognizes three types of questions:

| Input text | Detected as |
|---|---|
| `What is photosynthesis?` | Question mark sentence |
| `How do plants make food` | Interrogative keyword (adds `?`) |
| `5 + 3` | Math expression → `What is 5 + 3?` |
| `The sky is blue.` | Not detected (no question) |

To test without screenshots, use curl directly:

```bash
# Send a caption with a question in it
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{"meeting_title": "Test Class", "speaker": "", "text": "What is the capital of France?"}'

# Send a question for AI answering
curl -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{"question": "What is the capital of France?", "context": "The teacher was discussing European geography.", "meeting_title": "Test Class"}'
```

**Test: Server-side dedupe**

1. Press Print Screen on the same screen twice (same text).
2. Expected:
   - First capture: `Caption sent → lesson X, chunk Y, new=True`
   - Second capture: `Caption sent → lesson X, chunk Z, new=False`

### 11.4 Phase 4 — AI answering + streaming dashboard

**Prerequisite:** `OPENAI_API_KEY` must be set in `.env` and Docker restarted.

**Test: AI answers via desktop app capture**

1. Open Google Meet with CC enabled (or any page with a question visible).
2. Press Print Screen to capture a question.
3. Activity log should show: `Question sent → ID X: [question]`
4. Open the dashboard → click the lesson → scroll to **Questions & Answers**.
5. Expected: the question appears with an AI-generated answer.

**Test: Streaming AI answers on dashboard**

1. Submit a question (via desktop app or curl).
2. Open the lesson detail page on the dashboard.
3. Expected: the answer streams in token-by-token via SSE (visible as text appearing progressively).
4. After streaming completes, the full answer is displayed.

**Test: AI answer via curl**

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{
    "question": "What is photosynthesis?",
    "context": "The teacher explained how plants convert sunlight into energy.",
    "meeting_title": "Biology Class"
  }'
```

Expected response:
```json
{
  "question_id": 1,
  "lesson_id": 1,
  "answer": "Photosynthesis is the process...",
  "model": "gpt-4o-mini",
  "latency_ms": 2500
}
```

**Test: SSE streaming endpoint**

Open in browser (must be logged in to the dashboard):

```
http://localhost:8000/api/questions/1/stream/
```

Expected: SSE events with `{"token": "...", "done": false}` followed by `{"done": true}`.

**Test: Dashboard auto-refresh**

1. Open a lesson detail page on the dashboard.
2. From the desktop app, capture a new screenshot with a question.
3. Expected: the new Q&A appears on the dashboard within a few seconds (auto-refresh).

### 11.5 End-to-end test (full flow)

Run through the complete flow in one session:

1. `docker compose up --build` — start backend
2. `cd desktop && .venv/bin/python main.py` — start desktop app
3. Pair the desktop app (generate code on `/devices/`, enter in app)
4. Open Google Meet → enable CC → join or start a meeting
5. Wait for the teacher/speaker to ask a question
6. Press **Print Screen**
7. Check desktop app activity log — should show OCR text, caption sent, question detected and sent
8. Open dashboard → click the lesson → see the question with a streaming AI answer
9. Verify answer appears within ~5 seconds of the capture

### 11.6 Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError: No module named 'pytesseract'` | Run `pip install -r requirements.txt` in `desktop/` |
| `tesseract is not installed or not in PATH` | Install Tesseract: `sudo apt install tesseract-ocr` |
| OCR returns empty text | Ensure the screenshot has readable text; try larger font/zoom |
| `ConnectionError` when sending captions | Ensure backend is running: `docker compose up` |
| "Not paired" after restart | Config is stored in `~/.meet_lessons/config.json` — re-pair if needed |
| Print Screen not detected | On some Linux DEs, Print Screen is intercepted by the screenshot tool. Try running with `sudo` or disable the system screenshot shortcut |
| `tkinter` not found | Install: `sudo apt install python3-tk` |
| No AI answer returned | Ensure `OPENAI_API_KEY` is set in `.env` and Docker is restarted |

## 12) Non-goals (for MVP)

- Chrome extension (abandoned — Google Meet DOM too brittle)
- Audio capture / speech-to-text from raw audio
- Multi-language OCR support
- Offline/local AI models
- Showing AI answers in the desktop app (paywall: answers only on dashboard)
