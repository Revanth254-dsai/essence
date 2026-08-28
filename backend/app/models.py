import uuid
from datetime import datetime

from sqlalchemy import (
    Computed,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

TSV_EXPRESSION = """
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(summary_text, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(source_text, '')), 'C')
"""

class Summary(Base):
    __tablename__ = "summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    model: Mapped[str] = mapped_column(String(64), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    summary_chars: Mapped[int] = mapped_column(Integer, nullable=False)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    meta: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(TSV_EXPRESSION, persisted=True)
    )

    __table_args__ = (
        Index(
            "ix_summaries_search_vector",
            "search_vector",
            postgresql_using="gin"
        ),
        Index(
            "ix_summaries_created_at",
            created_at.desc()
        ),
        Index(
            "ix_summaries_source_type",
            "source_type"
        ),
    )

    @property
    def compression_ratio(self) -> float:
        return self.summary_chars / self.source_chars if self.source_chars else 0.0