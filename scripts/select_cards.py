#!/usr/bin/env python3
"""
select_cards.py — turn the raw downloaded sources into a curated CSV
ready for build_session.py.

STATUS: STUB. CLI surface is final; implementation is intentionally skeletal.
Claude Code (or a future you) is expected to fill in the TODO blocks.

CSV output schema (must match what build_session.py expects):
    de, en, de_example, en_example, tag

L1 mode (word cards):
    Reads top-N words from data/sources/de_50k.txt (Hermit Dave frequency list).
    For each word, looks up English translation + tags + example in
    data/sources/kaikki_german.json (Wiktextract).
    Optionally filters by tag (e.g. --slang-only).

L2 mode (sentence cards):
    Reads data/sources/deu_sentences.tsv and joins against eng_sentences.tsv
    via data/sources/links.csv to find German↔English sentence pairs.
    Filters by sentence length, vocabulary, optional tag.

Usage:
    python scripts/select_cards.py --level L1 --count 500 \\
        --output data/csvs/L1_top500.csv

    python scripts/select_cards.py --level L1 --slang-only \\
        --output data/csvs/L1_slang.csv

    python scripts/select_cards.py --level L2 --max-tokens 8 --count 200 \\
        --output data/csvs/L2_short.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO_ROOT / "data" / "sources"


# ---------- L1: words ----------

def load_frequency_list(path: Path, limit: int | None = None) -> list[tuple[str, int]]:
    """Read Hermit Dave de_50k.txt: 'wort 12345' lines, return [(word, rank)]."""
    out: list[tuple[str, int]] = []
    with path.open(encoding="utf-8") as f:
        for rank, line in enumerate(f, start=1):
            parts = line.strip().split()
            if not parts:
                continue
            out.append((parts[0], rank))
            if limit and rank >= limit:
                break
    return out


def kaikki_lookup(kaikki_path: Path, words: set[str]) -> dict[str, dict]:
    """
    Stream the kaikki JSONL dump and pull entries for words we care about.

    Each line in kaikki_german.json is one entry. Relevant fields per entry:
        word           - lowercased headword
        senses[]       - each has glosses[] (English defs), tags[] (e.g. 'colloquial')
        senses[].examples[] - {text, english} pairs sometimes present

    TODO (implementer):
      - Open kaikki_path, iterate JSONL.
      - For each entry whose lemma matches one of `words`, collect:
          { 'en': first English gloss,
            'tags': sorted unique tags from senses,
            'de_example': first example with German + English,
            'en_example': matching English }
      - Return dict keyed by lemma.
      - The file is huge; do this with a single streaming pass.
      - If `words` is empty, raise so we don't accidentally load the whole dict.
    """
    raise NotImplementedError("TODO: implement kaikki streaming lookup (see docstring)")


def build_l1_rows(args) -> list[dict]:
    freq_path = SOURCES_DIR / "de_50k.txt"
    kaikki_path = SOURCES_DIR / "kaikki_german.json"
    if not freq_path.exists():
        sys.exit(f"missing {freq_path}; run scripts/fetch_sources.py")
    if not kaikki_path.exists():
        sys.exit(f"missing {kaikki_path}; run scripts/fetch_sources.py --only kaikki")

    freq = load_frequency_list(freq_path, limit=args.count * 5)  # over-fetch
    candidate_words = {w for w, _ in freq}
    lookups = kaikki_lookup(kaikki_path, candidate_words)

    rows: list[dict] = []
    for word, rank in freq:
        entry = lookups.get(word)
        if not entry:
            continue
        if args.slang_only and not any(t in entry.get("tags", [])
                                       for t in ("colloquial", "slang", "vulgar")):
            continue
        rows.append({
            "de": word,
            "en": entry["en"],
            "de_example": entry.get("de_example", ""),
            "en_example": entry.get("en_example", ""),
            "tag": ",".join(entry.get("tags", []) or ["a1"]),
        })
        if len(rows) >= args.count:
            break
    return rows


# ---------- L2: sentences ----------

def build_l2_rows(args) -> list[dict]:
    """
    TODO (implementer):
      - Load deu_sentences.tsv (cols: id<TAB>lang<TAB>text) into {id: text}.
      - Load eng_sentences.tsv similarly.
      - Stream links.csv (cols: source_id<TAB>target_id) to find pairs where
        source is in the German set and target is in the English set.
      - For each pair, optionally filter by token count of the German side
        (<= args.max_tokens).
      - Random-sample down to args.count for variety; seed via args.seed.
      - Return rows with {de, en, de_example: "", en_example: "", tag: "a1..."}.

    Notes:
      - Tatoeba sentences carry no CEFR level. For grading by difficulty,
        join against the L1 frequency list and accept only sentences whose
        words are all within top-K frequency.
      - eng_sentences.tsv is millions of rows; load just the IDs you need
        (two-pass: first scan links to learn relevant English IDs, then a
        targeted read of eng_sentences).
    """
    raise NotImplementedError("TODO: implement Tatoeba join (see docstring)")


# ---------- output ----------

def write_csv(rows: list[dict], out_path: Path) -> None:
    if not rows:
        sys.exit("error: no rows produced; widen filters or run fetch_sources first")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["de", "en", "de_example", "en_example", "tag"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows → {out_path}", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--level", choices=["L1", "L2"], required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--count", type=int, default=200, help="number of cards (default 200)")
    p.add_argument("--seed", type=int, default=42)

    # L1-only
    p.add_argument("--slang-only", action="store_true",
                   help="L1: keep only entries tagged colloquial/slang/vulgar")

    # L2-only
    p.add_argument("--max-tokens", type=int, default=None,
                   help="L2: max German tokens per sentence (e.g. 8 for short)")
    p.add_argument("--frequency-cap", type=int, default=None,
                   help="L2: accept sentences only if every word is within top-K of frequency list")

    args = p.parse_args()

    if args.level == "L1":
        rows = build_l1_rows(args)
    else:
        rows = build_l2_rows(args)

    write_csv(rows, args.output)


if __name__ == "__main__":
    main()
