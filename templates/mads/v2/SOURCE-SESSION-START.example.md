---
protocol: project.git-coordination.v2
id: PROJECT-OWNER-ORDER-20261120-042
type: ORDER
event: SESSION_START
from: owner
to: project-ci-01
created_utc: "2026-11-20T10:00:00Z"   # example only
role_id: project-ci-01
session_id: project-ci-01-20261120-dev-s001
lease_epoch: 1
work_branch: agent/project-ci-01/CI-001
base_main: "<actual exact main commit>"
source_head: "<exact work-branch commit>"
source_tree: "<exact Git tree>"
lock_sha256: "<lock content hash or null>"
source_write_authorized: true
allowed_paths: ["src/ci/**", "tests/ci/**"]
denied_paths: ["Cargo.lock", "secrets/**", ".github/workflows/**"]
production_authorized: false
external_host_authorized: false
requires_ack: true
status: OPEN
---

# Source SESSION_START — template only

Replace every placeholder with actual exact source, write/deny scope, expiry, task queue and authorized Owner identity. This example does not activate a specialist; verified second ACK, status and strong repository write control are still required.
