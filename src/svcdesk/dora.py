# ai-generated: 90% - Claude Code wrote it from METRIC-SPEC.md rule by rule, checked against the practice fixture
"""DORA's five delivery metrics over a JSONL event log (Lab 2, METRIC-SPEC.md)."""
import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

UTC = timezone.utc
SPEC_VERSION = "1.0.0"
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$")


class InvalidLog(Exception):
    pass


# --- parsing and well-formedness (section 1, R-05) ----------------------------------------------

def parse_instant(value, what: str) -> datetime:
    if not isinstance(value, str) or not RFC3339.match(value):
        raise InvalidLog(f"{what} must be an RFC 3339 instant with an offset")
    try:
        return datetime.fromisoformat(value.replace("z", "Z").replace("t", "T")).astimezone(UTC)
    except ValueError as exc:
        raise InvalidLog(f"{what} is not a valid instant") from exc


def fmt(instant: datetime) -> str:
    if instant.microsecond:
        return instant.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    return instant.strftime("%Y-%m-%dT%H:%M:%SZ")


def _str(event: dict, field: str, nullable: bool = False) -> str | None:
    value = event.get(field)
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value:
        raise InvalidLog(f"event {event.get('event_id')!r}: {field} must be a non-empty string")
    return value


def _str_list(event: dict, field: str) -> list[str]:
    value = event.get(field)
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise InvalidLog(f"event {event.get('event_id')!r}: {field} must be an array of strings")
    return value


def parse_window(body) -> tuple[datetime, datetime]:
    if not isinstance(body, dict):
        raise InvalidLog("the body must be a JSON object")
    window = body.get("window")
    if not isinstance(window, dict):
        raise InvalidLog("window is required")
    start = parse_instant(window.get("from"), "window.from")
    end = parse_instant(window.get("to"), "window.to")
    if end <= start:
        raise InvalidLog("window.to must be after window.from")
    return start, end


def parse_events(raw) -> tuple[dict, list, dict]:
    """Returns commits by sha, deployments, incidents by id; raises InvalidLog on a malformed log."""
    if not isinstance(raw, list):
        raise InvalidLog("events must be an array")

    seen_ids: set[str] = set()
    commits: dict[str, dict] = {}
    deployments: list[dict] = []
    incidents: dict[str, dict] = {}

    for event in raw:
        if not isinstance(event, dict):
            raise InvalidLog("every event must be a JSON object")
        event_id = event.get("event_id")
        if not isinstance(event_id, str) or not 1 <= len(event_id) <= 64:
            raise InvalidLog("event_id must be a string of 1 to 64 characters")
        if event_id in seen_ids:  # R-05: the first occurrence wins
            continue
        seen_ids.add(event_id)
        kind = event.get("type")
        at = parse_instant(event.get("at"), f"event {event_id!r}: at")

        if kind == "commit":
            sha = _str(event, "sha")
            if sha in commits:
                raise InvalidLog(f"sha {sha!r} is not unique")
            branch = event.get("branch")
            if not isinstance(branch, str):
                raise InvalidLog(f"event {event_id!r}: branch must be a string")
            change_id = _str(event, "change_id", nullable=True)
            reverts = _str(event, "reverts", nullable=True)
            if (change_id is None) == (reverts is None):
                raise InvalidLog(f"event {event_id!r}: a commit carries change_id exactly when reverts is null")
            commits[sha] = {"at": at, "branch": branch, "change_id": change_id, "reverts": reverts}

        elif kind == "deployment":
            outcome = event.get("outcome")
            if outcome not in ("success", "failure"):
                raise InvalidLog(f"event {event_id!r}: outcome must be success or failure")
            unplanned = event.get("unplanned")
            if not isinstance(unplanned, bool):
                raise InvalidLog(f"event {event_id!r}: unplanned must be a boolean")
            deployments.append({
                "id": _str(event, "deployment_id"),
                "at": at,
                "environment": _str(event, "environment"),
                "outcome": outcome,
                "commits": _str_list(event, "commits"),
                "unplanned": unplanned,
                "caused_by": _str(event, "caused_by", nullable=True),
            })

        elif kind == "incident":
            incident_id = _str(event, "incident_id")
            phase = event.get("phase")
            if phase not in ("opened", "resolved"):
                raise InvalidLog(f"event {event_id!r}: phase must be opened or resolved")
            incident = incidents.setdefault(incident_id, {"id": incident_id, "opened": None,
                                                          "resolved": None, "deployments": set()})
            if incident[phase] is not None:
                raise InvalidLog(f"incident {incident_id!r} has more than one {phase} event")
            incident[phase] = at
            incident["deployments"].update(_str_list(event, "deployments"))

        else:
            raise InvalidLog(f"event {event_id!r}: type must be commit, deployment or incident")

    deployment_ids = {d["id"] for d in deployments}
    for sha, commit in commits.items():
        if commit["reverts"] is not None and commit["reverts"] not in commits:
            raise InvalidLog(f"commit {sha!r} reverts an unknown sha")
    for deployment in deployments:
        for sha in deployment["commits"]:
            if sha not in commits:
                raise InvalidLog(f"deployment {deployment['id']!r} carries an unknown sha {sha!r}")
        if deployment["caused_by"] is not None and deployment["caused_by"] not in incidents:
            raise InvalidLog(f"deployment {deployment['id']!r} is caused by an unknown incident")
    for incident in incidents.values():
        if incident["opened"] is None:
            raise InvalidLog(f"incident {incident['id']!r} resolved without being opened")
        if not incident["deployments"] <= deployment_ids:
            raise InvalidLog(f"incident {incident['id']!r} names an unknown deployment")

    return commits, deployments, incidents


