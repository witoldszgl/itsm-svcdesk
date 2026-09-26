# ai-generated: 90% - Claude Code drafted, reviewed by the student
"""Run the suite against SVCDESK_URL and print the ITSMLAB-TESTS summary as the very last line."""
import os
import sys
import time

import httpx
import pytest


class Counter:
    def __init__(self):
        self.passed = 0
        self.failed = 0

    def pytest_runtest_logreport(self, report):
        if report.when == "call" and report.passed:
            self.passed += 1
        elif report.failed:
            self.failed += 1


def wait_for_service(url: str, seconds: int = 90) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            if httpx.get(f"{url}/health", timeout=2).status_code == 200:
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)


def main() -> int:
    wait_for_service(os.environ.get("SVCDESK_URL", "http://svcdesk:8080"))
    counter = Counter()
    code = pytest.main(["-q", "-p", "no:cacheprovider", os.path.dirname(os.path.abspath(__file__))],
                       plugins=[counter])
    sys.stdout.flush()
    print(f"ITSMLAB-TESTS: passed={counter.passed} failed={counter.failed}", flush=True)
    return 0 if code == 0 and counter.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
