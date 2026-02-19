# Testing Guide (Phase 1-5)

Status:
- Phase 1 verified — 2026-02-14 (Google login, user dashboard, admin login/pages)
- Phase 2 verified — 2026-02-14 (device pairing UI + API)
- Phase 3 verified — 2026-02-14 (desktop capture pipeline + backend APIs, including Linux clipboard watcher fallback)
- Phase 4 verified — 2026-02-14 (AI answering + SSE streaming; answers visible on dashboard and in Django Admin records)
- Phase 5 verified — 2026-02-15 (Stripe Checkout subscription flow, webhook sync, entitlement checks)

Summary of what was validated:
- Google OAuth login via django-allauth
- Subscriber settings form (save + reload)
- Authenticated dashboard shell
- Static assets served via WhiteNoise
- Device pairing code generation + countdown timer on `/devices/`
- `POST /api/devices/pair/` — exchange code for device token
- `POST /api/captions/` — caption ingestion with server-side dedupe + auto-create lesson
- `POST /api/questions/` — question submission with AI answering (OpenAI)
- `GET /api/questions/<id>/stream/` — SSE streaming of AI answer tokens
- Device token auth (`X-Device-Token` header) — 401 on missing/invalid tokens
- Billing endpoints: `/billing/subscribe/`, `/billing/checkout/`, `/billing/portal/`, `/billing/webhook/`
- Subscription enforcement on AI answering when billing is configured

## 0) Prerequisites

- `.env` contains: `DJANGO_SECRET_KEY`, `DEVICE_TOKEN_SECRET`, `OPENAI_API_KEY`
- Optional: `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for OAuth
- Tesseract OCR installed: `sudo apt install tesseract-ocr`
- Services running: `docker compose up --build`

## 1) Test Google OAuth login

1. Visit `http://localhost:8000/accounts/login/`
2. Click Google and complete consent
3. Expected: redirects to `/` (dashboard), navbar shows Settings + Logout

## 2) Test Subscriber profile + settings

1. Visit `http://localhost:8000/settings/` (logged in)
2. Change grade_level and max_sentences, save
3. Expected: form displays saved values

## 3) Test dashboard pages

1. Visit `http://localhost:8000/` while logged in
2. Expected: "Lessons" dashboard loads
3. Auth check: incognito → `http://localhost:8000/` → redirected to login

## 4) Quick commands

```bash
docker compose up --build          # Start services
docker compose run --rm web python manage.py createsuperuser  # Create admin
docker compose logs -f web         # Tail logs
```

## 5) Test device pairing API

### 5a) Get a device token

1. Generate a pairing code on `/devices/`
2. Exchange it:
   ```bash
   curl -X POST http://localhost:8000/api/devices/pair/ \
     -H "Content-Type: application/json" \
     -d '{"code": "YOUR_CODE", "label": "curl test"}'
   ```
3. Save the `token` from the response.

### 5b) Auth failure tests

```bash
# No token → 401
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'

# Bad token → 401
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: fake-token" \
  -d '{"text": "test"}'
```

## 6) Test caption ingestion API

```bash
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{
    "meeting_id": "test-meeting-1",
    "meeting_title": "Math Class",
    "speaker": "",
    "text": "The teacher asked what is 2 plus 2. The student answered 4."
  }'
```

Expected:
- Response: `{"lesson_id": 1, "chunk_id": 1, "created": true}`
- A new Lesson appears in Admin (title: "Math Class")
- Sending the same text again returns `"created": false` (dedupe)

## 7) Test AI answering API

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{
    "question": "What is photosynthesis?",
    "context": "The teacher was explaining how plants make food using sunlight.",
    "meeting_title": "Biology Class"
  }'
