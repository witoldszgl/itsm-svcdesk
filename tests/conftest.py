# ai-generated: 90% - Claude Code drafted, reviewed by the student
import os

import httpx
import pytest

T1 = "2026-10-14T10:00:00Z"


@pytest.fixture(scope="session")
def client():
    with httpx.Client(base_url=os.environ.get("SVCDESK_URL", "http://svcdesk:8080"), timeout=10) as c:
        yield c


@pytest.fixture
def create(client):
    def _create(clock=T1, impact=2, urgency=2, vip=False, **extra):
        body = {"title": "own test", "reporter": {"name": "Tester", "vip": vip},
                "impact": impact, "urgency": urgency, **extra}
        response = client.post("/tickets", json=body, headers={"X-Test-Clock": clock})
        assert response.status_code == 201, response.text
        return response.json()
    return _create


@pytest.fixture
def act(client):
    def _act(ticket_id, action, clock):
        return client.post(f"/tickets/{ticket_id}/{action}", headers={"X-Test-Clock": clock})
    return _act
