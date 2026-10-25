---
lab4_comms:
  awareness: 2026-10-12T06:42:00Z
  detection: 2026-10-12T06:39:19Z
  classification: 2026-10-12T07:30:00Z
  nis2:
    early_warning_due: 2026-10-13T06:42:00Z      # awareness + 24 h
    notification_due: 2026-10-15T06:42:00Z       # awareness + 72 h
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z       # one calendar month after notification_sent
  ksc:
    early_warning_due: 2026-10-13T06:39:19Z      # detection + 24 h
    notification_due: 2026-10-15T06:39:19Z       # detection + 72 h
    notification_sent: 2026-10-13T09:00:00Z
    final_report_due: 2026-11-13T09:00:00Z       # one calendar month after notification_sent
  dora:
    initial_due: 2026-10-12T11:30:00Z            # classification + 4 h; earlier than awareness + 24 h
    initial_sent: 2026-10-12T10:00:00Z
    intermediate_due: 2026-10-15T10:00:00Z       # initial_sent + 72 h
    intermediate_sent: 2026-10-14T10:00:00Z
    final_due: 2026-11-14T10:00:00Z              # one calendar month after intermediate_sent
  log:
    - {at: 2026-10-12T10:00:00Z, to: the financial supervisor (KNF), what: DORA initial notification of a major ICT-related incident}
    - {at: 2026-10-12T12:00:00Z, to: the CSIRT, what: NIS2 and KSC early warning}
    - {at: 2026-10-13T09:00:00Z, to: the CSIRT, what: NIS2 and KSC incident notification}
    - {at: 2026-10-14T10:00:00Z, to: the financial supervisor (KNF), what: DORA intermediate report}
---
<!-- ai-generated: 80% - Claude Code chose the instants with the postmortem's timeline and computed the deadlines; the student checked the arithmetic -->

# Communications log: the regulators' clocks

The shop is assumed to be an entity that NIS2, the Polish KSC act and DORA all apply to, and the incident of
12 October 2026 (recording lab4-rec-4) significant under the first two and major under the third. Every instant is
UTC; 12 October is a Monday, so no weekend falls inside the first clocks.

## The three instants you defend

**Detection (KSC), 06:39:19Z.** The amended KSC act counts "od momentu jego wykrycia", from the moment of detection.
The earliest moment the organisation's own systems detected the incident is the start of the ShopCheckoutErrors page,
06:39:19Z: the detecting instant of the postmortem. I take the machine's detection, not the human's, because the
alert is the organisation detecting; a later instant would be hard to defend to the regulator.

**Awareness (NIS2), 06:42:00Z.** NIS2 counts from "becoming aware of the significant incident" - aware not of an
alert but of an incident that is significant. At 06:40:09Z the on-call acknowledged the page knowing only that
checkout errors crossed 5 %. By 06:42:00Z the 5-minute window showed 31 % of orders failing, every failure a failed
payment charge, and a 16x surge of front-page traffic: a disruption of the core service to customers, which is what
makes it significant. That is the instant I defend.

**Classification (DORA), 07:30:00Z.** DORA's clock for the initial notification runs from the classification as major
under the Delegated Regulation's criteria (clients affected, duration, service criticality). Service was restored at
06:44:19Z; the counts of failed orders (8 of 65 in ten minutes) and the duration were available from the snapshot
within the hour, and the classification as major was made at 07:30:00Z, inside the 24 hours after awareness, so the
initial notification is due at the earlier of classification + 4 h (11:30:00Z) and awareness + 24 h.

## The log

| at (UTC) | to | what | clock it answers |
|---|---|---|---|
| 2026-10-12T10:00:00Z | the financial supervisor (KNF) | DORA initial notification | due 11:30:00Z the same day (classification + 4 h) |
| 2026-10-12T12:00:00Z | the CSIRT | NIS2 and KSC early warning | due 2026-10-13 at 06:42:00Z (NIS2) and 06:39:19Z (KSC) |
| 2026-10-13T09:00:00Z | the CSIRT | NIS2 and KSC incident notification | due 2026-10-15 at 06:42:00Z and 06:39:19Z; the final reports are then due 2026-11-13T09:00:00Z |
| 2026-10-14T10:00:00Z | the financial supervisor (KNF) | DORA intermediate report | due 2026-10-15T10:00:00Z (initial + 72 h); the final report is then due 2026-11-14T10:00:00Z |

The KSC clock starts 2 min 41 s before the NIS2 clock for the same incident: detection comes before awareness. One
notification sent at 09:00Z on Tuesday meets both, which is why it goes out once to the CSIRT.
