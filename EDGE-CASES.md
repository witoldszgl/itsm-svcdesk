---
lab2_edge_cases:
  E1: {rule: R-08, count: 3}
  E2: {rule: R-06, count: 2}
  E3: {rule: R-09, count: 4}
  E4: {rule: R-10, count: 4}
  E5: {rule: R-12, count: 1}
  E6: {rule: R-13, count: 11}
---
<!-- ai-generated: 80% - Claude Code drafted the sections from METRIC-SPEC.md and the practice log; the student reviewed them and owns the reasoning -->

# Edge cases in the practice event log

The six counts above are what our own service reports for `fixtures/events-practice.jsonl` over the published
window (`metrics.json`). Each section names the events in the practice log, what the usual one-line definition
would have done with them, and why the specification's rule gives the person reading the dashboard a truer number.

## E1 - clock skew produces a negative lead time

- What the log contains: three commits timestamped after the successful deployment that shipped them: sha-0040
  is 834 s after DEP-0012, sha-0094 is 51 s after DEP-0024 and sha-0123 is 780 s after DEP-0031. A commit cannot
  be shipped before it exists, so these are clocks that disagreed, not time travel.
- What a default definition would have done: `deployment.at - commit.at` for every pair, which puts three
  negative durations into the median, or a filter `lead > 0` that silently drops the three pairs. The first
  pulls the median down with impossible values; the second shrinks the sample without anyone noticing.
- Why the rule is defensible: the change really was delivered, and delivered quickly, so the pair belongs in
  the median. Clamping to zero keeps it at the most honest value we can defend (it cannot be less than zero),
  and counting it in `negative_lead_time_pairs` tells the reader that the clocks need fixing instead of hiding
  the problem. A dashboard that drops data quietly is worse than one that shows it with a warning.

## E2 - a revert of a revert

- What the log contains: sha-0070 reverts sha-0069 (change CHG-0033, first committed on 31 August), and
  sha-0071 reverts sha-0070 a few hours later on 7 September, which re-applies the original work. The two reverts carry no `change_id` of
  their own.
- What a default definition would have done: count every commit, or every distinct commit message, as a
  change: three changes where the team did one piece of work, took it out and put it back. Changes delivered
  would be inflated, and the lead time of the real change would be measured from the last revert instead of
  from when the work started.
- Why the rule is defensible: a revert is not new work, it is the same unit of work moving back and forth.
  Resolving the chain transitively to the original `change_id` keeps one change with its true first commit
  instant, so the ground truth lead time shows how long the work really took, including the back-and-forth.
  The count of 2 collapsed commits shows how much churn there was without letting it pose as throughput.

## E3 - a hotfix that never touched `main`

- What the log contains: four commits on hotfix branches that reached production directly: sha-0019
  (`hotfix/2609`, DEP-0006), sha-0077 (`hotfix/4347`, DEP-0019), sha-0108 (`hotfix/6085`, DEP-0028) and
  sha-0127 (`hotfix/1544`, DEP-0033), all on successful deployments in the window.
- What a default definition would have done: "lead time for changes" is usually written as commit to main
  until production, so a filter `branch == "main"` drops the four hotfixes from the lead time median entirely,
  exactly the urgent changes that were delivered fastest.
- Why the rule is defensible: the customer does not care which branch the fix came from, only that it reached
  production. Dropping hotfixes makes the team look slower than it is and hides the path used in emergencies.
  Counting them in `commits_never_on_main` keeps the process risk visible (code in production that bypassed
  the main-branch review) without distorting delivery speed.

## E4 - a deployment with zero linked commits

- What the log contains: four production deployments in the window with an empty `commits` list: DEP-0026 and
  DEP-0032 succeeded, DEP-0043 and DEP-0044 failed. They are configuration or infrastructure deployments that
  change what runs in production without new code.
- What a default definition would have done: either skip deployments without commits everywhere (they have
  no lead time, so a join on commits drops them), or divide by the number of commits and crash or return
  nonsense. Skipping them would remove two failures from the change fail rate, making production look safer.
- Why the rule is defensible: a configuration push is a deployment and it can break production just like
  code; here two of the four did. It has no commit, so it gives no lead-time pair, but it must stay in
  frequency, change fail rate and rework rate. Otherwise the least reviewed kind of change would be the one
  whose failures never show up on the dashboard.

## E5 - a deployment that failed and never recovered

- What the log contains: DEP-0015 failed on 7 September at 06:12:35Z; incident INC-0004 covering it was opened
  at 06:35:41Z and has no `resolved` event anywhere in the log. It is the one open failure; the other seven
  failed deployments were recovered.
- What a default definition would have done: close the failure at the window's end (inventing a recovery
  time of about fifteen days) or drop the failed deployment altogether. The first makes up a number that
  nobody measured; the second makes the change fail rate look better by removing the worst failure.
- Why the rule is defensible: a recovery time that has not happened cannot be measured, so it is excluded
  from the recovery median and counted as `open_failures`, while the failure itself still counts in the change
  fail rate. The reader sees both facts: how fast recovered failures were fixed, and that one is still open,
  which is the most important thing to know on Monday morning.

## E6 - overlapping incidents

- What the log contains: eleven incidents, and 11 pairs of them overlap. INC-0004 is never resolved, so its
  interval runs from 7 September to the end of the window and overlaps every later incident; on 7 September
  INC-0010, INC-0011, INC-0004 and INC-0005 are open at the same time, each covering a different failed
  deployment.
- What a default definition would have done: merge overlapping incidents into one outage (one recovery time
  for four failures) or sum incident durations as wall-clock downtime (counting the same hours several
  times). Either way the recovery median describes incidents, not the failed deployments DORA asks about.
- Why the rule is defensible: failed deployment recovery time answers "how long after a bad deployment did
  we recover from it", so it is computed per failed deployment from its covering incident. Overlapping
  incidents stay separate and are counted, so the reader learns that failures clustered, a signal about
  deployment practice, without that clustering changing each deployment's own recovery time.

## Gaming demonstration

We improved `deployment_frequency_per_day` by exploiting R-11 together with R-10: the frequency counts every
production deployment in the window of any kind, including deployments that carry no commits. In
`gaming/after.jsonl` the team holds back its last real releases of the window (six successful deployments from
18 to 21 September, DEP-0033 and DEP-0037 to DEP-0042, move to 23 September, after the reporting period; moving a deployment later is permitted by
R-19) and fills the three weeks with 20 empty "heartbeat" production deployments that change nothing. No event
was deleted and no outcome was flipped. The frequency rises from 2.0 to 2.67 deployments per day, a 33 % rise
that clears the 25 % margin, and it looks like an elite team speeding up.

Delivery got worse: measured on the base work only, the changes that reached production inside the window fall
from 65 to 56 (86 %, below the 90 % harm threshold), and the true change lead time rises from 539 452 s to
555 237 s. Customers waited longer for real fixes while the dashboard improved.

The incentive that produces this is a target or bonus on deployment frequency alone, for example a quarterly
OKR "deploy at least twice a day" or a ranking of teams by DORA frequency. The team lead and the platform team
that own the pipeline metric would be rewarded, and anyone who pointed out that the extra deployments are empty
would look like they are arguing against the numbers. The cost falls on the reporters whose tickets waited for
the held-back releases. The guard against it is to read frequency next to changes delivered and true lead time,
never alone.
