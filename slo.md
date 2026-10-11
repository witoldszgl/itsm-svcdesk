---
lab3_slo:
  service: svcdesk
  route: /kb/search
  window: 28d
  slis:
    availability:
      objective: 0.99
      good: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search", http_response_status_code!~"5.."}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
    latency:
      objective: 0.99
      threshold_seconds: 0.2
      good: 'sum(rate(http_server_request_duration_seconds_bucket{job="svcdesk", http_route="/kb/search", le="0.2"}[5m]))'
      valid: 'sum(rate(http_server_request_duration_seconds_count{job="svcdesk", http_route="/kb/search"}[5m]))'
      error_budget: {fraction: 0.01, minutes: 403.2}
  alerts:
    - {alert: KbSearchErrorsBurnFast, sli: availability, burn_rate: 14.4, long_window: 1h, short_window: 5m}
    - {alert: KbSearchErrorsBurnSlow, sli: availability, burn_rate: 6, long_window: 6h, short_window: 30m}
    - {alert: KbSearchLatencyBurnFast, sli: latency, burn_rate: 14.4, long_window: 1h, short_window: 5m}
---
<!-- ai-generated: 70% - Claude Code drafted the numbers and the prose from my load 3 measurement; I checked the arithmetic and the choices -->

# SLO for `GET /kb/search`

What I measured with `itsmlab load 3` for my login (`witoldszgl`), 60 s open-loop at 40 requests per second:
p50 16.4 ms, p90 27.4 ms, p95 33.1 ms, **p99 (q) 109.7 ms**, p99.9 128.8 ms, p99.99 139.8 ms; q_kb (kb-index
measured directly) 105.7 ms; 2,390 answers 200 and 10 answers 502 (0.42 %). The distribution has two modes: almost
everything is between 10 and 45 ms, and about 3 % of the searches fall into a narrow slow mode between roughly
85 and 140 ms. Nothing came back slower than about 0.14 s.

The window is 28 days (40,320 minutes): four whole weeks, so every window holds the same number of weekends and
Mondays, and an error budget of 1 % is 403.2 minutes.

## Availability

SLI: the share of `/kb/search` answers that are not 5xx, out of all `/kb/search` answers (400/422 refusals of a bad
`q` count as good: the service did what it should). Objective **0.99**, error budget 1 % = 403.2 minutes in 28 days.

Why not stricter: the 502s are not my bugs, they are `kb-index`'s own 503s passed on (M-02 forbids retrying them).
Its baseline failure rate in my profile is about 0.4 %, so with 99 % the dependency alone already burns about 40 % of
the budget (burn rate 0.4) on a normal day. At 99.5 % the same baseline would be a burn rate of 0.84: the budget
would be almost gone without any incident, and the Lab 6 canary gate would roll back honest releases just because
of the dependency's noise. At 99.9 % the objective would be broken by `kb-index` alone, every day. 99 % leaves
about 60 % of the budget for my own mistakes and for real incidents of `kb-index`.

## Latency

SLI: the share of `/kb/search` answers that took at most **0.2 s**, out of all `/kb/search` answers, counted by
the bucket `le="0.2"` (0.2 is one of my boundaries, so the SLI counts requests instead of interpolating them).
Objective **0.99**, error budget 1 % = 403.2 minutes.

Why 0.2 s: my p99 is 0.110 s and the whole slow mode of `kb-index` ends at about 0.14 s. A threshold inside the
slow mode (for example 0.1 s) would make the ~3 % of searches that `kb-index` serves slowly *by design* count as
bad; with a 1 % budget that is a permanent burn rate of about 2 to 3, an SLO broken every month by the normal
behaviour of the dependency. 0.2 s is above the slow mode with a margin (about 45 % above the slowest searches I
saw), so normally almost nothing is bad and the budget is spent only when something really changes: `kb-index`
gets slower (its latency multiplied, as `/admin/degrade` does), svcdesk queues requests, or the network adds
delay. 0.2 s is also far below 1 s, which Lab 6 requires, and still a fast answer for a person typing a search.

Why 0.99 and not 0.999: 0.2 s is only 1.8 x my p99, and another machine (the grader, Lab 6's canary) can be slower
by tens of per cent; with 99.9 % a few hundred slow requests in a month would already break it.

## Alerts

| alert | SLI | burn rate | long / short window | budget spent when it fires | severity: page or chat |
|---|---|---|---|---|---|
| KbSearchErrorsBurnFast | availability | 14.4 | 1h / 5m | 14.4 x 1h / 672h = 2.1 % in one hour; whole budget gone in under 2 days | P1, page |
| KbSearchErrorsBurnSlow | availability | 6 | 6h / 30m | 6 x 6h / 672h = 5.4 % in six hours; budget gone in under 5 days | P2, chat |
| KbSearchLatencyBurnFast | latency | 14.4 | 1h / 5m | 2.1 % of the latency budget in one hour | P2, chat |

Every alert is multiwindow: the long window says the burn is real and big enough, the short window says it is
still happening, so the alert stops a few minutes after the burn stops instead of firing for another half an hour.
None has a `for:`; the two windows already filter out one-off spikes.

**KbSearchErrorsBurnFast pages (P1).** At 14.4x more than 14 % of all searches fail - for users the search is
visibly broken, and if nobody acts the whole month's budget is gone in less than two days. Waking a person at
night costs that person real sleep, but waiting until morning (say 8 hours) would spend about 17 % of the monthly
budget and leave every night user with a broken search. Because the threshold is so high, this alert does not fire
on the 0.4 % baseline (it would need 36 times more errors), so a page is rare and almost always real.

**KbSearchErrorsBurnSlow goes to chat (P2).** At 6x (6 % of searches failing for hours) the budget lasts almost five
days. That is a problem to fix today, during working hours, not at 3 a.m.: waiting until morning costs a few per
cent of the budget, while a night page for it would teach people to ignore pages.

**KbSearchLatencyBurnFast goes to chat (P2).** Searches slower than 0.2 s are an annoyance, not an outage: the
user still gets the answer. Even at 14.4x the user experience is degraded, not broken, so it is reported to the
team's chat; if it lasts, the error alerts usually follow (timeouts become 502s).

## Buckets

My ladder has 29 finite boundaries (limit 30):
0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.075, **0.09, 0.095, 0.1, 0.105, 0.11, 0.115, 0.12,
0.125, 0.13, 0.14, 0.15, 0.175, 0.2**, 0.25, 0.3, 0.5, 1, 2, 5.

My measured q = 0.1097 s falls in the bucket (0.105, 0.11], 5 ms wide: 4.6 % of q, far below the 20 % that M-11
allows, so `histogram_quantile` can be off by at most 5 ms there. The grader measures on another machine with other
random draws, so I did not design for one point: every bucket from 0.075 s up to 0.25 s is at most 20 % as wide as
its lower end, which resolves any q from about 0.075 to 0.25 s - from about -32 % to +128 % around my q, much more
than the required +-10 %. Inside the most likely band (0.09 to 0.13 s, about +-18 %) the step is 5 ms, so the
error of the interpolated p99 there is at most 5 %.

The rest of the boundaries: 0.005 to 0.06 cover the fast mode where the median lives (p50 16 ms, p95 33 ms), coarse
enough not to waste boundaries but good enough for a p50/p95 panel; 0.2 is the latency SLI's threshold; 0.25 to 5
cover the tail and degradations (`latency_factor` up to 20 x and the upstream timeout of 5 s), so a slow incident
still lands in a finite bucket and the p99 panel shows a number instead of the last boundary.
