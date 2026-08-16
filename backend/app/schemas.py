import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

Mode = Literal["bullets", "tldr", "keyfacts"]
SourceType = Literal["html", "pdf", "youtube"]


class SummarizeRequest(BaseModel):
    """Mode is a Literal, so FastAPI validates it and /docs documents it.
    v2 hand-rolled this check in two places that could drift apart.
    """
    url: HttpUrl
    mode: Mode = "bullets"


class SummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_url: str | None
    source_type: str
    mode: str
    model: str
    summary_text: str
    source_chars: int
    summary_chars: int
    latency_ms: int
    created_at: datetime

    @property
    def compression_ratio(self) -> float:
        return self.summary_chars / self.source_chars if self.source_chars else 0.0


class SummaryListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    source_url: str | None
    source_type: str
    mode: str
    source_chars: int
    summary_chars: int
    created_at: datetime


class SearchHit(BaseModel):
    id: uuid.UUID
    title: str
    source_url: str | None
    source_type: str
    mode: str
    source_chars: int
    summary_chars: int
    created_at: datetime
    rank: float
    snippet: str


class SearchResponse(BaseModel):
    query: str
    total: int
    hits: list[SearchHit]


class ListResponse(BaseModel):
    total: int
    items: list[SummaryListItem]


class StatsResponse(BaseModel):
    total: int
    source_chars: int
    summary_chars: int
    compression_ratio: float
    avg_latency_ms: int
    by_source_type: dict[str, int] = Field(default_factory=dict)
