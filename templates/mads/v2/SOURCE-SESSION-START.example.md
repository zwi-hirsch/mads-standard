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
source_write_authorized: true # conditional offer; effective status stays false until verified activation
activation_mode: IMMEDIATE_AFTER_VERIFIED_PREFLIGHT_ACK_AND_STATUS
first_source_task: "<real implementation task ID>"
monitoring_mode: "<REAL_SCAN or EXPLICIT_BOUNDED_MANUAL_EXCEPTION>"
allowed_paths: ["src/ci/**", "tests/ci/**"]
denied_paths: ["Cargo.lock", "secrets/**", ".github/workflows/**"]
production_authorized: false
external_host_authorized: false
requires_ack: true
status: OPEN
---

# Source SESSION_START — template only

Replace every placeholder with actual exact source, write/deny scope, expiry, task queue and authorized Owner identity. This example does not activate a specialist; verified first and second ACKs, exact pins, STOP/lease/path checks and status readback are required. Start the first task immediately after activation, without a new human turn. A manual exception never waives write fencing or grants G9 PASS.

## Replacement-session continuity (MADS v2.0.3 §28)
For replacement rather than first admission, attach the immutable complete obligation ledger (all original/reserve/blocked/deferred/review tasks), previous role ID and lease epoch, old source refs and exact HEAD/TREE, STOP/closure reference and proof of non-concurrent writing, verified Git-only artifact manifest, successor ACK/status and first READY task. Retain the canonical role ID regardless of chat number unless an explicit Owner succession mapping exists. Do not issue or activate competing source rights if prior fencing is unproven; read-only recovery may proceed. Missing evidence or dependencies remain BLOCKED. No task can disappear because a session was replaced.
