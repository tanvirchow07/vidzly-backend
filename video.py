"""
All actual video editing happens here via ffmpeg subprocess calls.
No heavy Python video libraries needed — ffmpeg does the real work,
this module just builds correct, safe command lines for it.
"""
import subprocess
import shlex
from pathlib import Path


class FFmpegError(RuntimeError):
    pass


def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise FFmpegError(
            f"ffmpeg command failed ({' '.join(shlex.quote(c) for c in cmd)}):\n{result.stderr[-2000:]}"
        )
    return result


def extract_audio(video_path: str, audio_path: str):
    _run([
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1",
        audio_path,
    ])


def get_duration_seconds(video_path: str) -> float:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", video_path],
        capture_output=True, text=True,
    )
    return float(result.stdout.strip() or 0)


def cut_clip(source_path: str, start: float, end: float, out_path: str):
    """Cut [start, end] out of the source video, re-encoding for a clean keyframe boundary."""
    duration = max(0.5, end - start)
    _run([
        "ffmpeg", "-y",
        "-ss", f"{start:.2f}", "-i", source_path, "-t", f"{duration:.2f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k",
        out_path,
    ])


def crop_to_vertical(input_path: str, output_path: str, target_w=1080, target_h=1920):
    """
    Center-crop + scale the clip to 9:16. This is the MVP "smart crop" —
    true face/subject-tracking crop would replace this filter with a
    per-frame detection pass (see README for how to extend it).
    """
    vf = (
        f"scale={target_w}:-2,"
        f"crop={target_w}:{target_h}"
    )
    # If source is wider than tall after scaling to width, this centers vertically;
    # for landscape source we scale by height instead so cropping the sides works.
    vf_landscape = (
        f"scale=-2:{target_h},"
        f"crop={target_w}:{target_h}"
    )
    try:
        _run([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf_landscape,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            output_path,
        ])
    except FFmpegError:
        # fall back to the other scaling direction if the source aspect
        # makes the first filter graph invalid
        _run([
            "ffmpeg", "-y", "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-c:a", "copy",
            output_path,
        ])


def _format_srt_timestamp(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def write_srt(segments: list, clip_start: float, clip_end: float, srt_path: str):
    """
    Build a caption file scoped to one clip, with timestamps shifted so
    0:00 in the SRT lines up with the start of the cut clip.
    """
    lines = []
    idx = 1
    for seg in segments:
        if seg["end"] <= clip_start or seg["start"] >= clip_end:
            continue
        start = max(seg["start"], clip_start) - clip_start
        end = min(seg["end"], clip_end) - clip_start
        if end <= start:
            continue
        lines.append(str(idx))
        lines.append(f"{_format_srt_timestamp(start)} --> {_format_srt_timestamp(end)}")
        lines.append(seg["text"].strip())
        lines.append("")
        idx += 1
    Path(srt_path).write_text("\n".join(lines), encoding="utf-8")
    return idx - 1  # number of caption lines written


def burn_captions(input_path: str, srt_path: str, output_path: str):
    """
    Burns bold, high-contrast captions onto the vertical clip using
    ffmpeg's subtitles filter. force_style controls the caption look —
    tweak these values to match a different Vidzly caption style.
    """
    style = (
        "FontName=Arial Black,FontSize=14,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,BorderStyle=3,Outline=2,Shadow=0,"
        "Alignment=2,MarginV=90"
    )
    srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
    _run([
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"subtitles={srt_escaped}:force_style='{style}'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        output_path,
    ])
