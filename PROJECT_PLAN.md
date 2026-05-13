# RunDictation — Project Plan

Generate bilingual audio MP3s for language-learning on runs. Play through headphones with iPhone screen off.

---

## Goal

Replace passively listening to foreign-language podcasts on Spotify (which doesn't teach much without comprehension) with structured German→English audio that fits naturally into a run. Pre-generate everything as plain MP3s so screen-off playback, lockscreen controls, and Bluetooth headphone buttons all work without any custom mobile app.

Target language: **German first**. Extensible to French and Italian (same TTS provider supports both with equal quality).

---

## Architecture: the three levels

| Level | Content | Format per "card" | Use case |
|-------|---------|-------------------|----------|
| **L1** | Top ~500 most common words | `[de word] · pause · [en translation]` | Vocabulary building, easy runs |
| **L2** | Common sentences (A1–B1) | `[de sentence] · pause · [en translation]` | Grammar + listening comprehension |
| **L3** | Long-form German (books, podcasts, YouTube) | Continuous German audio | Immersion once L1/L2 give you a foothold |

The same `build_session.py` produces L1 and L2 sessions — only the CSV input differs. L3 has its own tools: `tts_long.py` for text-to-audio, `grab_audio.py` for downloading existing audio.

---

## Data sources (no LLM-generated content)

**Frequency lists (L1):**
- **Hermit Dave's FrequencyWords** — `github.com/hermitdave/FrequencyWords/raw/master/content/2018/de/de_50k.txt`. Top 50,000 German words by real-world frequency from OpenSubtitles corpus. CC-BY-SA.

**Translations for L1:**
- **dict.cc** German-English dictionary export (free for personal use), OR
- **Wiktionary** dumps (free, CC-licensed), OR
- A pre-built Anki deck like *"A Frequency Dictionary of German: 4034 Words"* (Jones & Tschirner) exported to CSV.
- *Decision needed below: which translation source to use.*

**Sentence pairs (L2):**
- **Tatoeba** — `downloads.tatoeba.org/exports/sentences.tar.bz2` + `links.tar.bz2`. ~370k German sentences, each with one or more human-contributed English translations. CC-BY 2.0 FR. Filter by length, vocabulary, and tags to grade difficulty.

**Long-form German text (L3):**
- **Project Gutenberg** German collection (`gutenberg.org/browse/languages/de`) — public domain. Kafka, the Grimms, Goethe, Mann's earlier work, etc.
- Your own legally-owned EPUBs (personal-use TTS is fine).
- Any text you paste into a `.txt` file.

**Long-form German audio (L3):**
- **LibriVox** (`librivox.org`) — free public-domain German audiobooks read by volunteers.
- **YouTube** — via `yt-dlp`, any video's audio track.
- **Podcasts** — directly from RSS, via `yt-dlp` or `podcast-dl`. (Or just use Apple Podcasts; it already handles screen-off playback.)

---

## TTS

**`edge-tts`** (Python package, calls Microsoft Edge's neural TTS API).

- Free, no API key, no realistic quota for personal use.
- German voices: `de-DE-KatjaNeural` (F), `de-DE-ConradNeural` (M). Both genuinely natural.
- English voice (for translations): `en-US-AriaNeural` (F) or `en-US-GuyNeural` (M).
- French/Italian voices available when we expand.

Fallback option if Edge TTS ever becomes unavailable: **Piper** (fully offline neural TTS, free).

---

## Audio specs

**Default L2 (sentence) card timing:**
```
[0.3s silence] [German sentence] [2.0s gap] [English translation] [1.5s gap]
```

**Default L1 (word + example) card timing:**
```
[0.3s silence] [German word] [1.5s gap] [English translation] [1.0s gap] [German example sentence] [2.0s gap] [English example translation] [1.5s gap]
```

The 2.0s post-German gap is the "translate it in your head" window. Tunable; you'll likely want to shorten as you improve.

**Optional knobs (CLI flags):**
- `--gap-de SECONDS` — pause after German (default 2.0)
- `--gap-en SECONDS` — pause after English (default 1.5)
- `--repeat N` — repeat each card N times (default 1)
- `--speed FLOAT` — German playback speed (default 1.0; try 0.9 for harder content)
- `--voice-de VOICE` — German voice (default `de-DE-KatjaNeural`)
- `--voice-en VOICE` — English voice (default `en-US-AriaNeural`)
- `--include-example` — for L1 word cards, append a German example phrase after the translation
- `--shuffle` / `--seed N` — randomize card order, with reproducible seed

**Target session length:** 30–40 min per MP3 (configurable via card count). One MP3 = one run.

---

## File layout

```
RunDictation/
├── PROJECT_PLAN.md           ← this file
├── README.md                 ← short usage doc (written last)
├── requirements.txt          ← edge-tts, pydub, requests, yt-dlp
├── scripts/
│   ├── fetch_sources.py      ← one-time data download
│   ├── select_cards.py       ← raw sources → curated CSV
│   ├── build_session.py      ← CSV → bilingual MP3 (L1 + L2)
│   ├── tts_long.py           ← German text → long MP3 (L3)
│   └── grab_audio.py         ← URL → MP3 (L3 alt)
├── data/
│   ├── sources/              ← raw downloads (gitignored if we ever git this)
│   │   ├── de_50k.txt
│   │   ├── tatoeba_de.tsv
│   │   └── tatoeba_links.tsv
│   └── csvs/                 ← curated decks ready for build_session.py
│       ├── L1_top500.csv
│       ├── L2_a2_sentences.csv
│       └── L2_b1_sentences.csv
├── output/
│   ├── L1/                   ← generated MP3s, one per session
│   ├── L2/
│   └── L3/
└── cache/                    ← per-sentence TTS cache for resume-on-failure
```

---

## Per-script CLIs

```bash
# One-time setup
python scripts/fetch_sources.py                      # downloads everything into data/sources/

# Build a curated CSV from sources
python scripts/select_cards.py \
    --level L1 \
    --count 500 \
    --output data/csvs/L1_top500.csv

python scripts/select_cards.py \
    --level L2 \
    --max-length 8 \
    --count 200 \
    --output data/csvs/L2_short.csv

# Build an audio session
python scripts/build_session.py \
    --input data/csvs/L1_top500.csv \
    --output output/L1/session_001.mp3 \
    --gap-de 2.0 --gap-en 1.5 \
    --shuffle --seed 42

# Long-form: book or article
python scripts/tts_long.py \
    --input my_book.txt \
    --output output/L3/kafka_verwandlung.mp3 \
    --voice-de de-DE-KatjaNeural

# Long-form: YouTube / podcast
python scripts/grab_audio.py \
    --url "https://www.youtube.com/watch?v=..." \
    --output output/L3/easy_german_117.mp3 \
    --slow 0.9    # optional: 0.9x speed, pitch-preserved
```

---

## iPhone playback workflow

1. AirDrop the generated MP3 to your iPhone.
2. Open in **VLC for Mobile** (free, App Store) — gives you a library, playlists, position memory, playback speed control.
3. Plug in headphones, lock the screen, start your run.

Alternative: drop MP3s into Apple Music via Finder sync. Works the same, plays through the native Music app.

---

## Locked decisions

1. **German voice:** alternates between Katja (F) and Conrad (M) per card, deterministic via `--voice-seed` (default 42). English voice stays consistent (Aria) so the "translation" role is audibly distinct from the "prompt" role.
2. **L1 card format:** `word → translation → example sentence (German) → example sentence (English)`. Four segments per card with configurable gaps between each.
3. **L1 translation source:** **kaikki.org Wiktextract** as primary (free, downloadable, includes slang/colloquial/vulgar tags, has example sentences). Tatoeba layered on for additional example sentences with verified translations. dict.cc as an optional add-on if Wiktextract's slang coverage feels thin — user grabs it manually and we re-ingest.
4. **Slang:** entries tagged `colloquial`, `slang`, or `vulgar` in Wiktextract are preserved with their tags. Two ways to use them: (a) mixed into normal decks at natural frequency, (b) dedicated "slang only" decks via a `--slang-only` flag on `select_cards.py`.
5. **Repeat:** each card plays once. `--repeat 2` available as a flag if we want it later.

---

## Future extensions (not v1)

- **Web app frontend (Vercel-hosted).** Replace the terminal with a simple web UI: paste a YouTube URL or a text passage, click a button, get an MP3 download link. Sketch:
  - **Frontend** (Vercel/Next.js): form with text-area + URL input + voice/speed/gap controls; submits a job, polls for status, downloads when done.
  - **Backend**: Vercel's serverless functions have a 10–60s timeout that's too short for long TTS jobs, so the realistic options are (a) a small always-on backend on Render/Railway/Fly.io free tier, (b) a self-hosted backend on the user's Mac exposed via ngrok or Cloudflare Tunnel, or (c) for short-text-only mode, run TTS in a serverless function and stream the MP3 back.
  - **YouTube/podcast capture**: requires `yt-dlp` on the backend (can't run inside Vercel functions), so this feature needs option (a) or (b).
  - **Storage**: generated MP3s live in the backend's `output/` for a few hours, served via signed URL or short-lived public link. No need for a real DB; a JSON file mapping job IDs → file paths is fine.
  - **Auth**: keep it private with a single shared password or a magic-link email login (no accounts to manage).
- **Spaced repetition log** — track which cards have been "heard" in sessions, surface less-frequent ones over time. Simple JSON state file.
- **L2.5: bilingual book reading** — translate a German book sentence-by-sentence and produce `[de] · pause · [en] · pause` audio for the whole thing. Bridges L2 and L3.
- **Whisper transcription** — for podcasts/videos that don't have transcripts, run `whisper` locally to get text, then translate, then re-narrate as L3+translation.
- **Themed decks** — restaurant German, train-station German, weather, past-tense verbs, etc. Just filter Tatoeba by tags.
- **French + Italian** — same pipeline, swap voice IDs and source CSVs.

---

## Out of scope

- Custom mobile app (unnecessary — MP3 + VLC solves this).
- Cloud sync, accounts, multi-user.
- Real-time/streaming TTS (we generate ahead of time on purpose).
- Anything requiring DRM circumvention.
