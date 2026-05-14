# Web App Handoff — RunDictation

Read [`../CLAUDE.md`](../CLAUDE.md) first if you haven't. This doc is the spec for the web-app extension only.

---

## Mission

Build a web app, hosted on Vercel under Aiden's account, that lets him generate language-learning MP3s **without the terminal**. He pastes a YouTube URL or some German text into a form, clicks a button, gets an MP3 to download (then AirDrops it to his iPhone and listens on a run).

This replaces the CLI workflow for ad-hoc inputs. The CLI tools (`build_session.py` etc.) stay for batch deck generation.

---

## Current status

**v2.5 is deployed and working** (as of 2026-05-14).

- Frontend: Next.js 14 on Vercel (`webapp/`)
- Backend: FastAPI on Render free tier (`backend/`)
- Auth: shared passphrase, HTTP-only cookie + hash-in-header for backend calls
- TTS: `edge-tts` v7 (Python) on the Render backend — all jobs go through the backend
- UI: light theme (white background), tabbed generate page
- **Quick Generate** (v2.5): auto-generate bilingual MP3s from pre-processed datasets
  - L1 word cards (4,178 words with translations from kaikki.org Wiktextract, 1,409 with example sentences)
  - L2 sentence pairs (20,000 from Tatoeba, tagged by theme: daily life, food, travel, business)
  - Cumulative difficulty selector (Top 100 / Top 500 / Top 2,000 / Top 5,000 — each includes all easier words)
  - Count or duration targeting (25/50/100/200 items, or 15min/30min/1hr)
  - Daily Mix (date-seeded deterministic selection for fresh content each day)
  - Themed packs for L2 (All / Daily Life / Food & Drink / Travel / Business)
- **From Text** (v2): paste German text for single-voice TTS, voice dropdown (Auto/Katja/Conrad), speed input (default 1.0x)

---

## Decisions made

These were confirmed at the start of the build session:

1. **Auth**: shared passphrase (single user, simplest)
2. **Voice exposure**: dropdown with all 3 options — Auto (random), Katja (female), Conrad (male)
3. **Speed default**: 1.0x
4. **Scope**: skipped v1 (Vercel-only short text), went straight to v2 with Render backend
5. **Backend**: Render free tier (best free option — 512MB RAM, spins down after 15 min idle, ~30s cold start)
6. **Domain**: default `*.vercel.app` domain

---

## User flows

**Flow A — Quick Generate (implemented, v2.5):**
1. User opens the app, enters passphrase (or is already logged in via cookie).
2. On the "Quick Generate" tab, picks a mode: Words (L1) or Sentences (L2).
3. For L1: selects difficulty level (Top 100 / 500 / 2,000 / 5,000 most common words).
   For L2: selects a topic (All / Daily Life / Food & Drink / Travel / Business).
4. Chooses amount by count (25/50/100/200) or duration (15min/30min/1hr).
5. Optionally clicks "Daily Mix" for a date-seeded selection (same day = same words, fresh each day).
6. Picks voice and speed, clicks "Generate."
7. Backend selects cards from pre-processed datasets, builds bilingual audio (German → pause → English for each card), returns MP3.
8. Downloads the MP3.

**Flow B — paste German text (implemented, v2):**
1. User switches to the "From Text" tab.
2. Pastes a chunk of German text (an article, a chapter, anything).
3. Picks a voice (Auto / Katja / Conrad), optionally adjusts speed (1.0x default).
4. Clicks "Generate."
5. Sees loading state while backend processes. Backend wakes on page load to reduce cold-start delay.
6. Downloads the resulting MP3.

**Flow C — YouTube URL (not yet built, v3):**
1. Same login.
2. Pastes a YouTube URL.
3. Optionally picks a target duration and a speed (0.85x is great for German podcasts).
4. Clicks "Capture."
5. App downloads audio via `yt-dlp`, optionally adjusts speed, returns the MP3.

**Flow D (later, optional) — paste English/foreign text, get bilingual audio:**
1. User pastes text in the *target* language.
2. App translates each sentence and produces the `[de] · pause · [en] · pause` audio the CLI does today.
3. Downloads the resulting MP3.

---

## Architecture

```
┌─────────────────────────┐
│ User's iPhone / Mac     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│ Vercel: Next.js app     │
│ - login form (/)        │
│ - generate form         │
│   (/generate)           │
│ - auth API route        │
│   (POST /api/auth)      │
│ - middleware (protects   │
│   /generate)            │
└────────┬────────────────┘
         │  all TTS jobs
         │  (submit + poll + download)
         ▼
┌──────────────────────────┐
│ Render: FastAPI backend   │
│ - POST /jobs (text TTS)  │
│ - POST /jobs/quick       │
│   (bilingual card gen)   │
│ - GET /jobs/:id (poll)   │
│ - GET /files/:id (MP3)   │
│ - GET /stats (dataset)   │
│ - GET /health (wake-up)  │
│ - edge-tts v7 + pydub    │
│ - pre-processed data:    │
│   4,178 words, 20k sents │
│ - async job processing   │
│ - MP3s in /tmp (cleaned  │
│   after 1 hour)          │
└──────────────────────────┘
```

