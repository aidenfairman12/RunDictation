#!/usr/bin/env python3
"""
fetch_sources.py — one-time download of the raw data RunDictation depends on.

Drops everything into data/sources/. Idempotent: skips already-downloaded files
unless --force is passed. Run from the repo root:

    python scripts/fetch_sources.py
    python scripts/fetch_sources.py --only frequency tatoeba
    python scripts/fetch_sources.py --force

Sources:
  frequency — Hermit Dave's FrequencyWords (top 50k German words by frequency).
              https://github.com/hermitdave/FrequencyWords  (CC-BY-SA)
  tatoeba   — Per-language sentence dumps + the cross-language links file.
              Used to find English translations for German sentences.
              https://tatoeba.org/eng/downloads  (CC-BY 2.0 FR)
  kaikki    — Wiktextract-parsed German Wiktionary entries with senses, tags,
              examples. Includes 'colloquial', 'slang', 'vulgar' tags we want.
              https://kaikki.org/dictionary/German  (CC-BY-SA, ~hundreds of MB)

If a URL ever 404s, Tatoeba changes its export paths occasionally — check
https://downloads.tatoeba.org/exports/ for the current layout.
"""
from __future__ import annotations

import argparse
import bz2
import shutil
import sys
import tarfile
import urllib.request
from pathlib import Path

# Layout: name -> {url, dest (relative to repo root), extract_to (optional)}
SOURCES: dict[str, dict] = {
    "frequency": {
        "url": "https://raw.githubusercontent.com/hermitdave/FrequencyWords/master/content/2018/de/de_50k.txt",
        "dest": "data/sources/de_50k.txt",
    },
    "tatoeba_de": {
        "url": "https://downloads.tatoeba.org/exports/per_language/deu/deu_sentences.tsv.bz2",
        "dest": "data/sources/deu_sentences.tsv.bz2",
        "extract_bz2_to": "data/sources/deu_sentences.tsv",
    },
    "tatoeba_en": {
        "url": "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2",
        "dest": "data/sources/eng_sentences.tsv.bz2",
        "extract_bz2_to": "data/sources/eng_sentences.tsv",
    },
    "tatoeba_links": {
        "url": "https://downloads.tatoeba.org/exports/links.tar.bz2",
        "dest": "data/sources/links.tar.bz2",
        "extract_tar_to": "data/sources/",  # produces links.csv
    },
    "kaikki": {
        "url": "https://kaikki.org/dictionary/German/kaikki.org-dictionary-German.json",
        "dest": "data/sources/kaikki_german.json",
        "optional": True,  # large; opt in with --only kaikki or full run
        "note": "Large file (~hundreds of MB). Skip with --skip kaikki if you want a faster setup.",
    },
}

ALIASES = {
    "tatoeba": ["tatoeba_de", "tatoeba_en", "tatoeba_links"],
}


def expand_names(names: list[str]) -> list[str]:
    """Expand aliases like 'tatoeba' → ['tatoeba_de', ...]."""
    out: list[str] = []
    for n in names:
        out.extend(ALIASES.get(n, [n]))
    return out


def human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def download(url: str, dest: Path, force: bool = False) -> bool:
    """Download `url` to `dest`. Returns True if a download happened."""
    if dest.exists() and not force:
        print(f"  ✓ already have {dest} ({human_bytes(dest.stat().st_size)})", file=sys.stderr)
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ↓ downloading {url}", file=sys.stderr)
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with urllib.request.urlopen(url) as resp, tmp.open("wb") as out:
            total = int(resp.headers.get("Content-Length", 0))
            read = 0
            chunk = 1024 * 64
            while True:
                buf = resp.read(chunk)
                if not buf:
                    break
                out.write(buf)
                read += len(buf)
                if total:
                    pct = 100 * read / total
                    print(f"    {human_bytes(read)} / {human_bytes(total)}  ({pct:.1f}%)",
                          end="\r", file=sys.stderr)
            print("", file=sys.stderr)  # newline after progress
        tmp.rename(dest)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise
    return True


def extract_bz2(src: Path, dest: Path, force: bool = False) -> None:
    if dest.exists() and not force:
        return
    print(f"  ⇪ decompressing {src.name} → {dest.name}", file=sys.stderr)
    with bz2.open(src, "rb") as fin, dest.open("wb") as fout:
        shutil.copyfileobj(fin, fout)


def extract_tar(src: Path, dest_dir: Path, force: bool = False) -> None:
    # Skip if any obvious extracted file is present
    if (dest_dir / "links.csv").exists() and not force:
        return
    print(f"  ⇪ extracting {src.name} → {dest_dir}", file=sys.stderr)
    with tarfile.open(src, "r:bz2") as tar:
        tar.extractall(dest_dir)  # noqa: S202  (trusted source)


def fetch(name: str, force: bool, repo_root: Path) -> None:
    spec = SOURCES[name]
    print(f"\n[{name}]", file=sys.stderr)
    if note := spec.get("note"):
        print(f"  note: {note}", file=sys.stderr)
    dest = repo_root / spec["dest"]
    download(spec["url"], dest, force=force)
    if extract := spec.get("extract_bz2_to"):
        extract_bz2(dest, repo_root / extract, force=force)
    if extract := spec.get("extract_tar_to"):
        extract_tar(dest, repo_root / extract, force=force)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--only", nargs="+", choices=list(SOURCES) + list(ALIASES),
                   help="fetch only these (default: all)")
    p.add_argument("--skip", nargs="+", choices=list(SOURCES) + list(ALIASES),
                   help="fetch everything except these")
    p.add_argument("--force", action="store_true", help="re-download even if file exists")
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent

    targets = list(SOURCES.keys())
    if args.only:
        targets = expand_names(args.only)
    if args.skip:
        for s in expand_names(args.skip):
            targets = [t for t in targets if t != s]

    print(f"Fetching {len(targets)} source(s) into {repo_root / 'data/sources'}", file=sys.stderr)
    for name in targets:
        fetch(name, force=args.force, repo_root=repo_root)
    print("\nDone.", file=sys.stderr)


if __name__ == "__main__":
    main()
