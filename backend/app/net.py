"""Network safety helpers.

Two problems this solves, both flagged in the v2 review:
  1. SSRF - the API fetches arbitrary user-supplied URLs server-side.
  2. Unbounded downloads - requests.get() pulls a whole response into memory.
"""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from .config import settings


class IngestionError(Exception):
    """Raised when a source cannot be fetched or parsed. Maps to HTTP 422."""


def _is_public_ip(host: str) -> bool:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise IngestionError(f"Could not resolve host: {host}") from exc

    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local          # blocks 169.254.169.254 cloud metadata
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return False
    return True


def assert_safe_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise IngestionError(f"Unsupported scheme '{parsed.scheme}'. Use http or https.")
    if not parsed.hostname:
        raise IngestionError("URL has no host.")
    if settings.allow_private_hosts:
        return
    if not _is_public_ip(parsed.hostname):
        raise IngestionError("Refusing to fetch a private or loopback address.")


async def fetch_bytes(url: str, client: httpx.AsyncClient) -> tuple[bytes, str]:
    """Download a URL with a hard size cap. Returns (body, content_type)."""
    assert_safe_url(url)

    try:
        async with client.stream("GET", url) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").split(";")[0].strip()

            declared = response.headers.get("content-length")
            if declared and int(declared) > settings.max_download_bytes:
                raise IngestionError(
                    f"Source is {int(declared) // 1024} KB, over the "
                    f"{settings.max_download_bytes // 1024} KB limit."
                )

            chunks: list[bytes] = []
            total = 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > settings.max_download_bytes:
                    raise IngestionError(
                        f"Source exceeded the {settings.max_download_bytes // 1024} KB limit."
                    )
                chunks.append(chunk)

    except httpx.TimeoutException as exc:
        raise IngestionError(f"Timed out after {settings.request_timeout_s}s.") from exc
    except httpx.HTTPStatusError as exc:
        raise IngestionError(f"Server returned {exc.response.status_code}.") from exc
    except httpx.RequestError as exc:
        raise IngestionError(f"Could not reach the source: {exc}") from exc

    return b"".join(chunks), content_type
