# Plan: Builder-Agent versteht das Sprach-Feature (Nachzug zu ADR-0045)

## Context

Nach dem Merge von PR #357 („ein Element, eine Sprache", ADR-0045) wurde
geprüft, ob der Builder-Agent die Sprache setzen/ändern kann und ob er das
Feature versteht. Befund:

- **Technisch vollständig.** `locale` ist in allen fünf `create_*`- und allen
  fünf `update_*`-MCP-Tools ein LLM-sichtbares Feld (Property im
  `data`-Objekt); Default = Workspace-Sprache (`_default_content_locale`,
  `apps/mcp/.../server.py:879-892`), Sprachwechsel via `update_*.locale`,
  `'fr'` scheitert an der Pydantic-Validierung. Read-Tools liefern `locale`
  als Top-Level-Metadatum.
- **Inhaltlich blind.** In ALLEN ausgerollten Builder-Inhalten existiert genau
  EIN Satz zum Feature: `builder_playbook_persona_body.json`, Block
  `pb-persona-li-3`. Die Konventions-Resource (laut eigener Description
  „Single-Source fuer die Builder-Playbooks") hat keinen Sprach-Abschnitt;
  Playbook-/Resource-/Agent-/External-Tool-Anlage erwähnen Sprache nicht; der
  Drift-Check prüft keine Sprach-Konsistenz; Persona (identity/allowed/
  forbidden/Modi) hat keinen Sprach-Bezug; nirgends steht, dass der Inhalt
  eines Elements in dessen Sprache zu verfassen ist.
- **Aktiver Widerspruch.** `agent_builder_body.json` Block `ab-p8` („…nutze
  die gleiche Sprache wie der Nutzer.") und `customer_support_body.json`
  Block `cs-p6` kollidieren mit der harten Renderer-Injektion „Antworte auf
  Deutsch." (`services/agent_language.py`), deren Docstring fälschlich
  annimmt, die Template-Bodies seien sprachneutral.
- **Schema-Lücke.** Die `locale`-Felder der fünf `*Create`/`*Update`-Modelle
  haben kein `Field(description=…)` und kein Enum — das LLM sieht nur
  `locale: string | null`; die Semantik steht nur in den Tool-Docstrings.
- `whoami` liefert die Workspace-Sprache nicht; es gibt kein
  `get_workspace`-Tool (`client.get_workspace()` ist interner Helper).

**User-Entscheidungen (2026-07-25):**
1. **Antwortsprache:** Element-Sprache ist Vorgabe, der Nutzer kann sie
   kippen — Injektion wird weich formuliert, widersprüchliche Template-Prosa
   entfällt.
2. **Builder-Wissen:** volle Nachrüstung (Konventions-Resource + alle
   Anlege-Playbooks + Drift-Check + Persona), DE und EN.

## Arbeitspakete

Alle Content-Änderungen gelten **paarweise DE + EN** (`repositories/*.json`
und `repositories/en/*.json`) mit **identischen Block-IDs und Struktur** —
`apps/api/tests/test_builder_content.py` prüft die Pack-Parität, die
Struktur-Parität der Sidecars muss erhalten bleiben.

### WP-A — Antwortsprache: weiche Vorgabe + Kollision auflösen
- `apps/api/src/who2be_api/services/agent_language.py`: Anweisungs-Map neu
  formulieren, z. B. DE „Standard-Antwortsprache ist Deutsch. Schreibt der
  Nutzer in einer anderen Sprache, folge seiner Sprache." / EN analog.
  Docstring korrigieren (Annahme „Bodies sind sprachneutral" ist falsch →
  Regel: Sprachaussagen gehören NICHT in Template-Bodies).
- Widersprüchliche Prosa entfernen: `agent_builder_body.json` `ab-p8` und
  `customer_support_body.json` `cs-p6` (+ EN-Pendants) — Satzteil zur
  Sprachwahl streichen, Rest des Blocks unverändert (Blockanzahl/IDs bleiben).
- Tests in `apps/api/tests/test_agent_language.py` + Renderer-Tests auf die
  neue Formulierung ziehen.

### WP-B — Konventions-Resource: Sprach-Abschnitt
- `builder_resource_conventions_body.json` (DE + EN): neuer Abschnitt
  `res-conv-h-sprache` (+ Body-Blöcke, IDs im Schema der Nachbarn) mit den
  verbindlichen Regeln: ein Element = eine Sprache; Default =
  Workspace-Sprache, `locale` nur bei bewusster Abweichung setzen; **Inhalt
  in der Sprache des Elements verfassen** (Name, Description, Body, Trigger,
  Tags); Sprachwechsel via `update_*.locale` (Historie behält alte Werte);
  Sprache eines Elements aus dem `locale`-Feld der Read-Antworten ablesen.
  Platzierung nach `res-conv-h-naming` (thematisch: Benennung/Verfassen).

### WP-C — Playbooks + Persona
- Fünf Anlege-Playbooks (`persona`, `playbook`, `agent`, `external_tool`
  sowie der Resource-Pfad) bekommen die Sprache im Vorschlags- bzw.
  Create-Schritt: knapper Zusatz „Sprache = Workspace-Sprache, außer der
  Nutzer will bewusst abweichen; Inhalt in dieser Sprache verfassen" mit
  Verweis auf den neuen Konventions-Abschnitt. `pb-persona-li-3` ist bereits
  korrekt und dient als Vorlage.
- `builder_playbook_consistency_body.json` (DE + EN): Sprach-Konsistenz als
  Prüfpunkt im Drift-Sweep (Element-Sprache vs. tatsächlich verfasster
  Inhalt; Ausreißer gegenüber der Workspace-Sprache melden, nicht
  automatisch ändern — Kurator-Prinzip).
- `builder_persona_content.json` (DE + EN): Erlaubt-Liste um den
  Sprach-Aspekt ergänzen (Sprache beim Anlegen setzen/über `update` wechseln);
  Modi bleiben unberührt.
- `BUILDER_CONTENT_VERSION` in
  `repositories/workspace_repository.py` auf **13** (Content-Änderung in
  beiden Sprachen; Boot-Sync verteilt an Bestands-Workspaces).

### WP-D — Selbstdokumentierende Schnittstelle
- `packages/models/.../{persona,playbook,resource,external_tool,
  system_prompt_template}.py`: `Field(description=…)` an den fünf
  `locale`-Feldern (Create + Update) — kurze, für ein LLM lesbare Semantik
  inkl. der erlaubten Werte `de`/`en`. Damit steht die Regel im
  Tool-Input-Schema, nicht nur im Docstring.
- `WhoAmIRead.content_locale` (`packages/models/.../whoami.py`) + Befüllung
  im API-`whoami`-Pfad und im MCP-Tool: der Agent kann die Workspace-Sprache
  direkt erfragen, statt sie aus Elementen zu erschließen. Docstring des
  `whoami`-Tools ergänzen.
- Update-Docstrings der fünf `update_*`-Tools um den Hinweis erweitern, wie
  die aktuelle Workspace-Sprache zu erfahren ist (`whoami`).

## Kritische Dateien

- `apps/api/src/who2be_api/services/agent_language.py`
- `apps/api/src/who2be_api/repositories/builder_resource_conventions_body.json`
  (+ `en/`), `builder_playbook_{persona,playbook,agent,consistency,
  external_tool,maintenance}_body.json` (+ `en/`),
  `builder_persona_content.json` (+ `en/`), `agent_builder_body.json` (+ `en/`),
  `customer_support_body.json` (+ `en/`)
- `apps/api/src/who2be_api/repositories/workspace_repository.py`
  (`BUILDER_CONTENT_VERSION`)
- `packages/models/src/who2be_models/{persona,playbook,resource,
  external_tool,system_prompt_template,whoami}.py`
- `apps/mcp/src/who2be_mcp/server.py` (whoami-Tool + Update-Docstrings)

## Verifikation

- `uv run pytest --cov --cov-fail-under=85`, `uv run ruff check .`,
  `uv run ruff format --check .`, `uv run mypy .` — inkl.
  `test_builder_content.py` (Pack-/Sidecar-Parität), `test_agent_language.py`
  (neue Formulierung DE/EN), Sync-Tests (Content-Version 13 verteilt beide
  Packs, kein Cross-Locale-Bleed), `whoami`-Tests (API + MCP).
- Struktur-Parität DE↔EN der geänderten Sidecars per Skript im Scratchpad
  prüfen (gleiche IDs/Typen/Blockanzahl), wie bei den Übersetzungen in #355.
- Stichprobe am gerenderten Prompt: Agent auf einem DE-Template →
  Injektion nennt Deutsch als Standard und erlaubt den Wechsel; kein
  widersprüchlicher Satz mehr im Body.

## Vorgehen

Ein Issue je WP (Folge-Issues zu #348–#356), Umsetzung auf einem neuen
`claude/`-Branch ab aktuellem `main` (PR #357 ist gemergt — kein Aufsetzen
auf der gemergten Historie), Sub-Agents datei-disjunkt (WP-A/WP-D Code,
WP-B/WP-C Content), danach Konsolidierung + DoD + Draft-PR.
