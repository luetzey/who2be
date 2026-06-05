# ADR-0012 — MCP-Write-Tools sind post-MVP

- Status: Superseded durch ADR-0030 (2026-06-05)
- Datum: 2026-05-26
- Kontext: Who2Be MVP (PROJ-19), Plan-Review 2026-05-26
- Bezug: ADR-0005 (MCP als HTTP-Client); abgeloest durch ADR-0030
  (MCP-Write-Tools), nachdem beide Re-Evaluation-Trigger erfuellt waren

## Kontext

Der MCP-Server exponiert heute nur Read-Tools: `ping`, `get_persona`,
`list_playbooks`, `fetch_playbook`. Es gab keine schriftliche
Begruendung, warum keine Write-Tools (`create_persona`,
`update_persona_version`, `link_playbook`, …) existieren. Ohne diese
ADR waere es nur eine Frage der Zeit, bis ein Write-Tool unter
"praktisch waere doch" reinwaechst.

## Optionen

- **A — Status quo: nur Read-Tools im MCP.** Brainstormer-Use-Case
  braucht nur Read; Schreibvorgaenge laufen ueber Web-UI / direktes
  REST. Klare Vertrauens-Grenze: Agent kann lesen, nicht persistieren.
- **B — Write-Tools im MCP zulassen.** Agent koennte
  Selbstmodifikation der eigenen Persona/Playbooks anstoßen
  (z.B. iteratives Refinement). Aber: jeder Write-Pfad eines Agenten
  ist ein potentieller Prompt-Injection-Vektor, der durch eine
  veraenderte Persona spaeter wieder gelesen wird (Persistence-Layer-
  Injection). Erfordert Audit-Layer und Owner-Bestaetigung.

## Entscheidung

**A — Read-only fuer den MVP.**

Das Brainstormer-Use-Case (MS-4) braucht keine Schreibvorgaenge ueber
MCP. Schreibwege bleiben:

- Web-UI fuer Menschen.
- REST direkt fuer Skripte (mit API-Token, MS-4 B2 Import-Skript).

Damit ist die Vertrauens-Grenze klar: Was ein Agent ueber MCP sieht,
hat **immer** ein Mensch oder ein verifiziertes Skript persistiert.

## Re-Evaluation-Trigger

Diese Entscheidung ist neu zu pruefen, wenn:

1. **Self-Refinement-Use-Case** entsteht (Agent soll eigene
   Playbook-Version vorschlagen). Dann mit explizitem
   Approval-Flow (z.B. Persona-Status `draft` mit Web-Review-
   Schritt vor `published`).
2. **Multi-User-Hosting** aktiviert wird — dann zuerst
   Owner-Scoping und Audit-Log fuer MCP-Writes, bevor Tools
   erscheinen.

Bei Trigger: neue ADR mit Approval-Flow-Design, Audit-Schema und
Rate-Limiting-Erweiterung. Diese ADR (0012) wird auf "Superseded"
gesetzt.

## Konsequenzen

- `apps/mcp/src/who2be_mcp/server.py` bleibt explizit Read-only —
  Pull-Request mit Write-Tool wird gegen diese ADR gepruefbar.
- Brainstormer-Migration (MS-4 B2) ist ein REST-Skript, nicht
  MCP — konsistent mit dieser Grenze.
- Kein Audit-Layer noetig fuer den MVP — Schreib-Audit lebt
  implizit ueber `created_by` in Versionen und Web-UI-Bedienspuren.
</content>
</invoke>