```

Expected:
- Response includes: `"question_id"`, `"lesson_id"`, `"answer"` (AI-generated), `"latency_ms"`
- A QuestionAnswer record in Admin with the AI answer filled in
- Context stored as a TranscriptChunk

## 8) Test SSE streaming endpoint

Open in browser (must be logged in):

```
http://localhost:8000/api/questions/1/stream/
```

Expected:
- If already answered: single SSE event with `{"token": "full answer...", "done": true}`
- If not yet answered: stream of `{"token": "...", "done": false}` events, then `{"done": true}`

## 9) Test desktop app

```bash
cd desktop
pip install -r requirements.txt
python main.py
```

1. Ensure `desktop/.env` contains `MEET_LESSONS_URL=http://localhost:8000`
2. Enter pairing code from dashboard → click "Pair Device" → should show "✓ Paired"
3. Open Google Meet with CC enabled (or any app/page with readable text)
4. Press Print Screen → activity log should show:
   - "Screenshot captured — running OCR..."
   - "OCR done (XXms): ..."
   - "Caption sent → lesson X, chunk Y, new=True"
   - "Found N question(s): ..."
   - "Question sent → ID Z: ..."
5. Click **Unpair** and confirm capture is blocked:
   - manual capture button is disabled
   - Print Screen logs: "Not paired — pair your device first to enable capture"
6. Verify auto-unpair on backend revocation (no capture required):
   - revoke the device in the dashboard or make the subscription inactive
   - wait ~30s
   - expected: desktop app clears pairing and shows "Not paired" without any manual action
6. Open dashboard → click the lesson → see Q&A with AI answers

## 10) Test desktop app question detection

The detector finds questions via:
- WH-start questions (`what`, `when`, `where`, `who`, `why`, `how`, `which`, etc.), with or without `?`
- Math expressions, including fractions (e.g. `5 + 3`, `1/4 x 1/5`)
- URL/UI OCR noise is ignored (e.g. `docs.google.com/.../edit?`)

To test without a screenshot, use the API directly (step 7 above).

## 11) Test Stripe subscriptions (Phase 5)

### 11a) Prerequisites

- Root `.env` contains `STRIPE_SECRET_KEY`
- Root `.env` contains `STRIPE_WEBHOOK_SECRET`
- `BillingPlan` in Django Admin has a valid `stripe_monthly_price_id` (`price_...`)
- Billing plan is configured as flat monthly price: **$15.00 USD**
- Stripe webhook forwarding is running:

```bash
docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest listen --forward-to http://localhost:8000/billing/webhook/
```

### 11b) Checkout flow

1. Log in to dashboard
2. Open `/billing/subscribe/`
3. Click **Subscribe now**
4. Complete Stripe Checkout in test mode
5. Expected:
   - Redirect to `/billing/success/`
   - Stripe webhook events are received
   - User gets a synced `StripeSubscription` row in Django Admin

### 11c) Webhook sync checks

Expected in Django Admin:

- Billing → Stripe events: new events recorded (idempotent)
- Billing → Stripe subscriptions: status updates (`active`/`trialing`/etc.)

Optional test events:

```bash
docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest trigger customer.subscription.updated

docker run --rm -it --network=host \
  -v "$HOME/.config/stripe:/root/.config/stripe" \
  stripe/stripe-cli:latest trigger invoice.payment_failed
```

### 11f) Coupon codes

1. In Stripe Dashboard (Test mode), create:
   - a Coupon (percentage or amount)
   - a Promotion Code for that coupon (copy the Promotion Code ID: `promo_...`)
   - If you do not want to create a Promotion Code, you can also use the Stripe Coupon ID directly.
2. In Django Admin, create a `CouponCode` row:
   - `code`: the text users will type (e.g. `SAVE20`)
   - `stripe_promotion_code_id`: the Stripe Promotion Code ID (`promo_...`) or Coupon ID
   - optional: `expires_at`, `max_redemptions`
3. Open `/billing/subscribe/`, enter the coupon code, click **Subscribe now**.

Expected:
- Invalid/expired/over-limit coupons show an inline error on the subscribe page.
- Valid coupon redirects to Stripe checkout and shows the discount applied.
- After successful payment, the coupon `redeemed_count` increments (webhook-driven).

### 11d) Entitlement checks

When billing is configured and user has no active subscription:

