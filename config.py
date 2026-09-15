"""
Vidzly backend configuration.
All values are read from environment variables so nothing secret
is ever hardcoded in the source. Copy .env.example to .env and fill
in your own values before running.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# --- Required ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# --- Storage (local disk for MVP; swap for S3 in production) ---
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "storage" / "uploads"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "storage" / "outputs"))
JOBS_DIR = Path(os.getenv("JOBS_DIR", BASE_DIR / "storage" / "jobs"))

for d in (UPLOAD_DIR, OUTPUT_DIR, JOBS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- Models ---
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-1")
MOMENTS_MODEL = os.getenv("MOMENTS_MODEL", "gpt-4o-mini")

# --- Processing limits (protect a small server from being overloaded) ---
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "500"))
MAX_CLIPS_PER_VIDEO = int(os.getenv("MAX_CLIPS_PER_VIDEO", "8"))
MIN_CLIP_SECONDS = int(os.getenv("MIN_CLIP_SECONDS", "20"))
MAX_CLIP_SECONDS = int(os.getenv("MAX_CLIP_SECONDS", "90"))

# --- Server ---
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")
