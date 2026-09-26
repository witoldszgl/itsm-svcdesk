<!-- ai-generated: 90% - drafted by Claude Code from REQUIREMENTS.md and API.md, reviewed by the student -->
# Feature specification: svcdesk, the service-desk ticketing API

Status: specification for the first build (Lab 1). Written before any code under `src/`.
Sources: REQUIREMENTS.md (R-01..R-25) is what the desk wants; API.md is the enforced HTTP contract;
CHECKS.md lists what the checker accepts. Where they differ in precision, API.md wins.

## 1. Scope

A small HTTP/JSON service for a desk of about 400 people: it stores tickets, computes their priority,
drives them through a fixed state machine, keeps two SLA targets per ticket and reports breach and pause.
Out of scope for Lab 1: authentication, users and roles, pagination, public holidays, notifications,
validation of `related_to`.

## 2. Resolution of the three conflicting pairs

REQUIREMENTS.md contains three pairs that cannot both hold. Each is resolved by rejecting the minimal
conflicting part of one requirement and keeping everything else, so both requirements of each pair stay
tested. Full reasoning is in `DECISIONS.md`.

| id | pair | resolution | value | what is rejected |
|---|---|---|---|---|
| C1 | R-13 (clocks pause outside business hours) vs R-14 (P1 around the clock) | P1 runs on the wall clock, P2..P4 on the business-hours clock | `wallclock` | the part of R-13 that would apply the business-hours pause to P1 |
| C2 | R-09 (closed ticket is immutable) vs R-10 (reopen resolved or closed within 7 days) | a closed ticket cannot be reopened; a resolved one can, within 7 days | `immutable` | the words "or closed" in R-10 |
| C3 | R-05 (priority from the matrix and nothing else) vs R-06 (VIP never lower than P2) | the matrix alone decides; `reporter.vip` is stored but does not change priority | `matrix` | R-06 as a priority rule |

## 3. Functional requirements

### 3.1 Interface (R-01, R-02, R-25)
- FR-1: HTTP on port 8080, `application/json` on every request and response.
- FR-2: `GET /health` returns 200 `{"status":"ok","service":"svcdesk"}`.
- FR-3: an unknown path returns 404 with a JSON body; an unknown ticket id returns 404 with
  `{"error": {"code": "not_found", "message": ...}}`. A wrong method on a known path may return 404 or 405.

### 3.2 Ticket model and creation (R-03, R-17, R-18, R-20)
- FR-4: `POST /tickets` accepts `title` (string, 1..200, required), `description` (string, 0..4000,
  optional, default ""), `reporter` (object: `name` string 1..100 required, `email` string or null,
  `vip` boolean default false), `impact` and `urgency` (integers 1..3, required; booleans and strings
  are errors), `related_to` (string or null, not validated).
- FR-5: on success 201 with the full ticket: `id` (UUID4, assigned by the service), all input fields,
  `priority`, `state = "new"`, `created_at = now`, `acknowledged_at`, `resolved_at`, `closed_at` null,
  and `sla: {ack_due_at, resolve_due_at}`.
- FR-6: any validation failure returns 422 with `{"error": {"code": "validation", "message": ...}}`.
  A body that is not a JSON object is a validation failure.
- FR-7: server-owned fields (`id`, `priority`, `state`, the four timestamps, `sla`) and unknown fields
  in the request are ignored silently.
- FR-8: every instant is returned in UTC with a `Z` suffix.

### 3.3 Priority (R-04, R-05, R-06, decision C3 = matrix)
- FR-9: priority = matrix(impact, urgency): (1,1) P1; (1,2) P2; (1,3) P3; (2,1) P2; (2,2) P3; (2,3) P4;
  (3,1) P3; (3,2) P4; (3,3) P4.
- FR-10: `reporter.vip` is stored and returned but never changes priority. A `priority` in the body is
  ignored.

### 3.4 Listing and reading (R-19)
- FR-11: `GET /tickets/{id}` returns 200 with the ticket, or 404.
- FR-12: `GET /tickets` returns all tickets as one JSON array; optional `state` and `priority`
  query parameters filter by exact match.

### 3.5 State machine (R-07, R-08, R-09, R-10, R-11, decision C2 = immutable)

