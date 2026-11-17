# ai-generated: 90% - Claude Code (Opus 5.5) wrote these boundary tests from the docstrings of slaclock.py; checked with itsmlab mutants 5
"""Tests of slaclock.py (Lab 5, Stretch 1): every boundary its docstrings promise, called only inside tests."""

from datetime import datetime, timedelta

import pytest

import slaclock
from slaclock import (
    add_business_minutes,
    business_minutes_between,
    escalation_tier,
    is_business_time,
    parse_duration,
    priority_of,
    sla_state,
    targets,
)

MON = datetime(2026, 1, 5)  # a Monday
FRI = datetime(2026, 1, 9)
SAT = datetime(2026, 1, 10)
SUN = datetime(2026, 1, 11)


def at(day, hh, mm=0, ss=0, us=0):
    return day.replace(hour=hh, minute=mm, second=ss, microsecond=us)


# ---------------------------------------------------------------- constants
def test_constants():
    assert slaclock.OPENING == 480
    assert slaclock.CLOSING == 960
    assert slaclock.MAX_DAYS == 366
    assert slaclock.WARNING_PERCENT == 75


# ---------------------------------------------------------------- priority_of
@pytest.mark.parametrize(
    "impact,urgency,expected",
    [
        (1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P3"), (2, 2, "P3"), (3, 1, "P3"),
        (2, 3, "P4"), (3, 2, "P4"), (3, 3, "P4"),
    ],
)
def test_priority_matrix(impact, urgency, expected):
    assert priority_of(impact, urgency) == expected
    assert priority_of(impact, urgency, False) == expected
    assert priority_of(impact, urgency, vip=False) == expected


@pytest.mark.parametrize(
    "impact,urgency,expected",
    [
        (1, 1, "P1"), (1, 2, "P2"), (2, 1, "P2"), (1, 3, "P2"), (2, 2, "P2"), (3, 1, "P2"),
        (2, 3, "P2"), (3, 2, "P2"), (3, 3, "P2"),
    ],
)
def test_priority_vip(impact, urgency, expected):
    assert priority_of(impact, urgency, vip=True) == expected
    assert priority_of(impact, urgency, True) == expected


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 1.0, True, False, "1", None, 10])
def test_priority_rejects_impact(bad):
    with pytest.raises(ValueError):
        priority_of(bad, 1)


@pytest.mark.parametrize("bad", [0, 4, -1, 2.0, 3.0, True, False, "3", None, 10])
def test_priority_rejects_urgency(bad):
    with pytest.raises(ValueError):
        priority_of(1, bad)


def test_priority_rejects_with_vip():
    with pytest.raises(ValueError):
        priority_of(4, 1, vip=True)
    with pytest.raises(ValueError):
        priority_of(1, 0, vip=True)


# ---------------------------------------------------------------- targets
def test_targets_values():
    assert targets("P1") == (15, 240)
    assert targets("P2") == (60, 480)
    assert targets("P3") == (240, 1440)
    assert targets("P4") == (480, 4320)


@pytest.mark.parametrize("bad", ["p1", " P1", "P1 ", "P5", "P0", "", "P", "1"])
def test_targets_rejects(bad):
    with pytest.raises(ValueError):
        targets(bad)


# ---------------------------------------------------------------- sla_state
@pytest.mark.parametrize(
    "elapsed,target,expected",
    [
        (0, 15, "ok"), (11, 15, "ok"), (12, 15, "warning"), (15, 15, "warning"), (16, 15, "breached"),
        (74, 100, "ok"), (75, 100, "warning"), (76, 100, "warning"), (99, 100, "warning"),
        (100, 100, "warning"), (101, 100, "breached"), (1000, 100, "breached"),
        (0, 1, "ok"), (1, 1, "warning"), (2, 1, "breached"),
        (2, 4, "ok"), (3, 4, "warning"), (4, 4, "warning"), (5, 4, "breached"),
        (179, 240, "ok"), (180, 240, "warning"), (240, 240, "warning"), (241, 240, "breached"),
        (359, 480, "ok"), (360, 480, "warning"),
    ],
)
def test_sla_state(elapsed, target, expected):
    assert sla_state(elapsed, target) == expected


@pytest.mark.parametrize("elapsed,target", [(-1, 10), (0, 0), (5, 0), (5, -1), (-1, 0), (0, -10)])
def test_sla_state_rejects(elapsed, target):
    with pytest.raises(ValueError):
        sla_state(elapsed, target)