- `POST /api/questions/` returns `403` with `{"error": "Subscription required"}`
- SSE endpoint returns `subscription_required` event for unanswered questions

When subscription is active:

- `POST /api/questions/` succeeds and returns AI answer payload as usual

### 11e) Device auto-revoke on inactive subscription

When billing is configured and user has no active subscription:

1. Open `/devices/`
2. Expected:
   - Active paired devices are automatically revoked
   - Pairing code generation is disabled
   - UI shows subscription-required notice
3. `POST /api/devices/pair/` with a valid code returns `403` with `{"error": "Subscription required"}`

When subscription becomes active again:

- User can generate a new pairing code and re-pair desktop device(s)

## Phase 7 — Render production hardening (verification)

### 7a) Local: confirm DEBUG=0 startup guard

Run with `DEBUG=0` and no `DJANGO_SECRET_KEY` set:

```bash
docker compose run --rm -e DJANGO_DEBUG=0 web python -c "import meet_lessons.settings"
```

Expected: `RuntimeError: DJANGO_SECRET_KEY must be set to a strong random value in production.`

### 7b) Local: confirm HTTPS settings are inactive in dev

With `DJANGO_DEBUG=1` (default), the following must NOT be set:

- `SECURE_SSL_REDIRECT` — would redirect all local HTTP to HTTPS and break dev
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` — would break cookie auth over HTTP

Verify by checking that the local dev stack (`docker compose up`) works normally with no HTTPS.

### 7c) Production (Render): CSRF_TRUSTED_ORIGINS

Set in Render environment:

```
DJANGO_CSRF_TRUSTED_ORIGINS=https://<your-service>.onrender.com
```

Expected: POST forms (subscribe, checkout, devices, settings) work without CSRF errors.

### 7d) Production (Render): HTTPS redirect

With `DJANGO_DEBUG=0` and `SECURE_SSL_REDIRECT=True`, any HTTP request should redirect to HTTPS automatically (Render handles TLS termination and sets `X-Forwarded-Proto: https`).

### 7e) Production: structured logging

Render log viewer should show structured lines like:

```
INFO 2026-02-18 10:00:00,000 views Caption received for user 1
WARNING 2026-02-18 10:00:01,000 billing Stripe key not configured
```

## Phase 10 — Windows desktop installer (verification) ✓

### 10a) Download button visibility ✓

- With `DESKTOP_DOWNLOAD_URL` **not set** (empty): the Download banner must **not** appear on `/devices/`.
- With `DESKTOP_DOWNLOAD_URL` set: the **Download for Windows** button must appear on `/devices/` and link to the correct URL.
- **Live URL (v1.0.6):** `https://github.com/RonaldAllanRivera/auto-respond/releases/download/v1.0.6/MeetLessonsInstaller.exe`

### 10b) GitHub Actions CI build ✓

- Push a `v*` tag → GitHub Actions spins up a Windows VM, downloads Tesseract dynamically, builds `MeetLessons.exe` with PyInstaller, compiles `MeetLessonsInstaller.exe` with Inno Setup 6, and publishes a GitHub Release automatically.
- First successful build: **`v1.0.6`** (all steps green).

### 10c) Install verification (pending — clean Windows VM)

On a **clean Windows VM** (no Python, no Tesseract):
- Run `MeetLessonsInstaller.exe` — Tesseract installs silently, app installs to `C:\Program Files\MeetLessons\`.
- Start Menu shortcut opens the app.
- Desktop shortcut opens the app (if selected during install).
- App connects to `https://meetlessons.onrender.com` automatically (no `.env` needed).
- Uninstall via Settings → Apps → Meet Lessons — app and shortcuts are removed cleanly.

### 10d) Shipping a new version

```bash
git tag v1.x.x
git push origin v1.x.x
```
GitHub Actions builds and publishes automatically. Update `DESKTOP_DOWNLOAD_URL` on Render to the new release URL.

## What's next (Phase 8)

- Dashboard realtime UX: latest Q&A panel on home, SSE/polling updates
