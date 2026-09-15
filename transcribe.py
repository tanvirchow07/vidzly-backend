"""
Speech-to-text using OpenAI's Whisper API.
Returns word/segment-level timestamps, which the moment-detection
and caption-burning steps both depend on.
"""
from openai import OpenAI
from . import config


def transcribe(audio_path: str) -> dict:
    """
    Returns a dict shaped like:
    {
      "text": "...full transcript...",
      "segments": [
         {"start": 0.0, "end": 3.2, "text": "So today we're talking about..."},
         ...
      ]
    }
    """
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file before "
            "running the pipeline — see .env.example."
        )

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    with open(audio_path, "rb") as f:
        result = client.audio.transcriptions.create(
            model=config.WHISPER_MODEL,
            file=f,
            response_format="verbose_json",
            timestamp_granularities=["segment"],
        )

    # The SDK returns a pydantic-like object; normalize to plain dict.
    segments = []
    for seg in getattr(result, "segments", []) or []:
        segments.append({
            "start": float(seg.start if hasattr(seg, "start") else seg["start"]),
            "end": float(seg.end if hasattr(seg, "end") else seg["end"]),
            "text": (seg.text if hasattr(seg, "text") else seg["text"]).strip(),
        })

    return {
        "text": getattr(result, "text", "") or "",
        "segments": segments,
    }
