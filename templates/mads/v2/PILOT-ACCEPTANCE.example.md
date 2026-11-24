# MADS v2.0 pilot admission — project-local evidence worksheet

**Example only.** Replace UNVERIFIED by actual PASS/FAIL/BLOCKED/NOT_RUN with source-bound proof. No evidence means NOT_RUN, never PASS.

| Gate | State | Exact SHA/run/log | Owner remediation |
|---|---|---|---|
| G0 canonical source and lock | NOT_RUN | — | — |
| G1 preflight ACK + real Watchdog or bounded manual exception | NOT_RUN | — | — |
| G2 immediate source SESSION_START ACK + status, same initialization | NOT_RUN | — | — |
| G3 two writers isolated paths | NOT_RUN | — | — |
| G4 remote source + independent bundle restore | NOT_RUN | — | — |
| G5 executable READY scheduler | NOT_RUN | — | — |
| G6 actual specialist code and PR | NOT_RUN | — | — |
| G7 independent agent current-head QA | NOT_RUN | — | — |
| G8 Owner exact-main merge gate | NOT_RUN | — | — |
| G9 scanner and actual notification delivery | NOT_RUN | — | — |
| G10 replacement session and stale lease | NOT_RUN | — | — |
| G11 canonical↔mirror drift rejection (if configured) | NOT_RUN | — | — |
| G12 separate production authority denial | NOT_RUN | — | — |
| G13 operator/AI-Ops and Kanban parity | NOT_RUN | — | — |

**Pilot verdict:** MADS_SOURCE_READY / MADS_PILOT_BLOCKED / MADS_OPS_PILOT_PASS, with explicit acceptance authority and source SHA. Documentation alone cannot satisfy a pilot gate.

Verify no probation, no extra human approval turn after all conditions pass; deny unACKed/stale/conflicting lease. A manual exception is not G9 PASS.
