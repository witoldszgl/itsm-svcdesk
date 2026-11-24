---
lab6_change:
  id: CHG-20261124T081611Z
  candidate: "itsmlab.local/lab6-candidate:9f12316a1b16"
  stable: "ghcr.io/swasik/svcdesk-v2-seeded:2.0.0"
  strategy: canary
  change_type: standard
  risk: low
  rollback_plan: "Caddy weights back to 100/0/0 in one admin-API call (never 0/0/0); svcdesk-stable 2.0.0 keeps running and serving throughout, the candidate container stays in svcdesk-canary at weight 0 until the next release"
  started: 2026-11-24T08:16:11Z
  finished: 2026-11-24T08:17:06Z
  outcome: promoted
  reason: "every phase passed: 770 canary searches in all, 2 5xx (0.2 %), 0 slower than 0.2 s, against thresholds of 10 % and 10 %"
  actions:
    - {at: 2026-11-24T08:16:12Z, action: "start svcdesk-canary with the candidate at weight 0", autonomy: approve-then-act, approval: "standard change model SCM-SVCDESK-CANARY: release procedure and gate of BLAST-RADIUS.md, pre-authorised for svcdesk-v2-seeded 2.x candidates"}
    - {at: 2026-11-24T08:16:17Z, action: "read svcdesk_build_info from Prometheus: canary track runs 2.1.0-rc.2, stable 2.0.0", autonomy: read-only}
    - {at: 2026-11-24T08:16:17Z, action: "set weights 0/0/100: every user search through the nginx mirror to 2.0.0, a copy to the candidate", autonomy: closed-loop}
    - {at: 2026-11-24T08:16:28Z, action: "read the canary's searches, 5xx and le=0.2 bucket every 2 s (6 looks): shadow passed after 10 s: 316 canary searches, 1 5xx, 0 slower than 0.2 s", autonomy: read-only}
    - {at: 2026-11-24T08:16:29Z, action: "set weights 90/10/0 (step 1 of 2)", autonomy: closed-loop}
    - {at: 2026-11-24T08:16:50Z, action: "read the canary's SLIs every 2 s (11 looks): step 1 at 10 % passed after 21 s: 114 canary searches, 0 5xx, 0 slower than 0.2 s", autonomy: read-only}
    - {at: 2026-11-24T08:16:50Z, action: "set weights 50/50/0 (step 2 of 2)", autonomy: closed-loop}
    - {at: 2026-11-24T08:17:06Z, action: "read the canary's SLIs every 2 s (8 looks): step 2 at 50 % passed after 15 s: 260 canary searches, 1 5xx, 0 slower than 0.2 s", autonomy: read-only}
    - {at: 2026-11-24T08:17:06Z, action: "set weights 0/100/0 (promote)", autonomy: closed-loop}
    - {at: 2026-11-24T08:17:06Z, action: "read svcdesk:release_build (ITSM-43, what changed): canary=2.1.0-rc.2, stable=2.0.0; builds seen in 10 min per track: canary: 2, stable: 1", autonomy: read-only}
---
# Change record

## Why this change type

Standard. The procedure is the same for every svcdesk 2.x candidate and was pre-authorised once, as a standard
change model (SCM-SVCDESK-CANARY): the candidate first sees only mirrored copies of live searches while every user
still gets 2.0.0, then 10 % and 50 % of the users, and an automatic gate on my own SLOs decides at every look. What
makes the risk low is not the candidate - it is untested by definition - but the procedure: the stable build never
stops, a rollback is one admin-API call, and the four practice runs (changes/) show the gate rolling back an errors,
a slow and a hanging candidate with almost no user failure and promoting the honest one. It stops being a standard
change if the plan changes (a first step above 20 %, no shadow, a gate window longer than a step), if the candidate
changes anything the shadow cannot exercise (a schema migration, a write path: the mirror would then duplicate
writes), or if the gate ever promotes a candidate that later breaks the SLO - then each release goes back to a
normal change with a person's approval before the run.

## Risk and what bounds it

What can go wrong for users: during the weighted steps a bad candidate answers a share of real searches. The shadow
is there so that this almost never happens: an errors or slow candidate shows its 30 % bad share among the first
few dozen mirrored searches, and a hang stops being observed after at most 120 of them, which at 40 mirrored
searches a second the stall rule notices within about 10-14 s, still before any user reaches it. If a bad
behaviour only showed itself under weighted traffic, the bound is c + R x w x q x D at the 10 % step: about
5 + 40 x 0.1 x 1 x 14 = 61 failed searches for the worst case (a hang), under the 150 ceiling. The gate's deadline
(timeout 165 s) rolls back anything undecided. What it cannot see: a defect on a route the traffic does not use, and
anything slower than the 1 s user patience but still within the SLO threshold of the gate (none, at 0.2 s).
