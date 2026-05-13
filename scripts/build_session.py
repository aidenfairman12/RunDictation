#!/usr/bin/env python3
"""
build_session.py — turn a CSV of bilingual flashcards into a single MP3 session.

CSV columns:
    de            (required) German word or sentence
    en            (required) English translation
    de_example    (optional) German example sentence (turns the row into an L1 word card)
    en_example    (optional) English translation of the example
    tag           (optional) free-form tag, ignored by this script but useful for filtering upstream

Card structure:
    L1 (word card, has de_example):
        [silence] [de word] [gap_word] [en word] [gap_def] [de example] [gap_ex] [en example] [gap_after]
    L2 (sentence card, no de_example):
        [silence] [de] [gap_de] [en] [gap_after]

German voice alternates between Katja and Conrad, seeded for reproducibility.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import random
import sys
from pathlib import Path

import edge_tts
from pydub import AudioSegment


GERMAN_VOICES = ["de-DE-KatjaNeural", "de-DE-ConradNeural"]
DEFAULT_ENGLISH_VOICE = "en-US-AriaNeural"

VOICE_ALIASES = {
    "katja":  "de-DE-KatjaNeural",
    "conrad": "de-DE-ConradNeural",
}


# ---------- TTS with on-disk cache ----------

async def tts_segment(text: str, voice: str, cache_dir: Path) -> AudioSegment:
    """Render `text` in `voice` to MP3 (cached on disk) and return as AudioSegment."""
    text = text.strip()
    if not text:
        return AudioSegment.silent(duration=0)
    key = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()[:20]
    path = cache_dir / f"{key}.mp3"
    if not path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        comm = edge_tts.Communicate(text, voice)
        await comm.save(str(path))
    return AudioSegment.from_mp3(path)


def silence(seconds: float) -> AudioSegment:
    return AudioSegment.silent(duration=int(seconds * 1000))


# ---------- Card builders ----------

async def build_word_card(row, voice_de, voice_en, gaps, cache_dir):
    """L1 word card: de_word -> en_word -> de_example -> en_example."""
    de_word = await tts_segment(row["de"], voice_de, cache_dir)
    en_word = await tts_segment(row["en"], voice_en, cache_dir)
    de_ex = await tts_segment(row["de_example"], voice_de, cache_dir)
    en_ex = await tts_segment(row["en_example"], voice_en, cache_dir)
    return (
        silence(0.3)
        + de_word + silence(gaps["word"])
        + en_word + silence(gaps["def"])
        + de_ex + silence(gaps["ex"])
        + en_ex + silence(gaps["after"])
    )


async def build_sentence_card(row, voice_de, voice_en, gaps, cache_dir):
    """L2 sentence card: de -> en."""
    de = await tts_segment(row["de"], voice_de, cache_dir)
    en = await tts_segment(row["en"], voice_en, cache_dir)
    return (
        silence(0.3)
        + de + silence(gaps["de"])
        + en + silence(gaps["after"])
    )


# ---------- Main pipeline ----------

def load_rows(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("de") and r.get("en")]
    if not rows:
        raise SystemExit(f"No usable rows found in {csv_path}")
    return rows


async def build_session(args):
    rows = load_rows(args.input)

    if args.shuffle:
        random.Random(args.seed).shuffle(rows)

    if args.limit:
        rows = rows[: args.limit]

    # Voice picker: deterministic, seeded by --voice-seed
    voice_rng = random.Random(args.voice_seed)

    # If session mode and no explicit --voice given, pick one voice for the whole session
    if args.voice_mode == "session":
        if args.voice:
            session_voice_de = VOICE_ALIASES.get(args.voice.lower(), args.voice)
        else:
            session_voice_de = voice_rng.choice(GERMAN_VOICES)
        print(f"Session voice (German): {session_voice_de}", file=sys.stderr)
    else:
        session_voice_de = None  # picked per card below

    cache_dir = Path(args.cache_dir)

    word_gaps = {
        "word": args.gap_word_def,
        "def":  args.gap_def_ex,
        "ex":   args.gap_ex_trans,
        "after": args.gap_between,
    }
    sentence_gaps = {
        "de":    args.gap_de_en,
        "after": args.gap_between,
    }

    sessions: list[AudioSegment] = []
    total = len(rows)
    for i, row in enumerate(rows, start=1):
        if args.voice_mode == "session":
            voice_de = session_voice_de
        elif args.voice_mode == "alternate":
            voice_de = GERMAN_VOICES[i % len(GERMAN_VOICES)]
        else:  # random
            voice_de = voice_rng.choice(GERMAN_VOICES)

        has_example = bool(row.get("de_example", "").strip()) and bool(row.get("en_example", "").strip())
        if has_example:
            card = await build_word_card(row, voice_de, args.voice_en, word_gaps, cache_dir)
        else:
            card = await build_sentence_card(row, voice_de, args.voice_en, sentence_gaps, cache_dir)

        # optional repeat
        for _ in range(args.repeat):
            sessions.append(card)

        print(f"  [{i}/{total}] {row['de'][:50]}", file=sys.stderr)

    print(f"Stitching {len(sessions)} card-plays...", file=sys.stderr)
    out = sum(sessions, AudioSegment.silent(duration=int(args.lead_in * 1000)))

    # Optional speed adjustment on the whole track (pitch-preserved via ffmpeg).
    # pydub doesn't do this natively well; we export, then re-encode if --speed != 1.0
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if args.speed != 1.0:
        tmp = out_path.with_suffix(".raw.mp3")
        out.export(tmp, format="mp3", bitrate=args.bitrate)
        import subprocess
        # ffmpeg atempo: 0.5 <= factor <= 100.0; chain if outside
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(tmp), "-filter:a", f"atempo={args.speed}",
             "-b:a", args.bitrate, str(out_path)],
            check=True,
        )
        tmp.unlink(missing_ok=True)
    else:
        out.export(out_path, format="mp3", bitrate=args.bitrate)

    duration_min = len(out) / 1000 / 60
    print(f"\nDone. {out_path}  ({duration_min:.1f} min)", file=sys.stderr)


def parse_args():
    p = argparse.ArgumentParser(description="Build a bilingual MP3 session from a flashcard CSV.")
    p.add_argument("--input",  required=True, type=Path, help="CSV of cards")
    p.add_argument("--output", required=True, type=Path, help="output MP3 path")
    p.add_argument("--cache-dir", type=Path, default=Path("cache"),
                   help="per-segment TTS cache (default: ./cache)")

    # Voice
    p.add_argument("--voice-en", default=DEFAULT_ENGLISH_VOICE)
    p.add_argument("--voice-mode", choices=["session", "alternate", "random"], default="session",
                   help="session: one German voice for the whole MP3 (default). "
                        "alternate: switch per card. random: pick per card.")
    p.add_argument("--voice", default=None,
                   help="pin German voice: 'katja', 'conrad', or a full voice ID. "
                        "Implies --voice-mode session.")
    p.add_argument("--voice-seed", type=int, default=42,
                   help="seed for random voice pick (in session or random mode)")

    # Sentence-card gaps
    p.add_argument("--gap-de-en", type=float, default=2.0,
                   help="L2: pause after German sentence, before English (default 2.0s)")
    # Word-card gaps
    p.add_argument("--gap-word-def", type=float, default=1.5,
                   help="L1: pause after German word, before English translation (default 1.5s)")
    p.add_argument("--gap-def-ex",   type=float, default=1.0,
                   help="L1: pause after translation, before example sentence (default 1.0s)")
    p.add_argument("--gap-ex-trans", type=float, default=2.0,
                   help="L1: pause after German example, before its English translation (default 2.0s)")
    # Shared
    p.add_argument("--gap-between", type=float, default=2.5,
                   help="pause between cards (default 2.5s) — wider than intra-card gaps "
                        "so card boundaries are audible on a run")
    p.add_argument("--lead-in",     type=float, default=0.5,
                   help="silence at the very start of the session (default 0.5s)")

    # Card order / repeat
    p.add_argument("--shuffle", action="store_true")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--limit", type=int, default=None, help="cap number of cards")
    p.add_argument("--repeat", type=int, default=1, help="play each card N times (default 1)")

    # Speed (pitch-preserved via ffmpeg)
    p.add_argument("--speed", type=float, default=1.0, help="playback speed (0.5..2.0)")
    p.add_argument("--bitrate", default="96k", help="MP3 bitrate (default 96k)")

    return p.parse_args()


def main():
    args = parse_args()
    asyncio.run(build_session(args))


if __name__ == "__main__":
    main()
