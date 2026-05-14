# RunDictation — orientation for Claude Code

This file orients you when you start a new session in this repo. Read it first, then read whichever sub-doc matches your task.

## What this project is

RunDictation generates German→English audio MP3s for language learning on runs. Audio plays on iPhone with the screen off; the listener hears a German prompt, a pause, then the English translation. Three "levels":

- **L1** — top common words, with example sentence (`build_session.py`)
- **L2** — common sentences (`build_session.py`)
- **L3** — long-form German audio: books, podcasts, YouTube (`tts_long.py`, `grab_audio.py` — not yet built)

See [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) at the repo root for full architecture, source data, file layout, and locked decisions.

## What's already built

### CLI tools
- `scripts/build_session.py` — CSV → bilingual MP3 generator. Works end-to-end with `edge-tts` (free, no API key) and `pydub`. **Reuse this** rather than rewriting the TTS/concat logic.
- `data/csvs/test_cards.csv` — 11 hand-crafted test cards (used for smoke-testing).

### Web app (deployed, v2)
- `webapp/` — Next.js 14 frontend on Vercel. Login page + generate page. Light theme, Tailwind v4, `lucide-react` icons.
- `backend/` — FastAPI backend on Render free tier. Async TTS job queue via `edge-tts` v7 (Python). Endpoints: `/jobs` (submit), `/jobs/:id` (poll), `/files/:id` (download), `/health` (wake-up).
- Auth: shared passphrase, HTTP-only cookie for page protection, SHA-256 hash in Authorization header for backend calls.
- See [`docs/WEBAPP_HANDOFF.md`](./docs/WEBAPP_HANDOFF.md) for full architecture, auth flow, and env vars.

### Docs
- `PROJECT_PLAN.md` — architecture decisions and the locked defaults below.
- `requirements.txt`, `README.md`, `.gitignore`.

## Locked defaults (do not change without asking)

- **TTS**: `edge-tts` (Microsoft Edge neural voices). Free, no API key, no realistic quota for personal use.
- **German voices**: `de-DE-KatjaNeural` (female), `de-DE-ConradNeural` (male).
- **English voice**: `en-US-AriaNeural`.
- **Voice consistency**: one German voice per generated MP3. Do not switch voices mid-session. See `memory/feedback_voice_consistency.md` if available.
- **Card timing**: defaults in `build_session.py`; the post-German "translate it in your head" gap is 2.0s.
- **No LLM-generated content** in the actual learning material — all words/sentences must come from real sources (Tatoeba, kaikki.org Wiktextract, FrequencyWords, user-supplied text). LLMs are fine for code, infra, and tooling.

## Tasks by sub-doc

- **Building the web app** (Vercel-hosted UI for pasting URLs/text without using the terminal): read [`docs/WEBAPP_HANDOFF.md`](./docs/WEBAPP_HANDOFF.md).
- **Building the next CLI tool** (`fetch_sources.py`, `select_cards.py`, `tts_long.py`, `grab_audio.py`): the spec lives in [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) under "Per-script CLIs."

## Conventions

- Python 3.10+, `asyncio` for `edge-tts` calls.
- Keep CLI tools self-contained scripts in `scripts/`. They should run via `python scripts/<name>.py --help`.
- Web app code lives in `webapp/` (Next.js 14). Backend lives in `backend/` (Python/FastAPI). Both deployed.
- Shared TTS logic: extract from `build_session.py` into `lib/tts.py` when you need to reuse it in the web app. Don't duplicate.
- Generated audio goes to `output/`; raw data downloads to `data/sources/`; both are gitignored.
- The user runs on macOS with `ffmpeg` (brew), `python3`, and `git` already installed.

## User profile (relevant for code style and explanations)

- Comfortable with Python and the terminal.
- Learning German first, plans to extend to French and Italian (same `edge-tts` voice swap).
- Uses iPhone; the playback target is always "MP3 that works in VLC/Apple Music with the screen off."
