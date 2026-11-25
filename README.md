# MADS Standard v2.0

**Portable, Git-native multi-agent software development protocol.** The standard is readable without credentials; individual adopting projects remain isolated and retain their own private Git credentials, code, mailboxes and source approval.

Read [MULTI-AGENT-DEVELOPMENT-SYSTEM.md](MULTI-AGENT-DEVELOPMENT-SYSTEM.md) in full, particularly its normative Sections 18–31.

## Core model

- Owner and qualified specialists **write actual source code and executable tests** in separate leased Git source branches.
- A READ_ONLY technical preflight and scoped `SESSION_START` + second ACK + verified status are one continuous initialization; immediately begin the first real task after verified activation, without probation or another human prompt.
- An independent test/optimization agent tests already authored code and can fix demonstrable bugs or optimize it; it is not the default new-feature author.
- Git coordination is source-bound, with immutable ORDER/ACK/REPORT/STOP, active lease scopes and independently checked source HEAD/TREE/lock.
- Every meaningful source change is committed/pushed and has a separately restored Git bundle before expensive regression. Only the Owner accepts/merges.
- One canonical writable Git authority per project, optionally mirrored across GitHub/Gitea. A source lease never gives production permissions.
- Finite READY queues and a shared deterministic Git Watchdog support work; inactive ordinary chats do not execute autonomously.

## Stable release v2.0.2

The recommended version is [v2.0.2](https://github.com/zwi-hirsch/mads-standard/releases/tag/v2.0.2) (Apache-2.0). It adds mandatory Git-only inter-agent project artifact handoff (Section 27) and retains the one-name Russian project bootstrap from v2.0.1. No source/role/security boundary is weakened.

Download the [ZIP](https://github.com/zwi-hirsch/mads-standard/releases/download/v2.0.2/mads-standard-v2.0.2.zip) and its [SHA-256 checksum](https://github.com/zwi-hirsch/mads-standard/releases/download/v2.0.2/mads-standard-v2.0.2.zip.sha256). Verify the actual ZIP bytes; pin the release version/tag/digest in each adopting project's own Git.

Earlier released [v2.0.1](https://github.com/zwi-hirsch/mads-standard/releases/tag/v2.0.1) and [v2.0.0](https://github.com/zwi-hirsch/mads-standard/releases/tag/v2.0.0) remain immutable. The v2.0.0 ZIP SHA-256 is `d1953b5100adf07743c1423cb42cca52f3b99b323a443b42ded7eaabb6380903`. Public main is mutable; it must not be treated as a pinned release.

## Project onboarding

1. Retrieve one released version/tag/ZIP of this public standard and validate its published SHA-256 manifest.
2. Copy the document and `templates/mads/v2/` into your project's *own* Git source. Commit a local `docs/mads/MADS-VERSION-LOCK.yaml` containing version, published release/tag/SHA256 and adopting project's acceptance source SHA.
3. Use [the Russian Owner bootstrap prompt](templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md) or an equivalent project-local prompt. Your Owner reads local MADS before modifying the project.
4. Complete immediate specialist admission in one initialization transaction and real code PR/pilot. Run G0–G13 and distinguish DOCS_SOURCE_READY from real installed operational features.
5. Update standards only by a reviewed project-local PR to a newer pinned release. Never depend on unpinned upstream main or grant your project Git token to the standards repository.

## Files

- [Main standard](MULTI-AGENT-DEVELOPMENT-SYSTEM.md)
- [Project manifest](templates/mads/v2/PROJECT-MANIFEST.example.yaml)
- [First read-only onboarding](templates/mads/v2/READ-ONLY-ONBOARDING.example.md)
- [Second coding source SESSION_START](templates/mads/v2/SOURCE-SESSION-START.example.md)
- [Source recovery/handoff](templates/mads/v2/SOURCE-HANDOFF.example.yaml)
- [Independent QA handoff](templates/mads/v2/INTEGRATION-HANDOFF.example.md)
- [Truthful progress report](templates/mads/v2/ROLE-REPORT.example.md)
- [Pilot evidence G0–G13](templates/mads/v2/PILOT-ACCEPTANCE.example.md)
- [Start a new project by providing **only its name** (RU)](templates/mads/v2/NEW-PROJECT-BOOTSTRAP-PROMPT.ru.md)

## Scope and release

This repository is a **protocol and templates**, not a CI/Watchdog scheduler or live coding agent. No protected branch, source lease or production permission becomes effective until an adopting project installs and independently tests it.

**License:** Apache License 2.0. See [LICENSE](LICENSE). You may use and modify MADS in private and commercial projects under its terms. Preserve required copyright and licensing notices.

**Maintaining source of truth:** once published, the **mads-standard** repository will be canonical for common MADS versions. Adopting repositories must pin released version+SHA, keep project-specific overlays and never blindly import source histories, customer data or secrets.

## Git-only inter-agent handoff (v2.0.2)

Normative [Section 27](MULTI-AGENT-DEVELOPMENT-SYSTEM.md#27-mandatory-git-only-project-artifact-transport-v202) requires all non-secret inter-agent **project** artifacts and individual UTF-8 source patches to travel through the adopting project's own authorized Git, with exact blob/SHA-256 manifests and remote readback. Chat ZIPs, Library, email and temporary storage are not artifact handoffs. Production keys stay outside Git and require independently approved secret provisioning. **A version bump in source is not a published release until the GitHub release tag, archive, sidecar and verification exist.**

## v2.0.3 candidate — immediate source admission

Section 18 defines no-probation admission with scoped conditional activation and explicit bounded monitoring fallback. This branch is a release candidate; the stable v2.0.2 tag remains immutable until v2.0.3 release assets are verified.


## v2.0.4 candidate — abrupt context recovery

Section 29 enables human-authorized manual chat replacement without an impossible old-session closure ACK; exact Git recovery, Owner STOP, monotonic lease, new ACK/status and scope remain mandatory. See [recovery template](templates/mads/v2/SESSION-RECOVERY.example.md). Not a published release or strong fencing proof.

## v2.0.5 candidate — proactive blocker remediation

Section 30 requires active blocker ownership, anticipatory readiness, timely authority requests and mandatory Owner initialization/milestone reporting. See [blocker ledger template](templates/mads/v2/BLOCKER-LEDGER.example.yaml). This is a source candidate, not a published release; v2.0.3/2.0.4 predecessors remain subject to acceptance.

## v2.0.6 candidate — interrupted REPORT publication

Section 31 requires a resumable Git publication journal, idempotent readback, recovery from orphaned source/evidence, separate recovery/correction reports and status reconciliation. See [publication checkpoint template](templates/mads/v2/REPORT-PUBLICATION.example.yaml). This source candidate includes prior §28–30 changes; stable release publication remains separate.
