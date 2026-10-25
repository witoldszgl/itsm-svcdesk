---
lab4_postmortem:
  ticket: "50ceffde-fa49-40b3-b4ca-957734d74bf7"
  detecting_alert: ShopCheckoutErrors
  onset: 2026-10-12T06:36:23Z
  detection: 2026-10-12T06:39:19Z
  acknowledgement: 2026-10-12T06:40:09Z
  recovery: 2026-10-12T06:44:19Z
  mttd_seconds: 176
  mtta_seconds: 50
  mttr_seconds: 476
  identified_flags: [paymentFailure, loadGeneratorFloodHomepage, recommendationCacheFailure]
---
<!-- ai-generated: 80% - Claude Code drafted the text from queries it ran on the served recording lab4-rec-4; the student reviewed it -->

# Postmortem: one order in four failed at payment while the shop's front page was flooded

## Date

The incident happened on Monday 12 October 2026, between 06:36 and 06:45 UTC (recording lab4-rec-4). This
postmortem was written on 25 October 2026 from the recording's Prometheus snapshot and its ticket.

## Authors

witoldszgl (GitHub login), writing as the on-call engineer on the recorded path of Laboratory 4. The page,
the ticket and the rollback in the recording were done by the course's on-call; the analysis and this text are mine.

## Status

Complete for the incident: service was restored at 06:44:19Z and the ticket was acknowledged. The problem record
below stays open, and the action items are in progress.

## Summary

For about eight minutes, from 06:36:23Z to 06:44:19Z, roughly one order in four failed at the payment step, and the
shop's front page received about fifteen times its normal traffic. Recommendations also became several times slower.
The checkout error page fired 176 s after the onset, and service recovered 476 s after the onset, after three
feature flags were switched off.

## Impact

Customers trying to pay: 8 of the 65 orders placed between 06:36:30Z and 06:46:30Z failed (12 % over the whole
window; 31 % at the worst 5-minute window ending 06:42Z), measured with
`sum(increase(traces_span_metrics_calls_total{service_name="checkout", span_kind="SPAN_KIND_SERVER", status_code="STATUS_CODE_ERROR"}[10m]))`
against the same query without `status_code`, at 06:46:30Z. Every failed order was a failed `charge` in the payment
service: 9.6 failed charges and 9.6 failed PlaceOrder calls in the 5 minutes to 06:42Z.

Front page: the frontend served 19,022 requests in the 5 minutes to 06:42Z against 1,142 on the healthy shop
(`sum(increase(traces_span_metrics_calls_total{service_name="frontend", span_kind="SPAN_KIND_SERVER"}[5m]))` at
06:42:00Z and 06:31:23Z), a 16x surge; frontend latency did not degrade (p99 stayed under 50 ms).

Recommendations: the recommendation service's p99 rose from about 6-8 ms to 47 ms
(`histogram_quantile(0.99, sum by (le) (rate(traces_span_metrics_duration_milliseconds_bucket{service_name="recommendation", span_kind="SPAN_KIND_SERVER"}[5m])))`,
maximum over 06:35-06:50Z). Users would hardly notice 47 ms, but it is a growing-resource symptom that would have
become worse had the incident lasted longer.

## Root Causes

Three feature flags were switched on together at 06:36:23Z, one from each class of the fault pool:

- `paymentFailure` made the payment service fail a share of its `charge` operations. Checkout calls payment
  synchronously and has no retry or fallback, so each failed charge became a failed order. Payment and checkout
  show identical error counts, and no other service had server errors.
- `loadGeneratorFloodHomepage` made the load generator flood the front page: frontend and frontend-proxy traffic rose
  about 15x from 06:38 and fell back after 06:46. The shop absorbed it, which is why no latency alert fired.
- `recommendationCacheFailure` made the recommendation service's cache stop working, so its latency grew (p99 from
  under 8 ms to 47 ms in the window ending 06:44). It is identified from that latency step alone, which is the
  weakest of the three conclusions: there is no flag state in the recording to confirm it.

Underneath the flags: a configuration change can switch failure modes on in production with no review, no
announcement and no metric naming it.

## Trigger

The trigger was the simultaneous activation of the three flags at the onset, 06:36:23Z (the fault injector was armed at
06:32:05Z, after a baseline that began at 06:22:03Z). Nothing was deployed; the change was in flag configuration only.

## Resolution

