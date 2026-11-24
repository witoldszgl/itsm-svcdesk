---
lab6_blast_radius:
  postmortem_action: {bug: ITSM-43, commit: b353d58ed7186797b389698d98d1d77532e6533f}
---
<!-- ai-generated: 70% - Claude Code drafted the prose from my practice runs (changes/) and the run logs; I checked every number against run.json and the timelines -->

# Blast radius

## Gate

**Baseline: my own Lab 3 SLO** (`baselines: {lab3: student}`): availability 99 % and latency 99 % within 0.2 s, both
over 28 days, so each error budget is 1 %. My `kb-index` profile (`witoldszgl`) puts the honest floor well below
both: over the warm-ups of the two `verify 6` runs the stable build answered 0.17 % and 0.46 % of searches with a
5xx, and 0.00 % slower than 0.2 s (its slow mode is 85-140 ms, below the threshold). A burn rate of 1 would put the
availability threshold at 1 %, only about twice the 0.46 % floor, so I chose **`max_burn_rate: 10` on both SLIs**:
a step fails when the canary's 5xx share exceeds 10 x (1 - 0.99) = **10 %**, or its share slower than 0.2 s exceeds
**10 %**. That is 20 times the availability floor and three times below the 30 % every errors or slow candidate
reaches (R-30); R-09 holds (10 >= 1, 10 % <= 20 %).

**Not the first 5xx.** A share alone is noisy on a handful of searches, so a share above its threshold fails only
with at least **`min_failures: 5`** bad searches behind it. Five bad and more than 10 % means at most 49 searches,
so a false rollback of the honest canary needs 5 `kb-index` failures within its first 49 searches: Poisson with
lambda = 49 x 0.0046 = 0.23 gives P(X >= 5) of about 4 x 10^-6 per phase. After 50 searches the honest floor can no
longer reach 10 % at all (it would need 5 failures in 50 = 10 %, i.e. 22 times its rate). A 30 % candidate, on the
other side, has its 5 bad searches after about 17 searches on average: the first look with data catches it.

**Where the searches come from.** The candidate's first searches are not users': for at least 10 s and 200
searches (`shadow: {tool: nginx, min_requests: 200}`) nginx mirrors every user search to it while every user still
gets 2.0.0 (Caddy weights 0/0/100). At 40 mirrored searches a second the shadow sees 300-440 searches - more than any
weighted step - so the gate judges on far more evidence than a 10 % step would give it in a minute. Then two weighted
steps, 10 % for 20 s (about 80 searches) and 50 % for 15 s (about 300), each needing `min_requests: 60`, the 10 %
step being what R-22 checks. The gate looks every **2 s** (`interval`) at a Prometheus that scrapes every 2 s, and
every number of one look is evaluated at the same `time` one second in the past, from raw counters of the fresh
canary container - no `[5m]` window at all: the share is the phase's own (counter now minus counter at the phase's
start) and the whole run's, never older than the candidate.