| action | endpoint | from | to | side effect |
|---|---|---|---|---|
| acknowledge | `POST /tickets/{id}/ack` | new | acknowledged | `acknowledged_at = now` |
| start | `POST /tickets/{id}/start` | acknowledged | in_progress | - |
| resolve | `POST /tickets/{id}/resolve` | in_progress | resolved | `resolved_at = now` |
| close | `POST /tickets/{id}/close` | resolved | closed | `closed_at = now` |
| reopen | `POST /tickets/{id}/reopen` | resolved, if `now <= resolved_at + 7 days` | in_progress | clears `resolved_at` and `closed_at` |

- FR-13: every other transition returns 409 `{"error": {"code": "invalid_transition", ...}}`.
- FR-14: reopen of a resolved ticket after the 7-day window returns 409 `reopen_window_expired`.
- FR-15: reopen of a closed ticket returns 409 `ticket_closed` whatever its age; follow-up work is a
  new ticket with `related_to` set to the closed ticket's id.
- FR-16: an action on an unknown id returns 404. Successful actions return 200 with the full ticket.
- FR-17: reopening never changes `sla.ack_due_at` or `sla.resolve_due_at`.

### 3.6 SLA targets and clocks (R-12, R-13, R-14, decision C1 = wallclock)

| priority | acknowledge | resolve | clock |
|---|---|---|---|
| P1 | 15 min | 4 h | wall clock: `created_at + target` |
| P2 | 1 h | 8 h | business hours |
| P3 | 4 h | 24 h | business hours |
| P4 | 8 h | 72 h | business hours |

- FR-18: business hours are Monday to Friday, the half-open window [08:00, 16:00) in Europe/Warsaw,
  DST-aware; public holidays are business days.
- FR-19: business-hours algorithm: take `created_at` in Europe/Warsaw; if outside a window move to the
  next opening; consume the target from consecutive windows; a target ending exactly at 16:00 is due
  at 16:00 of that day (tie rule); convert back to UTC.
- FR-20: the service must reproduce the eight test vectors T1..T8 of API.md section 4, using the
  wall-clock columns for P1 (T1, T3, T6) and the business columns for P2..P4.

### 3.7 Breach and pause (R-15, R-16)
- FR-21: `GET /tickets/{id}/sla` returns `{priority, ack_due_at, resolve_due_at, ack_breached,
  resolve_breached, paused}` evaluated at `now`.
- FR-22: `ack_breached` = not acknowledged and `now > ack_due_at`, or `acknowledged_at > ack_due_at`.
- FR-23: `resolve_breached` = `resolved_at` is null and `now > resolve_due_at`, or
  `resolved_at > resolve_due_at`. Equality is never a breach.
- FR-24: `paused` = state is neither resolved nor closed, the ticket's resolution target runs on the
  business-hours clock (every P2..P4; never P1 under C1 = wallclock), and `now` is outside a business
  window.

### 3.8 Test clock (R-21)
- FR-25: when `SVCDESK_TEST_CLOCK` is `1` or `true`, an `X-Test-Clock` header with an RFC 3339
  instant including an offset is `now` for that request only. A malformed or naive value returns 422.
  Without the header `now` is real UTC time. When the variable is unset or `0` the header is ignored.
- FR-26: the service never compares clocks across requests and never enforces monotonic time.

### 3.9 Packaging and persistence (R-22, R-23, R-24)
- FR-27: `docker-compose.yml` defines service `svcdesk` with `build:` from the repository, port 8080,
  `SVCDESK_TEST_CLOCK: "1"`, no bind mounts, all dependencies installed at build time (no network at
  run time), up and healthy within 120 s.
- FR-28: tickets are stored in SQLite on a named volume and survive a container restart.

## 4. Acceptance criteria
- Every check of CHECKS.md L1-CORE-1..4 passes; the observations are C1=wallclock, C2=immutable,
  C3=matrix and equal the front matter of `DECISIONS.md`.
- Specific vectors: T3 (P1, Friday 17:00 CEST) gives ack 2026-10-16T15:15:00Z and resolve
  2026-10-16T19:00:00Z; a ticket closed one day ago answers 409 to reopen; impact 3, urgency 3 with
  `vip: true` gives P4.
