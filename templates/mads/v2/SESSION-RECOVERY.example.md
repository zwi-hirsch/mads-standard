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

## Interrupted publication (§31)
Recover orphaned source/evidence and transaction journal against actual remote refs; compare exact report bytes and status. If report missing/partial, use new unique recovery/correction report with original transaction reference; never invent missing evidence or overwrite old mail. Validate new STOP/lease/expiry before further writes. Source and evidence already verified do not require rerun merely because the final report is missing.

## Owner-preauthorized automatic recovery (§32)
When an independently accepted broker is installed for this role, use the authenticated replacement launch and exact offer/ACK activation transaction in [SUCCESSOR-BROKER.example.md](SUCCESSOR-BROKER.example.md). Otherwise follow §29 manually. No self-issued epoch, no external worker replacement, no automatic source rights from chat initialization.

## Mandatory intake continuity (§34)
Before any new work recover frozen intake snapshots, all unresolved source/results and exact target PR/QA/main evidence, read global and personal decisions and ACK. A successor with ACTIVE lease but unresolved intake is INTAKE_ONLY, not permission to start new work. Preserve all historical source roots and do not delete or reassign unresolved results. Missing inventory or unread mail means BLOCKED_RESTORE/INTAKE; no automatic broker permission.