# ---------------------------------------------------------------- is_business_time
@pytest.mark.parametrize(
    "moment,expected",
    [
        (at(MON, 8, 0), True), (at(MON, 7, 59), False), (at(MON, 7, 59, 59), False),
        (at(MON, 15, 59), True), (at(MON, 15, 59, 59), True), (at(MON, 16, 0), False),
        (at(MON, 16, 1), False), (at(MON, 12, 0), True), (at(MON, 0, 0), False), (at(MON, 23, 59), False),
        (at(FRI, 8, 0), True), (at(FRI, 15, 59), True), (at(FRI, 16, 0), False),
        (at(SAT, 8, 0), False), (at(SAT, 12, 0), False), (at(SUN, 12, 0), False),
        (at(MON + timedelta(days=1), 9, 0), True), (at(MON + timedelta(days=2), 9, 0), True),
        (at(MON + timedelta(days=3), 9, 0), True),
    ],
)
def test_is_business_time(moment, expected):
    assert is_business_time(moment) is expected


# ---------------------------------------------------------------- add_business_minutes
@pytest.mark.parametrize(
    "start,minutes,expected",
    [
        (at(MON, 8), 0, at(MON, 8)),
        (at(MON, 10, 30), 0, at(MON, 10, 30)),
        (at(MON, 7), 0, at(MON, 8)),
        (at(MON, 16), 0, at(MON + timedelta(days=1), 8)),
        (at(MON, 20), 0, at(MON + timedelta(days=1), 8)),
        (at(SAT, 10), 0, at(MON + timedelta(days=7), 8)),
        (at(FRI, 16), 0, at(MON + timedelta(days=7), 8)),
        (at(MON, 8), 1, at(MON, 8, 1)),
        (at(MON, 8), 15, at(MON, 8, 15)),
        (at(MON, 8), 479, at(MON, 15, 59)),
        (at(MON, 8), 480, at(MON, 16)),
        (at(MON, 8), 481, at(MON + timedelta(days=1), 8, 1)),
        (at(MON, 15), 60, at(MON, 16)),
        (at(MON, 15), 61, at(MON + timedelta(days=1), 8, 1)),
        (at(MON, 15, 59), 1, at(MON, 16)),
        (at(MON, 15, 59), 2, at(MON + timedelta(days=1), 8, 1)),
        (at(MON, 6), 30, at(MON, 8, 30)),
        (at(MON, 17), 30, at(MON + timedelta(days=1), 8, 30)),
        (at(FRI, 15), 120, at(MON + timedelta(days=7), 9)),
        (at(FRI, 17), 10, at(MON + timedelta(days=7), 8, 10)),
        (at(SAT, 9), 480, at(MON + timedelta(days=7), 16)),
        (at(SUN, 9), 481, at(MON + timedelta(days=8), 8, 1)),
        (at(MON, 8), 480 * 5, at(FRI, 16)),
        (at(MON, 8), 480 * 5 + 1, at(MON + timedelta(days=7), 8, 1)),
        (at(MON, 12), 240, at(MON, 16)),
        (at(MON, 12), 241, at(MON + timedelta(days=1), 8, 1)),
        (at(MON, 9), 4320, at(MON + timedelta(days=11), 9)),
    ],
)
def test_add_business_minutes(start, minutes, expected):
    assert add_business_minutes(start, minutes) == expected


def test_add_business_minutes_ignores_seconds():
    assert add_business_minutes(at(MON, 9, 0, 59, 999), 10) == at(MON, 9, 10)
    assert add_business_minutes(at(MON, 9, 0, 30), 0) == at(MON, 9, 0)
    assert add_business_minutes(at(MON, 7, 59, 59), 0) == at(MON, 8)
    assert add_business_minutes(at(MON, 15, 59, 59), 1) == at(MON, 16)


def test_add_business_minutes_negative():
    with pytest.raises(ValueError):
        add_business_minutes(at(MON, 9), -1)
    with pytest.raises(ValueError):
        add_business_minutes(at(SAT, 9), -5)


def test_add_business_minutes_max_days():
    start = at(MON, 8)
    assert add_business_minutes(start, 126240) == datetime(2027, 1, 6, 16, 0)
    assert add_business_minutes(start, 126000) == datetime(2027, 1, 6, 12, 0)
    with pytest.raises(ValueError):
        add_business_minutes(start, 126241)
    with pytest.raises(ValueError):
        add_business_minutes(start, 10 ** 7)


# ---------------------------------------------------------------- business_minutes_between
@pytest.mark.parametrize(
    "start,end,expected",
    [
        (at(MON, 9), at(MON, 9), 0),
        (at(MON, 8), at(MON, 16), 480),
        (at(MON, 8), at(MON, 8, 1), 1),
        (at(MON, 15, 59), at(MON, 16), 1),
        (at(MON, 7), at(MON, 9), 60),
        (at(MON, 15), at(MON, 18), 60),
        (at(MON, 0), at(MON + timedelta(days=1), 0), 480),
        (at(MON, 16), at(MON + timedelta(days=1), 8), 0),
        (at(MON, 15), at(MON + timedelta(days=1), 9), 120),
        (at(FRI, 15), at(MON + timedelta(days=7), 9), 120),
        (at(SAT, 0), at(SUN, 23, 59), 0),
        (at(MON, 8), at(MON + timedelta(days=7), 8), 2400),
        (at(MON, 7), at(MON, 7, 59), 0),
        (at(MON, 16), at(MON, 23), 0),
        (at(MON, 9), at(MON + timedelta(days=2), 10), 960 + 60),
    ],
)
def test_business_minutes_between(start, end, expected):
    assert business_minutes_between(start, end) == expected