**Why all jobs go through the backend** (not dual-path): Vercel Hobby tier has a 10s function timeout. Even short TTS jobs can exceed this. Routing everything through Render avoids timeout issues entirely. The tradeoff is a ~30s cold start if the Render service has spun down, mitigated by pinging `/health` when the generate page loads.

---

## Auth flow

1. User enters passphrase on login page.
2. `POST /api/auth` compares against `WEBAPP_PASSPHRASE` env var.
3. If correct, sets HTTP-only cookie (`auth` = SHA-256 hash of passphrase) and returns the hash in the response body.
4. Client stores hash in `sessionStorage` for backend API calls.
5. Middleware on `/generate` validates the cookie (uses Web Crypto API, Edge-compatible).
6. Backend validates the hash in the `Authorization` header on every request.
7. Logout clears both the cookie and sessionStorage.

---

## Tech stack

- **Frontend**: Next.js 14 (App Router), Tailwind CSS v4, `lucide-react` icons, `@vercel/analytics`
- **Backend**: FastAPI, `edge-tts` v7, `pydub`, `audioop-lts`, `uvicorn`
- **Hosting**: Vercel (frontend), Render free tier (backend)
- **Auth**: shared passphrase, SHA-256 hash, HTTP-only cookie + header token

---

## Env vars

| Service | Variable | Value |
|---------|----------|-------|
| Vercel | `WEBAPP_PASSPHRASE` | the passphrase |
| Vercel | `NEXT_PUBLIC_BACKEND_URL` | Render backend URL (e.g. `https://rundictation-backend-xxxx.onrender.com`) |
| Render | `WEBAPP_PASSPHRASE` | same passphrase |

---

## File layout

```
webapp/
├── package.json
├── next.config.js, tsconfig.json, postcss.config.js
├── .env.local (local dev only — not committed)
├── .env.example
├── .nvmrc (Node 22)
└── src/
    ├── middleware.ts (protects /generate)
    └── app/
        ├── layout.tsx, globals.css
        ├── page.tsx (login)
        ├── generate/
        │   ├── page.tsx (tabbed layout: Quick Generate + From Text)
        │   ├── QuickTab.tsx (L1/L2 auto-generate UI)
        │   ├── TextTab.tsx (paste German text UI)
        │   └── shared.tsx (voice/speed controls, job hooks, stats hook)
        └── api/auth/route.ts (login + logout)

backend/
├── main.py (FastAPI app — jobs, quick-generate, stats, health, auth)
├── audio_builder.py (bilingual TTS: word/sentence card audio with gaps)
├── requirements.txt
└── data/
    ├── words.jsonl.gz (pre-processed L1 word data, ~195KB)
    ├── sentences.jsonl.gz (pre-processed L2 sentence pairs, ~760KB)
    └── stats.json (dataset counts for frontend display)

scripts/
├── build_session.py (CLI: CSV → bilingual MP3)
├── fetch_sources.py (download raw source data)
├── select_cards.py (CLI card selection — stub)
└── preprocess_data.py (raw sources → compact backend datasets)
```

---

## Next phases

### v3 — YouTube / podcast capture

Scope: paste a YouTube URL or RSS episode URL → MP3 download.

Deliverables:
- Backend endpoint accepts `{ type: "youtube", url, speed }`.
- Backend uses `yt-dlp` to fetch audio, `ffmpeg` to re-encode and optionally `atempo` for speed.
- Same job queue / polling pattern as v2.
- Frontend gets a second tab: "From URL" alongside "From text."

### v4 (optional, ambitious) — bilingual mode

Scope: paste English-or-other text → translated, then bilingual MP3 (German + English pairs, like the CLI).

Deliverables:
- Backend integrates a free MT engine (Argos Translate runs locally, or LibreTranslate self-hosted — both free).
- Same job pattern.
- Output mirrors `build_session.py`'s bilingual structure.

---

## Code that can be reused

- **`backend/audio_builder.py`** — bilingual TTS card builder, already extracted from `build_session.py`. Used by Quick Generate. Contains `tts_segment()`, `build_word_card()`, `build_sentence_card()`, and `build_session_audio()`.
- **`scripts/build_session.py`** — original CLI version with full CLI arg parsing, ffmpeg speed adjustment, and CSV loading. Still the right tool for batch generation from CSV files.
- **`scripts/preprocess_data.py`** — regenerate `backend/data/` from raw sources. Run after updating source data.
- **`PROJECT_PLAN.md`** is the source of truth for defaults (voice IDs, gap timings, card structure).
- **`memory/feedback_voice_consistency.md`** (if present): one voice per session, do not switch mid-session.

---

## Out of scope

- Multiple users / accounts.
- DRM-protected content (audiobooks behind Audible, paid podcasts).
- Mobile app (Vercel web UI is sufficient).
- Real-time/streaming TTS — generate-and-download is the right shape.
- Anki sync, spaced-repetition scoring — these go in the CLI side, not the web app.
