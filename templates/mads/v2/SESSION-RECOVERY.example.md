# Unplanned session recovery — template (not an executable lease)

Human replacement initialization (copy-ready): "Restore role <ROLE_ID> as the sole replacement of the exhausted previous manual chat. Apply MADS §29; the old session cannot supply a final handoff. Restore Git and continue the next safe READY task after Owner-authorized fencing and activation."

Owner recovery decision records: role ID, old session and epoch, human directive or approved standing-policy reference, old status ref/tip, source ref/HEAD/TREE/lock, last ACK/REPORT or MISSING, complete inherited task ledger ref, unpublished work status UNKNOWN/MISSING_SOURCE, immutable STOP, revoked status commit, successor unique session/epoch/branch, exact source pin, scope, expiry, monitoring, new order/ACK/status and first READY task. Do not record raw chat transcripts or personal data. Existing pending offers may be reused only after checking all conditions.

| Case | Expected |
|---|---|
| Human replacement after exhausted context, old ACK absent | recover; Owner revoke + new ACK/ACTIVE, no old closure wait |
| Pending correct replacement offer | reuse, no duplicate epoch |
| Remote commits newer than REPORT | recover and audit, not lose |
| Unpushed local changes | UNKNOWN/MISSING_SOURCE, reconstruct affected tasks |
| Silent chat without replacement authority | no inference or self-grant |
| Old writer returns or remote drift | stop/freeze and reconcile |
| External or concurrent runtime | require verified cessation/enforced revocation |
| Wrong pin, expired lease, missing ACK/monitoring/scope | BLOCKED |
| Duplicate activation or CAS race | reject second writer |
| Missing old final report only | not a blocker after human directive and required gates |
| Task ledger mismatch | reconcile, no silent task deletion |
| Production request from recovery | deny without separate authorization |

All rows are acceptance expectations, NOT_RUN until a real drill. Cooperative manual fencing is not technical token revocation or G10 PASS.

## Mandatory blocker continuity (§30)
Recover current Git blocker/dependency ledger, exact unresolved obligations, recurrence, owners, next actions and approval requirements. Check next-gate readiness, escalate repeated or orphaned blockers and initiate scope-safe remediation in the same active invocation. Record missing ledger evidence as UNKNOWN/BLOCKED_RESTORE as applicable. A successor does not require old-chat memory or final handoff; no new authority is implied.
