"""LLM access: one interface, three backends, streaming and non-streaming.

Every backend failure is normalised to LLMError so the API layer has exactly
one exception to catch. v2 leaked raw httpx/requests exceptions as 500s
because requests.exceptions.ConnectionError is not the builtin ConnectionError.
"""
import json
import logging
from collections.abc import AsyncIterator

import httpx

from .config import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Any backend failure. Maps to HTTP 503."""


MODE_PROMPTS = {
    "bullets": (
        "Summarise the text below as exactly 5 bullet points. "
        "Each bullet is one distinct key idea, one sentence, no preamble."
    ),
    "tldr": (
        "Write a single-paragraph TL;DR of the text below in 3-4 sentences. "
        "Direct and informative, no preamble."
    ),
    "keyfacts": (
        "Extract the 5 most important verifiable facts from the text below. "
        "Number them 1-5. State only what the text states."
    ),
}

CHUNK_PROMPT = (
    "Condense the section below into a dense factual digest of at most 200 words. "
    "Preserve names, numbers, and claims. No preamble."
)

SYSTEM_PROMPT = (
    "You summarise source documents faithfully. Never add facts that are not "
    "in the source. If the source is too thin to summarise, say so plainly."
)


def active_model() -> str:
    return {
        "groq": settings.groq_model,
        "openai": settings.openai_model,
        "ollama": settings.ollama_model,
    }[settings.llm_backend]


def _openai_compatible_config() -> tuple[str, str, str]:
    if settings.llm_backend == "groq":
        if not settings.groq_api_key:
            raise LLMError("GROQ_API_KEY is not set. Add it to backend/.env.")
        return settings.groq_base_url, settings.groq_api_key, settings.groq_model
    if not settings.openai_api_key:
        raise LLMError("OPENAI_API_KEY is not set. Add it to backend/.env.")
    return settings.openai_base_url, settings.openai_api_key, settings.openai_model


def _build_prompt(text: str, mode: str) -> str:
    if mode not in MODE_PROMPTS:
        raise LLMError(f"Unknown mode '{mode}'. Use: {', '.join(MODE_PROMPTS)}")
    return f"{MODE_PROMPTS[mode]}\n\n---\n{text}\n---"


# --------------------------------------------------------------------------
# streaming
# --------------------------------------------------------------------------

async def stream_completion(prompt: str) -> AsyncIterator[str]:
    """Yields text deltas as they arrive."""
    try:
        if settings.llm_backend == "ollama":
            async for delta in _stream_ollama(prompt):
                yield delta
        else:
            async for delta in _stream_openai_compatible(prompt):
                yield delta
    except LLMError:
        raise
    except httpx.TimeoutException as exc:
        raise LLMError(f"The model timed out after {settings.llm_timeout_s}s.") from exc
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:300]
        raise LLMError(f"{settings.llm_backend} returned "
                       f"{exc.response.status_code}: {detail}") from exc
    except httpx.RequestError as exc:
        raise LLMError(f"Could not reach {settings.llm_backend}: {exc}") from exc


async def _stream_openai_compatible(prompt: str) -> AsyncIterator[str]:
    base_url, api_key, model = _openai_compatible_config()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "stream": True,
    }

    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        async with client.stream(
            "POST",
            f"{base_url}/chat/completions",
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.startswith("data:"):
                    continue
                data = line[5:].strip()
                if data == "[DONE]":
                    return
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {}).get("content")
                if delta:
                    yield delta


async def _stream_ollama(prompt: str) -> AsyncIterator[str]:
    payload = {
        "model": settings.ollama_model,
        "prompt": f"{SYSTEM_PROMPT}\n\n{prompt}",
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=settings.llm_timeout_s) as client:
        async with client.stream(
            "POST", f"{settings.ollama_base_url}/api/generate", json=payload
        ) as response:
            if response.status_code >= 400:
                await response.aread()
                response.raise_for_status()

            async for line in response.aiter_lines():
                if not line.strip():
                    continue
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if chunk.get("response"):
                    yield chunk["response"]
                if chunk.get("done"):
                    return


# --------------------------------------------------------------------------
# non-streaming (used for the map step)
# --------------------------------------------------------------------------

async def complete(prompt: str) -> str:
    parts = [delta async for delta in stream_completion(prompt)]
    return "".join(parts).strip()


async def summarize_chunks(chunks: list[str], mode: str) -> AsyncIterator[str]:
    """Map-reduce over chunks, streaming only the final reduce step.

    One chunk: summarise directly. Many: condense each, then summarise the
    condensed digests. The user sees tokens from the step that produces the
    text they actually read.
    """
    if len(chunks) == 1:
        async for delta in stream_completion(_build_prompt(chunks[0], mode)):
            yield delta
        return

    logger.info("map-reduce over %d chunks", len(chunks))
    digests: list[str] = []
    for index, chunk in enumerate(chunks, start=1):
        digest = await complete(f"{CHUNK_PROMPT}\n\n---\n{chunk}\n---")
        digests.append(f"[Section {index}]\n{digest}")

    combined = "\n\n".join(digests)
    async for delta in stream_completion(_build_prompt(combined, mode)):
        yield delta
