from pydantic import BaseModel
from typing import Optional, List


class MomentScore(BaseModel):
    hook: int
    pacing: int
    emotion: int
    clarity: int
    visual: int

    @property
    def overall(self) -> int:
        return round((self.hook + self.pacing + self.emotion + self.clarity + self.visual) / 5)


class Moment(BaseModel):
    start: float          # seconds into source video
    end: float             # seconds into source video
    title: str              # short punchy title, e.g. "Nobody expected this..."
    category: str           # PODCAST / GAMING / COMEDY / etc.
    score: MomentScore


class Clip(BaseModel):
    id: str
    title: str
    category: str
    duration_seconds: float
    score: int
    breakdown: MomentScore
    download_path: str      # relative path served by /api/download/{clip_id}


class JobStatus(BaseModel):
    job_id: str
    step: str                  # uploading | transcribing | finding_moments | analyzing | captioning | motion | rendering | done | error
    progress: int               # 0-100
    message: str
    error: Optional[str] = None
    clips: List[Clip] = []
