# PROJECT — Wohin (Ziel-Anker)

**Mission:** Who2Be ist eine selbst-gehostete AgentDB für **versionierte Persona-
und Playbook-Verwaltung** — eine zentrale, versionierte Quelle der Wahrheit für
Agent-Persona, Playbooks, Resources und Composites, abrufbar per REST-API und MCP.

**Outcome:** Teams pflegen Personae/Playbooks/Resources versioniert (draft →
review → active → inactive), nutzen sie über MCP in beliebigen LLM-Clients und
verwalten Zugriff mandantenfähig (Org → Workspace → Rollen).

## Non-Goals (stoppt Scope-Drift)

- **Kein** allgemeines CMS / Wiki — der Fokus ist Agent-Persona/Playbook/Resource.
- **Kein** Chat-/Agent-Runtime-Host — Who2Be *speichert und liefert* Kontext, es
  *führt* keine Agents aus.
- **Kein** Vendor-Lock-in auf eine LLM — MCP-first, modellneutral.
- **Kein** Verzicht auf die On-Prem-Edition zugunsten Cloud — eine Codebase, zwei
  Build-Profile (ADR-0028/0029); Billing ist build-isoliert.

## Pointer

- Einstieg: [`../../README.md`](../../README.md), [`../../AGENTS.md`](../../AGENTS.md)
- Architektur-Blueprint: [`../../docs/architecture.md`](../../docs/architecture.md)
- Aktueller Stand: [`STATE.md`](STATE.md)

_Snapshot: 2026-06-14. Update nur bei Ziel-Änderung._
