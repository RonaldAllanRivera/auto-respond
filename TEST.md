# Testing Guide (Phase 1, 2 & 3)

Status:
- Phase 1 verified — 2026-02-13
- Phase 2 backend verified — 2026-02-13 (pairing code generation tested; extension pairing pending extension install)
- Phase 3 backend verified — 2026-02-13 (caption + question APIs tested via curl/Python)

Summary of what was validated:
- Google OAuth login via django-allauth (Google button renders and redirects)
- Subscriber settings form (save + reload)
- Authenticated dashboard shell
- Static assets served via WhiteNoise; Tailwind styling present on public pages
- Device pairing code generation + countdown timer on `/devices/`
- `POST /api/devices/pair/` — exchange code for device token
- `POST /api/captions/` — caption ingestion with server-side dedupe + auto-create lesson
- `POST /api/questions/` — question submission with context storage
- Device token auth (`X-Device-Token` header) — 401 on missing/invalid tokens

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

## 7) Test caption ingestion API (Phase 3)

These endpoints require a device token. To get one for testing, either:
- Pair via the extension, or
- Use curl to pair manually (see step 7a).

### 7a) Get a device token for testing

1. Generate a pairing code on `/devices/`
2. Exchange it:
   ```bash
   curl -X POST http://localhost:8000/api/devices/pair/ \
     -H "Content-Type: application/json" \
     -d '{"code": "YOUR_CODE", "label": "curl test"}'
   ```
3. Save the `token` from the response.

### 7b) POST /api/captions/

```bash
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{
    "meeting_id": "abc-defg-hij",
    "meeting_title": "Math Class",
    "speaker": "Teacher",
    "text": "What is 2 plus 2?"
  }'
```

Expected:
- Response: `{"lesson_id": 1, "chunk_id": 1, "created": true}`
- A new Lesson appears in Admin (title: "Math Class", meeting_id: "abc-defg-hij")
- A TranscriptChunk is created under that lesson
- Sending the same caption again returns `"created": false` (dedupe)

### 7c) Auto-create lesson per meeting

Send captions with different `meeting_id` values:
- Same `meeting_id` + same date → same lesson
- Different `meeting_id` → new lesson
- No `meeting_id` → always creates a new lesson

### 7d) Manual lesson selection

```bash
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{"lesson_id": 1, "speaker": "Student", "text": "Is it 4?"}'
```

Expected: caption stored under lesson ID 1 (no auto-create).

### 7e) POST /api/questions/

```bash
curl -X POST http://localhost:8000/api/questions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: YOUR_TOKEN" \
  -d '{
    "question": "What is photosynthesis?",
    "context": "The teacher was explaining how plants make food using sunlight.",
    "meeting_id": "abc-defg-hij",
    "meeting_title": "Biology Class"
  }'
```

Expected:
- Response: `{"question_id": 1, "lesson_id": 2}`
- A QuestionAnswer record in Admin with empty answer (Phase 4 will fill it)
- Context stored as a TranscriptChunk

### 7f) Auth failure tests

```bash
# No token
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -d '{"text": "test"}'
# Expected: 401 "Missing X-Device-Token header"

# Bad token
curl -X POST http://localhost:8000/api/captions/ \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: fake-token" \
  -d '{"text": "test"}'
# Expected: 401 "Invalid or revoked device token"
```

## What's next (Phase 4 preview)

- AI answering (streaming):
  - OpenAI API integration with streaming mode
  - SSE endpoint for live answer tokens
  - Dashboard EventSource JS for live rendering
  - QuestionAnswer record persisted after stream completes
