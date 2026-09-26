<!-- ai-generated: 90% - drafted by Claude Code from plan.md, reviewed by the student -->
# Tasks: svcdesk

- [x] T001 Dockerfile from `python:3.13-slim`, pinned requirements, non-root user, `/data` volume, healthcheck
- [x] T002 docker-compose.yml: service `svcdesk` with `build:`, port 8080, `SVCDESK_TEST_CLOCK: "1"`, named volume
- [x] T003 SQLite store (`src/svcdesk/store.py`)
- [x] T004 Test-clock middleware with RFC 3339 parsing, 422 on malformed or naive values
- [x] T005 `GET /health`, JSON 404 for unknown paths and ids
- [x] T006 `POST /tickets` with validation (R-03, R-20), priority from the matrix (C3 = matrix)
- [x] T007 `GET /tickets` with `state` and `priority` filters, `GET /tickets/{id}`
- [x] T008 State machine: ack, start, resolve, close; 409 on every other transition
- [x] T009 Reopen from resolved within 7 days; 409 from closed (C2 = immutable)
- [x] T010 Business-hours clock with the tie rule; wall clock for P1 (C1 = wallclock); vectors T1..T8
- [x] T011 `GET /tickets/{id}/sla`: breach and pause
- [x] T012 Own pytest suite and `tests` compose profile printing `ITSMLAB-TESTS: passed=<n> failed=0`
- [x] T013 DECISIONS.md with C1=wallclock, C2=immutable, C3=matrix
- [x] T014 Converge report, CLAUDE.md, reviewer sub-agent and AGENT-POLICY.md