**No data.** Every query ends in `or vector(0)`: a canary nobody has called has no series, and that is 0 searches,
not a pass - with 0 searches nothing can pass `min_requests`. The hang is judged by a separate rule, the **stall**:
when the canary's search counter has not moved for `stall_after: 10s` while the stable build's counter says the
canary should have received at least 20 searches (all of them in the shadow, w/(100-w) of the stable's in a step),
the gate fails the phase - a canary whose searches stop arriving is a canary that stopped answering, whatever
`/health` says. Prometheus not answering for 5 looks in a row is also a failure (no evidence is not a pass), and the
script's own deadline (165 s, 12 s kept back for the rollback and the record) rolls back anything undecided.

## Blast radius

Measured in the four practice runs saved in `changes/` (seed `practice`, `verify 6 --save`, 24 November 2026), with
R = 40 searches a second. During the shadow the users' weight on the candidate is **w = 0**: whatever the candidate
does to the mirrored copies, nobody waits for its answer, so the formula predicts zero for every behaviour the
shadow catches.

| run | behaviour | outcome | measured blast radius | c | w | q | D (s) | predicted |
|---|---|---|---|---|---|---|---|---|
| `20261124T081452Z-rc.1` | hang (stopped after 40 searches) | rolled back after 22 s, in the shadow | 0 | 0 | 0 | 1 | 13 | 0 |
| `20261124T081611Z-rc.2` | honest | promoted after 55 s | 1 (1 timeout; 2 candidate 5xx against a floor of 3) | - | 0.1, 0.5 | 0.0046 | - | about 0 |
| `20261124T081802Z-rc.3` | slow (42 of 118 slower than 0.2 s) | rolled back after 12 s, in the shadow | 0 | 5 | 0 | 0.36 | 6 | 0 |
| `20261124T081910Z-rc.4` | errors (20 of 66 answered 5xx) | rolled back after 9 s, in the shadow | 0 | 5 | 0 | 0.30 | 4 | 0 |

The same seed in my first `verify 6 --save` gave 0, 0, 1 and 0, and seed `p07` gave 0 on all four (errors in rc.1,
hang in rc.2, honest in rc.3, slow in rc.4), so the numbers are not one lucky assignment. The honest run's single
headerless failure is one search that timed out while the weights were reloaded or `kb-index` was slow; its 2
candidate 5xx are `kb-index`'s ordinary failures, below the 3 the stable build's share predicts for its 985 answers.

**What the shadow buys.** Without it, the first exposure would be the 10 % step, and the hang dominates: it answers
up to k = 120 searches (30 s at 4 a second) and then holds every canary search. c = 0 (nothing fails that the gate
can count), D = 10 s of stall + up to 2 s for the scrape + up to 2 s for the next look, about 14 s:
40 x 0.1 x 1 x 14 = **56** failed searches. An errors candidate at q = 0.6: 5 + 40 x 0.1 x 0.6 x 5 = **17**; a slow one
at q = 0.3, whose searches are observed 1.2-2 s late: 5 + 40 x 0.1 x 0.3 x 7 = **13**. All under 150 even without the
mirror, which is why the weighted steps are kept as a second line, not removed. What would push a run over the
ceiling: a first step at 25 % or more for the hang (40 x 0.25 x 14 = 140, a coin toss), a window of minutes instead of
raw counters, or a stall rule longer than about 30 s. With the shadow, the bad candidate's failures land on copies
nobody waits for, and the only cost left is the honest floor every build shares.

## Change classification

My records declare a **standard** change, with **risk: low**. The procedure is identical for every 2.x candidate
and is the thing pre-authorised (the approval named in the record, `SCM-SVCDESK-CANARY`): a candidate the script
has never seen goes first into a shadow where it can answer nobody, then to 10 % and 50 %, and every step can be
undone in one admin-API call while 2.0.0 keeps running. The evidence for "well understood and low risk" is the
practice runs: on two seeds, eight releases, every bad candidate rolled back with a blast radius of 0 and every
honest one promoted with a blast radius of 0 or 1. It would become a **normal** change - a person approving each
release before it starts - if the candidate touched what the mirror cannot exercise safely (a write path: the
shadow would duplicate writes; a schema change), if the plan lost the shadow or got a first step above 20 %, or after
the first time the gate promoted something that later burned the SLO. An emergency change I would run with the same
gate but shorter steps, accepting a larger D, never without the gate.

The autonomy classes, as each record lists them: **starting the candidate in `svcdesk-canary` is approve-then-act** -
it is the act the pre-authorisation covers, and it changes nothing users see (weight 0). **Reading Prometheus is
read-only**: the build on each track, then the canary's searches, 5xx and `le="0.2"` bucket at every look, and the
release state at the end. **Every weight change is closed-loop** - the shadow on, the 10 % and 50 % steps, the
promotion and the rollback - because the script decides from its own readings, with nobody asked: during a run there
is nobody to ask (stdin is closed), and a rollback that waited for a person would turn a 0 blast radius into
minutes of failures. The asymmetry is deliberate: a rollback only returns to the build that already served
everything, so it can safely be closed-loop; a promotion is closed-loop only because the shadow and two steps came
before it. In a real service I would want a person to approve the standard change model itself and every change to
`deploy.config.yaml` (thresholds, steps, the shadow) - the procedure, not each run.

## Postmortem action

**The action item.** My Lab 4 postmortem (`postmortem.md`, accepted with `lab4/v1`) found that three failure-mode
flags could be switched on in production "with no review, no announcement and no metric that shows their state"; the
known error was that "flag changes are invisible to monitoring until their symptoms cross an alert threshold". Action
item **ITSM-43** asked to "expose the state of every feature flag as a metric and annotate Grafana when one changes,
so 'what changed?' is one query".

**What the commit does.** A release is the same kind of change as a flag: it changes which code answers users. Commit
`b353d58` adds to the release stack's Prometheus (`release/compose.yml`, config `release-rules`) a recording rule
`svcdesk:release_build` - the build version on each track as one series, so "what runs where?" is one query - and
`svcdesk:release_builds_seen:10m`, the number of builds a track served in the last 10 minutes, with an alert
`SvcdeskReleaseChanged` (severity P3, to chat, `system: svcdesk`) when it is above 1. It fires for any change of a
track's build, whether `deploy.sh` made it or someone ran `docker compose up` by hand - exactly the unannounced kind
of change the incident had. `deploy.sh` reads both series at the end of every run and writes the answer into the
record as a read-only action, e.g. in the honest practice run: "canary=2.1.0-rc.2, stable=2.0.0; builds seen in
10 min per track: canary: 2, stable: 1".

**Where it stops short.** It covers the release's state, not the Caddy weights (they are not a metric: they live only
in Caddy's admin API and in the record), and there is no Grafana in this stack to annotate, so the alert and the
record replace the annotation. The flags of the Lab 4 shop remain outside it; the same rule over a flag service's
state metric would be the next step.
