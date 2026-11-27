# MADS v2.0 portable templates

All examples are non-operational placeholders and do not grant source rights or start agents.

| File | Purpose |
|---|---|
| PROJECT-MANIFEST.example.yaml | Project-local canonical Git, roles, isolation and admission |
| MADS-VERSION-LOCK.example.yaml | Each project's pinned standard version, release digest, and accepted source |
| READ-ONLY-ONBOARDING.example.md | Technical preflight ACK, immediately followed by source activation |
| SOURCE-SESSION-START.example.md | Conditional scoped source lease, second ACK/status, immediate first task |
| SESSION-RECOVERY.example.md | Abrupt human-authorized replacement, exact Git recovery, no old ACK wait |
| SOURCE-HANDOFF.example.yaml | Exact source HEAD/TREE/lock, test logs and Git bundle proof |
| INTEGRATION-HANDOFF.example.md | Independent QA/optimization of Owner-accepted source |
| ROLE-REPORT.example.md | Evidence and honest product/task/QA Kanban outcomes |
| PILOT-ACCEPTANCE.example.md | G0–G13 acceptance drills with PASS/BLOCKED/NOT_RUN |
| NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md | Copy-ready Russian project Owner instruction |

Copy templates into **your own** project repository, replace placeholders with actual Git refs, toolchain and owner authorization, test role-source write admission and bundle restore. Retain separate project-private source credentials. Do not copy another project's role sessions or code.

- `BLOCKER-LEDGER.example.yaml`: stable evidence-bound blockers, accountable remediation, next-gate readiness and independent closure under §30.

- `REPORT-PUBLICATION.example.yaml`: resumable publication transaction, recovery and readback (§31).

- `INTAKE-LEDGER.example.md`: mandatory §34 frozen intake, historical recovery and independent progression gate; apply before initial assignments and every successor.
