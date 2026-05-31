# Agent-Invocation-Achsen

Zwei orthogonale Wege, wie ein Agent ein Playbook zur Laufzeit nutzt.

## Applied vs. Triggered

| Achse | Mechanik | Laufzeit-Verhalten |
|---|---|---|
| **Applied** (immer geladen) | `{{playbook}}`-Pill im System-Prompt-Template | Der Resolver bettet die aktive Version bei jedem `fetch_agent`-Aufruf fix ein — kein Trigger noetig, kein MCP-Call. |
| **Triggered** (on-demand) | `persona_playbook`-Link + denormalisiertes `triggers`-Feld | Der Agent ruft `list_triggers()` → Trigger-Match → `fetch_playbook(id)` nur wenn ein Keyword auftaucht. |

**Wichtig:** Applied-Playbooks fuehren typischerweise kein `triggers`-Feld und
erscheinen deshalb nicht in der `list_triggers`-Discovery-Liste (Test: `test_list_triggers_excludes_triggerless_playbook`). Die Trennung ist damit sauber — kein doppeltes Laden.

## Composite-aware Pill (B1)

Zeigt eine Applied-Pill auf ein **Composite-Playbook** (hat Kinder in
`playbook_composition`), rendert der `PlaybookResolver` automatisch die
Orchestrierungs-Sequenz:

1. Composite-Body zuerst.
2. `## Ablauf (Sub-Playbooks)` — nummerierte Liste der aktiven Kinder, geordnet
   nach `position`. Inaktive oder geloeschte Kinder werden uebersprungen.

Atomic-Pills bleiben unveraendert (nur eigener Body).

## Agenten-Reise (Kurzfassung)

1. **Boot:** `fetch_agent` → gerenderter System-Prompt mit expandierten Pills
   (applied Playbooks + Tools-Uebersicht + Datum bereits inline).
2. **Persona:** `get_persona()` fuer volles Profil + Modi (C4).
3. **Prozess:** `list_triggers()` → Match → `fetch_playbook()` (inkl.
   Composite-Sequenz via `composed_playbooks`-Feld).
4. **Wissen:** `list_resources(tag?)` → `fetch_resource()`.

Verweis: ADR-0024 (Composite-Playbooks), Plan `2026-05-31-1630_composite-applied-modi.md` Track B.
