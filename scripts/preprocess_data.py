#!/usr/bin/env python3
"""
preprocess_data.py — build compact datasets for the Quick Generate backend.

Reads raw source files from data/sources/ and produces deploy-ready
JSON files in backend/data/ that ship with the Render backend.

Sources consumed:
  - data/sources/de_50k.txt            (FrequencyWords: top 50k German words)
  - data/sources/kaikki_german.jsonl   (Wiktextract: dictionary with translations)
  - data/sources/deu_sentences.tsv     (Tatoeba: German sentences)
  - data/sources/eng_sentences.tsv     (Tatoeba: English sentences)
  - data/sources/links.csv             (Tatoeba: sentence translation links)

Run:
    python scripts/preprocess_data.py
    python scripts/preprocess_data.py --max-words 3000 --max-sentences 10000
"""
from __future__ import annotations

import argparse
import gzip
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SOURCES = REPO_ROOT / "data" / "sources"
OUT_DIR = REPO_ROOT / "backend" / "data"

# ---------- Theme keyword lists ----------

THEME_KEYWORDS: dict[str, list[str]] = {
    "travel": [
        "Flughafen", "Hotel", "Reise", "reisen", "Zug", "Bahnhof", "Ticket",
        "Koffer", "Urlaub", "Flug", "Grenze", "Pass", "Visum", "Gepäck",
        "Taxi", "Bus", "Bahn", "Schiff", "Hafen", "Flugzeug", "Ankunft",
        "Abfahrt", "Abreise", "Tourist", "Karte", "Fahrkarte", "Landkarte",
        "Reisebüro", "Sehenswürdigkeit", "Museum", "Strand", "Berg",
        "Reservierung", "buchen", "fliegen", "ankommen", "abfahren",
    ],
    "food": [
        "essen", "Essen", "Küche", "Restaurant", "kochen", "Brot", "Wasser",
        "Kaffee", "Bier", "Wein", "Frühstück", "Mittagessen", "Abendessen",
        "Kuchen", "Fleisch", "Fisch", "Gemüse", "Obst", "Suppe", "Salat",
        "Tee", "Milch", "Zucker", "Salz", "Pfeffer", "Käse", "Butter",
        "Reis", "Kartoffel", "Tomate", "Ei", "Schokolade", "Speise",
        "Gericht", "Rezept", "Teller", "Gabel", "Messer", "Löffel",
        "Kellner", "Rechnung", "bestellen", "schmecken", "trinken",
        "hungrig", "satt", "lecker",
    ],
    "business": [
        "Arbeit", "arbeiten", "Büro", "Chef", "Firma", "Besprechung",
        "Projekt", "Vertrag", "Gehalt", "Kollege", "Kollegin", "Beruf",
        "Karriere", "Bewerbung", "Lebenslauf", "Vorstellungsgespräch",
        "Unternehmen", "Geschäft", "Kunde", "Markt", "Wirtschaft",
        "Handel", "Produkt", "Fabrik", "Industrie", "Manager", "Termin",
        "Konferenz", "Präsentation", "Bericht", "E-Mail", "Telefon",
        "Sitzung", "Abteilung", "Rechnung", "Konto", "Bank", "Geld",
        "verdienen", "kündigen", "einstellen",
    ],
    "daily_life": [
        "Haus", "Wohnung", "Zimmer", "Schule", "Familie", "Kinder", "Kind",
        "Morgen", "Abend", "schlafen", "aufstehen", "Freund", "Freundin",
        "Nachbar", "Straße", "Garten", "Tür", "Fenster", "Schlüssel",
        "Uhr", "Zeit", "Tag", "Nacht", "Woche", "Monat", "Jahr",
        "Geburtstag", "Feier", "Hobby", "Sport", "Musik", "Buch",
        "Film", "Zeitung", "Arzt", "Krankenhaus", "Apotheke", "Wetter",
        "Regen", "Sonne", "kalt", "warm", "Kleidung", "Schuhe",
        "einkaufen", "Supermarkt", "Laden", "Preis", "bezahlen",
    ],
}

# Pre-compile patterns for each theme
THEME_PATTERNS: dict[str, re.Pattern] = {}
for _theme, _words in THEME_KEYWORDS.items():
    # Match whole words (word boundary aware)
    pattern = r"\b(" + "|".join(re.escape(w) for w in _words) + r")\b"
    THEME_PATTERNS[_theme] = re.compile(pattern, re.IGNORECASE)

# Frequency bands
FREQ_BANDS = [
    ("top100", 1, 100),
    ("101-500", 101, 500),
    ("501-2000", 501, 2000),
    ("2001-5000", 2001, 5000),
]


def freq_band_for(rank: int) -> str:
    for name, lo, hi in FREQ_BANDS:
        if lo <= rank <= hi:
            return name
    return "5000+"


# ---------- L1: Word cards ----------

