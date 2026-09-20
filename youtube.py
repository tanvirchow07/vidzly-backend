"""
Downloads a YouTube video to local disk so the existing pipeline can
process it exactly like an uploaded file.

Only use this for videos you own or are otherwise authorized to
download and edit — downloading other people's videos without
permission can violate YouTube's Terms of Service and copyright law.
This module does not (and cannot) verify authorization; that
responsibility sits with whoever operates this server.
"""
import uuid
from pathlib import Path
from yt_dlp import YoutubeDL

import config


class DownloadError(RuntimeError):
    pass


def download_youtube(url: str) -> str:
    job_prefix = uuid.uuid4().hex[:12]
    out_template = str(config.UPLOAD_DIR / f"{job_prefix}_yt.%(ext)s")

    ydl_opts = {
        "format": "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/mp4/best",
        "merge_output_format": "mp4",
        "outtmpl": out_template,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": config.MAX_UPLOAD_MB * 1024 * 1024,
        # Cloud-server IPs frequently trigger YouTube's "sign in to confirm
        # you're not a bot" check on the default web client. Requesting the
        # android/ios player clients instead usually avoids it since they
        # use a different, less-flagged verification path. Not a 100%
        # guarantee — YouTube changes this over time — but it's the
        # standard, current mitigation.
        "extractor_args": {
            "youtube": {"player_client": ["android", "ios", "web"]}
        },
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            final_path = ydl.prepare_filename(info)
            # merge_output_format can change the extension after download
            final_path = str(Path(final_path).with_suffix(".mp4"))
            if not Path(final_path).exists():
                # fall back to whatever file actually landed with this prefix
                matches = list(config.UPLOAD_DIR.glob(f"{job_prefix}_yt.*"))
                if not matches:
                    raise DownloadError("Download finished but the output file was not found.")
                final_path = str(matches[0])
            return final_path
    except Exception as e:
        raise DownloadError(f"Could not download this YouTube video: {e}")
