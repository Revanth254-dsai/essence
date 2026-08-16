import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from . import repository
from .config import settings
from .db import SessionLocal, get_session, init_db
from .ingestion import Document, ingest_upload, ingest_url
from .llm_client import LLMError, active_model, summarize_chunks
from .net import IngestionError
from .processor import chunk_text, clean_text, truncate_at_sentence
from .schemas import (
    ListResponse, Mode, SearchResponse, StatsResponse,
    SummarizeRequest, SummaryOut,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Web Summarizer API",
    description="Ingests web pages, PDFs, and YouTube transcripts; summarises "
                "them with a streaming LLM; archives the result in Postgres "
                "with full-text search.",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sse(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


async def _summarize_stream(document: Document, mode: str) -> AsyncIterator[str]:
    """Shared SSE generator for both URL and upload flows.

    Persists to Postgres only after the model finishes, so a failed or
    cancelled generation never leaves a half-written row in the archive.
    """
    started = time.perf_counter()

    cleaned = truncate_at_sentence(clean_text(document.text), settings.max_source_chars)
    chunks = chunk_text(cleaned)

    yield sse("meta", {
        "title": document.title,
        "source_type": document.source_type,
        "source_url": document.source_url,
        "source_chars": len(cleaned),
        "chunks": len(chunks),
        "model": active_model(),
        "mode": mode,
    })

    parts: list[str] = []
    try:
        async for delta in summarize_chunks(chunks, mode):
            parts.append(delta)
            yield sse("token", {"t": delta})
    except LLMError as exc:
        logger.warning("llm failure: %s", exc)
        yield sse("error", {"message": str(exc)})
        return
    except asyncio.CancelledError:
        logger.info("client disconnected; discarding partial summary")
        raise

    summary_text = "".join(parts).strip()
    if not summary_text:
        yield sse("error", {"message": "The model returned an empty summary."})
        return

    latency_ms = int((time.perf_counter() - started) * 1000)

    async with SessionLocal() as session:
        record = await repository.create_summary(
            session,
            title=document.title[:512],
            source_url=document.source_url,
            source_type=document.source_type,
            mode=mode,
            model=active_model(),
            summary_text=summary_text,
            source_text=cleaned,
            source_chars=len(cleaned),
            summary_chars=len(summary_text),
            latency_ms=latency_ms,
            meta=document.meta,
        )

    yield sse("done", {
        "id": str(record.id),
        "latency_ms": latency_ms,
        "summary_chars": record.summary_chars,
        "source_chars": record.source_chars,
        "compression_ratio": round(record.compression_ratio, 4),
        "created_at": record.created_at,
    })


SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",   # stops nginx buffering the stream
}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "backend": settings.llm_backend, "model": active_model()}


@app.post("/summarize/stream")
async def summarize_stream(request: SummarizeRequest):
    """Ingest a URL and stream the summary back as Server-Sent Events."""
    try:
        document = await ingest_url(str(request.url))
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return StreamingResponse(
        _summarize_stream(document, request.mode),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.post("/summarize/upload")
async def summarize_upload(
    file: UploadFile = File(...),
    mode: Mode = Form("bullets"),
):
    """Same pipeline, but the source is an uploaded PDF."""
    body = await file.read()
    try:
        document = await ingest_upload(file.filename or "upload.pdf", body)
    except IngestionError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return StreamingResponse(
        _summarize_stream(document, mode),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )


@app.get("/summaries", response_model=ListResponse)
async def list_summaries(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    source_type: str | None = Query(None, pattern="^(html|pdf|youtube)$"),
    session: AsyncSession = Depends(get_session),
):
    items, total = await repository.list_summaries(session, limit, offset, source_type)
    return ListResponse(total=total, items=items)


@app.get("/summaries/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description='Supports "exact phrases", OR, and -exclusions'),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    hits, total = await repository.search_summaries(session, q, limit, offset)
    return SearchResponse(query=q, total=total, hits=hits)


@app.get("/summaries/stats", response_model=StatsResponse)
async def stats(session: AsyncSession = Depends(get_session)):
    return StatsResponse(**await repository.archive_stats(session))


@app.get("/summaries/{summary_id}", response_model=SummaryOut)
async def get_summary(
    summary_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    record = await repository.get_summary(session, summary_id)
    if not record:
        raise HTTPException(status_code=404, detail="No summary with that id.")
    return record


@app.delete("/summaries/{summary_id}", status_code=204)
async def delete_summary(
    summary_id: uuid.UUID, session: AsyncSession = Depends(get_session)
):
    if not await repository.delete_summary(session, summary_id):
        raise HTTPException(status_code=404, detail="No summary with that id.")
