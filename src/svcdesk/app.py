# ai-generated: 90% - Claude Code drafted from specs/001-svcdesk/spec.md, reviewed by the student
"""svcdesk HTTP API (API.md sections 1-8)."""
import json
import os
import re
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .sla import UTC, due_instants, in_business_hours, priority_for, uses_business_clock
from .store import Store

REOPEN_WINDOW = timedelta(days=7)
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")
TIMESTAMPS = ("created_at", "acknowledged_at", "resolved_at", "closed_at")


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = Store(os.environ.get("SVCDESK_DB", "/data/svcdesk.db"))
    yield


app = FastAPI(title="svcdesk", lifespan=lifespan)


# --- helpers -----------------------------------------------------------------------------------

def error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def fmt(instant: datetime | None) -> str | None:
    if instant is None:
        return None
    instant = instant.astimezone(UTC)
    if instant.microsecond:
        return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def test_clock_enabled() -> bool:
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")


def now_of(request: Request) -> datetime:
    return request.state.now


def not_found(ticket_id: str) -> JSONResponse:
    return error(404, "not_found", f"ticket {ticket_id} does not exist")


@app.middleware("http")
async def clock_middleware(request: Request, call_next):
    """R-21 / API.md section 8: `now` is the X-Test-Clock of this request, else real UTC time."""
    now = datetime.now(UTC)
    header = request.headers.get("x-test-clock")
    if header is not None and test_clock_enabled():
        value = header.strip()
        try:
            if not RFC3339.match(value):
                raise ValueError(value)
            now = datetime.fromisoformat(value.replace("z", "Z")).astimezone(UTC)
        except ValueError:
            return error(422, "invalid_clock", "X-Test-Clock must be an RFC 3339 instant with an offset")
    request.state.now = now
    return await call_next(request)


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException):
    code = "not_found" if exc.status_code == 404 else "http_error"
    return error(exc.status_code, code, str(exc.detail))


@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    return error(500, "internal", "internal server error")


# --- validation (R-03, R-20, API.md section 7) --------------------------------------------------

class ValidationFailure(Exception):
    pass


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def validate(body) -> dict:
    if not isinstance(body, dict):
        raise ValidationFailure("request body must be a JSON object")

    title = body.get("title")
    if title is None:
        raise ValidationFailure("title is required")
    if not isinstance(title, str) or not 1 <= len(title) <= 200:
        raise ValidationFailure("title must be a string of 1 to 200 characters")

    description = body.get("description")
    if description is None:
        description = ""
    if not isinstance(description, str) or len(description) > 4000:
        raise ValidationFailure("description must be a string of at most 4000 characters")

    reporter = body.get("reporter")
    if not isinstance(reporter, dict):
        raise ValidationFailure("reporter is required and must be an object")
    name = reporter.get("name")
    if not isinstance(name, str) or not 1 <= len(name) <= 100:
        raise ValidationFailure("reporter.name must be a string of 1 to 100 characters")
    email = reporter.get("email")
    if email is not None and not isinstance(email, str):
        raise ValidationFailure("reporter.email must be a string or null")
    vip = reporter.get("vip", False)
    if vip is None:
        vip = False
    if not isinstance(vip, bool):
        raise ValidationFailure("reporter.vip must be a boolean")

    for field in ("impact", "urgency"):
        value = body.get(field)
        if value is None:
            raise ValidationFailure(f"{field} is required")
        if not is_int(value) or not 1 <= value <= 3:
            raise ValidationFailure(f"{field} must be an integer from 1 to 3")

    related_to = body.get("related_to")
    if related_to is not None and not isinstance(related_to, str):
        raise ValidationFailure("related_to must be a string or null")

    return {
        "title": title,
        "description": description,
        "reporter": {"name": name, "email": email, "vip": vip},
        "impact": body["impact"],
        "urgency": body["urgency"],
        "related_to": related_to,
    }


# --- endpoints ---------------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "svcdesk"}


