---
protocol: project.git-coordination.v2
id: PROJECT-CI-01-REPORT-YYYYMMDD-001
type: REPORT
from: project-ci-01
to: owner
created_utc: "REPLACE_WITH_REAL_UTC"
in_reply_to: PROJECT-OWNER-ORDER-YYYYMMDD-001
role_id: project-ci-01
session_id: "<EXACT_ACTIVE_SESSION>"
lease_epoch: 1
source_head: "<REAL_REMOTE_HEAD>"
source_tree: "<REAL_GIT_TREE>"
lock_sha256: "<LOCK_OR_NULL>"
status: PARTIAL_OR_DONE_AS_EVIDENCED
---
# Actual source implementation report

- **Product behavior implemented**: exact source modules and user-visible functionality; no generic claims.
- **Changed paths / source commits**: explicit SHA and review PR URL.
- **Targeted tests executed**: command, environment/tool version, exit code, raw log SHA, negative tests.
- **Final-tree full regression**: PASS / FAIL / NOT_RUN / BLOCKED and the exact source HEAD.
- **Recovery**: Git bundle bytes physical location, prerequisite, SHA256 and independent restore HEAD/TREE/fsck result.
- **Runtime/product boundary**: SOURCE_COMMITTED / SOURCE_TESTED / MERGED / DEPLOYED and separate production gate. No false promotion.
- **Per-role queue**: PRIMARY DONE/READY/BLOCKED/remaining, RESERVE DONE/READY/BLOCKED/remaining.
- **Canonical Kanban**: DONE, READY, IN_PROGRESS, BLOCKED, BACKLOG, REMAINING, TOTAL; date and immutable owner-accepted source.
- **Source acceptance requests**: exact HEAD/TREE and unresolved contract change requests.
- **Next READY**: 5 or so dependency-safe tasks / explicit blocked remediation with owner and evidence.
