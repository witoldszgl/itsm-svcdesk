# ai-generated: 90% - Claude Code drafted from MONITORING-SPEC.md M-03 to M-07, reviewed by the student
"""Lab 3: the RED histogram of every request (MONITORING-SPEC.md M-03 to M-07)."""
import os
import time

os.environ.setdefault("PROMETHEUS_DISABLE_CREATED_SERIES", "True")

from prometheus_client import CONTENT_TYPE_LATEST, Histogram, generate_latest  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import Response  # noqa: E402

# M-06, M-11: the ladder, in seconds. Designed from the measured p99 (slo.md, section "Buckets").
# The measured q (p99) of witoldszgl's profile is about 0.110 s; every bucket from 0.075 to 0.2 is at most 20 % as
# wide as its lower end, so any q in that band is resolved (M-11). 0.2 is the latency SLI's threshold (M-13).
BUCKETS = (
    0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.075,
    0.09, 0.095, 0.1, 0.105, 0.11, 0.115, 0.12, 0.125, 0.13, 0.14, 0.15, 0.175, 0.2,
    0.25, 0.3, 0.5, 1, 2, 5,
)

REQUEST_DURATION = Histogram(
    "http_server_request_duration_seconds",
    "Duration of HTTP server requests, in seconds.",
    ["http_request_method", "http_route", "http_response_status_code"],
    buckets=BUCKETS,
)

UNMATCHED = "unmatched"


def route_template(request: Request) -> str:
    """M-05: the template of the matched route, never the raw path; one constant value otherwise."""
    route = request.scope.get("route")
    return getattr(route, "path", None) or UNMATCHED


async def metrics_middleware(request: Request, call_next):
    """Observes every request exactly once, except /metrics itself (M-04)."""
    if request.url.path == "/metrics":
        return await call_next(request)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        REQUEST_DURATION.labels(request.method, route_template(request), str(status)).observe(
            time.perf_counter() - start
        )


def metrics_response() -> Response:
    """M-03: the Prometheus text format, Content-Type text/plain; version=0.0.4."""
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
