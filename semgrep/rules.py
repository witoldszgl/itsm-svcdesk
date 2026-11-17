# ai-generated: 80% - Claude Code (Opus 5.5) wrote the test cases of semgrep/rules.yml (CI-SPEC.md P-31)
import os

from fastapi import FastAPI

# ruleid: svcdesk-env-read-at-import
DB_PATH = os.environ.get("SVCDESK_DB", "/data/svcdesk.db")
# ruleid: svcdesk-env-read-at-import
os.environ.setdefault("PROMETHEUS_DISABLE_CREATED_SERIES", "True")
# ruleid: svcdesk-env-read-at-import
URL = os.getenv("KB_INDEX_URL")
# ruleid: svcdesk-env-read-at-import
TOKEN = os.environ["SVCDESK_TOKEN"]
# ok: svcdesk-env-read-at-import
DEFAULT_DB = "/data/svcdesk.db"


def test_clock_enabled() -> bool:
    # ok: svcdesk-env-read-at-import
    return os.environ.get("SVCDESK_TEST_CLOCK", "").strip().lower() in ("1", "true")


async def lifespan(app: FastAPI):
    # ok: svcdesk-env-read-at-import
    app.state.db = os.environ.get("SVCDESK_DB", DEFAULT_DB)
    yield


def error(status, code, message):
    return {"status": status, "code": code, "message": message}


def get_ticket(ticket_id):
    # ruleid: svcdesk-error-echoes-input
    return error(404, "not_found", f"ticket {ticket_id} does not exist")


def transition(action, state):
    # ruleid: svcdesk-error-echoes-input
    return error(409, "invalid_transition", f"cannot {action} a ticket in state {state}")


def bad_body():
    # ok: svcdesk-error-echoes-input
    return error(400, "invalid_body", "the body must be a JSON object")


def plain_message(ticket_id):
    # ok: svcdesk-error-echoes-input
    return {"message": f"ticket {ticket_id} does not exist"}
