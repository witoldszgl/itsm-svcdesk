---
lab3_first_draft:
  source: ai
  tool: "Claude Opus 5.5 (claude-opus-5-5) in Claude Code CLI, 11 October 2026"
  ladder: [0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.15, 0.2, 0.3, 0.5, 0.75, 1, 2, 5]
  verdict: TODO
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
lab3_flawed_ladder:
  verdict: refuted
  evidence: {p99_seconds: TODO, bucket: [TODO, TODO], relative_width: TODO}
---
<!-- ai-generated: TODO -->

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

TODO

## The draft alert rule

TODO

## Verdict on the instructor's flawed ladder

TODO
