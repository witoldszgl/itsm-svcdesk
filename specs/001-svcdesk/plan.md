<!-- ai-generated: 90% - drafted by Claude Code from spec.md, reviewed by the student -->
# Implementation plan: svcdesk

## Technical context
- Language: Python 3.13; framework: FastAPI on uvicorn; storage: SQLite (stdlib `sqlite3`) on the named
  volume `svcdesk-data` mounted at `/data`; time zones: stdlib `zoneinfo` with `tzdata` pinned in the image.
- Image: `python:3.13-slim`, dependencies pinned in `src/requirements.txt` and installed at build time;
  runs as a non-root user; listens on 0.0.0.0:8080; healthcheck on `/health`.
- Request bodies are parsed by hand, not by Pydantic models, so that booleans are not accepted as integers
  and unknown or server-owned fields are ignored without surprises.

## Layout
- `src/svcdesk/sla.py`: priority matrix (C3), SLA targets, the wall clock and the business-hours clock (C1),
  `in_business_hours`.
- `src/svcdesk/store.py`: SQLite store, one row per ticket, the ticket as JSON.
- `src/svcdesk/app.py`: HTTP layer; test-clock middleware; validation; endpoints; state machine (C2).
- `tests/`: own pytest suite run by the compose `tests` profile (Stretch S3).
- `Dockerfile`, `Dockerfile.tests`, `docker-compose.yml`: the compose contract.

## Key design points
- `now` is computed once per request in a middleware and stored in `request.state`; nothing else reads
  the system clock.
- Due instants are computed once at creation and stored; reopen never recomputes them (R-11).
- Business-hours arithmetic works on UTC instants of each day's local 08:00 and 16:00 windows, so DST is
  handled by `zoneinfo`; `remaining <= available` implements the tie rule.
- The decision values are constants in `sla.py` (C1, C3) and one branch in `app.py` (C2).
