import asyncio
import glob
import gzip
import hashlib
import json
import os
import random
import time
import uuid
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Optional

import edge_tts
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from audio_builder import build_session_audio, GERMAN_VOICES

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, dict] = {}

# ---------- Pre-processed data (loaded at startup) ----------

DATA_DIR = Path(__file__).parent / "data"

WORDS: list[dict] = []
SENTENCES: list[dict] = []
WORDS_BY_BAND: dict[str, list[dict]] = defaultdict(list)
SENTENCES_BY_THEME: dict[str, list[dict]] = defaultdict(list)
STATS: dict = {}


def load_data():
    """Load pre-processed word and sentence data into memory."""
    global WORDS, SENTENCES, STATS

    words_path = DATA_DIR / "words.jsonl.gz"
    sentences_path = DATA_DIR / "sentences.jsonl.gz"
    stats_path = DATA_DIR / "stats.json"

    if words_path.exists():
        with gzip.open(words_path, "rt", encoding="utf-8") as f:
            WORDS.extend(json.loads(line) for line in f)
        for w in WORDS:
            WORDS_BY_BAND[w["freq_band"]].append(w)
        print(f"Loaded {len(WORDS)} words")

    if sentences_path.exists():
        with gzip.open(sentences_path, "rt", encoding="utf-8") as f:
            SENTENCES.extend(json.loads(line) for line in f)
        for s in SENTENCES:
            for theme in s.get("themes", ["general"]):
                SENTENCES_BY_THEME[theme].append(s)
        # Also add all sentences under "all"
        SENTENCES_BY_THEME["all"] = list(SENTENCES)
        print(f"Loaded {len(SENTENCES)} sentences")

    if stats_path.exists():
        with stats_path.open(encoding="utf-8") as f:
            STATS.update(json.load(f))
        print(f"Loaded stats")


# Load on import (runs at startup)
load_data()


# ---------- Auth ----------

def _passphrase_hash() -> str:
    return hashlib.sha256(os.environ["WEBAPP_PASSPHRASE"].encode()).hexdigest()


def verify_auth(authorization: str = Header(None)):
    if not authorization or authorization != _passphrase_hash():
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------- Cleanup ----------

def cleanup_old_files():
    cutoff = time.time() - 3600
    for f in glob.glob("/tmp/rd-*.mp3"):
        try:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
        except OSError:
            pass


# ---------- Request models ----------

class TTSRequest(BaseModel):
    text: str
    voice: str
    speed: float = 1.0


class QuickGenerateRequest(BaseModel):
    type: str  # "l1" or "l2"
    voice: str = "auto"
    speed: float = 1.0
    count: Optional[int] = None
    duration: Optional[int] = None  # target duration in minutes
    freq_band: str = "top100"
    theme: str = "all"
    seed: Optional[str] = None  # e.g. "2026-05-14" for daily mix


# ---------- Card selection ----------

SECONDS_PER_L1_CARD = 27.5
SECONDS_PER_L2_CARD = 17.5


def select_cards(req: QuickGenerateRequest) -> list[dict]:
    """Select cards based on request parameters."""
    rng = random.Random(req.seed) if req.seed else random.Random()

    if req.type == "l1":
        pool = list(WORDS_BY_BAND.get(req.freq_band, []))
        secs_per_card = SECONDS_PER_L1_CARD
    else:
        pool = list(SENTENCES_BY_THEME.get(req.theme, SENTENCES_BY_THEME.get("all", [])))
        secs_per_card = SECONDS_PER_L2_CARD

    if not pool:
        return []

    rng.shuffle(pool)

    # Determine count
    if req.duration:
        count = max(1, int(req.duration * 60 / secs_per_card))
    elif req.count:
        count = req.count
    else:
        count = 50  # default

    return pool[:count]


def resolve_voice(voice: str, seed: Optional[str] = None) -> str:
    """Resolve voice selection. 'auto' picks randomly (seeded for daily mix)."""
    if voice != "auto":
        return voice
    rng = random.Random(seed) if seed else random.Random()
    return rng.choice(GERMAN_VOICES)


# ---------- Endpoints ----------

@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/stats")
async def get_stats(authorization: str = Header(None)):
    verify_auth(authorization)
    return STATS


@app.post("/jobs")
async def create_job(
    req: TTSRequest,
    authorization: str = Header(None),
):
    verify_auth(authorization)
    cleanup_old_files()

    job_id = str(uuid.uuid4())
    jobs[job_id] = {"status": "pending", "created": time.time()}
    asyncio.create_task(_run_tts(job_id, req.text, req.voice, req.speed))
    return {"jobId": job_id}


@app.post("/jobs/quick")
async def create_quick_job(
    req: QuickGenerateRequest,
    authorization: str = Header(None),
):
    verify_auth(authorization)
    cleanup_old_files()

    # Select cards
    cards = select_cards(req)
    if not cards:
        raise HTTPException(status_code=400, detail="No cards available for this selection")

    voice_de = resolve_voice(req.voice, req.seed)

    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "status": "pending",
        "created": time.time(),
        "card_count": len(cards),
        "voice": voice_de,
    }
    asyncio.create_task(
        _run_quick_generate(job_id, cards, req.type, voice_de, req.speed)
    )
    return {"jobId": job_id, "cardCount": len(cards)}


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    authorization: str = Header(None),
):
    verify_auth(authorization)
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "error": job.get("error"),
        "cardCount": job.get("card_count"),
        "progress": job.get("progress"),
    }


@app.get("/files/{job_id}")
async def get_file(
    job_id: str,
    authorization: str = Header(None),
):
    verify_auth(authorization)
    job = jobs.get(job_id)
    if not job or job["status"] != "done":
        raise HTTPException(status_code=404, detail="File not ready")
    return FileResponse(
        job["path"],
        media_type="audio/mpeg",
        filename="dictation.mp3",
    )


# ---------- Job runners ----------

async def _run_tts(job_id: str, text: str, voice: str, speed: float):
    """Simple text-to-speech job (existing v2 flow)."""
    jobs[job_id]["status"] = "running"
    try:
        output_path = f"/tmp/rd-{job_id}.mp3"
        rate = f"{int((speed - 1) * 100):+d}%"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)
        jobs[job_id]["status"] = "done"
        jobs[job_id]["path"] = output_path
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)


async def _run_quick_generate(
    job_id: str,
    cards: list[dict],
    card_type: str,
    voice_de: str,
    speed: float,
):
    """Bilingual card-based audio generation job."""
    jobs[job_id]["status"] = "running"
    try:
        output_path = f"/tmp/rd-{job_id}.mp3"
        await build_session_audio(
            cards=cards,
            card_type=card_type,
            voice_de=voice_de,
            speed=speed,
            output_path=output_path,
        )
        jobs[job_id]["status"] = "done"
        jobs[job_id]["path"] = output_path
    except Exception as e:
        jobs[job_id]["status"] = "error"
        jobs[job_id]["error"] = str(e)
