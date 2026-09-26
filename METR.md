---
feature: "GET /dora/ticket-events: the lifecycle stream of every ticket, with its own tests"
predicted_minutes: 20
actual_minutes: 1.28
started_at: "2026-09-26T13:14:10Z"
finished_at: "2026-09-26T13:15:27Z"
ratio: 0.06
---
<!-- ai-generated: 80% - drafted by Claude Code from the recorded timestamps; the student reviewed it -->

# METR n=1 replication

Prediction (PREDICTION.md, receipted in issue #121 at 2026-09-26T13:13:10Z): 20 minutes for
`GET /dora/ticket-events` with its tests, working with Claude Code.

Measured: the first line of `src/svcdesk/ticket_events.py` was written at 13:14:10Z, right after the receipt.
The feature passed the own test suite (46 tests, run in the compose `tests` profile) and check L2-CORE-2.12 of
`itsmlab verify 2` at 13:15:27Z. Actual time 77 seconds, 1.28 minutes.

**actual/predicted = 1.28 / 20 = 0.06**

What this number does and does not say. The ratio is a large speed-up, and it is an honest measurement of the
interval the prediction named, but it should not be read as "AI makes this 16 times faster". The prediction
was made as if a person would write the code with an assistant helping, while in fact the agent wrote the
module, the route and the tests in one pass and ran the checker itself. The minutes of reading METRIC-SPEC.md
section 7 and designing the tie order had already been spent before the receipt, and the time the student
then spent reading and checking the code afterwards is outside the measured interval. That is the verification
tax the DORA reports describe: time saved writing is re-spent reviewing. METR's own study measured experienced
developers on familiar, much larger tasks and found the opposite direction, so an n=1 on a 30-line endpoint
says more about the size of the task and the shape of the prediction than about AI productivity in general.
