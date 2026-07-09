# ADR-0040 — Builder darf System-Prompt-Templates verfassen (nicht aktivieren)

- Status: Accepted (umgesetzt: Capability `system_prompt_write` +
  System-Prompt-MCP-Tools + Web-Policy-Toggle, PR #266;
  Proposed → Accepted 2026-07-08)
- Datum: 2026-06-27
- Kontext: Der Meta-Agent „Builder" soll den gesamten Agent-Erstellungs-/
  Anpassungs-Workflow fahren — inkl. des System-Prompts eines Agenten.
- Bezug: ADR-0030 (MCP-Write-Tools), ADR-0012 (Prompt-Injection-Risiko),
  ADR-0023 (RBAC / Per-Agent-Policy), ADR-0009 (JSONB-Schema-Evolution)

## Kontext

System-Prompt-Templates sind ein versioniertes Aggregat
(`agent.system_prompt_template_id`), aber bisher **nicht über MCP verwaltbar**:
es gibt REST-Endpunkte (CRUD/versions/transition/diff), aber keine MCP-Tools, und
agent-gebundene Tokens sind von **Template-Transitionen komplett gesperrt**
(`version_status.py`, `actionable_by="none"`). Begründung der Sperre: ein Agent,
der seinen eigenen (oder einen fremden) System-Prompt scharfschalten kann,
schreibt die ihn steuernde Instruktion ohne menschliche Freigabe um — der
schärfste Prompt-Injection-/Selbstmodifikations-Vektor.

Der Builder kann dadurch heute keinen System-Prompt anlegen/anpassen — der
Agent-Erstellungs-Workflow bleibt unvollständig.

## Entscheidung

Der Builder (und allgemein jeder Agent, dem es der Owner gewährt) darf
System-Prompt-Templates **lesen, erstellen, anpassen und zur Review einreichen
(draft→review)** — aber **nicht aktivieren oder zurückziehen** (→active/→inactive).
Das Scharfschalten bleibt eine menschliche/Admin-Handlung.

- **Neue Capability `system_prompt_write`** in `AgentToolPolicy` (Default
  `False`, secure-by-default). Sie gated über MCP die Mutationen
  create/update/restore **und** die draft/review-Transitionen.
- **Die Aktivierungs-Sperre bleibt unverändert hart:** für agent-gebundene
  Tokens liefert jeder Template-Übergang nach `active`/`inactive` weiterhin 403
  `actionable_by="none"` — keine Capability schaltet das frei. Die Grenze aus
  ADR-0012 bleibt damit exakt erhalten; verschoben wird nur das *Authoring*
  hinter die Grenze.
- **Reads** (`list_system_prompts`, `get_system_prompt`, Versions/Diff über die
  generischen Track-1-Tools) sind technisch workspace-offen wie bisher; im
  System-Prompt werden die Tools über die `system_prompt_write`-Capability
  angezeigt (Toolbox nur für Autoren).
- **Service-Tightening:** create/update/restore erhalten zusätzlich zum
  bestehenden `require_role(editor)` ein `require_capability(system_prompt_write)`
  — bisher waren sie für agent-gebundene Tokens nur rollen-gegated. Für
  ungebundene Tokens (Web-UI/Mensch) ist `require_capability` ein No-Op; das
  Web-Verhalten ändert sich nicht.
- **Builder-Seed** erhält `system_prompt_write=True`; Bestands-Builder werden per
  idempotenter Migration (`0052`, Muster ADR-0009/Migration 0051,
  `slug='agent-builder'`) nachgezogen.

## Warum nicht volle Autonomie (Option B verworfen)

Dem Builder auch das Aktivieren zu erlauben (`promote_system_prompt`) würde die
deliberate Injection-Grenze öffnen: ein kompromittierter oder fehlgeleiteter
Builder könnte den steuernden System-Prompt eines beliebigen Agenten live
schalten. Das Vier-Augen-Prinzip (Agent verfasst, Mensch promotet, ADR-0023)
ist hier kein Hindernis, sondern der Sinn der Funktion.

## Konsequenzen

- `tool_policy.py`: neue Capability + Feld + `is_within`-Erweiterung. Kein
  Schema-Migrationszwang (JSONB, ADR-0009).
- `version_status.py`: Sonderzweig für `system_prompt_template` im
  Transition-Gate (review erlaubt mit Cap, active/inactive hart gesperrt).
- Neue MCP-Tools (Reads + Writes); 403 mit klarer ToolError-Meldung beim Versuch
  zu aktivieren.
- `tools.py`-Register: Tool-Übersicht zeigt die neuen Tools policy-gated.
- Web-UI-Toggle für die Capability folgt mit Track 4 (Policy-Editor); der Builder
  funktioniert vorher über Seed/Backfill.
