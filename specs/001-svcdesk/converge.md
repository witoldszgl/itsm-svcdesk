<!-- ai-generated: 90% - comparison of spec.md with the implementation, drafted by Claude Code, checked by the student -->
# Converge report: specification vs. implementation

Compared `specs/001-svcdesk/spec.md` with `src/svcdesk/` and the own test suite after implementation.

| requirement | specified | built | status |
|---|---|---|---|
| R-01, R-02 | JSON API on 8080, `/health` | FastAPI on 0.0.0.0:8080, `/health` returns `{"status":"ok","service":"svcdesk"}` | converged |
| R-03, R-20 | ticket fields and validation, 400/422 with `error` | hand-written validation, 422 with `{"error": {"code": "validation", ...}}`; booleans rejected as integers | converged |
| R-04, R-05 | priority from the matrix only | `MATRIX` in `sla.py`; `priority` in the body ignored | converged |
| R-06 | VIP never below P2 | rejected by decision C3 = matrix; `reporter.vip` stored only | converged with decision |
| R-07, R-08 | five states, one endpoint per transition, 409 otherwise | `transition()` in `app.py` | converged |
| R-09, R-10, R-11 | reopen resolved within 7 days, closed immutable | 409 `ticket_closed` from closed, 409 `reopen_window_expired` after 7 days; due instants never recomputed | converged with decision C2 = immutable |
| R-12, R-13, R-14 | targets; P1 wall clock, P2..P4 business hours | `due_instants()`; all eight vectors T1..T8 reproduced by the own tests | converged with decision C1 = wallclock |
| R-15, R-16 | `/sla` with breach and pause | `get_sla()`; equality is not a breach; P1 never paused | converged |
| R-17, R-18, R-19 | UTC `Z` instants, UUID ids, list filters | `fmt()`, `uuid4()`, `list_tickets()` | converged |
| R-21 | per-request test clock | middleware; naive or malformed header answers 422 | converged |
| R-22, R-24 | compose, build, no bind mounts, up within 120 s | `docker-compose.yml` with `build:`, named volume, healthcheck | converged |
| R-23 | tickets survive restart | SQLite on the named volume `svcdesk-data` | converged (not checked in Lab 1) |
| R-25 | JSON 404 | exception handler for unknown paths, `not_found` for ids | converged |

No remediation tasks remain. One deliberate addition beyond the specification: the service runs as a
non-root user in the image.
