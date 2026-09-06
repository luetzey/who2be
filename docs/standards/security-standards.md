# Security-Standards

Sicherheit ist Teil des Designs, kein nachgelagerter Schritt. Repo-spezifische
Befunde + Umsetzung: [`../security-findings.md`](../security-findings.md),
[`../security-findings-phase-2.md`](../security-findings-phase-2.md), ADR-0052
(loest ADR-0035 ab);
Security-Header zentral im [`../../deploy/hetzner/Caddyfile`](../../deploy/hetzner/Caddyfile).
Für Auth, DB-Zugriff, MCP-Tools und externe Inputs den Subagent
**`security-reviewer`** nutzen.

## Prinzipien

- **Security-First:** von Anfang an integrieren.
- **Zero-Trust:** keine implizite Vertrauensstellung zwischen Komponenten oder
  gegenüber Eingaben.
- **Eingaben validieren:** alle externen Eingaben an System-, API- und
  Modulgrenzen prüfen.
- **Server-seitige Validierung & Autorisierung:** jede Zugriffsprüfung
  server-seitig durchsetzen. Client-Validierung/UI-Guards sind UX, kein Schutz —
  dem Client nie vertrauen.
- **Secrets bleiben server-seitig:** keine Keys/Tokens/Credentials im Client-Code
  oder im Bundle; nur bewusst Öffentliches wird exponiert.
- **Tokens/Sessions in sicheren Cookies** (`httpOnly`/`Secure`/`SameSite`), nicht
  im Web-Storage (dort per XSS auslesbar). *(Repo-Ausnahme + Begründung:
  ADR-0052, die ADR-0035 ablöst.)*
- **Untrusted HTML sanitisieren** vor dem Einfügen; XSS-Oberfläche minimieren.
- **Security-Header auf genau einer Ebene** (Reverse-Proxy/Caddy), nicht doppelt:
  CSP, HSTS, X-Content-Type-Options, Referrer-Policy, Permissions-Policy,
  frame-ancestors.
- **fail-closed:** im Zweifel verweigern, nicht durchlassen (z. B. MFA-/AAL-Gate
  in der Cloud, ADR/QW-Härtung).
- **Security-ADRs:** sicherheitsrelevante Entscheidungen als ADR festhalten.

## Anti-Patterns

- Security am Ende angeflanscht; externe Eingaben ungeprüft; Secrets im Code/in
  Commits; implizites Vertrauen zwischen Komponenten; Zugriffsprüfung nur
  clientseitig; Auth-Tokens im Web-Storage; Fremd-HTML ohne Sanitizing;
  fail-open statt fail-closed.
