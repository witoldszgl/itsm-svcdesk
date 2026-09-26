---
feature: "GET /dora/ticket-events: the lifecycle stream of every ticket, with its own tests"
predicted_minutes: 20
predicted_at: "2026-09-26T13:08:00Z"
feature_path: src/svcdesk/ticket_events.py
---
<!-- ai-generated: 50% - Claude Code proposed the feature and the format; the prediction is agreed by the student -->

# Prediction

The feature is `GET /dora/ticket-events` (METRIC-SPEC.md section 7): one event per lifecycle instant the
service actually holds, for every ticket, ordered by `at` then `ticket_id`, with the ticket's state at that
instant. It lives in `src/svcdesk/ticket_events.py`, wired into the existing FastAPI app, with tests in the
own suite.

Predicted: 20 minutes of wall-clock time from the first line of the feature until it passes the own tests and
check L2-CORE-2.12, working with Claude Code as in Lab 1. The estimate assumes the ticket model from Lab 1 is
reused unchanged and that the only real decision is the tie order of events at the same instant.
