---
protocol: project.git-coordination.v2
id: PROJECT-OWNER-ORDER-YYYYMMDD-001
type: ORDER
event: WATCHDOG_ATTACH_READ_ONLY
from: owner
to: project-ci-01
created_utc: "REPLACE_WITH_REAL_UTC"
role_id: project-ci-01
session_id: null
lease_epoch: null
source_write_authorized: false
production_authorized: false
requires_ack: true
status: OPEN
---
# Read-only first-contact admission — example ONLY

Read canonical main/AGENTS.md, MADS v2, both own mailbox refs, role memory, role status ref, STOP/security decisions and exact source baseline. Independently verify all three refs and a real shared Git Watchdog scan or explicit bounded Owner manual-monitoring exception (Section 18). Reply with immutable ACK to your OWN outbound mailbox citing this order ID and observed inbound Git SHA. Verify remote ACK readback.

**This is deliberately NOT a coding lease.** Role state remains ONBOARDING_READ_ONLY until a scoped conditional Owner SESSION_START is ACKed and status activation verified. Preprovision the branch and first source task; perform both steps in one initialization. Immediately start coding when conditions pass, without waiting for another human prompt. If a developer cannot proceed due to permissions, report BLOCKED_ADMISSION rather than undertaking endless DATA_ONLY work.
