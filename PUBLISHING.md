# Publish MADS v2.0 to its own public GitHub repository

This is an operator action; do not treat staging files as a public release.

## One-time repository creation

1. Sign in to GitHub as the intended standard owner. Open https://github.com/new.
2. Repository name: `mads-standard`; visibility: **Public**. Initialize with README and an explicit reuse license **only after rights review** (recommended Apache-2.0 for combined documentation/code templates; the standard owner must decide).
3. Set repository description: "MADS — portable Git-native multi-agent development standard".
4. In https://github.com/settings/installations configure the GitHub App/ChatGPT integration to include this repo with **Contents: Read/Write** if ChatGPT will populate it. Never grant access to other project repositories merely to share the standard.
5. Independently confirm repository `public=true`, correct owner and installed connector write permissions. If this is unavailable, an authorized operator can use GitHub Upload files in the public repo or run the local export script, without granting any other project token broader access.

## Copy staged sanitized files only

Copy **contents** of the source distribution directory to the public repo root (not the entire private/source development repository, not its `.git` history). Whitelist:
- `MULTI-AGENT-DEVELOPMENT-SYSTEM.md`
- `README.md`, `SECURITY.md`, `PUBLISHING.md`, `MADS-VERSION.yaml`
- `templates/mads/v2/*`
- `scripts/build_release.py`

No old workspace, tickets, role memory, Git mailbox history, customer data, private SHA claims, credentials, user chat transcripts, test evidence or toolchains may be copied. Inspect all files and run secret/private-identifier scan before copying.

## Release

1. Review the license, add a correct `LICENSE` file and set `publication_status: RELEASED` in `MADS-VERSION.yaml`.
2. Run `python3 scripts/build_release.py --out dist` in a clean checkout of the **public** repo. The deterministic script checks required files, 31 sections, basic secret patterns, UTF-8 and the LICENSE/status gate. It writes `mads-standard-v2.0.6.zip`, the SHA256 sidecar and an embedded per-file manifest; confirm clean unzip/manifest.
3. Review a PR and merge approved standard content. Tag the exact commit `v2.0.6`; run the verified `.github/workflows/release-v2.yml` automated publisher (or GitHub Releases with exactly the same generated ZIP and `.sha256`) and verify the release/tag/assets.
4. Re-download as anonymous/public reader, verify SHA256 and that every file can be read **without signing into a private project**.
5. For each adopting project, copy the released files into its own repo, record project-local `docs/mads/MADS-VERSION-LOCK.yaml` with tag/SHA256/adoption commit, and run MADS G0–G13. Never update from mutable upstream `main` automatically.

## Independent project credentials

The **public standard requires no write/API key for reading**. The *new project* uses only its own private scoped API key/connector for **its own** repository. It does not need and must not receive the standard maintainer's token or any unrelated private project key.

## Limitations

A GitHub connector with Contents write may create files in an **existing accessible** repository; repository creation, access-configuration changes, GitHub Release asset publication or branch protection administration may not be available through that connector. In that case the authorized human completes only those UI steps. Do not claim the repo is public or a release has shipped until these checks really succeed.
