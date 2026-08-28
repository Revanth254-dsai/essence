from dataclasses import dataclass
from typing import Literal

SourceType = Literal["html", "pdf", "youtube"]

@dataclass(slots=True)
class Document:
    title: str
    text: str
    source_type: SourceType
    source_url: str | None = None
    meta: dict | None = None