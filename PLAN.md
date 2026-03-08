# PLAN — Meet Lessons SaaS (Django + Desktop App → Screenshot OCR → AI Q&A)

## Table of contents

- [1) Goal](#1-goal)
- [2) Security & configuration principles](#2-security--configuration-principles)
- [3) SaaS architecture (high level)](#3-saas-architecture-high-level)
- [4) Authentication model](#4-authentication-model)
- [5) Stripe billing (monthly subscription)](#5-stripe-billing-monthly-subscription)
- [6) Data model (multi-tenant)](#6-data-model-multi-tenant)
- [7) Subscriber dashboard scope](#7-subscriber-dashboard-scope)
- [8) Owner (admin) CMS scope](#8-owner-admin-cms-scope)
- [9) Deployment to Render](#9-deployment-to-render)
- [10) Phased implementation plan](#10-phased-implementation-plan)
- [11) Testing](#11-testing)
- [12) Non-goals (for MVP)](#12-non-goals-for-mvp)

Related docs:

- `README.md` — project overview + setup guides
- `ENV.md` — environment variable contract
- `TEST.md` — step-by-step verification checklists
- `CHANGELOG.md` — historical record of changes

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
- **Question detection**: scan OCR text for WH-start questions (`what`, `when`, `where`, `who`, `why`, `how`, `which`, etc.; with or without `?`) and math expressions (including fractions like `1/4 x 1/5`), while filtering URL/UI OCR noise.
- Send full OCR text to `POST /api/captions/` for transcript storage.
- Send detected questions to `POST /api/questions/` for AI answering.
- Show **pairing status** and **activity log** only (no AI answers — those are on the dashboard).
- Periodically re-validate device token (~30s) and auto-unpair when backend access is revoked (e.g., subscription inactive).
- One-time pairing flow (subscriber copies a pairing code from the web dashboard).

### 3.3 Real-time Q&A flow
1. Student opens Google Meet with CC/subtitles enabled.
2. Student presses **Print Screen** → desktop app grabs the screenshot.
3. Desktop app runs local OCR (Tesseract, ~200ms).
4. Desktop app detects questions via WH-start patterns and math expressions (including fractions), and filters URL/UI OCR noise.
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
Coupon codes are admin-managed and backed by Stripe.

Best-practice approach:

- Use Stripe **Coupons + Promotion Codes** as the billing source of truth.
- Store a local `CouponCode` record that maps:
  - `code` (what the user types)
  - `stripe_promotion_code_id` (`promo_...`)
  - `active`, `max_redemptions`, `expires_at`
- Validate the code before creating the Checkout Session.
- Increment redemption usage via webhook (idempotent) after successful checkout.

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
- `CouponCode`
  - code, stripe promotion code id, active, expiry, max redemptions, redeemed count

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
- Stripe webhook destination exposed publicly (Render URL, configured via Workbench)

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

### Phase 3 — Screenshot capture + OCR + question detection (Completed)
- **(backend)** `POST /api/captions/` endpoint — receive + store OCR text ✓
- **(backend)** Server-side dedupe via content_hash ✓
- **(backend)** Auto-create lesson per meeting title + date ✓
- **(desktop)** Print Screen hotkey listener (pynput) ✓
- **(desktop)** Clipboard screenshot capture (Pillow ImageGrab) ✓
- **(desktop)** Local OCR via Tesseract (pytesseract) ✓
- **(desktop)** Question detection (WH-start + optional `?` + math/fractions + URL/UI filtering) ✓
- **(desktop)** Send captions and questions to backend API ✓
- **(desktop)** Activity log in tkinter UI ✓

### Phase 4 — AI answering (Completed)
- **(backend)** `POST /api/questions/` calls OpenAI API synchronously ✓
- **(backend)** Retrieves transcript chunks for the lesson as context ✓
- **(backend)** Builds prompt with question + transcript + grade-level setting ✓
- **(backend)** Persists `QuestionAnswer` record with answer, model, latency ✓
- **(backend)** `GET /api/questions/<id>/stream/` SSE endpoint for dashboard ✓
- **(backend)** Dashboard lesson detail page with SSE streaming Q&A display ✓
- **(backend)** `EventSource` JS renders answer tokens live ✓

### Phase 5 — Stripe subscriptions (monthly) (Completed)
- Flat monthly plan: $15.00 USD ✓
- Stripe Checkout Session creation ✓
- Stripe webhook handler + subscription sync ✓
- Entitlement checks on AI answering ✓
- Auto-revoke paired devices on `/devices/` when subscription is inactive/ended ✓
- Billing subscribe page UX emphasizes importance with pricing clarity, trust signals, and next steps ✓
- Billing portal session flow ✓

### Phase 6 — Coupons (admin CMS) (Completed)
- `CouponCode` model + Django Admin (maps local code → Stripe Promotion Code ID or Coupon ID) ✓
- Coupon code field on `/billing/subscribe/` applied during Stripe Checkout Session creation ✓
- Validation rules: active flag, expiry timestamp, max redemptions (tracked via webhook) ✓

### Phase 7 — Render production hardening (Completed)
- Proper `ALLOWED_HOSTS` from env var ✓
- HTTPS security headers: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, HSTS ✓
- `CSRF_TRUSTED_ORIGINS` from env var (required for Render HTTPS POST forms) ✓
- `SECRET_KEY` startup guard: raises `RuntimeError` if default key used in production ✓
- Static files via WhiteNoise + `collectstatic` at container start ✓
- DB migrations run at container start (`migrate --noinput`) ✓
- Structured console logging (`LOGGING` config) ✓
- Gunicorn (production WSGI server) in Dockerfile CMD ✓

### Deploy checkpoint — Render production deploy (Completed 2026-02-24)
- Push all completed phases to `main` and trigger a Render redeploy. ✓
- Migrate from Render Postgres to Neon Postgres (free tier, no expiry). ✓
- Set `DATABASE_URL` on Render to Neon connection string. ✓
- Set `SITE_ID=1` on Render environment. ✓
- Fix Google OAuth `MultipleObjectsReturned` error (removed programmatic APP config from settings.py). ✓
- Configure Google OAuth via Django Admin (Social Applications). ✓
- Set `DESKTOP_DOWNLOAD_URL` on Render environment (same GitHub Releases URL as local `.env`). ✓
- Verify `/devices/` shows the **Download for Windows** button in production. ✓
- Verify Google login works end-to-end on Render. ✓
- Configure Stripe production webhook destination (new Stripe UI: Workbench → Add destination → 3-step wizard). ✓
- Set `STRIPE_WEBHOOK_SECRET` on Render. ✓
- Configure `BillingPlan.stripe_monthly_price_id` in Django Admin. ✓
- Successfully tested 3 subscriptions in production ($15/month). ✓
- **Remaining:** Verify device pairing, smoke-test full student flow (pair device → capture question → see AI answer on dashboard).

### Phase 8 — Dashboard realtime UX (Django templates, pre-Next.js)
- Add **"Latest Q&A" panel** on `/` (dashboard home) — shows the most recent question + AI answer for the logged-in user.
- Add a lightweight **session-auth JSON endpoint** (`GET /api/lessons/latest/`) returning the latest N Q&A pairs.
- Use **JavaScript polling** (every 3–5 s) on the dashboard home to refresh the panel without a page reload.
  - Polling is simpler and more reliable than SSE for this use case (SSE already used for the answer stream itself).
  - Stop polling when the tab is hidden (`document.visibilityState`), resume on focus.
- Show a **loading spinner** on first load and a **"No questions yet"** empty state.
- Ensure the first detected question/answer appears immediately without waiting for the next poll cycle (push on question creation via the existing SSE stream or trigger a poll immediately after answer completes).

### Phase 9 — Frontend migration to Next.js (post-core completion)
- Migrate user-facing pages to Next.js after core backend/deployment phases are stable.
- Keep Django as API/admin service while Next.js handles subscriber UI.
- Preserve current API contract and parity for lessons, transcripts, Q&A streaming, settings, devices, and billing views.

### Phase 10 — Windows desktop installer (Completed)
- Bundle Python desktop app into a single `.exe` using **PyInstaller** (Windows build step). ✓
- Package into a one-click **Inno Setup** installer that: ✓
  - Silently installs Tesseract OCR (bundled Tesseract `setup.exe` run with `/S`). ✓
  - Installs app to `C:\Program Files\MeetLessons\`. ✓
  - Creates Start Menu shortcut and desktop shortcut. ✓
  - Registers a clean uninstaller (visible in Windows "Add or Remove Programs"). ✓
- Add a custom `.ico` app icon (multi-size: 256×256, 48×48, 32×32, 16×16). ✓
- Host the final `MeetLessonsInstaller.exe` as a **GitHub Release** asset. ✓
- Add a **Download Desktop App** button/link on the Django `/devices/` page via `DESKTOP_DOWNLOAD_URL` env var. ✓
- Document the full build process in `desktop/BUILD.md`. ✓
- GitHub Actions workflow (`.github/workflows/build-desktop.yml`) auto-builds + publishes installer on `v*` tag push. ✓

### Phase 11 — Document Ingestion Pipeline (Backend) ✓ Completed
- **(backend)** Add `source_type` field to `Lesson` model (recitation vs lesson) ✓
- **(backend)** Add `page_number` field to `TranscriptChunk` for PDF page tracking ✓
- **(backend)** Install PyMuPDF dependency for PDF processing ✓
- **(backend)** Create `lessons/document_processor.py` module: ✓
  - PDF text extraction (fast path for text-based PDFs) ✓
  - PDF → image → OCR pipeline (for scanned PDFs) ✓
  - Image OCR processing (JPG, PNG, WEBP, TIFF) ✓
  - AI lesson naming via OpenAI API (gpt-4o-mini) ✓
- **(backend)** Create `POST /api/lessons/upload/` endpoint: ✓
  - Accept multipart/form-data (up to 100 files) ✓
  - Validate file types and sizes (max 100MB total) ✓
  - Process files in memory (no disk storage) ✓
  - Generate AI lesson name from transcribed content ✓
  - Create Lesson with source_type='lesson' ✓
  - Return lesson_id, lesson_name, pages_processed ✓
- **(backend)** Create `GET /api/lessons/list/` endpoint: ✓
  - Filter by source_type (recitation/lesson) ✓
  - Return lesson list for desktop app selection ✓
- **(backend)** Add rate limiting (50 uploads/day per user) ✓
- **(backend)** Add subscription enforcement for uploads ✓
- **(backend)** Install Tesseract OCR in Docker container ✓

### Phase 12 — Dashboard Upload & Editing UI ✓ Completed
- **(dashboard)** Create `/lessons/upload/` page: ✓
  - File upload form with drag-and-drop ✓
  - File preview list (name, size, page count) ✓
  - Progress indicator during processing ✓
  - Success/error states ✓
  - Max 100 files, 100MB total validation ✓
  - Rate limit warnings prominently displayed ✓
- **(dashboard)** Update `/lessons/` (dashboard home): ✓
  - Add tabs: "Recitations" | "Lessons" | "All" ✓
  - Filter lessons by source_type ✓
  - Show source badges (🎤 Recitation, 📄 Lesson) ✓
  - Add "Upload Documents" button ✓
  - Display rate limit info for subscribed users ✓
- **(dashboard)** Update `/lessons/<id>/` (lesson detail): ✓
  - Show page numbers for Lesson-type content ✓
  - Fixed URL namespacing issues ✓
- **(dashboard)** Inline editing for lesson title (deferred to Phase 14)
- **(dashboard)** Inline editing for TranscriptChunk text (deferred to Phase 14)

### Phase 12.5 — Delete Functionality & Transcript Formatting ✓ Completed
- **(backend)** Add `DELETE /api/lessons/<id>/delete/` endpoint: ✓
  - Delete single lesson with all associated data ✓
  - Verify lesson ownership before deletion ✓
  - Cascade delete TranscriptChunks and QuestionAnswers ✓
- **(backend)** Add `POST /api/lessons/bulk-delete/` endpoint: ✓
  - Accept array of lesson IDs ✓
  - Verify all lessons belong to user ✓
  - Delete multiple lessons in single transaction ✓
- **(dashboard)** Add bulk delete UI to dashboard: ✓
  - Checkboxes for each lesson ✓
  - Bulk actions toolbar (shows when items selected) ✓
  - "Delete Selected" button with confirmation ✓
  - Clear selection functionality ✓
- **(dashboard)** Add single delete to lesson detail page: ✓
  - "Delete Lesson" button in header ✓
  - Confirmation dialog before deletion ✓
  - Redirect to dashboard after successful delete ✓
- **(dashboard)** Improve transcript formatting: ✓
  - Preserve line breaks and paragraphs from PDFs/images ✓
  - Added `whitespace-pre-wrap` CSS and `linebreaks` filter ✓
  - Display page numbers for document-sourced lessons ✓
- **(backend)** PDF extraction bug fixes: ✓
  - Fixed page_count access after document close ✓
  - Lowered MIN_TEXT_PER_PAGE from 50 to 10 chars ✓
  - Improved OCR fallback to preserve extracted text ✓
  - Added detailed debug logging ✓
- **(desktop)** Question detection improvements: ✓
  - Added imperative keyword detection (explain, describe, define, etc.) ✓
  - Now detects command-style prompts like "Explain Python Programming Language" ✓
  - Expanded from 9 to 23+ trigger keywords ✓
  - All detected prompts sent to AI (not just WH-questions) ✓
- **Best practices:**
  - Confirmation dialogs prevent accidental deletion
  - User ownership verification on backend
  - Cascade deletes maintain data integrity
  - CSRF protection on all delete endpoints
  - Clear user feedback on success/error
  - Preserve original document formatting

### Phase 13 — AI Persona & Mode-Specific Behavior ✓ Completed
**Goal:** Add AI persona/description customization and implement different AI roles for Recitation vs Lesson modes.

- **(backend)** AI persona and description settings: ✓
  - Added `ai_persona` field (TextField, optional, default: "You are a helpful tutor") ✓
  - Added `ai_description` field (TextField, optional, default: "") ✓
  - Created `/lessons/settings/` page for editing persona and description ✓
  - Removed grade_level from UI (kept in database for backward compatibility) ✓
- **(backend)** Mode-specific AI behavior: ✓
  - **Recitation mode:** Uses persona + description from user settings ✓
  - **Lesson mode:** Uses tutor mode, ignores persona/description ✓
  - Added `source_type` parameter to all AI functions ✓
  - Different system prompts based on `lesson.source_type` ✓
- **(backend)** Context handling improvements: ✓
  - Recitation mode: Uses last 10 captions as context ✓
  - Lesson mode: Uses **full lesson transcript** with page numbers ✓
  - Page numbers formatted as `[Page X]` in lesson context ✓
- **(backend)** AI prompt construction: ✓
  - Recitation: "{persona}. {description}. Answer in {max_sentences} sentences..." ✓
  - Lesson: "You are a helpful tutor. Explain concepts from the lesson clearly..." ✓
  - Removed all grade_level references from prompts ✓
- **(backend)** Code cleanup: ✓
  - Removed grade_level from settings view POST handler ✓
  - Removed grade_level from admin display ✓
  - Removed grade_level from forms ✓
  - Updated `answer_question()` and `answer_question_streaming()` signatures ✓
- **Best practices:**
  - Clear separation: Recitation = homework help, Lesson = study help
  - Context optimization: Recent captions vs full transcript
  - Backward compatible: Defaults to recitation mode if not specified
  - User control: Persona settings only affect recitation mode

### Phase 14 — Desktop App Stability & Auto-Capture ✓ Completed
- **(desktop)** Fixed UI freezing/shaking: ✓
  - Replaced blocking `time.sleep()` with non-blocking `tkinter.after()` ✓
  - Clipboard polling uses 200ms intervals without blocking main thread ✓
  - Print Screen capture waits up to 8 seconds for Ctrl+C without UI freeze ✓
- **(desktop)** Auto-capture improvements: ✓
  - Re-enabled clipboard watcher for automatic capture on Ctrl+C ✓
  - Ignores pre-existing clipboard images on startup (only captures NEW images) ✓
  - Daily lesson grouping: all captures from same day grouped into one lesson ✓
  - AI-generated lesson titles from first captured text ✓
- **(desktop)** Long-running stability (4+ hour sessions): ✓
  - Activity log auto-trims to 500 lines to prevent memory growth ✓
  - Clipboard signature cache bounded to 200 entries ✓
  - Memory-efficient: ~60MB for 4-hour sessions (~2.5MB/hour growth) ✓
  - All threads are daemon threads for proper cleanup ✓
- **(dashboard)** Bulk selection improvements: ✓
  - Added "Select All" checkbox for bulk lesson selection ✓
  - Bulk delete now supports selecting all lessons at once ✓
- **(testing)** Comprehensive test suite: ✓
  - Created `desktop/test_desktop.py` with 19 tests ✓
  - Tests for clipboard capture, UI responsiveness, OCR, question detection ✓
  - Performance benchmarks: capture < 1s, processing < 5s ✓
  - Added `pytest` and `pytest-mock` to requirements ✓
- **(documentation)** Stability guides: ✓
  - `desktop/README_TESTS.md` - Test suite documentation ✓
  - `desktop/LONG_RUNNING.md` - 4-hour session stability guide ✓
  - Memory benchmarks and monitoring commands ✓

### Phase 15 — Desktop Clipboard Polling Optimization (Future)
**Goal:** Eliminate desktop icon shaking by implementing event-driven clipboard monitoring instead of continuous polling.

**Current Issue:**
- Clipboard polling every 0.9-4 seconds causes desktop icon to shake
- Unnecessary CPU/battery usage when idle
- May trigger antivirus alerts

**Solution: Option 4 - Hybrid Approach (Recommended)**
- **(desktop)** Disable continuous clipboard polling by default
- **(desktop)** Start temporary clipboard polling only when Print Screen is pressed
- **(desktop)** Poll for 10 seconds after Print Screen, then auto-stop
- **(desktop)** Zero resource usage when idle (no polling)
- **(desktop)** Auto-capture still works: Print Screen → select region → Ctrl+C

**Implementation:**
```python
# Idle state: No clipboard polling (0% CPU)
# Print Screen pressed: Start 10-second temporary polling
# Capture detected: Stop polling, return to idle
# Timeout: Stop polling after 10 seconds, return to idle
```

**Benefits:**
- ✅ No icon shaking during idle
- ✅ Auto-captures on Ctrl+C after Print Screen
- ✅ Zero resource usage when not capturing
- ✅ Better battery life on laptops
- ✅ Cleaner system behavior

**Alternative Approaches Considered:**
1. Disable polling entirely (requires manual button click)
2. Event-driven monitoring (platform-specific, complex)
3. Adaptive polling with idle detection (still some polling)
4. **Hybrid approach (recommended)** - best balance of functionality and performance

**Priority:** Low (current implementation works, this is optimization)

### Phase 16 — Desktop App Mode Selection & Lesson UI ✅ COMPLETED
**Goal:** Add UI to desktop app for switching between Recitation and Lesson modes, with lesson selection dropdown and session-based context management.

**Status:** ✅ Completed (Mar 8, 2026)

**What Was Implemented:**
- ✅ Mode selector UI with radio buttons (Recitation vs Lesson)
- ✅ Lesson selection dropdown (fetches from backend API)
- ✅ Session context management using `deque(maxlen=10)`
- ✅ Session-based lesson grouping (unique ID per app session)
- ✅ Mode-specific API calls (lesson_id + context)
- ✅ Config persistence for mode selection
- ✅ Clear session context button
- ✅ Fixed duplicate capture bug (Print Screen + clipboard watcher conflict)
- ✅ Fixed lesson loading bug (API response parsing)
- ✅ Markdown rendering for AI answers

**Implementation Plan:**

- **(desktop)** Add mode selector UI:
  - Radio buttons: "Recitation Mode (Live)" | "Lesson Mode (Study)"
  - Place below "Device Pairing" section, above "Screenshot Capture"
  - Default: Recitation Mode
  - Persist selection in config file
  - **Both modes use Print Screen → Ctrl+C** (no manual capture needed)

- **(desktop)** Add lesson selection dropdown:
  - Only visible when Lesson mode is selected
  - Fetch lessons from `GET /api/lessons/list/?source_type=lesson`
  - Display lesson titles in dropdown (e.g., "Photosynthesis Chapter 3", "Math Homework")
  - Store selected `lesson_id` in memory
  - Refresh button to reload lesson list
  - Show "(Upload lessons via web dashboard)" if list is empty
  - Require lesson selection before allowing captures in Lesson mode

- **(desktop)** Session Context Management (IMPORTANT):
  - **Purpose:** Maintain conversational context within same session
  - **Implementation:** Use `deque(maxlen=10)` to store last 10 captured texts
  - **Memory impact:** ~3KB (negligible)
  - **Lifecycle:**
    - App starts → Context is empty
    - Each capture → Add text to deque (auto-limits to 10)
    - App closes → Context cleared automatically
  - **Usage:**
    - Recitation mode: Send last 10 captions as context to backend
    - Lesson mode: Send empty context (backend uses lesson transcript)
  - **Example:**
    ```python
    # desktop/main.py
    class MeetLessonsApp:
        def __init__(self):
            self._session_context = deque(maxlen=10)  # Last 10 captions
        
        def _process_text(self, text):
            # Add to session context
            self._session_context.append(text)
            
            # Build context string for API
            if self._mode == "recitation":
                context = "\n".join(self._session_context)
            else:  # lesson mode
                context = ""  # Backend uses lesson transcript
            
            self._send_question(text, context)
    ```
  - **Benefits:**
    - Teacher asks about photosynthesis → Student asks follow-up about chlorophyll
    - AI knows context from previous questions in same session
    - Natural conversation flow
    - Automatic cleanup on app restart

- **(desktop)** Optional: Manual session reset:
  - Add "Clear Session Context" button
  - Useful when switching topics mid-session
  - Clears `_session_context` deque

- **(desktop)** Update API client:
  - Modify `send_question()` to accept `lesson_id` and `context`
  - **Recitation mode:** Send `lesson_id=null`, `context=last_10_captions`
  - **Lesson mode:** Send `lesson_id=selected_id`, `context=""`
  - Backend automatically detects mode from `lesson_id` presence

- **(desktop)** Update capture workflow:
  - **Both modes:** Print Screen → Ctrl+C → OCR → detect questions → send to API
  - **Recitation mode:** Creates/uses daily lesson, includes session context
  - **Lesson mode:** Uses selected lesson_id, backend uses full lesson transcript
  - **No manual capture buttons needed** (Print Screen workflow is fast enough)

- **(desktop)** UI Layout:
  ```
  ┌─ Device Pairing ────────────────┐
  │ ✓ Paired (device abc...)        │
  └─────────────────────────────────┘
  
  ┌─ Mode Selection ────────────────┐
  │ ○ Recitation Mode (Live Capture)│
  │ ● Lesson Mode (Study Documents) │
  │                                  │
  │ Select Lesson:                   │
  │ [Photosynthesis Chapter 3  ▼]   │
  │ [Refresh Lessons]                │
  └─────────────────────────────────┘
  
  ┌─ Screenshot Capture ────────────┐
  │ Press Print Screen to capture   │
  │ [Capture Now (Manual)]          │
  └─────────────────────────────────┘
  ```

- **(backend)** API endpoint already exists:
  - `GET /api/lessons/list/?source_type=lesson` returns lesson list ✓
  - `POST /api/questions/` accepts `lesson_id` and `source_type` ✓
  - No backend changes needed

- **(testing)** Verification steps:
  - Test mode switching updates UI correctly
  - Test lesson dropdown populates from API
  - Test Recitation mode sends questions with session context
  - Test Lesson mode sends questions with selected lesson_id
  - Test backend uses correct AI behavior for each mode
  - Test session context accumulates and clears on app restart
  - Test Print Screen hotkey works in both modes

**User Workflow:**

**Recitation Mode (Homework Help with Session Context):**
1. Select "Recitation Mode"
2. Press Print Screen → select region → Ctrl+C
3. Desktop app captures, runs OCR, detects questions
4. Adds text to session context (last 10 captions)
5. Sends to backend with persona/description + session context
6. AI answers as student with awareness of previous questions in session
7. Example conversation:
   - Q1: "What is photosynthesis?" → AI answers
   - Q2: "What is chlorophyll?" → AI knows context from Q1
   - Q3: "How do plants use it?" → AI knows context from Q1 & Q2

**Lesson Mode (Study from Uploaded Documents):**
1. Upload PDF via web dashboard (e.g., "Photosynthesis Chapter 3")
2. Select "Lesson Mode" in desktop app
3. Choose lesson from dropdown: "Photosynthesis Chapter 3"
4. Press Print Screen → select region → Ctrl+C
5. Desktop app captures, runs OCR, detects questions
6. Sends to backend with lesson_id (no session context needed)
7. AI explains based on uploaded document content (tutor mode)
8. Answer appears on web dashboard under selected lesson

**API Examples:**

**Recitation Mode (with session context):**
```python
# First question in session
POST /api/questions/
{
    "question": "What is photosynthesis?",
    "lesson_id": null,
    "context": "",  # Empty on first question
    "initial_text": "What is photosynthesis?"
}

# Second question in same session
POST /api/questions/
{
    "question": "What is chlorophyll?",
    "lesson_id": null,
    "context": "Q1: What is photosynthesis?",  # Last 10 captions
    "initial_text": "What is chlorophyll?"
}

# Backend behavior:
# - Uses persona + description from user settings
# - Includes session context in AI prompt
# - AI knows previous questions in conversation
```

**Lesson Mode (with lesson transcript):**
```python
POST /api/questions/
{
    "question": "What is photosynthesis?",
    "lesson_id": 42,  # Selected from dropdown
    "context": "",  # Ignored - backend uses lesson transcript
    "initial_text": "What is photosynthesis?"
}

# Backend behavior:
# - Detects lesson_id is present → Lesson mode
# - Fetches full lesson transcript from database
# - Uses tutor mode (ignores persona/description)
# - AI explains based on uploaded document content
```

**Benefits:**
- ✅ Clear user control over Recitation vs Lesson modes
- ✅ Session context enables natural conversation flow in Recitation mode
- ✅ Lesson mode enables studying from uploaded documents
- ✅ Backend already supports both modes (no backend changes needed)
- ✅ Simple UI with radio buttons and dropdown
- ✅ Backward compatible (defaults to Recitation mode)
- ✅ Memory-efficient session management (~3KB)

**Priority:** Medium (enhances usability, backend already ready)

### Phase 17 — Daily AI Output Limits (Future)
**Goal:** Implement daily question limits per user to control OpenAI API costs and prevent abuse.

**Current State:**
- No daily limits on AI questions
- Only subscription check (active subscription = unlimited questions)
- No rate limiting or usage quotas
- No tracking of daily question counts

**Implementation Plan:**

- **(backend)** Add daily question counter:
  - Track `QuestionAnswer` count per user per day
  - Add `daily_question_limit` field to `BillingPlan` model
  - Default limits: Basic = 50/day, Pro = 200/day, Unlimited = None

- **(backend)** Implement limit checking:
  - Check daily count before calling OpenAI API
  - Return 429 (Too Many Requests) when limit exceeded
  - Include reset time in error response (midnight UTC)

- **(backend)** Add usage tracking:
  - Create `DailyUsage` model to track questions per day
  - Aggregate queries for dashboard analytics
  - Cache daily counts in Redis for performance

- **(dashboard)** Usage display:
  - Show "X / Y questions used today" in dashboard header
  - Progress bar for daily limit
  - Upgrade prompt when approaching limit

- **(desktop)** Handle limit errors:
  - Display friendly error message in activity log
  - Show "Daily limit reached - upgrade or wait until tomorrow"
  - Don't retry automatically when limit hit

**API Response Example:**
```python
# When limit exceeded
{
    "error": "Daily question limit reached",
    "limit": 50,
    "used": 50,
    "reset_at": "2026-03-08T00:00:00Z",
    "upgrade_url": "https://meetlessons.com/billing/"
}
```

**Database Schema:**
```python
class DailyUsage(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField()
    question_count = models.PositiveIntegerField(default=0)
    
    class Meta:
        unique_together = [["user", "date"]]
        indexes = [models.Index(fields=["user", "date"])]
```

**Benefits:**
- ✅ Control OpenAI API costs
- ✅ Prevent abuse (spam questions)
- ✅ Encourage upgrades to higher tiers
- ✅ Fair usage across all users
- ✅ Analytics for usage patterns

**Priority:** Low (cost control, not critical for MVP)

## 11) Testing

This document intentionally stays high-level.

For step-by-step verification (device pairing, OCR capture, AI answering, Stripe subscriptions, coupon codes, and revocation behavior), use:

- `TEST.md`

## 12) Non-goals (for MVP)

- Chrome extension (abandoned — Google Meet DOM too brittle)
- Audio capture / speech-to-text from raw audio
- Multi-language OCR support
- Offline/local AI models
- Showing AI answers in the desktop app (paywall: answers only on dashboard)
