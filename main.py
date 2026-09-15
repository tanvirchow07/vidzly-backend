"""
Vidzly backend API.

Run locally:
    uvicorn app.main:app --reload --port 8000

Endpoints:
    POST /api/projects            upload a video, starts processing, returns job_id
    GET  /api/projects/{job_id}   poll status + progress + finished clips
    GET  /api/download/{clip_id}  download a finished vertical clip (mp4)
    GET  /api/health              simple uptime check
"""
import uuid
import shutil
from pathlib import Path

from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from . import config, pipeline, jobstore
from .models import JobStatus

app = FastAPI(title="Vidzly API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/projects")
async def create_project(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    if not file.filename.lower().endswith((".mp4", ".mov", ".m4v", ".webm")):
        raise HTTPException(400, "Unsupported file type. Upload MP4, MOV, M4V or WEBM.")

    job_id = uuid.uuid4().hex[:12]
    dest = config.UPLOAD_DIR / f"{job_id}_{file.filename}"

    size = 0
    max_bytes = config.MAX_UPLOAD_MB * 1024 * 1024
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > max_bytes:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(413, f"File exceeds the {config.MAX_UPLOAD_MB}MB limit.")
            out.write(chunk)

    jobstore.save(JobStatus(job_id=job_id, step="uploading", progress=1, message="Upload received."))
    background_tasks.add_task(pipeline.run_pipeline, job_id, str(dest))

    return {"job_id": job_id}


@app.get("/api/projects/{job_id}", response_model=JobStatus)
def get_project(job_id: str):
    status = jobstore.load(job_id)
    if not status:
        raise HTTPException(404, "Unknown job_id.")
    return status


@app.get("/api/download/{clip_id}")
def download_clip(clip_id: str):
    job_id = clip_id.split("_")[0]
    path = config.OUTPUT_DIR / job_id / f"{clip_id}_final.mp4"
    if not path.exists():
        raise HTTPException(404, "Clip not found or not finished yet.")
    return FileResponse(path, media_type="video/mp4", filename=f"{clip_id}.mp4")
