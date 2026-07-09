# Engineering-Standards

Die stehenden, projektübergreifenden Engineering-Standards für Who2Be — als
self-contained Markdown, damit ein LLM das Projekt aus dem Repo allein versteht
und ohne Drift entwickelt.

Diese Dateien sind **generisch/prinzipien-orientiert**. Die **repo-spezifische
Konkretisierung** (konkrete Tools, Pfade, Werte) steht in [`../../CLAUDE.md`](../../CLAUDE.md)
und den Skills unter `.claude/skills/`. **Bei Konflikt gewinnt die repo-spezifische
Ebene.**

## Inhalt

| Standard | Datei | Repo-spezifische Quelle |
|---|---|---|
| Arbeitsmethode (Understand→Plan→Implement→Verify→Document) | [`engineering-method.md`](engineering-method.md) | `CONTRIBUTING.md`, `.claude/plan/` |
| Architektur, Design-Prinzipien, Clean-Code | [`coding-standards.md`](coding-standards.md) | `CLAUDE.md` §Code-Style, `.claude/skills/python-conventions`, ADR-0001/0002/0003 |
| Test-Strategie / TDD / Pyramide | [`testing-standards.md`](testing-standards.md) | ADR-0041 (Test-Strategie), `CONTRIBUTING.md` §DoD |
| Security (Zero-Trust, fail-closed, Auth, Header) | [`security-standards.md`](security-standards.md) | `docs/security-findings*.md`, ADR-0035, `deploy/hetzner/Caddyfile`, Subagent `security-reviewer` |
| Frontend (Design-System, Tokens, A11y) | [`frontend-standards.md`](frontend-standards.md) | `docs/frontend/design-language.md`, `.claude/skills/react-conventions` |
| Compliance + OSS-Lizenz-Hygiene | [`compliance-standards.md`](compliance-standards.md) | `docs/compliance/`, ADR-0033, `LICENSE.md` |

## Prinzip

> Jede Regel hat **genau einen** maßgeblichen Ort. Wo der Repo eine Regel bereits
> als ADR/Skill/Doc abdeckt, **verlinken** diese Dateien dorthin statt zu kopieren —
> damit keine zweite, driftende Wahrheit entsteht.
