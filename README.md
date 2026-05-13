# RunDictation

Generate bilingual German→English MP3s for language-learning on runs. Play on iPhone with screen off.

See [`PROJECT_PLAN.md`](./PROJECT_PLAN.md) for the full architecture.

## Setup (one time, on your Mac)

```bash
cd ~/Documents/Claude/Projects/RunDictation

# 1. Make sure ffmpeg is installed (pydub depends on it):
brew install ffmpeg

# 2. Create a virtualenv and install Python deps:
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Quick smoke test

Generate a test MP3 from the included `test_cards.csv`:

```bash
source .venv/bin/activate     # if not already active
python scripts/build_session.py \
    --input data/csvs/test_cards.csv \
    --output output/L1/smoke_test.mp3
```

By default this picks one German voice (Katja or Conrad) for the whole MP3. To pin a specific one:

```bash
python scripts/build_session.py \
    --input data/csvs/test_cards.csv \
    --output output/L1/smoke_test_katja.mp3 \
    --voice katja
```

Then AirDrop the MP3 to your iPhone, open in VLC, and listen.

## Daily use (once we've built fetch_sources.py + select_cards.py)

```bash
# Build a fresh L1 session:
python scripts/select_cards.py --level L1 --count 200 --output data/csvs/L1_today.csv
python scripts/build_session.py --input data/csvs/L1_today.csv --output output/L1/run_$(date +%Y%m%d).mp3
```

## CSV format

`build_session.py` accepts a CSV with these columns:

| Column | Required? | Example |
|--------|-----------|---------|
| `de` | yes | `der Hund` |
| `en` | yes | `the dog` |
| `de_example` | optional | `Der Hund bellt laut.` |
| `en_example` | optional | `The dog barks loudly.` |
| `tag` | optional | `slang`, `a1`, `verbs`, etc. |

If `de_example` is present, the card plays 4 segments (word → translation → example → example translation). If not, it plays 2 segments (sentence → translation). Mix both kinds in one CSV freely.

## iPhone playback

- **VLC for Mobile** (free on the App Store) — recommended. AirDrop the MP3, "Open in VLC". Lockscreen + Bluetooth controls work.
- **Apple Music** — alternative. Drag MP3 into Finder library, sync.
- Both play with screen off, both respond to headphone skip/pause buttons.
