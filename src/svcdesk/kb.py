# ai-generated: 90% - Claude Code drafted from MONITORING-SPEC.md M-02, reviewed by the student
"""Lab 3: GET /kb/search, one call to kb-index per request (MONITORING-SPEC.md M-02)."""
import os

import httpx

KB_INDEX_URL = os.environ.get("KB_INDEX_URL", "http://kb-index:8080").rstrip("/")
UPSTREAM_TIMEOUT_SECONDS = 5.0  # M-02: at least 2 s


class UpstreamUnavailable(Exception):
    pass


def new_client() -> httpx.AsyncClient:
    # No retries, no cache: exactly one upstream request per search (M-02, M-10).
    return httpx.AsyncClient(
        timeout=UPSTREAM_TIMEOUT_SECONDS,
        limits=httpx.Limits(max_connections=200, max_keepalive_connections=100),
        transport=httpx.AsyncHTTPTransport(retries=0),
    )


def valid_query(q: str | None) -> bool:
    return isinstance(q, str) and 1 <= len(q) <= 200


async def search(client: httpx.AsyncClient, q: str) -> list:
    try:
        response = await client.get(f"{KB_INDEX_URL}/search", params={"q": q})
    except httpx.HTTPError as exc:
        raise UpstreamUnavailable(f"kb-index unreachable: {type(exc).__name__}") from exc
    if response.status_code != 200:
        raise UpstreamUnavailable(f"kb-index answered {response.status_code}")
    try:
        return response.json()["hits"]
    except (ValueError, KeyError, TypeError) as exc:
        raise UpstreamUnavailable("kb-index answered an unexpected body") from exc
