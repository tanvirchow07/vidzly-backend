"""
End-to-end pipeline: source video in, ranked vertical clips out.
Each step updates the job's status file so the frontend's processing
screen (Uploading / Transcribing / Finding best moments / ... /
Rendering) can poll GET /api/projects/{job_id}/status and reflect
real progress instead of a fake animation.
"""
import uuid
import shutil
from pathlib import Path

import config, transcribe, moments as moments_mod, video, jobstore
from models import JobStatus, Clip


STEPS = [
    "uploading", "transcribing", "finding_moments",
    "analyzing", "captioning", "rendering",
]


def _update(job_id: str, step: str, progress: int, message: str):
    status = jobstore.load(job_id) or JobStatus(job_id=job_id, step=step, progress=progress, message=message)
    status.step = step
    status.progress = progress
    status.message = message
    jobstore.save(status)


def run_pipeline(job_id: str, source_video_path: str):
    """
    Runs synchronously in a background task/thread. For heavier traffic,
    move this into a real task queue (Celery/RQ) so uploads don't block
    each other — see README "Scaling beyond the MVP".
    """
    work_dir = config.OUTPUT_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    try:
        _update(job_id, "uploading", 10, "Upload received, preparing video...")

        audio_path = str(work_dir / "audio.mp3")
        video.extract_audio(source_video_path, audio_path)

        _update(job_id, "transcribing", 25, "Transcribing speech to text...")
        transcript = transcribe.transcribe(audio_path)
        if not transcript["segments"]:
            raise RuntimeError("No speech detected in this video — nothing to clip.")

        _update(job_id, "finding_moments", 45, "Finding the strongest moments in your video...")
        found = moments_mod.find_moments(
            transcript["segments"],
            max_clips=config.MAX_CLIPS_PER_VIDEO,
            min_seconds=config.MIN_CLIP_SECONDS,
            max_seconds=config.MAX_CLIP_SECONDS,
        )
        if not found:
            raise RuntimeError("Could not identify any clip-worthy moments in this video.")

        _update(job_id, "analyzing", 55, "Analyzing engagement and pacing...")
        # (scores already computed by the LLM in the previous step; this
        # stage exists so the frontend's step list has something to show
        # and is a natural place to add a second-pass re-ranking later)

        clips = []
        total = len(found)
        for i, m in enumerate(found):
            base_progress = 60 + int((i / total) * 35)
            _update(job_id, "captioning", base_progress, f"Editing clip {i+1} of {total}...")

            clip_id = f"{job_id}_{i+1}"
            raw_cut = str(work_dir / f"{clip_id}_raw.mp4")
            vertical = str(work_dir / f"{clip_id}_vertical.mp4")
            srt_path = str(work_dir / f"{clip_id}.srt")
            final_path = str(work_dir / f"{clip_id}_final.mp4")

            video.cut_clip(source_video_path, m.start, m.end, raw_cut)
            video.crop_to_vertical(raw_cut, vertical)
            caption_lines = video.write_srt(transcript["segments"], m.start, m.end, srt_path)

            if caption_lines > 0:
                video.burn_captions(vertical, srt_path, final_path)
            else:
                shutil.copy(vertical, final_path)

            clips.append(Clip(
                id=clip_id,
                title=m.title,
                category=m.category,
                duration_seconds=round(m.end - m.start, 1),
                score=m.score.overall,
                breakdown=m.score,
                download_path=f"/api/download/{clip_id}",
            ))

            # keep the status file updated incrementally so clips already
            # done are visible even before the whole batch finishes
            status = jobstore.load(job_id)
            status.clips = clips
            jobstore.save(status)

        _update(job_id, "done", 100, "Your shorts are ready.")
        final_status = jobstore.load(job_id)
        final_status.clips = clips
        jobstore.save(final_status)

    except Exception as e:
        status = jobstore.load(job_id) or JobStatus(job_id=job_id, step="error", progress=0, message="Failed")
        status.step = "error"
        status.error = str(e)
        status.message = "Processing failed — see error."
        jobstore.save(status)
        raise
