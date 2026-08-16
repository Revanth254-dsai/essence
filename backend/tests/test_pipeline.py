import io

import pytest
from bs4 import BeautifulSoup

from app.ingestion.html import _extract_text
from app.ingestion.youtube import extract_video_id
from app.net import IngestionError, assert_safe_url
from app.processor import chunk_text, clean_text, truncate_at_sentence


# --------------------------- processor ---------------------------

def test_unicode_survives_cleaning():
    """The v2 regression: ASCII stripping deleted all non-English text."""
    text = clean_text("రేవంత్ కుమార్ studies at IIT Tirupati — cost ₹50,000.")
    assert "రేవంత్" in text
    assert "₹50,000" in text


def test_citation_markers_removed():
    out = clean_text("Newton stated this[1] clearly[citation needed] in 1687[a].")
    assert "[1]" not in out and "[citation needed]" not in out and "[a]" not in out
    assert "Newton stated this clearly in 1687." == out


def test_whitespace_collapsed_but_paragraphs_kept():
    out = clean_text("Para one.\n\n\n\nPara    two.")
    assert out == "Para one.\n\nPara two."


def test_truncate_lands_on_sentence_boundary():
    text = "First sentence here. " * 50
    out = truncate_at_sentence(text, 200)
    assert len(out) <= 200
    assert out.rstrip().endswith(".")


def test_short_text_is_not_chunked():
    assert chunk_text("hello world", chunk_chars=1000) == ["hello world"]


def test_long_text_chunks_and_preserves_content():
    paragraphs = "\n\n".join(f"Paragraph number {i} with filler text." * 20
                             for i in range(60))
    chunks = chunk_text(paragraphs, chunk_chars=2000, overlap=100)
    assert len(chunks) > 1
    assert all(len(c) <= 3000 for c in chunks)
    assert "Paragraph number 59" in chunks[-1]


def test_single_giant_paragraph_is_hard_split():
    chunks = chunk_text("x" * 20_000, chunk_chars=2000, overlap=100)
    assert len(chunks) > 1


# --------------------------- html extraction ---------------------------

def _soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def test_wikipedia_strategy_wins():
    html = f"""
    <body>
      <div id="mw-content-text"><p>{'Wiki body content. ' * 10}</p></div>
      <article><p>{'Decoy article text. ' * 10}</p></article>
    </body>"""
    assert "Wiki body" in _extract_text(_soup(html))


def test_multi_class_content_div_matches():
    """bs4 calls the class_ callback once per class name, not with the list."""
    html = f'<body><div class="wrapper post-content dark"><p>{"Real body text. " * 10}</p></div></body>'
    assert "Real body text" in _extract_text(_soup(html))


def test_div_only_site_falls_back_to_raw_text():
    """Sites that never use <p> used to yield an empty string."""
    html = f'<body><div class="content"><div>{"Body copy in a div. " * 30}</div></div></body>'
    assert "Body copy in a div" in _extract_text(_soup(html))


# --------------------------- youtube ---------------------------

@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/shorts/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://www.youtube.com/watch?list=PL1&v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
    ("https://example.com/watch?v=dQw4w9WgXcQ", None),
])
def test_video_id_extraction(url, expected):
    assert extract_video_id(url) == expected


# --------------------------- ssrf guard ---------------------------

@pytest.mark.parametrize("url", [
    "http://127.0.0.1:11434/api/generate",
    "http://localhost:8000/health",
    "http://169.254.169.254/latest/meta-data/",   # cloud metadata endpoint
    "http://10.0.0.5/internal",
    "file:///etc/passwd",
])
def test_dangerous_urls_are_refused(url):
    with pytest.raises(IngestionError):
        assert_safe_url(url)


def test_public_url_allowed():
    assert_safe_url("https://en.wikipedia.org/wiki/Machine_learning")


# --------------------------- pdf ---------------------------

def test_scanned_pdf_gives_actionable_error():
    from app.ingestion.pdf import _read_pdf
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = io.BytesIO()
    writer.write(buffer)

    with pytest.raises(IngestionError, match="OCR"):
        _read_pdf(buffer.getvalue())