def load_frequency_list(path: Path, max_words: int) -> list[tuple[str, int]]:
    """Return [(word, rank), ...] from FrequencyWords de_50k.txt."""
    words = []
    with path.open(encoding="utf-8") as f:
        for i, line in enumerate(f, start=1):
            parts = line.strip().split()
            if not parts:
                continue
            word = parts[0].lower()
            words.append((word, i))
            if i >= max_words:
                break
    return words


def stream_kaikki(path: Path, target_words: set[str]) -> dict[str, dict]:
    """Stream kaikki JSONL, collect entries matching target words.

    Returns {word: {en, de_example, en_example, tags, pos}} for matched words.
    Picks the first entry with a usable English gloss.
    """
    results: dict[str, dict] = {}
    skipped = 0

    print(f"  Streaming kaikki JSONL ({path.stat().st_size / 1e6:.0f} MB)...", file=sys.stderr)

    with path.open(encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            if line_num % 100_000 == 0:
                print(f"    ...{line_num:,} entries scanned, {len(results)} matched", file=sys.stderr)

            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            word = entry.get("word", "").lower()
            if word not in target_words or word in results:
                continue

            # Extract best English translation from senses
            en_translation = None
            de_example = None
            en_example = None
            tags = []
            pos = entry.get("pos", "")

            for sense in entry.get("senses", []):
                # Collect tags
                sense_tags = sense.get("tags", [])
                tags.extend(sense_tags)

                # Get English gloss
                glosses = sense.get("glosses", [])
                if not glosses:
                    raw_glosses = sense.get("raw_glosses", [])
                    glosses = raw_glosses

                if glosses and not en_translation:
                    gloss = glosses[0]
                    # Skip glosses that are just grammar notes
                    if gloss and len(gloss) < 200 and not gloss.startswith("inflection of"):
                        en_translation = gloss

                # Get example sentence
                for ex in sense.get("examples", []):
                    if de_example:
                        break
                    ex_text = ex.get("text", "").strip()
                    ex_english = ex.get("english", "").strip()
                    # Skip placeholder translations
                    if ex_text and ex_english and "please add" not in ex_english.lower():
                        de_example = ex_text
                        en_example = ex_english

            if en_translation:
                results[word] = {
                    "en": en_translation,
                    "de_example": de_example or "",
                    "en_example": en_example or "",
                    "tags": list(set(tags)),
                    "pos": pos,
                }

            # Early exit if we found all target words
            if len(results) >= len(target_words):
                break

    print(f"    Done. {len(results)}/{len(target_words)} words matched. "
          f"({skipped} parse errors skipped)", file=sys.stderr)
    return results


def build_words(max_words: int) -> tuple[list[dict], dict]:
    """Build L1 word data. Returns (word_list, band_stats)."""
    print("\n=== Building L1 word data ===", file=sys.stderr)

    freq_path = SOURCES / "de_50k.txt"
    kaikki_path = SOURCES / "kaikki_german.jsonl"

    if not freq_path.exists():
        raise SystemExit(f"Missing {freq_path}. Run: python scripts/fetch_sources.py --only frequency")
    if not kaikki_path.exists():
        raise SystemExit(f"Missing {kaikki_path}. Run: python scripts/fetch_sources.py --only kaikki")

    # Load frequency list
    freq_list = load_frequency_list(freq_path, max_words)
    target_words = {w for w, _ in freq_list}
    print(f"  Loaded {len(freq_list)} words from frequency list", file=sys.stderr)

    # Look up translations in kaikki
    kaikki_data = stream_kaikki(kaikki_path, target_words)

    # Build output
    words = []
    band_counts: dict[str, int] = defaultdict(int)

    for word, rank in freq_list:
        if word not in kaikki_data:
            continue

        info = kaikki_data[word]
        band = freq_band_for(rank)

        entry = {
            "de": word,
            "en": info["en"],
            "de_example": info["de_example"],
            "en_example": info["en_example"],
            "freq_rank": rank,
            "freq_band": band,
            "pos": info["pos"],
            "tags": info["tags"],
        }
        words.append(entry)
        band_counts[band] += 1

    print(f"  Result: {len(words)} words with translations", file=sys.stderr)
    for band_name, lo, hi in FREQ_BANDS:
        print(f"    {band_name}: {band_counts.get(band_name, 0)}", file=sys.stderr)

    return words, dict(band_counts)


# ---------- L2: Sentence pairs ----------

def tag_themes(text: str) -> list[str]:
    """Tag a German sentence with themes based on keyword matching."""
    themes = []
    for theme, pattern in THEME_PATTERNS.items():
        if pattern.search(text):
            themes.append(theme)
    return themes if themes else ["general"]


def build_sentences(max_sentences: int) -> tuple[list[dict], dict]:
    """Build L2 sentence pair data. Returns (sentence_list, theme_stats)."""
    print("\n=== Building L2 sentence data ===", file=sys.stderr)

    deu_path = SOURCES / "deu_sentences.tsv"
    eng_path = SOURCES / "eng_sentences.tsv"
    links_path = SOURCES / "links.csv"

    for p in (deu_path, eng_path, links_path):
        if not p.exists():
            raise SystemExit(f"Missing {p}. Run: python scripts/fetch_sources.py")

    # Load German sentences
    print(f"  Loading German sentences...", file=sys.stderr)
    de_sentences: dict[int, str] = {}
    with deu_path.open(encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                try:
                    sid = int(parts[0])
                    text = parts[2]
                    word_count = len(text.split())
                    # Filter: 3-15 words, reasonable length
                    if 3 <= word_count <= 15 and len(text) <= 200:
                        de_sentences[sid] = text
                except (ValueError, IndexError):
                    continue
    print(f"    {len(de_sentences):,} German sentences (3-15 words)", file=sys.stderr)

    # Load links (German → English)
    print(f"  Loading translation links...", file=sys.stderr)
    de_to_en: dict[int, list[int]] = defaultdict(list)
    with links_path.open(encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                try:
                    id1 = int(parts[0])
                    id2 = int(parts[1])
                    if id1 in de_sentences:
                        de_to_en[id1].append(id2)
                except (ValueError, IndexError):
                    continue
    print(f"    {len(de_to_en):,} German sentences have links", file=sys.stderr)

    # Collect needed English IDs
    needed_en = set()
    for en_ids in de_to_en.values():
        needed_en.update(en_ids)

    # Load matching English sentences
    print(f"  Loading English sentences ({len(needed_en):,} needed)...", file=sys.stderr)
    en_sentences: dict[int, str] = {}
    with eng_path.open(encoding="utf-8") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                try:
                    sid = int(parts[0])
                    if sid in needed_en:
                        en_sentences[sid] = parts[2]
                except (ValueError, IndexError):
                    continue
    print(f"    {len(en_sentences):,} English translations loaded", file=sys.stderr)

    # Build paired sentences
    print(f"  Building pairs and tagging themes...", file=sys.stderr)
    sentences = []
    seen_de: set[str] = set()  # deduplicate by German text
    theme_counts: dict[str, int] = defaultdict(int)

    for de_id, de_text in de_sentences.items():
        if de_text in seen_de:
            continue

        en_ids = de_to_en.get(de_id, [])
        en_text = None
        for eid in en_ids:
            if eid in en_sentences:
                en_text = en_sentences[eid]
                break

        if not en_text:
            continue

        seen_de.add(de_text)
        themes = tag_themes(de_text)
        word_count = len(de_text.split())

        entry = {
            "de": de_text,
            "en": en_text,
            "themes": themes,
            "word_count": word_count,
            "id": de_id,
        }
        sentences.append(entry)
        for t in themes:
            theme_counts[t] += 1

        if len(sentences) >= max_sentences:
            break

    print(f"  Result: {len(sentences):,} sentence pairs", file=sys.stderr)
    for theme in sorted(theme_counts):
        print(f"    {theme}: {theme_counts[theme]:,}", file=sys.stderr)

    return sentences, dict(theme_counts)


# ---------- Main ----------

def main():
    parser = argparse.ArgumentParser(description="Preprocess source data for Quick Generate backend")
    parser.add_argument("--max-words", type=int, default=5000,
                        help="max words from frequency list (default: 5000)")
    parser.add_argument("--max-sentences", type=int, default=20000,
                        help="max sentence pairs to keep (default: 20000)")
    args = parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # Build words
    words, band_stats = build_words(args.max_words)

    words_path = OUT_DIR / "words.jsonl.gz"
    with gzip.open(words_path, "wt", encoding="utf-8") as f:
        for w in words:
            f.write(json.dumps(w, ensure_ascii=False) + "\n")
    print(f"\n  Wrote {words_path} ({words_path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)

    # Build sentences
    sentences, theme_stats = build_sentences(args.max_sentences)

    sentences_path = OUT_DIR / "sentences.jsonl.gz"
    with gzip.open(sentences_path, "wt", encoding="utf-8") as f:
        for s in sentences:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    print(f"  Wrote {sentences_path} ({sentences_path.stat().st_size / 1024:.0f} KB)", file=sys.stderr)

    # Build stats
    words_with_examples = sum(1 for w in words if w["de_example"])

    stats = {
        "words": {
            "total": len(words),
            "with_examples": words_with_examples,
            "by_band": band_stats,
        },
        "sentences": {
            "total": len(sentences),
            "by_theme": theme_stats,
        },
        "timing_estimates": {
            "seconds_per_l1_card": 27.5,
            "seconds_per_l2_card": 17.5,
        },
    }

    stats_path = OUT_DIR / "stats.json"
    with stats_path.open("w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"  Wrote {stats_path}", file=sys.stderr)

    print(f"\n=== Done ===", file=sys.stderr)
    print(f"  {len(words)} words, {len(sentences):,} sentences", file=sys.stderr)
    print(f"  Files in {OUT_DIR}/", file=sys.stderr)


if __name__ == "__main__":
    main()
