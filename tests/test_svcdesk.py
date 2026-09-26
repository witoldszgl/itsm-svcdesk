# ai-generated: 90% - Claude Code drafted from API.md and CHECKS.md, reviewed by the student
"""Own suite for svcdesk: C1 = wallclock, C2 = immutable, C3 = matrix."""
import pytest

from conftest import T1

MATRIX = [(1, 1, "P1"), (1, 2, "P2"), (1, 3, "P3"), (2, 1, "P2"), (2, 2, "P3"),
          (2, 3, "P4"), (3, 1, "P3"), (3, 2, "P4"), (3, 3, "P4")]

# (impact, urgency) giving the priority, created_at, ack due, resolve due; P1 on the wall clock (C1).
VECTORS = {
    "T1": ((1, 1), "2026-10-14T10:00:00Z", "2026-10-14T10:15:00Z", "2026-10-14T14:00:00Z"),
    "T2": ((1, 3), "2026-10-16T13:30:00Z", "2026-10-19T09:30:00Z", "2026-10-21T13:30:00Z"),
    "T3": ((1, 1), "2026-10-16T15:00:00Z", "2026-10-16T15:15:00Z", "2026-10-16T19:00:00Z"),
    "T4": ((1, 2), "2026-10-17T10:00:00Z", "2026-10-19T07:00:00Z", "2026-10-19T14:00:00Z"),
    "T5": ((2, 3), "2027-01-14T14:30:00Z", "2027-01-15T14:30:00Z", "2027-01-27T14:30:00Z"),
    "T6": ((1, 1), "2027-01-15T15:50:00Z", "2027-01-15T16:05:00Z", "2027-01-15T19:50:00Z"),
    "T7": ((1, 2), "2026-10-14T10:00:00Z", "2026-10-14T11:00:00Z", "2026-10-15T10:00:00Z"),
    "T8": ((1, 3), "2026-10-23T13:00:00Z", "2026-10-26T10:00:00Z", "2026-10-28T14:00:00Z"),
}


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "svcdesk"}


def test_unknown_route_is_json_404(client):
    response = client.get("/no-such-route")
    assert response.status_code == 404
    assert "error" in response.json()


@pytest.mark.parametrize("impact,urgency,expected", MATRIX)
def test_priority_matrix(create, impact, urgency, expected):
    assert create(impact=impact, urgency=urgency)["priority"] == expected


def test_vip_does_not_raise_priority(create):
    assert create(impact=3, urgency=3, vip=True)["priority"] == "P4"


def test_vip_p1_stays_p1(create):
    assert create(impact=1, urgency=1, vip=True)["priority"] == "P1"


def test_priority_in_body_is_ignored(create):
    assert create(impact=3, urgency=3, vip=True, priority="P1")["priority"] == "P4"


@pytest.mark.parametrize("body", [
    {"reporter": {"name": "x"}, "impact": 1, "urgency": 1},
    {"title": "x" * 201, "reporter": {"name": "x"}, "impact": 1, "urgency": 1},
    {"title": "x", "reporter": {"name": "x"}, "impact": 5, "urgency": 1},
    {"title": "x", "reporter": {"name": "x"}, "impact": 1, "urgency": "high"},
    {"title": "x", "reporter": {"name": "x"}, "impact": True, "urgency": 1},
    {"title": "x", "impact": 1, "urgency": 1},
])
def test_validation_rejected(client, body):
    response = client.post("/tickets", json=body, headers={"X-Test-Clock": T1})
    assert response.status_code in (400, 422)
    assert "error" in response.json()


def test_malformed_clock_rejected(client):
    body = {"title": "x", "reporter": {"name": "x"}, "impact": 1, "urgency": 1}
    for clock in ("yesterday", "2026-10-14T10:00:00"):
        response = client.post("/tickets", json=body, headers={"X-Test-Clock": clock})
        assert response.status_code in (400, 422)


def test_server_owned_fields_ignored(create):
    ticket = create(id="mine", state="closed", created_at="2000-01-01T00:00:00Z", foo="bar")
    assert ticket["id"] != "mine" and ticket["state"] == "new"
    assert ticket["created_at"] == T1


