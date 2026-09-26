---
svcdesk_decisions:
  C1: wallclock      # wallclock | business
  C2: immutable      # reopen | immutable
  C3: matrix         # matrix | vip
---
<!-- ai-generated: 80% - Claude Code drafted the three sections from REQUIREMENTS.md and CHECKS.md; the student reviewed and owns every decision -->

# Decisions

## C1 - SLA clock for P1

**Decision:** P1 tickets run on the wall clock: acknowledge within 15 minutes and resolve within 4 hours of
creation, around the clock (R-14). P2 to P4 keep the business-hours clock of R-13. The rejected part is only
R-13's claim to cover "any SLA target": the business-hours pause does not apply to P1. A P1 raised on Friday
at 17:00 CEST is due for acknowledgement at 17:15, not on Monday at 08:15.

**Rejected alternative:** `business`: every priority, P1 included, pauses outside Monday to Friday 08:00 to
16:00. It is simpler (one clock for everything, no on-call), but a P1 raised on Friday evening would not be
late until Monday morning, which is exactly the situation R-14 was written to forbid.

**Reason:** P1 means the whole organisation is affected and work has stopped. The cost of such an outage
grows with every hour, including the hours after 16:00 and at weekends, and R-14 names this case explicitly
("a P1 raised on Friday evening is late at 15 minutes past"), whereas R-13 is a general rule. The specific
rule overrides the general one, and only for the one priority where waiting until Monday is unacceptable.
The price is real: the desk needs an on-call rota for P1 outside business hours, and P1 targets will be
breached more often in the reports until that rota exists. We accept that, because a report that shows a
P1 as "on time" on Monday morning after a weekend-long outage would be a false report.

**Service owner:** The Service Desk product owner (owner of the SLA catalogue), because committing to 24/7
response for P1 is a service-level commitment with staffing cost, and only the owner of the SLA targets
can make that commitment and fund the on-call rota that honours it.

**Customer outcome:** When the whole organisation cannot work, the outage is acknowledged within 15 minutes
and fixed within 4 hours whatever the time of day, and a missed P1 target is visible as a breach instead of
being hidden by a paused clock.

## C2 - Closed tickets and reopening

**Decision:** A closed ticket is immutable (R-09). Reopen is allowed only from `resolved`, within 7 days of
the resolution (R-10, R-11); reopening a closed ticket returns 409 whatever its age, and further work on
the same issue is a new ticket that references the closed one through `related_to`. The rejected part is
only the words "or closed" in R-10; the reopen window for resolved tickets is kept.

**Rejected alternative:** `reopen`: a closed ticket can be reopened within 7 days of closure. It saves the
reporter one step, but it makes "closed" provisional, so the Monday report of closed tickets could change
after it was produced, and a ticket's history would no longer be final once the reporter confirmed the fix.

**Reason:** The difference between `resolved` and `closed` in R-07 is the reporter's confirmation that the
fix works. Once the reporter has confirmed it, the record should be final: closure counts, resolution times
and SLA results reported for that ticket must not move afterwards. The 7-day safety net still exists while
the ticket is resolved, which is exactly the period in which the reporter checks the fix. After closure a
recurrence is a new event with its own priority and its own SLA clock, linked to the old ticket through
`related_to`, so the history is kept and nothing is lost. What we give up is convenience: a reporter who
closed too early has to open a new ticket.

**Service owner:** The Service Desk product owner, because this rule decides what the desk's closure figures
and reports mean, and the integrity of those reports is what this owner answers for to the organisation.

**Customer outcome:** The reporter can still reopen a resolved ticket for 7 days if the fix fails, and the
organisation gets closed tickets that stay closed, so reported closure and SLA figures do not change after
the fact; a recurrence is tracked as a linked new ticket with its own fresh target.

## C3 - VIP reporters and the priority matrix

**Decision:** Priority comes from the impact and urgency matrix and from nothing else (R-05). The
`reporter.vip` flag is stored and returned, but it does not change the priority: impact 3, urgency 3 is P4
for a VIP as for anyone else. The rejected part is R-06 as a priority rule; the flag itself (R-03) is kept,
so the desk can still see and filter who is a VIP.

**Rejected alternative:** `vip`: after the matrix, a VIP ticket at P3 or P4 is raised to P2. It makes
executive requests visible faster, but it lets the identity of the reporter, not the impact on the
organisation, decide who is served first, which is what R-05 forbids.

**Reason:** Priority drives the SLA targets and the order of work for the whole desk. If a cosmetic issue of
one executive becomes P2, it takes a 1-hour acknowledgement and an 8-hour resolution target and competes with
team-wide outages, while the matrix was built to put organisation- and team-wide impact first. R-05 also
states that nobody can request a priority; a VIP flag set by the reporter's side is a way of requesting one.
If an executive's problem really stops a team or the organisation, the matrix already gives it P1 or P2
through impact and urgency. What we give up is automatic visibility for VIPs; the flag is kept so the desk
can handle visibility in how it communicates, without distorting priority and SLA figures.

**Service owner:** The Service Desk product owner, because the priority matrix is part of the SLA catalogue
this owner defines, and any exception that reorders the queue for a group of people is their policy decision.

**Customer outcome:** Every reporter's ticket is prioritised by its real impact and urgency, so outages that
stop teams are not queued behind cosmetic issues of senior staff, and the priority and SLA figures in the
reports mean the same for every ticket.
