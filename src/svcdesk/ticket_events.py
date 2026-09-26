# ai-generated: 90% - Claude Code wrote it from METRIC-SPEC.md section 7 (the METR n=1 feature)
"""GET /dora/ticket-events: every ticket as a stream of the lifecycle instants the service holds."""
from datetime import datetime

# phase -> (timestamp field, state at that instant); the order breaks ties within one ticket.
PHASES = (
    ("created", "created_at", "new"),
    ("acknowledged", "acknowledged_at", "acknowledged"),
    ("resolved", "resolved_at", "resolved"),
    ("closed", "closed_at", "closed"),
)


def ticket_events(tickets: list[dict]) -> list[dict]:
    rows = []
    for ticket in tickets:
        for order, (phase, field, state) in enumerate(PHASES):
            at = ticket.get(field)
            if at is None:
                continue
            rows.append((datetime.fromisoformat(at), ticket["id"], order, {
                "ticket_id": ticket["id"],
                "at": at,
                "phase": phase,
                "priority": ticket["priority"],
                "state": state,
            }))
    rows.sort(key=lambda row: row[:3])
    return [row[3] for row in rows]