def test_get_list_and_filters(client, create):
    p1 = create(impact=1, urgency=1)
    p4 = create(impact=3, urgency=3)
    assert client.get(f"/tickets/{p1['id']}").json()["id"] == p1["id"]
    ids = [t["id"] for t in client.get("/tickets", params={"priority": "P1"}).json()]
    assert p1["id"] in ids and p4["id"] not in ids
    assert p4["id"] in [t["id"] for t in client.get("/tickets", params={"state": "new"}).json()]
    response = client.get("/tickets/does-not-exist")
    assert response.status_code == 404 and "error" in response.json()


@pytest.mark.parametrize("name", sorted(VECTORS))
def test_sla_vectors(create, name):
    (impact, urgency), created, ack_due, resolve_due = VECTORS[name]
    ticket = create(clock=created, impact=impact, urgency=urgency)
    assert ticket["sla"] == {"ack_due_at": ack_due, "resolve_due_at": resolve_due}


def test_state_machine(create, act):
    tid = create()["id"]
    assert act(tid, "start", T1).status_code == 409
    assert act(tid, "resolve", T1).status_code == 409
    assert act(tid, "close", T1).status_code == 409
    assert act(tid, "reopen", T1).status_code == 409
    r = act(tid, "ack", "2026-10-14T10:05:00Z")
    assert r.status_code == 200 and r.json()["acknowledged_at"] == "2026-10-14T10:05:00Z"
    assert act(tid, "ack", T1).status_code == 409
    assert act(tid, "resolve", T1).status_code == 409
    assert act(tid, "start", T1).json()["state"] == "in_progress"
    r = act(tid, "resolve", "2026-10-14T11:00:00Z")
    assert r.json()["state"] == "resolved" and r.json()["resolved_at"] == "2026-10-14T11:00:00Z"
    r = act(tid, "close", "2026-10-14T12:00:00Z")
    assert r.json()["state"] == "closed" and r.json()["closed_at"] == "2026-10-14T12:00:00Z"
    assert act("does-not-exist", "ack", T1).status_code == 404


def _resolved(create, act):
    tid = create()["id"]
    act(tid, "ack", T1)
    act(tid, "start", T1)
    act(tid, "resolve", "2026-10-14T11:00:00Z")
    return tid


def test_reopen_window(create, act):
    tid = _resolved(create, act)
    r = act(tid, "reopen", "2026-10-20T11:00:00Z")
    assert r.status_code == 200 and r.json()["state"] == "in_progress"
    assert r.json()["resolved_at"] is None
    assert act(_resolved(create, act), "reopen", "2026-10-21T11:00:01Z").status_code == 409
    assert act(_resolved(create, act), "reopen", "2026-10-21T11:00:00Z").status_code == 200


def test_closed_ticket_is_immutable(create, act):
    tid = _resolved(create, act)
    act(tid, "close", "2026-10-14T12:00:00Z")
    assert act(tid, "reopen", "2026-10-15T12:00:00Z").status_code == 409


def sla(client, tid, clock):
    return client.get(f"/tickets/{tid}/sla", headers={"X-Test-Clock": clock}).json()


def test_breach_and_pause(client, create, act):
    t2 = create(clock="2026-10-16T13:30:00Z", impact=1, urgency=3)["id"]
    s = sla(client, t2, "2026-10-19T09:31:00Z")
    assert s["ack_breached"] is True and s["resolve_breached"] is False
    assert sla(client, t2, "2026-10-19T09:30:00Z")["ack_breached"] is False
    assert sla(client, t2, "2026-10-17T10:00:00Z")["paused"] is True
    assert sla(client, t2, "2026-10-19T09:00:00Z")["paused"] is False
    fresh = create(clock="2026-10-16T13:30:00Z", impact=1, urgency=3)["id"]
    act(fresh, "ack", "2026-10-16T13:45:00Z")
    assert sla(client, fresh, "2026-10-19T12:00:00Z")["ack_breached"] is False


def test_p1_wallclock_never_paused(client, create):
    tid = create(clock="2026-10-16T15:00:00Z", impact=1, urgency=1)["id"]
    s = sla(client, tid, "2026-10-17T10:00:00Z")
    assert s["paused"] is False and s["ack_breached"] is True
