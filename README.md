# Web Summarizer v3

Ingests web pages, PDFs, and YouTube transcripts through one pipeline,
summarizes them with a streaming LLM, and archives every result in Postgres
with full-text search.

## What changed from v2

| | v2 | v3 |
|---|---|---|
| Sources | HTML only | HTML, PDF (URL or upload), YouTube transcripts |
| Long documents | Truncated at 4,000 chars | Chunked, map-reduced across the whole document |
| Output | One blocking response | Token-by-token SSE stream |
| Storage | None | Postgres archive with weighted full-text search |
| Config | `.env` never loaded (`load_dotenv` was missing) | `pydantic-settings`, typed and validated |
| Non-English text | Deleted by ASCII stripping | Preserved via NFKC normalization |
| SSRF | Any URL fetched server-side | Private, loopback, and link-local addresses refused |
| Errors | `requests` exceptions leaked as 500s | Normalized to `IngestionError` (422) / `LLMError` (503) |
| Tests | None | 22 passing |

## Architecture

```
                  ┌───────────────────────────────────┐
  URL / PDF ─────▶│ ingestion/router.py               │
                  │   html.py · pdf.py · youtube.py   │  → Document
                  └───────────────────────────────────┘
                                  │
                  ┌───────────────▼───────────────────┐
                  │ processor.py                      │
                  │   NFKC clean → paragraph chunking │
                  └───────────────┬───────────────────┘
                                  │
                  ┌───────────────▼───────────────────┐
                  │ llm_client.py                     │
                  │   map-reduce · SSE stream         │
                  │   groq | openai | ollama          │
                  └───────────────┬───────────────────┘
                                  │
              ┌───────────────────┴──────────────────┐
              ▼                                      ▼
     SSE to browser                        Postgres archive
     (token by token)                      (tsvector + GIN)
```

Every adapter returns the same `Document`, so adding a source format never
touches the summarization pipeline.

## Full-text search

`summaries.search_vector` is a Postgres **generated column**, so the index can
never drift from the row — there is no trigger to maintain:

```sql
setweight(to_tsvector('english', coalesce(title,        '')), 'A') ||
setweight(to_tsvector('english', coalesce(summary_text, '')), 'B') ||
setweight(to_tsvector('english', coalesce(source_text,  '')), 'C')
```

Queries use `websearch_to_tsquery`, which gives users real search syntax for
free, plus `ts_rank_cd` for density-aware ranking and `ts_headline` for
snippets:

| Input | Behaviour |
|---|---|
| `memory coalescing` | Stemmed match on either term |
| `"memory coalescing"` | Exact phrase |
| `transformer -warp` | Excludes the second term |
| `gin OR warp` | Either term |

`ts_headline` emits `[[HL]]…[[/HL]]` markers rather than `<mark>` tags,
because summary text is model-generated — returning HTML would force the
frontend to render untrusted markup. The client splits on the markers and
builds React elements instead.

## Setup (Windows / PowerShell)

### 1. Database

```powershell
docker compose up -d db
```

### 2. Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

Copy-Item .env.example .env
# then edit .env and set GROQ_API_KEY

uvicorn app.api:app --reload
```

API docs: `http://localhost:8000/docs`

### 3. Frontend

```powershell
cd frontend
npm install
npm run dev
```

App: `http://localhost:5173` (Vite proxies `/api` to the backend, so there is
no CORS round trip in development).

### 4. Tests

```powershell
cd backend
pytest -q
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/summarize/stream` | Ingest a URL, stream the summary as SSE |
| `POST` | `/summarize/upload` | Same pipeline for an uploaded PDF |
| `GET` | `/summaries` | Paginated archive, filterable by `source_type` |
| `GET` | `/summaries/search?q=` | Ranked full-text search with snippets |
| `GET` | `/summaries/stats` | Totals, compression ratio, average latency |
| `GET` | `/summaries/{id}` | One archived summary |
| `DELETE` | `/summaries/{id}` | Remove from the archive |

### SSE event sequence

```
event: meta   → title, source_type, source_chars, chunks, model
event: token  → { "t": "..." }        (repeated)
event: done   → id, latency_ms, compression_ratio
event: error  → { "message": "..." }  (terminal)
```

Rows are written only after the model finishes, so a cancelled or failed
generation never leaves a partial summary in the archive.

## Configuration

All settings come from `backend/.env` (see `.env.example`).

| Variable | Default | Notes |
|---|---|---|
| `LLM_BACKEND` | `groq` | `groq`, `openai`, or `ollama` |
| `GROQ_MODEL` | `llama-3.3-70b-versatile` | |
| `MAX_DOWNLOAD_BYTES` | `10485760` | Hard cap on any fetched source |
| `MAX_SOURCE_CHARS` | `60000` | Cap before chunking |
| `ALLOW_PRIVATE_HOSTS` | `false` | Set `true` only to summarize localhost in dev |

## Next

- Redis cache keyed on `(url, mode, model)` — the biggest single latency win
- `POST /summarize/batch` with `asyncio.gather` and a bounded semaphore
- Evaluation harness: ROUGE-L, BERTScore, and LLM-as-judge faithfulness
- OCR fallback for scanned PDFs
## License

MIT — see [LICENSE](LICENSE).