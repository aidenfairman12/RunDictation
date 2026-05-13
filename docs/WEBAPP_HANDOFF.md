# Web App Handoff — RunDictation

Read [`../CLAUDE.md`](../CLAUDE.md) first if you haven't. This doc is the spec for the web-app extension only.

---

## Mission

Build a web app, hosted on Vercel under Aiden's account, that lets him generate language-learning MP3s **without the terminal**. He pastes a YouTube URL or some German text into a form, clicks a button, gets an MP3 to download (then AirDrops it to his iPhone and listens on a run).

This replaces the CLI workflow for ad-hoc inputs. The CLI tools (`build_session.py` etc.) stay for batch deck generation.

---

## User flows

**Flow A — paste German text:**
1. User opens the app, enters a passphrase (or is already logged in).
2. Pastes a chunk of German text (an article, a chapter, lyrics, anything).
3. Picks a voice (Katja / Conrad), optionally a speed (1.0× default, 0.9× for slower).
4. Clicks "Generate."
5. Sees a progress indicator (TTS takes ~real-time-ish: 5 min of audio takes ~30s of generation).
6. Downloads the resulting MP3.

**Flow B — YouTube URL:**
1. Same login.
2. Pastes a YouTube URL.
3. Optionally picks a target duration and a speed (0.85× is great for German podcasts).
4. Clicks "Capture."
5. App downloads audio via `yt-dlp`, optionally adjusts speed, returns the MP3.

**Flow C (later, optional) — paste English/foreign text, get bilingual audio:**
1. User pastes text in the *target* language.
2. App translates each sentence and produces the `[de] · pause · [en] · pause` audio the CLI does today.
3. Downloads the resulting MP3.

---

## Tech stack (recommended)

- **Frontend + hosting**: Next.js (App Router) on Vercel. Free Hobby tier is fine to start.
- **Styling**: Tailwind CSS (default Next.js setup). Don't overdesign — this is a personal tool.
- **TTS**: keep `edge-tts` (already chosen and working). Call it from a server-side route. `edge-tts` uses WebSockets to `speech.platform.bing.com`; Vercel's Node runtime supports this. **Use Node.js TTS bindings**, not the Python lib, since Vercel functions are Node-first. See `msedge-tts` on npm — same Microsoft endpoint, same voices.
- **Authentication**: one shared passphrase, checked server-side, set as an HTTP-only cookie. Don't build accounts — there's one user.
- **Storage of generated MP3s**: for v1, stream the MP3 back in the response (no storage needed). For v2 jobs, use Vercel Blob (free tier: 1GB) or write to `/tmp` on the backend and serve a short-lived signed URL.

---

## The hard constraint: Vercel function timeouts

| Plan | Timeout | What fits |
|------|---------|-----------|
| Hobby | 10s | A few sentences of TTS only |
| Pro | 60s | A short article (~500 words German) |
| Background functions (Pro+) | 5 min | Most things, but $$$ |

`yt-dlp`, long-form TTS (a full book chapter), and bilingual generation all exceed 60s. That means the architecture has two halves:

- **Short-job mode** (text ≤ ~500 words): runs entirely inside a Vercel route, streams MP3 back. v1.
- **Long-job mode** (everything else): needs an always-on backend somewhere. v2+.

### Backend options for long-job mode (rank ordered)

1. **Render.com free web service** — Python FastAPI container, 512MB RAM, spins down after 15 min idle (~30s cold start), 750 free hours/month. Plenty for personal use. **Recommended primary**.
2. **Fly.io free tier** — similar shape, 3 small VMs free, no spindown if kept warm. Slightly more setup.
3. **User's own Mac, exposed via Cloudflare Tunnel** — free, full power, but Mac must be on. Good as a fallback or for heavy jobs.

The Vercel frontend talks to the backend over HTTPS for these heavy jobs. Backend URL goes in an env var.

---

## Architecture

```
┌─────────────────────────┐
│ User's iPhone / Mac     │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐    short jobs       ┌─────────────────────┐
│ Vercel: Next.js app     │◄────────────────────►│ Vercel API route    │
│ - login form            │                      │ (edge-tts, < 60s)   │
│ - text/URL form         │                      └─────────────────────┘
│ - progress UI           │
└────────┬────────────────┘    long jobs
         │                     (submit + poll)
         ▼
┌─────────────────────────┐
│ Render / Fly backend    │
│ - FastAPI / Express     │
│ - edge-tts, yt-dlp,     │
│   ffmpeg                │
│ - job queue (in-process)│
│ - MP3 storage (/tmp)    │
└─────────────────────────┘
```

