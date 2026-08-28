import asyncio
import logging
import re

import httpx

from ..net import IngestionError
from .base import Document

logger = logging.getLogger(__name__)

VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?(?:.*&)?v=)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtu\.be/)([A-Za-z0-9_-]{11})"),
    re.compile(r"(?:youtube\.com/(?:embed|shorts|live)/)([A-Za-z0-9_-]{11})"),
]

LANGUAGES = ["en", "en-US", "en-GB", "hi", "te"]

def extract_video_id(url: str) -> str | None:
    for pattern in VIDEO_ID_PATTERNS:
        if match := pattern.search(url):
            return match.group(1)
    return None

def _fetch_transcript(video_id: str) -> str:
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise IngestionError("youtube-transcript-api is not installed.") from exc

    try:
        if hasattr(YouTubeTranscriptApi, "get_transcript"):
            entries = YouTubeTranscriptApi.get_transcript(video_id, languages=LANGUAGES)
            segments = [e["text"] for e in entries]
        else:
            fetched = YouTubeTranscriptApi().fetch(video_id, languages=LANGUAGES)
            segments = [snippet.text for snippet in fetched]
    except Exception as exc:
        raise IngestionError(
            f"No transcript available for this video ({type(exc).__name__}). "
            "Captions may be disabled or the video may be private."
        ) from exc

    text = " ".join(s.strip() for s in segments if s and s.strip())
    text = re.sub(r"\[(?:Music|Applause|Laughter|__)\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        raise IngestionError("The transcript for this video is empty.")

    return text

async def _fetch_title(url: str, client: httpx.AsyncClient) -> str | None:
    try:
        response = await client.get(
            "https://www.youtube.com/oembed",
            params={"url": url, "format": "json"},
        )
        response.raise_for_status()
        return response.json().get("title")
    except Exception:
        return None

async def ingest_youtube(url: str, client: httpx.AsyncClient) -> Document:
    video_id = extract_video_id(url)

    if not video_id:
        raise IngestionError("Could not find a video ID in that YouTube URL.")

    text, title = await asyncio.gather(
        asyncio.to_thread(_fetch_transcript, video_id),
        _fetch_title(url, client),
    )

    logger.info("youtube: %d transcript chars for %s", len(text), video_id)

    return Document(
        title=title or f"YouTube video {video_id}",
        text=text,
        source_type="youtube",
        source_url=url,
        meta={"video_id": video_id},
    )