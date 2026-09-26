# ai-generated: 90% - Claude Code wrote the transformation, the student chose the gaming strategy
"""Build gaming/after.jsonl from the practice log (METRIC-SPEC.md section 8).

Strategy, exploiting R-11 with R-10: the team is scored on deployment frequency. It holds back the last real
releases of the window until after the reporting period ends (moving deployments later is allowed by R-19),
and fills the calendar with empty "heartbeat" production deployments that carry no commits. Every empty
deployment counts in the frequency (R-10, R-11); fewer real changes reach production inside the window.
"""
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from svcdesk.dora import compute  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
WINDOW = {"from": "2026-09-01T00:00:00Z", "to": "2026-09-22T00:00:00Z"}
START = datetime(2026, 9, 1, tzinfo=timezone.utc)
END = datetime(2026, 9, 22, tzinfo=timezone.utc)
HELD_UNTIL = END + timedelta(days=1)  # released the day after the reporting window closes
TARGET_DEPLOYMENTS = 56               # 2.667 per day against 2.0: a 33 % rise, above the 25 % margin


def at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def iso(instant: datetime) -> str:
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> None:
    lines = (ROOT / "fixtures" / "events-practice.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in lines if line.strip()]
    before = compute({"window": WINDOW, "events": events})
    limit = before["ground_truth"]["changes_delivered"] * 0.9  # R-21: at most 90 % of the base's

    # Hold back the latest successful real releases in the window until the delivered changes drop enough.
    releases = sorted(
        (e for e in events if e["type"] == "deployment" and e["environment"] == "production"
         and e["outcome"] == "success" and e["commits"] and START <= at(e["at"]) < END),
        key=lambda e: at(e["at"]),
        reverse=True,
    )
    for release in releases:
        if compute({"window": WINDOW, "events": events})["ground_truth"]["changes_delivered"] <= limit - 1:
            break
        release["at"] = iso(max(at(release["at"]), HELD_UNTIL))

    # Fill the window with empty heartbeat deployments until the frequency clears the margin.
    in_window = compute({"window": WINDOW, "events": events})["counts"]["deployments"]
    extra = TARGET_DEPLOYMENTS - in_window
    step = (END - START) / (extra + 1)
    for n in range(1, extra + 1):
        events.append({
            "event_id": f"d-g{n:03d}", "type": "deployment", "at": iso(START + step * n),
            "deployment_id": f"DEP-G{n:03d}", "environment": "production", "outcome": "success",
            "commits": [], "unplanned": False, "caused_by": None,
        })

    out = ROOT / "gaming" / "after.jsonl"
    out.write_text("".join(json.dumps(e, separators=(",", ":")) + "\n" for e in events), encoding="utf-8", newline="\n")
    after = compute({"window": WINDOW, "events": events})
    print("frequency", before["deployment_frequency_per_day"], "->", after["deployment_frequency_per_day"])
    print("changes delivered", before["ground_truth"]["changes_delivered"], "->",
          after["ground_truth"]["changes_delivered"])
    print("true lead p50", before["ground_truth"]["true_change_lead_time_seconds_p50"], "->",
          after["ground_truth"]["true_change_lead_time_seconds_p50"])


if __name__ == "__main__":
    main()
