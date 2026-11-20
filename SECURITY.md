# Security and isolation policy

This standard publishes only project-neutral text, configuration examples and optional export scripts. It must never contain access tokens, private keys, real personal or customer data, private repository histories, production signing roots, provider credentials, private incident logs or source artifacts from an adopting project.

- Every project grants its owner AI access **only to that project's own Git repository**; it does not need write or read access to MADS upstream if its release files have been vendored locally.
- Public upstream reads (HTTP GET) and private project writes are separate security domains. Never paste API tokens into a prompt or install a broad cross-project GitHub App to bypass missing standards access.
- Strong Git permissions require tested provider branch rules, scoped tokens or broker; a source SESSION_START message by itself is cooperative authorization only.
- External hosts, production credentials, CI providers with privileged runners and paid operations require separate explicit scope, approval and rollback.
- Report a suspected secret exposure privately to the repository owner using GitHub's private report/security contact when configured; do not file a public issue containing credentials.
- Verify release SHA256 and exact source files before adopting or updating MADS. A template is never evidence that an implementation works.

If project-only credentials cannot access a *private* standard, distribute a public sanitized MADS release, a local ZIP attachment, or pre-commit the standard into the project's own repo. Never share another private project's credential.
