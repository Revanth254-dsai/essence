"""Picks the right adapter for a source. Adding a format means adding a branch here."""
import logging
from urllib.parse import urlparse

import httpx

from ..config import settings
from ..net import IngestionError, assert_safe_url
from .base import Document
from .html import ingest_html
from .pdf import ingest_pdf_bytes, ingest_pdf_url
from .youtube import extract_video_id, ingest_youtube

logger = logging.getLogger(__name__)

YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com",
                 "youtu.be", "www.youtu.be"}


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=settings.request_timeout_s,
        follow_redirects=True,
        max_redirects=5,
        headers={"User-Agent": "WebSummarizer/3.0 (+https://github.com/)"},
    )


async def ingest_url(url: str) -> Document:
    assert_safe_url(url)
    host = (urlparse(url).hostname or "").lower()

    async with _client() as client:
        if host in YOUTUBE_HOSTS and extract_video_id(url):
            return await ingest_youtube(url, client)

        if urlparse(url).path.lower().endswith(".pdf"):
            return await ingest_pdf_url(url, client)

        # Content-type sniff: some PDF links have no .pdf extension.
        try:
            head = await client.head(url)
            if "application/pdf" in head.headers.get("content-type", "").lower():
                return await ingest_pdf_url(url, client)
        except httpx.RequestError:
            pass  # HEAD is often blocked; fall through to HTML.

        return await ingest_html(url, client)


async def ingest_upload(filename: str, body: bytes) -> Document:
    if not filename.lower().endswith(".pdf"):
        raise IngestionError("Only PDF uploads are supported right now.")
    if len(body) > settings.max_download_bytes:
        raise IngestionError(
            f"File is over the {settings.max_download_bytes // 1024 // 1024} MB limit."
        )
    return await ingest_pdf_bytes(body, filename)
