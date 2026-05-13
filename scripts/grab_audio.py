#!/usr/bin/env python3
"""
grab_audio.py — capture audio from a YouTube video or podcast URL as MP3.

Used for L3 (long-form German audio). The output MP3 is plain German audio
with no English translation; the listener immerses in the language directly.

Requires `yt-dlp` and `ffmpeg` on PATH. Install:

    pip install yt-dlp
    brew install ffmpeg

Usage:

    python scripts/grab_audio.py --url "https://www.youtube.com/watch?v=..." \\
        --output output/L3/easy_german_117.mp3

Optional speed adjustment (pitch-preserved via ffmpeg's atempo filter), useful
for fast podcasts:

    python scripts/grab_audio.py --url "..." --output out.mp3 --slow 0.9
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def require(tool: str) -> None:
    if shutil.which(tool) is None:
        sys.exit(f"error: '{tool}' not found on PATH. Install it and retry.")


def yt_dlp_to_mp3(url: str, tmp_dir: Path) -> Path:
    """Download best-quality audio from `url`, return path to resulting MP3."""
    template = str(tmp_dir / "audio.%(ext)s")
    cmd = [
        "yt-dlp",
        "-x", "--audio-format", "mp3", "--audio-quality", "0",
        "-o", template,
        url,
    ]
    subprocess.run(cmd, check=True)
    candidates = list(tmp_dir.glob("audio.mp3"))
    if not candidates:
        sys.exit("error: yt-dlp succeeded but no MP3 was produced")
    return candidates[0]


def ffmpeg_atempo(src: Path, dst: Path, factor: float, bitrate: str) -> None:
    """Adjust playback speed (pitch-preserved) by `factor`."""
    if not (0.5 <= factor <= 2.0):
        sys.exit(f"error: --slow must be between 0.5 and 2.0 (got {factor})")
    cmd = [
        "ffmpeg", "-y", "-i", str(src),
        "-filter:a", f"atempo={factor}",
        "-b:a", bitrate,
        str(dst),
    ]
    subprocess.run(cmd, check=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--url",    required=True, help="YouTube / podcast / direct audio URL")
    p.add_argument("--output", required=True, type=Path, help="output MP3 path")
    p.add_argument("--slow",   type=float, default=None,
                   help="speed factor (e.g. 0.9 for 10%% slower, pitch preserved)")
    p.add_argument("--bitrate", default="128k", help="MP3 bitrate (default 128k)")
    args = p.parse_args()

    require("yt-dlp")
    require("ffmpeg")

    args.output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        raw = yt_dlp_to_mp3(args.url, tmp)
        if args.slow is not None and args.slow != 1.0:
            ffmpeg_atempo(raw, args.output, args.slow, args.bitrate)
        else:
            shutil.move(str(raw), args.output)

    size_mb = args.output.stat().st_size / (1024 * 1024)
    print(f"\nDone. {args.output}  ({size_mb:.1f} MB)", file=sys.stderr)


if __name__ == "__main__":
    main()
