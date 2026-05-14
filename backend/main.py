import asyncio
import glob
import hashlib
import os
import time
import uuid

import edge_tts
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: dict[str, dict] = {}


def _passphrase_hash() -> str:
    return hashlib.sha256(os.environ["WEBAPP_PASSPHRASE"].encode()).hexdigest()


def verify_auth(authorization: str = Header(None)):
    if not authorization or authorization != _passphrase_hash():
        raise HTTPException(status_code=401, detail="Unauthorized")


def cleanup_old_files():
    cutoff = time.time() - 3600
    for f in glob.glob("/tmp/rd-*.mp3"):
        try:
            if os.path.getmtime(f) < cutoff:
                os.remove(f)
        except OSError:
            pass


class TTSRequest(BaseModel):
    text: str
    voice: str
    speed: float = 1.0


@app.get("/health")
async def health():
    return {"status": "ok"}


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


@app.get("/jobs/{job_id}")
async def get_job(
    job_id: str,
    authorization: str = Header(None),
):
    verify_auth(authorization)
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"status": job["status"], "error": job.get("error")}


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


async def _run_tts(job_id: str, text: str, voice: str, speed: float):
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
