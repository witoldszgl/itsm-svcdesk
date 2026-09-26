# ai-generated: 90% - Claude Code drafted from METRIC-SPEC.md and CHECKS.md, reviewed by the student
"""Own suite for Lab 2: POST /dora/metrics and GET /dora/ticket-events."""
import json
import os
from datetime import datetime

import pytest

FIXTURES = os.environ.get("FIXTURES_DIR", os.path.join(os.path.dirname(__file__), "..", "fixtures"))
WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}


def load_events():
    with open(os.path.join(FIXTURES, "events-practice.jsonl"), encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def expected():
    with open(os.path.join(FIXTURES, "metrics-practice.json"), encoding="utf-8") as f:
        return json.load(f)


def metrics(client, events, window=WINDOW):
    response = client.post("/dora/metrics", json={"window": window, "events": events})
    assert response.status_code == 200, response.text
    return response.json()


def test_practice_fixture_matches_answer_key(client, expected):
    assert metrics(client, load_events()) == expected


def test_order_and_duplicates_do_not_matter(client, expected):
    events = load_events()
    assert metrics(client, list(reversed(events))) == expected
    assert metrics(client, events + events) == expected


def test_empty_log(client):
    body = metrics(client, [])
    assert body["deployment_frequency_per_day"] == 0.0
    assert body["change_lead_time_seconds_p50"] is None
    assert body["change_fail_rate"] is None and body["deployment_rework_rate"] is None
    assert set(body["counts"].values()) == {0} and set(body["anomalies"].values()) == {0}


@pytest.mark.parametrize("body", [
    {"events": []},
    {"window": {"from": "2026-09-22T00:00:00Z", "to": "2026-09-01T00:00:00Z"}, "events": []},
    {"window": WINDOW},
    {"window": WINDOW, "events": {}},
    {"window": WINDOW, "events": [{"event_id": "c-1", "type": "commit", "at": "2026-09-01T00:00:00Z",
                                   "sha": "a", "branch": "main", "change_id": None, "reverts": "missing"}]},
])
def test_rejections(client, body):
    response = client.post("/dora/metrics", json=body)
    assert response.status_code in (400, 422)
    assert "error" in response.json()


def test_revert_of_revert_is_one_change(client):
    events = [
        {"event_id": "c1", "type": "commit", "at": "2026-09-02T00:00:00Z", "sha": "s1", "branch": "main",
         "change_id": "CHG-1", "reverts": None},
        {"event_id": "c2", "type": "commit", "at": "2026-09-03T00:00:00Z", "sha": "s2", "branch": "main",
         "change_id": None, "reverts": "s1"},
        {"event_id": "c3", "type": "commit", "at": "2026-09-04T00:00:00Z", "sha": "s3", "branch": "hotfix",
         "change_id": None, "reverts": "s2"},
        {"event_id": "d1", "type": "deployment", "at": "2026-09-04T00:00:00Z", "deployment_id": "D1",
         "environment": "production", "outcome": "success", "commits": ["s3"], "unplanned": False,
         "caused_by": None},
    ]
    body = metrics(client, events)
    assert body["counts"]["changes"] == 1
    assert body["anomalies"]["revert_chains_collapsed"] == 2
    assert body["anomalies"]["commits_never_on_main"] == 1
    assert body["ground_truth"]["true_change_lead_time_seconds_p50"] == 2 * 86400


def test_ticket_events_stream(client, create, act):
    ticket = create(clock="2026-10-14T10:00:00Z")
    act(ticket["id"], "ack", "2026-10-14T10:05:00Z")
    act(ticket["id"], "start", "2026-10-14T10:06:00Z")
    act(ticket["id"], "resolve", "2026-10-14T11:00:00Z")
    response = client.get("/dora/ticket-events")
    assert response.status_code == 200
    stream = response.json()
    keys = [(datetime.fromisoformat(e["at"]), e["ticket_id"]) for e in stream]
    assert keys == sorted(keys)
    mine = [(e["phase"], e["state"]) for e in stream if e["ticket_id"] == ticket["id"]]
    assert mine == [("created", "new"), ("acknowledged", "acknowledged"), ("resolved", "resolved")]
    assert all(e["priority"] == ticket["priority"] for e in stream if e["ticket_id"] == ticket["id"])
