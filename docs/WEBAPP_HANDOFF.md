# Web App Handoff — RunDictation

Read [`../CLAUDE.md`](../CLAUDE.md) first if you haven't. This doc is the spec for the web-app extension only.

---

## Mission

Build a web app, hosted on Vercel under Aiden's account, that lets him generate language-learning MP3s **without the terminal**. He pastes a YouTube URL or some German text into a form, clicks a button, gets an MP3 to download (then AirDrops it to his iPhone and listens on a run).

This replaces the CLI workflow for ad-hoc inputs. The CLI tools (`build_session.py` etc.) stay for batch deck generation.

---

## Current status

**v2 is deployed and working** (as of 2026-05-14).

- Frontend: Next.js 14 on Vercel (`webapp/`)
- Backend: FastAPI on Render free tier (`backend/`)
- Auth: shared passphrase, HTTP-only cookie + hash-in-header for backend calls
- TTS: `edge-tts` v7 (Python) on the Render backend — all jobs go through the backend
- UI: light theme (white background), voice dropdown (Auto/Katja/Conrad), speed input (default 1.0x)

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

**Flow A — paste German text (implemented):**
1. User opens the app, enters passphrase (or is already logged in via cookie).
2. Pastes a chunk of German text (an article, a chapter, anything).
3. Picks a voice (Auto / Katja / Conrad), optionally adjusts speed (1.0x default).
4. Clicks "Generate."
5. Sees loading state while backend processes. Backend wakes on page load to reduce cold-start delay.
6. Downloads the resulting MP3.

**Flow B — YouTube URL (not yet built, v3):**
1. Same login.
2. Pastes a YouTube URL.
3. Optionally picks a target duration and a speed (0.85x is great for German podcasts).
4. Clicks "Capture."
5. App downloads audio via `yt-dlp`, optionally adjusts speed, returns the MP3.

**Flow C (later, optional) — paste English/foreign text, get bilingual audio:**
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
┌─────────────────────────┐
│ Render: FastAPI backend  │
│ - POST /jobs (submit)   │
│ - GET /jobs/:id (poll)  │
│ - GET /files/:id (MP3)  │
│ - GET /health (wake-up) │
│ - edge-tts v7 (Python)  │
│ - async job processing  │
│ - MP3s in /tmp (cleaned │
│   after 1 hour)         │
└─────────────────────────┘
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
- **Backend**: FastAPI, `edge-tts` v7, `uvicorn`
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
        ├── generate/page.tsx (main form)
        └── api/auth/route.ts (login + logout)

backend/
├── main.py (FastAPI app — jobs, files, health, auth)
└── requirements.txt
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

- **`scripts/build_session.py`** has all the TTS + gap + concat logic. For bilingual mode (v4), **extract it into a Python module (`lib/tts.py`)**. Don't rewrite the gap math — copy it.
- **`PROJECT_PLAN.md`** is the source of truth for defaults (voice IDs, gap timings, card structure).
- **`memory/feedback_voice_consistency.md`** (if present): one voice per session, do not switch mid-session.

---

## Out of scope

- Multiple users / accounts.
- DRM-protected content (audiobooks behind Audible, paid podcasts).
- Mobile app (Vercel web UI is sufficient).
- Real-time/streaming TTS — generate-and-download is the right shape.
- Anki sync, spaced-repetition scoring — these go in the CLI side, not the web app.