# --- arithmetic (R-03, R-04) --------------------------------------------------------------------

def seconds(delta) -> Decimal:
    return Decimal(str(delta.total_seconds()))


def whole_seconds(value: Decimal) -> int:
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def ratio(numerator, denominator) -> float | None:
    if not denominator:
        return None
    return float((Decimal(numerator) / Decimal(denominator)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP))


def median(values: list[Decimal]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return whole_seconds(ordered[middle])
    return whole_seconds((ordered[middle - 1] + ordered[middle]) / 2)


def clamp(value: Decimal) -> Decimal:
    return value if value > 0 else Decimal(0)


# --- the metrics (sections 2 to 5) --------------------------------------------------------------

def resolve_change(sha: str, commits: dict) -> str | None:
    """R-06: a revert inherits, transitively, the change_id of the commit it reverts."""
    seen = set()
    while sha is not None and sha not in seen:
        seen.add(sha)
        commit = commits[sha]
        if commit["change_id"] is not None:
            return commit["change_id"]
        sha = commit["reverts"]
    return None


def compute(body) -> dict:
    start, end = parse_window(body)
    if not isinstance(body, dict) or "events" not in body:
        raise InvalidLog("events is required")
    commits, deployments, incidents = parse_events(body["events"])

    change_of = {sha: resolve_change(sha, commits) for sha in commits}
    first_commit_at: dict[str, datetime] = {}
    for sha, commit in commits.items():
        change = change_of[sha]
        if change is not None and (change not in first_commit_at or commit["at"] < first_commit_at[change]):
            first_commit_at[change] = commit["at"]

    # R-01, R-02: production deployments inside [from, to); order-independent processing order.
    in_scope = sorted(
        (d for d in deployments if d["environment"] == "production" and start <= d["at"] < end),
        key=lambda d: (d["at"], d["id"]),
    )
    successful = [d for d in in_scope if d["outcome"] == "success"]
    failed = [d for d in in_scope if d["outcome"] == "failure"]

    # R-08, R-09, R-10: one pair per sha at its first successful deployment; E1 clamps.
    lead_times: list[Decimal] = []
    negative_pairs = 0
    paired: set[str] = set()
    for deployment in successful:
        for sha in deployment["commits"]:
            if sha in paired:
                continue
            paired.add(sha)
            lead = seconds(deployment["at"] - commits[sha]["at"])
            if lead < 0:
                negative_pairs += 1
            lead_times.append(clamp(lead))

    never_on_main = {sha for d in in_scope for sha in d["commits"] if commits[sha]["branch"] != "main"}
    without_commits = sum(1 for d in in_scope if not d["commits"])

    # R-12, R-13: recovery per failed deployment from its covering incident; E5 open failures.
    recoveries: list[Decimal] = []
    open_failures = 0
    for deployment in failed:
        covering = min(
            (i for i in incidents.values() if deployment["id"] in i["deployments"]),
            key=lambda i: (i["opened"], i["id"].encode()),
            default=None,
        )
        if covering is None or covering["resolved"] is None:
            open_failures += 1
        else:
            recoveries.append(clamp(seconds(covering["resolved"] - deployment["at"])))

    intervals = [(i["opened"], i["resolved"] if i["resolved"] is not None else end) for i in incidents.values()]
    overlapping = sum(
        1
        for a in range(len(intervals))
        for b in range(a + 1, len(intervals))
        if intervals[a][0] < intervals[b][1] and intervals[b][0] < intervals[a][1]
    )

    rework = sum(1 for d in in_scope if d["unplanned"] and d["caused_by"] is not None)

    # R-16, R-17: ground truth over changes, from each change's first commit instant.
    first_delivery: dict[str, datetime] = {}
    for deployment in successful:
        for sha in deployment["commits"]:
            change = change_of[sha]
            if change is not None and change not in first_delivery:
                first_delivery[change] = deployment["at"]
    true_leads = [clamp(seconds(at - first_commit_at[change])) for change, at in first_delivery.items()]

    days = Decimal(str((end - start).total_seconds())) / Decimal(86400)
    return {
        "spec_version": SPEC_VERSION,
        "window": {"from": fmt(start), "to": fmt(end)},
        "deployment_frequency_per_day": ratio(len(in_scope), days) or 0.0,
        "change_lead_time_seconds_p50": median(lead_times),
        "failed_deployment_recovery_time_seconds_p50": median(recoveries),
        "change_fail_rate": ratio(len(failed), len(in_scope)),
        "deployment_rework_rate": ratio(rework, len(in_scope)),
        "counts": {
            "deployments": len(in_scope),
            "successful_deployments": len(successful),
            "failed_deployments": len(failed),
            "recovered_failures": len(recoveries),
            "open_failures": open_failures,
            "rework_deployments": rework,
            "lead_time_pairs": len(lead_times),
            "changes": len({c for c in change_of.values() if c is not None}),
        },
        "anomalies": {
            "negative_lead_time_pairs": negative_pairs,
            "deployments_without_commits": without_commits,
            "commits_never_on_main": len(never_on_main),
            "revert_chains_collapsed": sum(1 for c in commits.values() if c["reverts"] is not None),
            "overlapping_incident_pairs": overlapping,
        },
        "ground_truth": {
            "changes_delivered": len(first_delivery),
            "true_change_lead_time_seconds_p50": median(true_leads),
        },
    }
