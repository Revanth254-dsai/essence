import logging

import httpx
from bs4 import BeautifulSoup

from ..net import IngestionError, fetch_bytes
from .base import Document

logger = logging.getLogger(__name__)

NOISE_TAGS = ["script", "style", "nav", "footer", "header", "aside", "form", "noscript", "iframe"]
CONTENT_CLASSES = ["content", "post-content", "entry-content", "article-body", "story-body"]

async def ingest_html(url: str, client: httpx.AsyncClient) -> Document:
    body, _ = await fetch_bytes(url, client)
    soup = BeautifulSoup(body, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else url

    for tag in soup(NOISE_TAGS):
        tag.decompose()

    text = _extract_text(soup)

    if not text.strip():
        raise IngestionError("No readable text found on this page.")

    logger.info("html: extracted %d chars from %s", len(text), url)
    return Document(title=title, text=text, source_type="html", source_url=url)

def _extract_text(soup: BeautifulSoup) -> str:
    wiki = soup.find("div", {"id": "mw-content-text"})
    if wiki and (t := _paragraphs(wiki)):
        return t

    for tag in ("article", "main"):
        node = soup.find(tag)
        if node and (t := _paragraphs(node)):
            return t

    for cls in CONTENT_CLASSES:
        node = soup.find("div", class_=lambda c, want=cls: bool(c) and want in c.lower())
        if node and (t := _paragraphs(node)):
            return t

    return _paragraphs(soup.find("body") or soup)

def _paragraphs(element, min_len: int = 40) -> str:
    parts = [
        p.get_text(separator=" ").strip()
        for p in element.find_all("p")
        if len(p.get_text(strip=True)) > min_len
    ]

    if parts:
        return " ".join(parts)

    fallback = element.get_text(separator=" ", strip=True)
    return fallback if len(fallback) > 200 else ""