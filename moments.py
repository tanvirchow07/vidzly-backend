"""
Uses an LLM to read the transcript and pick the strongest standalone
moments for short-form clips, with a 5-axis retention heuristic score.

This is explicitly a heuristic — it estimates hook/pacing/emotion/
clarity/visual strength from the text alone. It is a prioritization
aid, not a guarantee of how a clip will actually perform.
"""
import json
from openai import OpenAI
from . import config
from .models import Moment, MomentScore

SYSTEM_PROMPT = """You are Vidzly's clip-selection engine. You read a timestamped
podcast/video transcript and select the strongest self-contained moments for
short-form vertical video (9:16), each 20-90 seconds long.

For each moment, pick a start and end timestamp that begins and ends on a clean
sentence boundary so the clip makes sense on its own with no missing context.

Return ONLY valid JSON, an array of objects, no prose, no markdown fences:
[
  {
    "start": 12.4,
    "end": 47.8,
    "title": "a short punchy hook-style title, under 60 chars, in quotes style",
    "category": "one of PODCAST, GAMING, COMEDY, ENTERTAINMENT, EDUCATION, MOTIVATION, BUSINESS, SPORTS, VLOG, TECH, INTERVIEW",
    "hook": 0-100,
    "pacing": 0-100,
    "emotion": 0-100,
    "clarity": 0-100,
    "visual": 0-100
  }
]

Scoring guide:
- hook: how strong the first 3 seconds are at stopping a scroll
- pacing: how tightly the moment moves, no dead air
- emotion: how much genuine emotional charge or surprise is present
- clarity: how understandable the moment is without outside context
- visual: how much visual interest the moment likely has (reactions, motion, expressions)
"""


def find_moments(transcript_segments: list, max_clips: int, min_seconds: int, max_seconds: int) -> list:
    if not config.OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Add it to your .env file before "
            "running the pipeline — see .env.example."
        )

    client = OpenAI(api_key=config.OPENAI_API_KEY)

    transcript_text = "\n".join(
        f"[{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}" for seg in transcript_segments
    )

    user_prompt = (
        f"Transcript (timestamps in seconds):\n{transcript_text}\n\n"
        f"Select up to {max_clips} moments. Each clip must be between "
        f"{min_seconds} and {max_seconds} seconds long. Return JSON only."
    )

    response = client.chat.completions.create(
        model=config.MOMENTS_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.4,
        response_format={"type": "json_object"} if False else None,
    )

    raw = response.choices[0].message.content.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            # some models wrap the array in {"moments": [...]}
            data = data.get("moments") or next(iter(data.values()))
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Moment detection returned invalid JSON: {e}\nRaw: {raw[:500]}")

    moments = []
    for item in data:
        try:
            m = Moment(
                start=float(item["start"]),
                end=float(item["end"]),
                title=str(item["title"])[:120],
                category=str(item.get("category", "ENTERTAINMENT")).upper(),
                score=MomentScore(
                    hook=int(item["hook"]),
                    pacing=int(item["pacing"]),
                    emotion=int(item["emotion"]),
                    clarity=int(item["clarity"]),
                    visual=int(item["visual"]),
                ),
            )
            if m.end - m.start >= 5:  # sanity floor
                moments.append(m)
        except (KeyError, ValueError, TypeError):
            continue  # skip malformed entries rather than failing the whole job

    return moments[:max_clips]
