# ai-generated: 90% - Claude Code drafted, checked against the T1..T8 vectors of API.md
"""Priority matrix, SLA targets and the two clocks (decisions C1 and C3)."""
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
WARSAW = ZoneInfo("Europe/Warsaw")
OPEN = time(8, 0)
CLOSE = time(16, 0)

# Decision C1 = wallclock: P1 runs around the clock (R-14), P2..P4 on business hours (R-13).
# Decision C3 = matrix: the matrix alone decides the priority (R-05); reporter.vip is stored only.
C1 = "wallclock"
C3 = "matrix"

MATRIX = {
    (1, 1): "P1", (1, 2): "P2", (1, 3): "P3",
    (2, 1): "P2", (2, 2): "P3", (2, 3): "P4",
    (3, 1): "P3", (3, 2): "P4", (3, 3): "P4",
}

TARGETS = {
    "P1": (timedelta(minutes=15), timedelta(hours=4)),
    "P2": (timedelta(hours=1), timedelta(hours=8)),
    "P3": (timedelta(hours=4), timedelta(hours=24)),
    "P4": (timedelta(hours=8), timedelta(hours=72)),
}


def priority_for(impact: int, urgency: int, vip: bool) -> str:
    priority = MATRIX[(impact, urgency)]
    if C3 == "vip" and vip and priority in ("P3", "P4"):
        priority = "P2"
    return priority


def uses_business_clock(priority: str) -> bool:
    return not (priority == "P1" and C1 == "wallclock")


def _window(day: date) -> tuple[datetime, datetime]:
    """Business window of a local day, as UTC instants."""
    opening = datetime.combine(day, OPEN, tzinfo=WARSAW).astimezone(UTC)
    closing = datetime.combine(day, CLOSE, tzinfo=WARSAW).astimezone(UTC)
    return opening, closing


def add_business_time(start: datetime, target: timedelta) -> datetime:
    """Consume `target` from consecutive business windows starting at `start`."""
    now = start.astimezone(UTC)
    remaining = target
    day = now.astimezone(WARSAW).date()
    while True:
        if day.weekday() < 5:
            opening, closing = _window(day)
            if now < opening:
                now = opening
            if now < closing:
                available = closing - now
                # Tie rule: a target ending exactly at closing is due at closing.
                if remaining <= available:
                    return now + remaining
                remaining -= available
        day += timedelta(days=1)
        now = _window(day)[0]


def due_instants(priority: str, created_at: datetime) -> tuple[datetime, datetime]:
    ack, resolve = TARGETS[priority]
    if uses_business_clock(priority):
        return add_business_time(created_at, ack), add_business_time(created_at, resolve)
    return created_at + ack, created_at + resolve


def in_business_hours(now: datetime) -> bool:
    local = now.astimezone(WARSAW)
    return local.weekday() < 5 and OPEN <= local.time() < CLOSE
