# STATE — Wo stehen wir (Snapshot, pro Run überschrieben)

_Stand: 2026-06-14_

## Funktioniert

- Phase 1–3 abgeschlossen: Tenancy, Status-Workflow + Dashboard, Resources +
  BlockNote, Multi-User-RBAC, MCP Read/Write-Tools, Einzel-Delete/Export, i18n.
- Security-Findings (Phase 1 + 2) alle **Closed**, Ampel Grün.
- Public-Switch-Vorbereitung: LICENSE.md (FSL-1.1), CONTRIBUTING.md, SECURITY.md;
  Notion-Entkopplung; LLM-Standards-Schicht (`docs/standards/`, `AGENTS.md`,
  `.claude/context/`).
- Lokale Verifikation grün: ruff, mypy strict (256 Dateien), pytest
  (358 passed / 177 skipped ohne DB).

## In Arbeit

- LLM-Optimierung / Standards-Materialisierung (dieser Run) — PR offen.

## Bekannte Probleme

- **CI-Runner-Infra defekt:** alle GitHub-Actions-Jobs scheitern in ~2 s,
  `runner_id=0`, keine Logs → mutmaßlich erschöpfte **Actions-Minuten / Billing**
  des privaten Repos. Nicht im Code behebbar. **Public-Flip löst es** (Actions ist
  für öffentliche Repos frei/unbegrenzt).
- E2E-Gate bleibt Soft, bis die CI-Infra steht.

## Nächste Schritte (nicht-Code, manuell beim Owner)

1. CI-Billing klären **oder** direkt auf Public flippen.
2. GitHub-Settings: Description, Topics, Issues/Discussions/Security-Advisories,
   Branch-Protection (CI-grün-Required erst nach CI-Fix).
3. CLA-Assistant aktivieren.
4. Visibility Private → Public (finaler Flip durch den Owner).