---

## Implementation phases

### v1 — MVP (Vercel-only, short text)

Scope: paste up to ~500 words of German text → MP3 download. No backend service.

Deliverables:
- `webapp/` Next.js app deployed to Vercel.
- Pages: `/` (login) and `/generate` (form).
- API route `POST /api/tts` that takes `{ text, voice, speed }`, calls `msedge-tts`, streams MP3 back.
- Shared passphrase auth (env var `WEBAPP_PASSPHRASE`).
- Tailwind UI: one big text-area, a voice select, a generate button, a download link when ready.
- Hard limit: server-side reject text longer than 2000 chars (≈ what fits in Pro's 60s) and recommend the CLI for longer.

Definition of done: Aiden can paste a German paragraph, hit generate, and download an MP3 he can AirDrop to his phone.

### v2 — long jobs + queue

Scope: handle long text (full chapters, articles) without timing out.

Deliverables:
- `backend/` FastAPI service deployed to Render free tier.
- Backend endpoints:
  - `POST /jobs` — submit a job (text, voice, speed, type=tts), returns `{ jobId }`.
  - `GET /jobs/:id` — status (`pending` / `running` / `done` / `error`) and download URL when done.
  - `GET /files/:id` — download the MP3 (signed token in query string).
- Frontend submits to backend, polls `/jobs/:id`, shows progress, offers download when ready.
- In-process job queue (a simple `asyncio.Queue` is fine for one user); MP3s saved to `backend/output/`, deleted after 24h.
- Backend URL configured via env var `BACKEND_URL` in Vercel.

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

- **`scripts/build_session.py`** has all the TTS + gap + concat logic. For the web app, **extract it into a Python module (`lib/tts.py`) or port the equivalent to TypeScript using `msedge-tts`.** Don't rewrite the gap math — copy it.
- **`PROJECT_PLAN.md`** is the source of truth for defaults (voice IDs, gap timings, card structure). Use those exact values so the web app sounds identical to the CLI output.
- **`memory/feedback_voice_consistency.md`** (if present in the user's memory): one voice per session, do not switch mid-session.

---

## Questions to ask Aiden at the start of the Claude Code session

Before writing code, confirm these:

1. **Auth approach**: shared passphrase (recommended for one user, simplest) or magic-link login?
2. **Voice exposure**: in the UI, expose Katja/Conrad as a dropdown, or auto-pick per session like the CLI does?
3. **Speed default**: 1.0× or 0.9× by default for long-form?
4. **v1 scope**: ship a Vercel-only MVP first (short text, no backend), or skip straight to v2 with the Render backend so it can handle long jobs day one?
5. **Backend choice for v2**: Render free tier (recommended), Fly.io, or his own Mac via Cloudflare Tunnel?
6. **Domain**: deploy to `*.vercel.app` or set up a custom subdomain?

---

## Deployment notes

- Vercel: `vercel link`, then `vercel --prod` from `webapp/`. Vercel auto-deploys on `git push` once the GitHub repo is linked.
- Render: connect the GitHub repo, point at `backend/`, set `pip install -r requirements.txt` + `uvicorn main:app --host 0.0.0.0 --port $PORT`. Render auto-deploys on push.
- Env vars to configure:
  - Vercel: `WEBAPP_PASSPHRASE`, `BACKEND_URL` (for v2+).
  - Render: `WEBAPP_PASSPHRASE` (same value, used to validate requests from frontend).

---

## Out of scope

- Multiple users / accounts.
- DRM-protected content (audiobooks behind Audible, paid podcasts).
- Mobile app (Vercel web UI is sufficient).
- Real-time/streaming TTS — generate-and-download is the right shape.
- Anki sync, spaced-repetition scoring — these go in the CLI side, not the web app.

---

## Definition of "done" overall

When v1 is live: Aiden visits `runDictation.vercel.app` (or wherever), enters a passphrase, pastes a German paragraph, clicks a button, and gets an MP3. End to end works from his phone too (so he can paste from articles he finds while browsing).

When v3 is live: same site, paste a YouTube URL, get the audio (optionally slowed), MP3 ready to download.
