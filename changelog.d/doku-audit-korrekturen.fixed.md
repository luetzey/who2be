- Doku-Korrekturen aus dem Doku-Audit: falsche MCP-Tool-Zahl, drei
  `workspace_quota`-Lücken in der Metadaten-Konvention, veralteter
  Branch-Protection-Status, toter Plan-Link, veraltete ADR-Zahl, eine zweite
  DoD-Kette und ein unhaltbarer Vollständigkeitsanspruch.

  Die MCP-Tool-Zahl stand an vier Stellen auf 81, der Code registriert 83
  (`packages/models/tests/test_tool_requirements.py#test_mapping_covers_all_registered_server_tools`);
  korrigiert in `ROADMAP.md` und zweimal in `.claude/context/STATE.md`, dort
  wandern die Summanden 58 + 23 auf 58 + 25 mit. Die vierte Stelle in
  `CLAUDE.md` bleibt offen — die Datei ist schreibgeschuetzt.

  `docs/licensing/plans.md` nennt sich Single Source of Truth für Tarife,
  kannte `workspace_quota` in der Metadaten-Konvention aber nicht — obwohl
  `packages/billing/src/who2be_billing/plans.py#Plan.metadata` den Schlüssel
  schreibt und
  `packages/billing/src/who2be_billing/mollie.py#metadata_to_entitlement` sowie
  `packages/billing/src/who2be_billing/webhook.py#map_event_to_entitlement`
  ihn lesen. Nachgetragen in Tabelle und Beispiel-JSON; der Rückfall-Absatz
  behauptete für einen fehlenden Schlüssel „unbegrenzt", während
  `apps/api/src/who2be_api/licensing/entitlement.py#effective_workspace_quota`
  in der Cloud auf den
  Tarifwert zurückfällt — so gelesen hätte eine gekündigte Organisation
  unbegrenzt Workspaces anlegen dürfen.

  `docs/branch-protection-main.md` trug „Vorschlag. Nicht angewendet.",
  während das Ruleset `16707501` seit 2026-09-22 aktiv ist (`pull_request`,
  `required_status_checks` mit `all-green`, `bypass_actors` leer); der Index in
  `docs/README.md` wiederholte die falsche Aussage und nennt jetzt zusätzlich
  `docs/auto-merge-agenten.md`, das dort fehlte.

  Außerdem: der zweifache Link auf `.claude/plans/…shiny-lollipop.md` in
  `docs/frontend/design-language.md` gestrichen (Verzeichnis heißt
  `.claude/plan/`, die Datei existierte nie), ADR-Zahl in `docs/README.md` von
  49 auf 52, die zweite und kürzere DoD-Kette in `docs/architecture.md` durch
  den Verweis auf `CONTRIBUTING.md` §Definition of Done ersetzt, und
  `docs/frontend/component-map.md` nimmt den Vollständigkeitsanspruch zurück
  (gelistet sind 5 von 18 `components/data/`-Bausteinen).
