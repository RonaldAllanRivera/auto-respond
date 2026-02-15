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

## What's next (Phase 6)

- Coupons:
  - Coupon model + admin workflows
  - Coupon application in Checkout