def test_business_minutes_between_ignores_seconds():
    assert business_minutes_between(at(MON, 9, 0, 59), at(MON, 9, 1, 0)) == 1
    assert business_minutes_between(at(MON, 9, 0, 1), at(MON, 9, 0, 59)) == 0
    assert business_minutes_between(at(MON, 9, 0, 59), at(MON, 9, 0, 1)) == 0


def test_business_minutes_between_rejects_backwards():
    with pytest.raises(ValueError):
        business_minutes_between(at(MON, 10), at(MON, 9, 59))
    with pytest.raises(ValueError):
        business_minutes_between(at(MON + timedelta(days=1), 9), at(MON, 9))


def test_business_minutes_between_max_days():
    start = at(MON, 8)
    assert business_minutes_between(start, datetime(2027, 1, 6, 16, 0)) == 126240
    assert business_minutes_between(start, datetime(2027, 1, 6, 23, 59)) == 126240
    with pytest.raises(ValueError):
        business_minutes_between(start, datetime(2027, 1, 7, 0, 0))
    with pytest.raises(ValueError):
        business_minutes_between(start, datetime(2027, 1, 7, 9, 0))


@pytest.mark.parametrize(
    "start", [at(MON, 8), at(MON, 7, 30), at(MON, 15, 30), at(FRI, 14, 5), at(SAT, 11), at(MON, 16, 45)]
)
@pytest.mark.parametrize("minutes", [0, 1, 59, 60, 479, 480, 481, 1000, 2400, 2401, 9999])
def test_round_trip(start, minutes):
    assert business_minutes_between(start, add_business_minutes(start, minutes)) == minutes


# ---------------------------------------------------------------- escalation_tier
@pytest.mark.parametrize(
    "priority,breached,reopens,expected",
    [
        ("P1", False, 0, 1), ("P2", False, 0, 1), ("P3", False, 0, 0), ("P4", False, 0, 0),
        ("P1", True, 0, 3), ("P2", True, 0, 2), ("P3", True, 0, 1), ("P4", True, 0, 1),
        ("P1", False, 1, 1), ("P2", False, 1, 1), ("P3", False, 1, 0), ("P4", False, 1, 0),
        ("P1", False, 2, 2), ("P2", False, 2, 2), ("P3", False, 2, 1), ("P4", False, 2, 1),
        ("P1", False, 5, 2), ("P3", False, 3, 1),
        ("P1", True, 2, 3), ("P2", True, 2, 3), ("P3", True, 2, 2), ("P4", True, 2, 2),
        ("P2", True, 1, 2), ("P3", True, 1, 1), ("P1", True, 1, 3), ("P1", True, 9, 3),
    ],
)
def test_escalation_tier(priority, breached, reopens, expected):
    assert escalation_tier(priority, breached, reopens) == expected


@pytest.mark.parametrize("priority,reopens", [("P5", 0), ("p1", 0), ("", 0), (" P1", 0), ("P1", -1), ("P3", -1)])
def test_escalation_tier_rejects(priority, reopens):
    with pytest.raises(ValueError):
        escalation_tier(priority, False, reopens)


# ---------------------------------------------------------------- parse_duration
@pytest.mark.parametrize(
    "text,expected",
    [
        ("90m", 90), ("4h", 240), ("1h30m", 90), ("2d", 2880), ("1d4h", 1680), ("1d0h5m", 1445),
        ("1h59m", 119), ("60m", 60), ("0h60m", 60), ("1m", 1), ("59m", 59), ("1h", 60), ("1d", 1440),
        ("  90m  ", 90), ("\t2d\n", 2880), ("1d1m", 1441), ("1d59m", 1499), ("0d1m", 1), ("0d0h1m", 1),
        ("120m", 120), ("25h", 1500), ("0d2h", 120), ("10d", 14400), ("1d2h3m", 1563), ("0h1m", 1),
    ],
)
def test_parse_duration(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "", "   ", "0m", "0h", "0d", "0d0h0m", "1.5h", "30m1h", "-5m", "1 h", "1h60m", "1d60m", "0d1h60m",
        "1H", "1M", "1D", "5", "h", "m", "1h 30m", "1s", "1m1m", "1h1h", "1d1d", "abc", "1h-5m", "+5m",
    ],
)
def test_parse_duration_rejects(text):
    with pytest.raises(ValueError):
        parse_duration(text)