The three flags were switched off through the injector, the last at about 06:43:18Z (the last sample of the
injector's active-fault indicator). Payment errors stopped, and the detecting alert's 5-minute window then slid past the
fault: ShopCheckoutErrors resolved at 06:44:19Z, which is the recovery. Frontend traffic returned to its baseline by
06:48 and recommendation latency by 06:50. The workaround (flags off) restored service; the underlying problem is
in the problem record.

## Detection

ShopCheckoutErrors (P1: more than 5 % of checkout's server spans failed over 5 minutes, `for: 1m`) began firing at
06:39:19Z, 176 s after the onset (MTTD). Most of that is structural: span metrics arrive once a minute, the 5-minute
rate needs two or three failed minutes to cross 5 %, and `for: 1m` adds a minute. The pager received the page within
a minute (`itsm_pager_notifications_total{receiver="pager", status="firing"}` rose at 06:40). The P2 ShopServiceErrors
alerts on checkout and payment followed at 06:41. Nothing alerted on the traffic flood or on the recommendation
latency: these were found only by looking at the dashboards. Without the page, customers would have reported failed
payments first.

## Action Items

| Action Item | Type | Owner | Bug |
|---|---|---|---|
| Add a P3 alert on frontend request rate above 5x its 1-hour average, so a traffic flood is visible in chat | prevent | on-call team (witoldszgl) | ITSM-41 |
| Add a P3 alert on recommendation p99 above 3x its 1-hour average, so a resource leak is seen before users feel it | prevent | on-call team (witoldszgl) | ITSM-42 |
| Expose the state of every feature flag as a metric and annotate Grafana when one changes, so "what changed?" is one query | mitigate | platform team | ITSM-43 |
| Require a review and a chat announcement for every production flag change, with an owner for each failure-mode flag | process | change advisory board | ITSM-44 |
| Lower the error alert's `for:` from 1m to 30s and test whether it stays quiet on the baseline, to cut MTTD | mitigate | on-call team (witoldszgl) | ITSM-45 |

## Lessons Learned

### What went well

The symptom page on checkout errors fired on the first fault class, reached the pager within a minute, and the ticket
was acknowledged 50 s later. Payment and checkout error counts matched exactly, which made the failing dependency
obvious in two queries.

### What went wrong

Two of the three faults raised no alert at all; they were found only by comparing dashboards with the baseline.
Nothing in the metrics names a flag, so identifying the cause meant inferring it from the shape of symptoms. The AI
investigator queried two of its five instants at a date two years outside the window, and then concluded that
checkout had no errors (H5, hallucinated).

### Where we got lucky

The payment failure rate was moderate, so three orders in four still went through. The flood hit only the front page,
which had enough headroom. The recommendation slowdown was caught at 47 ms, long before a memory exhaustion would have
restarted the service.

## Timeline

All times UTC, 12 October 2026.

- 06:22:03 - the fault injector starts; healthy baseline begins.
- 06:32:05 - the injector is armed (unknown to the on-call: the onset comes 2 to 6 minutes later).
- 06:35:00 - last quiet minute: checkout errors 0, frontend about 3.8 requests/s, recommendation p99 under 8 ms.
- 06:36:23 - onset: the three flags switch on.
- 06:38 - frontend traffic starts climbing (9.8/s on the 5-minute window, 63/s by 06:42).
- 06:39:19 - detection: ShopCheckoutErrors (P1) fires; checkout error ratio 13 %.
- 06:39:44 - P1 ticket 50ceffde-fa49-40b3-b4ca-957734d74bf7 created in svcdesk.
- 06:40 - the page reaches the pager.
- 06:40:09 - acknowledgement of the ticket.
- 06:41 - ShopServiceErrors (P2) fires for checkout and payment; muted in chat while the P1 fires.
- 06:42 - worst point: 31 % of orders failing, payment `charge` errors 0.032/s, frontend 63 requests/s.
- 06:43:18 - the last flag is switched off.
- 06:44 - recommendation p99 visible at 46 ms in the 5-minute window (it peaks at 47 ms by 06:46).
- 06:44:19 - recovery: ShopCheckoutErrors resolves.
- 06:50 - all three symptoms are back at baseline.

The AI investigator (ai-rca-eval.json) said payment's charge was failing and causing checkout's failures. H1 was
accepted on the query
`sum(rate(traces_span_metrics_calls_total{service_name="payment", span_name="charge", status_code="STATUS_CODE_ERROR"}[5m])) > 0.01`
(true at 06:42:00Z, false at 06:31:23Z). H3 was accepted on the same query joined with checkout's PlaceOrder errors.
H5, "no errors in checkout", was rejected by the traffic-unless-errors query; it did not enter the decisions. The
agent did not see the flood or the recommendation slowdown.

## Supporting information

`itsmlab incident 4` printed the run c1daa7d0f4acf990 and the four instants and three durations above. The snapshot
is `incident/tsdb-snapshot.tar.gz`, served on port 19090 for the analysis. The ticket is `incident/ticket.json`. The
alerting rules I would have used are in `prometheus/demo-alerts.yml`; ShopCheckoutErrors evaluated on the recording is
quiet before the onset and above 5 % from 06:39 to 06:44. The AI ledger is `ai-rca-eval.json`, scoring
`ai-rca/transcript.md` (recorded investigator, qwen3:4b-instruct): three correct, one partially correct and one
hallucinated hypothesis.

## Problem record

- Incident record: P1 ticket 50ceffde-fa49-40b3-b4ca-957734d74bf7, acknowledged 06:40:09Z; closes when service is restored.
- Root cause: three failure-mode feature flags (paymentFailure, loadGeneratorFloodHomepage, recommendationCacheFailure) can be switched on in production with no review, no announcement and no metric that shows their state.
- Known error: checkout has no fallback when payment's charge fails, so every failed charge is a lost order; flag changes are invisible to monitoring until their symptoms cross an alert threshold.
- Workaround: switch the failing flags off (POST /flags/{key}/off on the injector), then confirm that payment charge errors, frontend request rate and recommendation p99 return to their baseline.
