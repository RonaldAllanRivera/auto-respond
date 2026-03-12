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

### Phase 8 — Live Dashboard with Real-Time Streaming ✓ Completed
**Goal:** Create `/live/` dashboard for real-time Q&A streaming during Google Meet sessions, with ChatGPT-style answer display.

**Status:** ✅ Completed (Mar 9, 2026)

**Use Case:**
- User captures Google Meet captions via desktop app (screenshot + OCR)
- Desktop app sends questions to Django backend
- User switches to browser tab to see answers streaming in real-time
- Zero desktop app overhead (all processing on Django side)

**Phase 8.1: Live Dashboard (High Priority)**

**1. Create `/live/` View:**
- Shows active session (today's recitation or selected lesson)
- Displays Q&A in chronological order
- ChatGPT-style streaming display (word-by-word)
- Auto-scroll to latest question
- No page refresh needed
- Minimal JavaScript (vanilla JS + SSE)

**2. Add SSE Endpoint for New Questions:**
- `GET /api/sessions/live/` - Streams new question events
- Broadcasts when desktop app sends new question
- Returns: `{question_id, question_text, lesson_id, timestamp}`
- Auto-detects current session (session-based or lesson-based)

**3. Implement Real-Time Streaming:**
- Listen for new questions via SSE (no polling)
- Stream answers using existing `/api/questions/<id>/stream/` endpoint
- Display tokens as they arrive (like ChatGPT)
- Show "Thinking..." indicator while waiting for first token
- Mark answer as complete when streaming finishes

**4. UI/UX Features:**
- Auto-scroll to latest Q&A
- Show timestamp for each question
- Markdown rendering for AI answers
- Mobile-responsive design
- "No questions yet" empty state
- Session selector (switch between recitation/lesson modes)

**Phase 8.2: OCR Optimization (Quick Win)**

**1. Desktop App OCR Preprocessing:**
- Resize images to optimal size (~1920px width)
- Convert to grayscale for faster processing
- Enhance contrast for better accuracy
- Use faster Tesseract config (`--psm 6 --oem 3`)
- **Expected: 30-50% faster OCR (500-2000ms → 300-1000ms)**

**Expected Performance:**

**Before:**
- Desktop sends question
- Wait up to 10 seconds for page refresh
- See full answer at once
- **Perceived delay: 10+ seconds**

**After:**
- Desktop sends question
- Question appears in browser instantly (<100ms)
- Answer streams word-by-word (first word in ~200-500ms)
- **Perceived delay: <1 second** ✨

**Desktop App Impact:**
- RAM: ~50-100MB (unchanged)
- CPU: Spikes during OCR only (unchanged)
- All streaming happens on Django side

**Benefits:**
- ✅ ChatGPT-like streaming experience
- ✅ No React.js needed (pure Django + vanilla JS)
- ✅ Zero desktop app overhead
- ✅ 30-50% faster OCR
- ✅ Real-time updates (no polling)
- ✅ Works with existing SSE infrastructure

**Implementation Summary:**

**URL Structure:**
- `/` → Live Q&A (homepage, real-time streaming)
- `/lessons/` → Lessons Dashboard (archive)
- `/lessons/<id>/` → Lesson Detail

**Navigation:**
- Added "Live" and "Lessons" links to base template
- Live page is now the default homepage for instant access

**Live Dashboard Features:**
- Loads existing Q&A on page load (last 20)
- Auto-reloads every 5 seconds to check for new questions
- Streams answers using existing SSE endpoint (`/api/questions/<id>/stream/`)
- Latest questions appear at top (reverse chronological)
- Mode selector: Recitation (today's session) or Lesson (selected lesson)
- ChatGPT-style streaming with "Thinking..." indicator
- Markdown rendering for AI answers

**OCR Optimization (`desktop/ocr.py`):**
- Resize images to optimal size (~1920px width)
- Convert to grayscale for faster processing
- Enhance contrast (1.5x) for better accuracy
- Use PSM 6 config (uniform block of text)
- **Result: 30-50% faster OCR**

**Bug Fixes:**
- Removed infinite SSE polling loop that caused Gunicorn worker timeouts
- Replaced with simple page reload every 5 seconds
- Fixed desktop app HTTP connection errors
- Stable performance with zero worker crashes

**Files Modified:**
- `backend/lessons/views.py` - Added `live_dashboard()` view with Q&A loading
- `backend/lessons/urls.py` - Swapped routes: `/` → live, `/lessons/` → dashboard
- `backend/templates/base.html` - Added Live and Lessons navigation links
- `backend/templates/lessons/live.html` - Created live dashboard template
- `desktop/ocr.py` - Optimized preprocessing for faster OCR
- `README.md` - Updated URL documentation

### Phase 9 — PWA & Mobile Optimization (High Priority)
**Goal:** Enhance mobile experience with Progressive Web App features instead of React Native or Next.js migration.

**Status:** 📋 Planned

**Rationale:**
- Current Django + vanilla JS solution already works perfectly on mobile browsers
- Next.js migration would add complexity without value (separate deployment, CORS, duplicate auth)
- React Native would require 3-4 months development + app store maintenance
- PWA provides native-like experience with zero deployment overhead

**Phase 9.1: Progressive Web App (PWA) Support**

**1. Add PWA Manifest:**
- Create `/static/manifest.json` with app metadata
- Add icons (192x192, 512x512) for home screen
- Configure theme colors and display mode
- Enable "Add to Home Screen" on mobile devices

**2. Service Worker for Offline Support:**
- Cache static assets (CSS, JS, icons)
- Cache live page HTML for offline viewing
- Background sync for failed API requests
- Update notification when new version available

**3. Mobile App-Like Features:**
- Full-screen mode (no browser chrome)
- Splash screen on launch
- Status bar theming (iOS/Android)
- Install prompts for returning users

**Expected Benefits:**
- ✅ Looks like native app on mobile
- ✅ Works offline (cached content)
- ✅ Fast loading (cached assets)
- ✅ No app store submission required
- ✅ Instant updates (no approval delays)
- ✅ Works on ALL devices (iOS, Android, tablets)

**Phase 9.2: Mobile UI Optimization**

**1. Responsive Design Improvements:**
- Optimize live page layout for small screens
- Larger touch targets (48x48px minimum)
- Better typography scaling
- Collapsible sections for long answers

**2. Mobile-Specific Features:**
- Haptic feedback on new questions (Vibration API)
- Swipe to refresh
- Pull-to-load more questions
- Sticky header on scroll
- Bottom navigation for easier thumb access

**3. Performance Optimization:**
- Reduce auto-reload interval on mobile (10s instead of 5s to save battery)
- Lazy load images in answers
- Compress markdown rendering
- Reduce animation overhead

**Phase 9.3: Browser Push Notifications**

**1. Web Push API Integration:**
- Request notification permission on first visit
- Subscribe to push notifications via service worker
- Backend sends push when new answer arrives
- Show notification even when browser is closed

**2. Notification Features:**
- "New answer ready" notification with preview
- Click notification to open live page
- Badge count for unread answers
- Silent notifications option

**Expected Impact:**
- **Development Time:** 2-3 days (vs 3-4 months for React Native)
- **Ongoing Cost:** $0/month (vs $99-199/year for app stores)
- **User Experience:** Native-like on mobile browsers
- **Maintenance:** Minimal (same codebase as desktop)

**Why NOT Next.js or React Native:**
- ❌ Next.js: Adds complexity (separate deployment, CORS, duplicate auth) without solving real problems
- ❌ React Native: 3-4 months dev time, app store overhead, separate codebase to maintain
- ✅ PWA: Best of both worlds - native-like UX with web simplicity

**Implementation Priority:**
1. PWA manifest + service worker (High - 4 hours)
2. Mobile UI optimization (Medium - 3 hours)
3. Push notifications (Medium - 4 hours)
4. Advanced features (Low - as needed)

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

---

### Phase 16.5 — Question Detection Simplification ✅ COMPLETED
**Goal:** Fix multiple-choice question handling by sending entire screenshot text as one question instead of splitting into multiple sentences.

**Status:** ✅ Completed (Mar 9, 2026)

**Problem:**
- Desktop app was splitting OCR text into multiple sentences
- Multiple-choice questions were sent as separate questions (a., b., c. as individual questions)
- AI couldn't understand the full context
- Google Meet often omits punctuation, breaking sentence detection

**Solution:**
- Simplified `detect_questions()` to return **full OCR text as ONE question**
- Removed sentence splitting logic
- AI now receives complete screenshot context
- Updated AI prompt to handle any text format (questions, statements, multiple-choice)

**Changes:**
- `desktop/detector.py`: Simplified to return `[cleaned_text]` instead of splitting
- `backend/lessons/ai.py`: Updated prompts to explicitly handle multiple-choice questions
- AI instructions now: "If it's a multiple-choice question, identify the correct answer and explain why"

**Benefits:**
- ✅ Multiple-choice questions work correctly
- ✅ AI gets full context from each screenshot
- ✅ Works with or without punctuation
- ✅ Simpler code, fewer edge cases
- ✅ One screenshot = One question (natural user expectation)

---

### Phase 16.6 — Caption Deletion Feature 🚧 IN PROGRESS
**Goal:** Allow users to delete individual transcript chunks (captions) to clean up accidental captures that pollute session context.

**Status:** 🚧 In Progress (Mar 9, 2026)

**Problem:**
- Accidental screenshots add wrong data to transcript
- Session context (last 10 captions) includes wrong data
- No way to remove individual captions
- Only option was to delete entire lesson

**Solution:**
- Add delete button (✕) next to each transcript chunk
- Create `DELETE /api/chunks/<chunk_id>/` endpoint
- Confirmation dialog to prevent accidental deletion
- Immediate removal from session context

**Implementation:**
- Backend API: `api_chunk_delete()` in `lessons/api.py`
- URL route: `/api/chunks/<int:chunk_id>/delete/`
- Frontend: Delete button in `lesson_detail.html` transcript section
- JavaScript: `deleteChunk()` function with confirmation

**Benefits:**
- ✅ Precise control - delete only wrong captures
- ✅ Preserves good captions
- ✅ Cleans session context for future questions
- ✅ Simple UI - one button per chunk

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

---

### Phase 16.7 — Desktop App Async Startup Optimization ✓ Completed
**Goal:** Eliminate 5-10 second startup delay by moving blocking API calls to background threads with retry logic, caching, and offline support.

**Status:** ✅ Completed (Mar 11, 2026)

**Problem:**
- Desktop app blocked for 5-10 seconds on startup before user could paste screenshots
- Two blocking API calls in `__init__()`:
  1. `_refresh_pairing_status()` → `validate_device_token()` (10s timeout)
  2. `_on_mode_changed()` → `_refresh_lessons()` → `fetch_lessons()` (10s timeout)
- In Lesson mode + paired: 10-20 seconds total delay
- User could not interact with app during blocking

**Solution - 9 Improvements Implemented:**

**HIGH PRIORITY (Immediate Fix):**
1. ✅ Moved `_refresh_pairing_status()` to background thread
2. ✅ Moved `_refresh_lessons()` to background thread
3. ✅ Added `root.update()` after `_build_ui()` for instant UI render

**MEDIUM PRIORITY (Better UX):**
4. ✅ Added "Checking..." / "Validating..." status indicators
5. ✅ Lazy load lessons (only when switching to Lesson mode)
6. ✅ Cache lessons locally in `config.json` with 5-minute TTL

**LOW PRIORITY (Production Polish):**
7. ✅ Added retry logic for failed API calls (3 attempts with exponential backoff)
8. ✅ Added connection status indicator (Online/Offline)
9. ✅ Added clear offline feedback (fail fast, no queue)

**Implementation Details:**

**New Methods in `desktop/main.py`:**
- `_show_initial_pairing_status()` - Shows cached pairing status instantly (no API call)
- `_async_startup_validation()` - Background thread for pairing validation
- `_handle_startup_validation_result()` - Updates UI on main thread after validation
- `_async_refresh_lessons()` - Background thread for lesson fetching
- `_fetch_lessons_from_api()` - Fetch and cache lessons from API
- `_update_lessons_ui()` - Updates lesson dropdown on main thread
- `_handle_lessons_error()` - Error handling on main thread
- `_update_connection_status()` - Updates online/offline indicator (red/green)

**Enhanced `desktop/config.py`:**
- Added `cached_lessons` field for local lesson caching
- Added `last_lessons_fetch` timestamp for cache validation
- New functions: `cache_lessons()`, `get_cached_lessons()`, `is_lessons_cache_valid()`

**Offline Handling:**
- **No queue** - Fail fast with clear feedback
- Shows "⚠ Offline - Question not sent: [question]..." in activity log
- Shows "Reconnect to server to capture questions" message
- Connection status indicator: "● Online" (green) / "● Offline" (red)

**Enhanced `desktop/api_client.py`:**
- Added `@with_retry()` decorator for automatic retry with exponential backoff
- Applied to `validate_device_token()` and `fetch_lessons()`
- 3 retry attempts with 1.5x backoff multiplier

**Thread Safety:**
- All UI updates via `root.after(0, callback)` from background threads
- Config operations are thread-safe (atomic file I/O for small JSON)
- API calls run in daemon background threads
- No shared mutable state between threads

**Performance Impact:**

**Before:**
- Startup time: 10-20 seconds (Lesson mode + paired)
- User blocked: Cannot paste screenshots
- No offline support
- No retry on network errors

**After:**
- Startup time: < 1 second
- User can paste immediately
- Cached lessons show instantly
- Auto-retry on network errors (3 attempts)
- Clear offline feedback (no queue)
- Connection status indicator (red/green)

**Performance Improvement: 10-20x faster startup**

**Files Modified:**
- `desktop/main.py` - Async startup implementation (8 new methods, offline feedback)
- `desktop/config.py` - Lesson caching support (no queue)
- `desktop/api_client.py` - Retry logic decorator

**Benefits:**
- ✅ Instant app startup (< 1 second)
- ✅ User can paste screenshots immediately
- ✅ All pairing functionality preserved
- ✅ Graceful degradation on network errors
- ✅ Clear offline feedback (fail fast, no queue complexity)
- ✅ Local caching reduces API calls
- ✅ Better user experience with connection status indicator

---

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

---

### Phase 18 — Performance & Reliability Improvements (Medium Priority)
**Goal:** Optimize backend performance and add monitoring for production stability.

**Status:** 📋 Planned

**Phase 18.1: Database Optimization**

**1. Add Database Indexes:**
- Index on `Lesson.user_id` + `created_at` (for dashboard queries)
- Index on `QuestionAnswer.lesson_id` + `created_at` (for Q&A sorting)
- Index on `TranscriptChunk.lesson_id` + `page_number` (for lesson detail)
- Composite index on `Device.user_id` + `is_active` (for device list)

**2. Query Optimization:**
- Use `select_related()` for foreign keys (reduce N+1 queries)
- Use `prefetch_related()` for reverse relations
- Add `only()` and `defer()` for large fields
- Cache lesson lists in Redis (5-minute TTL)

**3. Connection Pooling:**
- Configure PostgreSQL connection pooling (pgBouncer)
- Optimize Gunicorn worker count based on CPU cores
- Add database query logging for slow queries (>100ms)

**Expected Impact:**
- 50-70% faster dashboard loading
- Reduced database load
- Better scalability for 100+ concurrent users

**Phase 18.2: Caching Strategy**

**1. Redis Integration:**
- Cache lesson lists per user (5-minute TTL)
- Cache user settings (persona, description)
- Cache subscription status (1-minute TTL)
- Session storage for Django sessions

**2. Static Asset Caching:**
- Add cache headers for CSS/JS (1 year)
- Enable gzip compression
- Use CDN for Tailwind CSS (already using CDN ✓)

**3. API Response Caching:**
- Cache `GET /api/lessons/list/` responses
- Invalidate cache on lesson creation/deletion
- Use ETags for conditional requests

**Phase 18.3: Monitoring & Alerts**

**1. Application Monitoring:**
- Add Sentry for error tracking
- Log all API errors with context
- Track SSE connection failures
- Monitor Gunicorn worker timeouts

**2. Performance Metrics:**
- Track API response times (p50, p95, p99)
- Monitor database query times
- Track OpenAI API latency
- Monitor memory usage per worker

**3. Uptime Monitoring:**
- Use UptimeRobot or similar (free tier)
- Monitor `/health/` endpoint
- Alert on downtime (email/SMS)
- Track uptime SLA (target: 99.9%)

**Expected Benefits:**
- ✅ Catch errors before users report them
- ✅ Identify performance bottlenecks
- ✅ Proactive issue resolution
- ✅ Better user experience

**Implementation Priority:**
1. Database indexes (High - 2 hours)
2. Query optimization (High - 3 hours)
3. Redis caching (Medium - 4 hours)
4. Monitoring setup (Medium - 3 hours)

---

### Phase 19 — User Experience Enhancements (Medium Priority)
**Goal:** Improve dashboard UX with features that increase engagement and retention.

**Status:** 📋 Planned

**Phase 19.1: Search & Filter**

**1. Question Search:**
- Full-text search across questions and answers
- Filter by date range (today, this week, this month)
- Filter by lesson/recitation
- Search suggestions as you type

**2. Lesson Organization:**
- Folders/tags for lessons
- Star/favorite important lessons
- Archive old lessons (hide from main view)
- Bulk operations (delete, archive, tag)

**Phase 19.2: Keyboard Shortcuts**

**1. Global Shortcuts:**
- `R` - Refresh page
- `C` - Clear filters
- `S` - Focus search box
- `N` - New lesson upload
- `?` - Show keyboard shortcuts help

**2. Navigation Shortcuts:**
- `1` - Go to Live page
- `2` - Go to Lessons page
- `3` - Go to Settings
- `Esc` - Close modals/dialogs

**Phase 19.3: Dark Mode**

**1. Theme Toggle:**
- Dark/Light mode switcher in header
- Persist preference in localStorage
- System preference detection (prefers-color-scheme)
- Smooth transition between themes

**2. Color Scheme:**
- Dark mode: Slate 900 background, Slate 100 text
- Maintain contrast ratios (WCAG AA compliance)
- Adjust syntax highlighting for code blocks
- Update markdown rendering colors

**Phase 19.4: Answer History & Analytics**

**1. Answer History:**
- View all past Q&A in chronological order
- Export Q&A to PDF/Markdown
- Share individual Q&A via link
- Print-friendly formatting

**2. Usage Analytics (User-facing):**
- Questions asked per day/week/month (chart)
- Most active lessons
- Average response time
- Study streak counter

**Expected Benefits:**
- ✅ Better content discovery
- ✅ Faster navigation
- ✅ Reduced eye strain (dark mode)
- ✅ Increased engagement

**Implementation Priority:**
1. Keyboard shortcuts (High - 2 hours)
2. Dark mode (Medium - 4 hours)
3. Search & filter (Medium - 6 hours)
4. Analytics (Low - 8 hours)

---

### Phase 20 — Desktop App Improvements (Low Priority)
**Goal:** Enhance desktop app reliability and user experience.

**Status:** 📋 Planned

**Phase 20.1: Auto-Update Mechanism**

**1. Version Check:**
- Check GitHub Releases API on startup
- Compare current version with latest release
- Show update notification if new version available
- "Download Update" button opens GitHub release page

**2. Update Notification:**
- Non-intrusive banner at top of window
- "Update available: v1.2.3 → v1.3.0"
- Changelog preview (first 3 bullet points)
- "Remind me later" option

**Phase 20.2: Better Error Messages**

**1. User-Friendly Errors:**
- Replace technical errors with plain English
- "Can't connect to server" instead of "HTTPConnectionError"
- "OCR failed - try a clearer screenshot" instead of "TesseractError"
- Actionable suggestions for common errors

**2. Error Recovery:**
- Auto-retry on network errors (3 attempts)
- Fallback to cached data when offline
- Queue questions when internet drops
- Sync queued questions when back online

**Phase 20.3: Offline Queue**

**1. Local Storage:**
- Save questions to SQLite when offline
- Store screenshot + OCR text + timestamp
- Sync to backend when connection restored
- Show "Offline - 3 questions queued" indicator

**2. Sync Logic:**
- Detect internet connectivity
- Upload queued questions in order
- Show sync progress
- Handle conflicts (duplicate questions)

**Expected Benefits:**
- ✅ Always up-to-date app
- ✅ Better error handling
- ✅ Works during internet outages
- ✅ No lost questions

**Implementation Priority:**
1. Better error messages (High - 2 hours)
2. Auto-update check (Medium - 3 hours)
3. Offline queue (Low - 8 hours)

---

### Phase 21 — Growth & Marketing Features (Low Priority)
**Goal:** Features that help with user acquisition, conversion, and retention.

**Status:** 📋 Planned

**Phase 21.1: Referral Program**

**1. Referral System:**
- Unique referral link per user
- Track referrals in database
- Reward: 1 month free for referrer + referee
- Dashboard showing referral count and rewards

**2. Implementation:**
- Add `referral_code` to User model
- Track `referred_by` on signup
- Auto-apply coupon when referee subscribes
- Email notification on successful referral

**Phase 21.2: Free Trial**

**1. Trial Period:**
- 7-day free trial for new users
- No credit card required
- Full access to all features
- Email reminders (day 5, day 6, day 7)

**2. Trial Conversion:**
- "2 days left in trial" banner
- Upgrade CTA on live page
- Show value: "You've asked 47 questions this week!"
- One-click upgrade to paid plan

**Phase 21.3: Usage Analytics (Admin)**

**1. Admin Dashboard:**
- Total users, active users, churn rate
- Revenue metrics (MRR, ARR, LTV)
- Conversion funnel (signup → trial → paid)
- Question volume trends

**2. Cohort Analysis:**
- Retention by signup month
- Feature usage by cohort
- Churn reasons (exit surveys)
- A/B test results

**Expected Benefits:**
- ✅ Organic growth through referrals
- ✅ Higher conversion from trial
- ✅ Data-driven decisions
- ✅ Better retention

**Implementation Priority:**
1. Free trial (High - 4 hours)
2. Referral program (Medium - 8 hours)
3. Admin analytics (Low - 12 hours)

---

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
