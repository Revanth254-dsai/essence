"""PDF adapter. Handles both a remote .pdf URL and a direct file upload."""
import asyncio
import io
import logging

import httpx
from pypdf import PdfReader

from ..net import IngestionError, fetch_bytes
from .base import Document

logger = logging.getLogger(__name__)

MAX_PAGES = 200


def _read_pdf(body: bytes) -> tuple[str, str]:
    """Blocking pypdf work. Always call this through asyncio.to_thread."""
    try:
        reader = PdfReader(io.BytesIO(body))
    except Exception as exc:
        raise IngestionError(f"Could not open the PDF: {exc}") from exc

    if reader.is_encrypted:
        try:
            reader.decrypt("")          # succeeds for empty-password PDFs
        except Exception as exc:
            raise IngestionError("This PDF is password protected.") from exc

    pages = reader.pages[:MAX_PAGES]
    text = "\n\n".join(page.extract_text() or "" for page in pages)

    if not text.strip():
        raise IngestionError(
            "No selectable text in this PDF. It is probably a scan - "
            "run OCR on it first."
        )

    title = ""
    if reader.metadata and reader.metadata.title:
        title = str(reader.metadata.title).strip()

    return title, text


async def ingest_pdf_bytes(body: bytes, filename: str,
                           source_url: str | None = None) -> Document:
    title, text = await asyncio.to_thread(_read_pdf, body)
    logger.info("pdf: extracted %d chars from %s", len(text), filename)
    return Document(
        title=title or filename,
        text=text,
        source_type="pdf",
        source_url=source_url,
        meta={"filename": filename},
    )


async def ingest_pdf_url(url: str, client: httpx.AsyncClient) -> Document:
    body, _ = await fetch_bytes(url, client)
    filename = url.rsplit("/", 1)[-1] or "document.pdf"
    return await ingest_pdf_bytes(body, filename, source_url=url)
