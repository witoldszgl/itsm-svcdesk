---
lab3_first_draft:
  source: ai
  tool: "Claude Opus 5.5 (claude-opus-5-5) in Claude Code CLI, 11 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 2, 5]
  verdict: refuted
  evidence: {p99_seconds: 0.1097, bucket: [0.1, 0.15], relative_width: 0.456}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: 0.1097, bucket: [0.04, 0.5], relative_width: 4.193}
---
<!-- ai-generated: 70% - the Prompt and Answer are the assistant exchange verbatim; the verdicts were drafted by Claude Code from my load 3 run and checked by me -->

# The assistant's first draft, and two verdicts

## Prompt

I am adding an endpoint GET /kb/search to a Python FastAPI service called svcdesk. For every request it calls an
upstream knowledge-base index service over HTTP (GET /search?q=...) and returns its hits; when the upstream fails
it answers 502. I want to instrument it with a Prometheus histogram http_server_request_duration_seconds (labels
http_request_method, http_route, http_response_status_code). Propose the histogram bucket boundaries, in seconds,
and one Prometheus alerting rule for this endpoint. I have not measured its latency yet.

## Answer

Since you have not measured yet, start from a ladder that is dense in the range where an HTTP endpoint backed by
one upstream call usually lives (a few ms to a few hundred ms), and still has a few coarse buckets for the tail and
for timeouts:

```python
KB_SEARCH_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 2, 5)
```

That is 14 finite boundaries (plus +Inf), which keeps the series count low (16 series per label combination
including _sum and _count). It is close to the prometheus_client default but adds 0.15, 0.2 and 0.3, where a
search backed by an index typically has its p95/p99, and drops 2.5/7.5/10 in favour of 2 and 5 to see your
upstream timeout.

Once you have real traffic, look at the p50/p99 and move boundaries so that the p99 falls into a narrow bucket;
the SLO threshold you pick (for example 300 ms) should be one of the boundaries.

An alert rule on the error ratio of the endpoint (5xx share over 5 minutes above 5 %):

```yaml
groups:
  - name: svcdesk-kb-search
    rules:
      - alert: KbSearchHighErrorRate
        expr: |
          sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search", http_response_status_code=~"5.."}[5m]))
            /
          sum(rate(http_server_request_duration_seconds_count{http_route="/kb/search"}[5m]))
            > 0.05
        for: 5m
        labels:
          severity: page
        annotations:
          summary: "More than 5% of /kb/search requests fail (upstream kb-index unavailable?)"
```

If you define an SLO later, replace the fixed 5 % with burn-rate alerts (for example 14.4x over 1h and 6x over
6h, each combined with a short window) so the alert is tied to the error budget rather than to a guessed number.

## Verdict on the draft ladder

The measurement: `itsmlab load 3` for my login `witoldszgl` (60 s open-loop at 40 requests/s, latency-corrected)
gave p50 16.4 ms, p95 33.1 ms and **p99 = 0.1097 s** (q_kb 0.1057 s). The draft ladder puts it in the bucket
**(0.1, 0.15]**: 0.05 s wide, which is 0.05 / 0.1097 = **45.6 %** of the p99, more than twice the 20 % that M-11
allows. The result does not depend on the few per cent the grader's q will differ by: 0.95q = 0.104 s and
1.05q = 0.115 s fall into the same bucket, with the same width of about 46 %.

What `histogram_quantile(0.99, ...)` could report from that bucket: it assumes the requests are spread evenly
between 0.1 and 0.15 s and interpolates, so the dashboard's p99 could be anything from just above 100 ms to 150 ms,
depending only on how many requests land below 0.1 s. My real slow mode sits between about 85 and 140 ms and is
not uniform inside that bucket, so a p99 of "130 ms" or "105 ms" would look equally believable and nothing would
warn me. The assistant's guess that the p99 of an index-backed search lives "at 0.15, 0.2, 0.3" was in the right
area, but its steps there (50 to 100 ms) are far too coarse for a p99 near 110 ms.

Verdict: **refuted** - the draft ladder does not resolve my p99 (45.6 % > 20 %).

## The draft alert rule

The assistant proposed one single-window rule: the 5xx share of `/kb/search` over 5 minutes above 5 %, `for: 5m`,
`severity: page`. For my SLO (availability 99 %, 28 days) a 5 % error share is a burn rate of 5: it would page a
person at night for a burn that spends the budget in about 5.6 days - a chat-level problem - and with only a 5-minute
window it would also page on a short blip of a few bad minutes that hardly touches the budget, and it has no `job`
filter and no `service`/`slo` labels, and `page` is not one of the P1/P2/P3 severities Lab 4 routes on.

What I kept: the shape of the expression - 5xx count rate on `http_route="/kb/search"` divided by the count rate of
all its requests, with `sum` so it is one series - and the advice from the end of the answer: burn rates 14.4 over
1h and 6 over 6h, each combined with a short window. In `prometheus/alerts.yml` these became
`KbSearchErrorsBurnFast` (14.4x, 1h and 5m, P1 page) and `KbSearchErrorsBurnSlow` (6x, 6h and 30m, P2 chat), with
thresholds written as `14.4 * (1 - 0.99)` and `6 * (1 - 0.99)`, plus a latency alert the draft did not have.

## Verdict on the instructor's flawed ladder

The flawed ladder spends twelve of its fourteen boundaries below 40 ms (0.001 to 0.04), where my median (16 ms) and
my p95 (33 ms) live, and then jumps straight to 0.5 and 2.5. My p99 of 0.1097 s falls into **(0.04, 0.5]**:
0.46 s wide, 0.46 / 0.1097 = **419.3 %** of the p99. `histogram_quantile` could report anything from 40 ms to
500 ms for it - in practice, with 1 % of requests above the p99 spread over a bucket ten times wider than the slow
mode, a number of a few hundred milliseconds that has nothing to do with the real 110 ms. The whole slow mode of my
`kb-index` (about 85 to 140 ms), which is exactly what the p99 is about, is invisible inside one bucket.

Verdict: **refuted** - 419.3 % is twenty times what M-11 allows.
