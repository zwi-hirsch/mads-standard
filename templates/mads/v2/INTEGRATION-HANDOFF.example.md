---
protocol: project.git-coordination.v2
id: PROJECT-OWNER-ORDER-YYYYMMDD-002
type: ORDER
event: INTEGRATION_HANDOFF
from: owner
to: independent-qa-agent
created_utc: "REPLACE_WITH_REAL_UTC"
requires_ack: true
main_head: "<EXACT_MAIN_SHA>"
source_role: project-ci-01
source_branch: "agent/project-ci-01/CI-001"
accepted_source_head: "<EXACT_SPECIALIST_SHA>"
accepted_source_tree: "<EXACT_TREE_SHA>"
lock_sha256: "<LOCK_SHA256_OR_NULL>"
qa_branch: "agent/qa/project-ci-001"
new_feature_implementation_authorized: false
existing_code_bugfix_optimization_authorized: true
merge_authorized: false
production_authorized: false
---
# Independent QA of already authored source (example ONLY)

First ACK the exact order, verify source head/tree/lock and checked source bundle, read STOP and test negative cases. Independently compile and run targeted/real integration/hostile tests of the authorized specialist source on a **separate** validation branch.

Only fix objectively reproduced defects in the already submitted implementation or optimize with evidence. If a new feature, interface or protocol is missing, write a source-bound CHANGE_REQUEST for the original specialist and Owner. Do not invent product features or edit the specialist's active branch. On source changes commit+push+bundle-restore immediately; full regression on final exact tree. REPORT with real RCs/logs and all unresolved authorizations.
