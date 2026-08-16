"""Data access. The search query here is deliberately hand-written SQL -
the ORM has no expressive equivalent for ts_rank_cd + ts_headline.
"""
import uuid

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Summary

# ts_headline wraps matches in these markers. They are NOT HTML: the summary
# text is model-generated, so returning real <mark> tags would mean the
# frontend has to render untrusted HTML. The client splits on these instead.
HEADLINE_OPTS = (
    "StartSel=[[HL]], StopSel=[[/HL]], "
    "MaxFragments=2, MinWords=6, MaxWords=24, "
    "FragmentDelimiter= … "
)

SEARCH_SQL = text(
    f"""
    WITH q AS (
        SELECT websearch_to_tsquery('english', :query) AS query
    )
    SELECT
        s.id,
        s.title,
        s.source_url,
        s.source_type,
        s.mode,
        s.model,
        s.source_chars,
        s.summary_chars,
        s.created_at,
        ts_rank_cd(s.search_vector, q.query, 32) AS rank,
        ts_headline('english', s.summary_text, q.query, '{HEADLINE_OPTS}') AS snippet
    FROM summaries s, q
    WHERE s.search_vector @@ q.query
    ORDER BY rank DESC, s.created_at DESC
    LIMIT :limit OFFSET :offset
    """
)

SEARCH_COUNT_SQL = text(
    """
    SELECT count(*) FROM summaries
    WHERE search_vector @@ websearch_to_tsquery('english', :query)
    """
)


async def search_summaries(
    session: AsyncSession, query: str, limit: int = 20, offset: int = 0
) -> tuple[list[dict], int]:
    """websearch_to_tsquery gives users real search syntax for free:
    quoted "exact phrases", OR, and -excluded terms.
    """
    if not query.strip():
        return [], 0

    rows = (
        await session.execute(
            SEARCH_SQL, {"query": query, "limit": limit, "offset": offset}
        )
    ).mappings().all()

    total = (
        await session.execute(SEARCH_COUNT_SQL, {"query": query})
    ).scalar_one()

    return [dict(row) for row in rows], int(total)


async def list_summaries(
    session: AsyncSession,
    limit: int = 20,
    offset: int = 0,
    source_type: str | None = None,
) -> tuple[list[Summary], int]:
    stmt = select(Summary).order_by(Summary.created_at.desc())
    count_stmt = select(func.count()).select_from(Summary)

    if source_type:
        stmt = stmt.where(Summary.source_type == source_type)
        count_stmt = count_stmt.where(Summary.source_type == source_type)

    items = (await session.execute(stmt.limit(limit).offset(offset))).scalars().all()
    total = (await session.execute(count_stmt)).scalar_one()
    return list(items), int(total)


async def get_summary(session: AsyncSession, summary_id: uuid.UUID) -> Summary | None:
    return await session.get(Summary, summary_id)


async def delete_summary(session: AsyncSession, summary_id: uuid.UUID) -> bool:
    result = await session.execute(delete(Summary).where(Summary.id == summary_id))
    await session.commit()
    return result.rowcount > 0


async def create_summary(session: AsyncSession, **fields) -> Summary:
    record = Summary(**fields)
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record


async def archive_stats(session: AsyncSession) -> dict:
    row = (
        await session.execute(
            text(
                """
                SELECT
                    count(*)                       AS total,
                    coalesce(sum(source_chars), 0) AS source_chars,
                    coalesce(sum(summary_chars), 0) AS summary_chars,
                    coalesce(avg(latency_ms), 0)   AS avg_latency_ms
                FROM summaries
                """
            )
        )
    ).mappings().one()

    by_type = (
        await session.execute(
            text("SELECT source_type, count(*) AS n FROM summaries GROUP BY 1")
        )
    ).mappings().all()

    source_chars = int(row["source_chars"])
    summary_chars = int(row["summary_chars"])

    return {
        "total": int(row["total"]),
        "source_chars": source_chars,
        "summary_chars": summary_chars,
        "compression_ratio": (summary_chars / source_chars) if source_chars else 0.0,
        "avg_latency_ms": int(row["avg_latency_ms"]),
        "by_source_type": {r["source_type"]: int(r["n"]) for r in by_type},
    }
