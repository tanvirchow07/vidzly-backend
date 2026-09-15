"""
Minimal job-status persistence: one JSON file per job under storage/jobs/.
Good enough for a single-server MVP. For multi-server deployments,
swap this for Redis or a real database — the read/write functions
below are the only two places that would need to change.
"""
import json
from pathlib import Path
from . import config
from .models import JobStatus


def _path(job_id: str) -> Path:
    return config.JOBS_DIR / f"{job_id}.json"


def save(status: JobStatus):
    _path(status.job_id).write_text(status.model_dump_json(indent=2), encoding="utf-8")


def load(job_id: str) -> JobStatus | None:
    p = _path(job_id)
    if not p.exists():
        return None
    return JobStatus.model_validate_json(p.read_text(encoding="utf-8"))
