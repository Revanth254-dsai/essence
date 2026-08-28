import logging
import re
import unicodedata

logger = logging.getLogger(__name__)

CITATION_RE = re.compile(r"\[(?:\d+|citation needed|edit|note \d+|[a-z])\]", flags=re.IGNORECASE)
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
WHITESPACE_RE = re.compile(r"[ \t\u00a0]+")
NEWLINE_RE = re.compile(r"\n{3,}")

def clean_text(raw: str) -> str:
    text = unicodedata.normalize("NFKC", raw)
    text = CITATION_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    text = WHITESPACE_RE.sub(" ", text)
    text = NEWLINE_RE.sub("\n\n", text)
    return text.strip()

def truncate_at_sentence(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    cut = max(window.rfind(". "), window.rfind("। "), window.rfind("\n"))
    if cut > max_chars * 0.6:
        window = window[:cut + 1]
    logger.info("truncated %d -> %d chars", len(text), len(window))
    return window

def chunk_text(text: str, chunk_chars: int = 12_000, overlap: int = 400) -> list[str]:
    if len(text) <= chunk_chars:
        return [text]
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current: list[str] = []
    size = 0
    for para in paragraphs:
        if size + len(para) > chunk_chars and current:
            chunks.append("\n\n".join(current))
            tail = "\n\n".join(current)[-overlap:]
            current, size = ([tail] if overlap else []), len(tail)
        current.append(para)
        size += len(para) + 2
    if current:
        chunks.append("\n\n".join(current))
    final: list[str] = []
    for chunk in chunks:
        while len(chunk) > chunk_chars * 1.5:
            final.append(chunk[:chunk_chars])
            chunk = chunk[chunk_chars - overlap:]
        final.append(chunk)
    logger.info("chunked %d chars into %d chunks", len(text), len(final))
    return final