@app.post("/tickets")
async def create_ticket(request: Request):
    try:
        body = json.loads(await request.body() or b"null")
    except (ValueError, UnicodeDecodeError):
        return error(422, "validation", "request body must be valid JSON")
    try:
        fields = validate(body)
    except ValidationFailure as exc:
        return error(422, "validation", str(exc))

    now = now_of(request)
    priority = priority_for(fields["impact"], fields["urgency"], fields["reporter"]["vip"])
    ack_due, resolve_due = due_instants(priority, now)
    ticket = {
        "id": str(uuid.uuid4()),
        **fields,
        "priority": priority,
        "state": "new",
        "created_at": fmt(now),
        "acknowledged_at": None,
        "resolved_at": None,
        "closed_at": None,
        "sla": {"ack_due_at": fmt(ack_due), "resolve_due_at": fmt(resolve_due)},
    }
    request.app.state.store.put(ticket)
    return JSONResponse(status_code=201, content=ticket)


@app.get("/tickets")
async def list_tickets(request: Request, state: str | None = None, priority: str | None = None):
    tickets = request.app.state.store.all()
    if state is not None:
        tickets = [t for t in tickets if t["state"] == state]
    if priority is not None:
        tickets = [t for t in tickets if t["priority"] == priority]
    return tickets


@app.get("/tickets/{ticket_id}")
async def get_ticket(request: Request, ticket_id: str):
    ticket = request.app.state.store.get(ticket_id)
    return ticket if ticket else not_found(ticket_id)


@app.get("/tickets/{ticket_id}/sla")
async def get_sla(request: Request, ticket_id: str):
    """R-15, R-16, API.md section 5."""
    ticket = request.app.state.store.get(ticket_id)
    if not ticket:
        return not_found(ticket_id)
    now = now_of(request)
    ack_due = parse(ticket["sla"]["ack_due_at"])
    resolve_due = parse(ticket["sla"]["resolve_due_at"])
    acknowledged_at = parse(ticket["acknowledged_at"])
    resolved_at = parse(ticket["resolved_at"])

    ack_breached = acknowledged_at > ack_due if acknowledged_at else now > ack_due
    resolve_breached = resolved_at > resolve_due if resolved_at else now > resolve_due
    is_open = ticket["state"] not in ("resolved", "closed")
    paused = is_open and uses_business_clock(ticket["priority"]) and not in_business_hours(now)
    return {
        "priority": ticket["priority"],
        "ack_due_at": ticket["sla"]["ack_due_at"],
        "resolve_due_at": ticket["sla"]["resolve_due_at"],
        "ack_breached": ack_breached,
        "resolve_breached": resolve_breached,
        "paused": paused,
    }


def transition(request: Request, ticket_id: str, action: str):
    """R-07..R-11, API.md section 6; C2 = immutable: a closed ticket is never reopened."""
    store = request.app.state.store
    ticket = store.get(ticket_id)
    if not ticket:
        return not_found(ticket_id)
    now = now_of(request)
    state = ticket["state"]

    if action == "ack" and state == "new":
        ticket.update(state="acknowledged", acknowledged_at=fmt(now))
    elif action == "start" and state == "acknowledged":
        ticket.update(state="in_progress")
    elif action == "resolve" and state == "in_progress":
        ticket.update(state="resolved", resolved_at=fmt(now))
    elif action == "close" and state == "resolved":
        ticket.update(state="closed", closed_at=fmt(now))
    elif action == "reopen" and state == "resolved":
        if now > parse(ticket["resolved_at"]) + REOPEN_WINDOW:
            return error(409, "reopen_window_expired", "the 7-day reopen window has passed")
        ticket.update(state="in_progress", resolved_at=None, closed_at=None)
    elif action == "reopen" and state == "closed":
        return error(409, "ticket_closed",
                     "a closed ticket is immutable; open a new ticket with related_to set to this id")
    else:
        return error(409, "invalid_transition", f"cannot {action} a ticket in state {state}")

    store.put(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/{action}")
async def act(request: Request, ticket_id: str, action: str):
    if action not in ("ack", "start", "resolve", "close", "reopen"):
        return error(404, "not_found", f"unknown action {action}")
    return transition(request, ticket_id, action)
