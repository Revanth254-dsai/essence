from dataclasses import dataclass
from typing import Literal

SourceType = Literal["html", "pdf", "youtube"]


@dataclass(slots=True)
class Document:
    """The single shape every ingestion adapter must return.

    Everything downstream - processor, chunker, LLM, database - works
    against this, so adding a new source type never touches the pipeline.
    """
    title: str
    text: str
    source_type: SourceType
    source_url: str | None = None
    meta: dict | None = None
