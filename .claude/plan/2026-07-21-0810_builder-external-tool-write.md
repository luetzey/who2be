# Plan — Builder kann External Tools konfigurieren (Policy + Seed-Content)

- Datum: 2026-07-21
- Branch: `claude/session-9nzi2n`
- Kontext: Gap-Analyse dieser Session — der Builder hat serverseitig alle
  Voraussetzungen (ADR-0043: 6 MCP-Tools, SSoT-Mapping ADR-0042), aber seine
  Policy traegt kein `external_tool_write`, und kein Builder-Seed-Content
  (Playbooks/Konventions-Resource) erklaert den External-Tool-Workflow.
  Folge: `create/update/restore_external_tool` sind fuer den Builder unsichtbar
  (403 bei Direktaufruf), und via `is_within`-Eskalations-Guard
  (`agent_service.py:_guard_policy_escalation`) kann er das Recht auch keinem
  anderen Agenten vergeben.

## Ziel

Der Builder (und Builder Lite) kann External-Tool-Bindungen anlegen, pflegen
und promoten UND das Schreibrecht per Tool-Policy an andere Agenten
weiterreichen; ein neues Builder-Playbook + Konventions-Sektion briefen ihn
auf den Workflow. Memory-Kuration bleibt bewusst UI-only (Owner-Entscheidung
aus der Analyse — Human-in-the-loop-Schleuse).

## Mechanik (keine SQL-Migration)

Seit Content-Stand 6 ist die Builder-`tool_policy` Teil des kanonischen
Builder-Stands und wird vom Start-Sync (`sync_managed_builder_content`)
verteilt; Konvention seit 0057: Sidecar/`_BUILDER_PLAYBOOKS`/Konstanten
anpassen + `BUILDER_CONTENT_VERSION` hochzaehlen — keine Spiegel-Migration.

## Arbeitspakete (ein zusammenhaengender Task, keine Sub-Agents)

1. **Policy:** `_builder_tool_policy()` += `external_tool_write=True`
   (`workspace_repository.py`); Versions-Kommentar v11;
   `BUILDER_CONTENT_VERSION = 11`. Der Policy-Sync verteilt an
   Builder + Builder-Lite aller Bestands-Workspaces.
2. **Neues Builder-Playbook** „External Tool anlegen & pflegen":
   - Sidecar `builder_playbook_external_tool_body.json` (BlockNote-Array,
     Struktur analog `builder_playbook_persona_body.json`): Zweck,
     Trigger-Stichworte, Prozedur (Create / Update+Rebind / Retire),
     Anti-Patterns, Verweis auf die Konventions-Resource (fetch_resource).
     Inhaltlich nach ADR-0043: Alias unveraenderlich (Slug 1–64,
     workspace-eindeutig, 409), rein instruktiv (keine URLs/Credentials),
     Content-Felder (display_name, mcp_server_name, tool_names, usage_notes,
     fallback_note), Status-Workflow draft→review→active,
     `tool-ref`-Pill (target_id = Alias) in Playbooks/Personas/Templates.
   - Eintrag in `_BUILDER_PLAYBOOKS` (Trigger-Hygiene: keine generischen
     Woerter; z. B. „external tool anlegen, tool-bindung anlegen,
     tool-bindung pflegen, tool anbinden, tool wechseln, tool-ref").
3. **Konventions-Resource:** neue Sektion „External Tools (Tool-Bindungen)"
   in `builder_resource_conventions_body.json` (Alias-Vertrag,
   Instruktiv-Grenze, Rebind-Muster „Content tauschen, Alias behalten",
   tool-ref-Konvention, Policy-Vergabe an Fach-Agenten inkl. is_within).
4. **Sync-Luecke schliessen:** Der Insert-missing-Zweig fuer neue Playbooks
   legt in Bestands-Workspaces Row+v1+Persona-Link an, aber KEINEN
   `playbook_resource_link` auf die Konventions-Resource (die Links aller
   Playbooks entstehen nur im Resource-Insert-missing-Zweig, der bei
   vorhandener Resource nicht laeuft). Fix: im Playbook-Insert-missing
   zusaetzlich die Resource per (workspace_id, name) aufloesen und den Link
   `link_scope='resource'` setzen (ON CONFLICT DO NOTHING; fehlt die
   Resource noch, uebernimmt der nachgelagerte Resource-Zweig alle Links).
5. **Tests:**
   - `test_seed_builder_agent.py`: Playbook-/Link-Zaehler 5→6,
     `external_tool_write`-Asserts fuer Builder + Lite.
   - `test_builder_content_sync.py`: Insert-missing-Test um den
     Resource-Link des neuen Playbooks erweitern; Policy-Sync-Test um
     `external_tool_write`; ggf. Namens-/Zaehler-Fixtures nachziehen.
   - `test_whoami.py` und weitere Treffer auf Builder-Capabilities pruefen.
   - Volle Gates: `uv run pytest --cov --cov-fail-under=85`, ruff, mypy.
6. **Doku:** DECISIONS.md (Builder erhaelt external_tool_write; Memory-
   Kuration bleibt UI-only), STATE.md, `.claude/plan/README.md`-Eintrag.

## Out of Scope

- MCP-Tools fuer Memory-Triage/-Guard (bewusst UI-only, Owner-Schleuse).
- `memory_mode='auto'` fuer den Builder.
- Gateway-/Proxy-Ausbau (ADR-0043 Stufe C).

## DoD

Alle Python-Gates lokal gruen (pytest inkl. Integration soweit DB verfuegbar,
ruff, mypy); PR mit Change-Log + Plan-Verweis.
