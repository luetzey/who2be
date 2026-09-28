# Security Policy

## Reporting a Vulnerability

Please do **not** report security vulnerabilities through public GitHub
issues, pull requests, or discussions.

Report privately through **GitHub Private Vulnerability Reporting**: open the
[Security tab](https://github.com/luetzey/who2be/security) and choose
"Report a vulnerability", or go straight to the
[advisory form](https://github.com/luetzey/who2be/security/advisories/new).
The report is visible only to you and the maintainers until an advisory is
published.

If you cannot use GitHub, email <luetzey@gmail.com> instead.

Where possible, please include in your report:

- the affected component (`apps/api`, `apps/mcp`, `apps/web`,
  `packages/models`, deployment/infra) and version/commit,
- a description of the vulnerability and its impact,
- steps to reproduce (if possible),
- a suggested fix, if you have one.

## Disclosure Policy

- We usually confirm receipt of a report within **3 business days**.
- We work on a fix and coordinate publication with you.
- A **coordinated disclosure period of 90 days** applies from receipt of the
  report: after this period, or once a fix is available (whichever comes
  first), details may be made public.
- We ask that you do not share discovered vulnerabilities publicly before
  the coordinated publication.

## Scope

This policy applies to the code in this repository (backend API, MCP server,
web UI, shared models, and the deployment configuration). For
vulnerabilities in third-party dependencies, please also report to the
respective upstream project.
