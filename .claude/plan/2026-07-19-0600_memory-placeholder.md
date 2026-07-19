# Plan: Placeholder-Kind `memory` — modus-bewusster Gedächtnis-Hinweis

- Datum: 2026-07-19
- Branch: `claude/autonomous-code-agent-setup-iz6ydx` (neu ab main, Folge zu
  PR #324/#325)
- Quelle: Builder-Briefing (Phase-4-Hand-Off, User-Auftrag 2026-07-19); Basis
  ADR-0044.

## Ziel

Template-Autoren (und die Seed-Templates) können den Gedächtnis-Hinweis
explizit positionieren: neuer Placeholder-Kind `memory` rendert beim
Agent-Rendern den zum `memory_mode`/`memory_directive` des Agenten passenden
Textblock. `off` rendert leer (kein Miss, nie ein Fehler).

## Abweichungen vom Briefing (verifiziert gegen Repo-Stand)

1. **Briefing-Punkt 3 (Tool-Gating) entfällt** — seit #324 vollständig
   implementiert (ADR-0042-Mapping: tools/list UND tools-overview filtern auf
   memory_mode). Kein Widerspruch Text ↔ Tools möglich.
2. **„Mit Freigabe"-Copy korrigiert:** Das Briefing beschreibt eine
   Chat-Bestätigung vor jedem Schreiben („Ohne Freigabe wird nichts
   geschrieben") — real ist die serverseitige Schleuse (save → `pending`,
   Freigabe durch den Workspace-Besitzer in der UI). Copy übernimmt Ton/
   Struktur des Builders, benennt aber die echte Mechanik.
3. **Doppel-Render-Schutz statt Entweder-Oder:** Seit #324 hängt
   `tools-overview` den Gedächtnis-Hinweis automatisch an. Damit Templates
   mit explizitem `memory`-Placeholder den Hinweis nicht doppelt bekommen:
   der Renderer scannt den Template-Body vor der Expansion auf
   `kind='memory'` und setzt `RenderContext.has_explicit_memory`;
   `tools-overview` unterdrückt dann seinen Auto-Append. Templates OHNE den
   Placeholder rendern unverändert (Abwärtskompatibilität wie im Briefing
   gefordert — inklusive Bestands-Workspaces, deren Default-Templates nicht
   synchron aktualisiert werden können, weil sie user-editierbar sind).

## Entscheidungen zu den offenen Briefing-Fragen

- **Position:** direkt nach dem `tools-overview`-Block (Briefing-Vorschlag).
- **`off`:** komplett leer — ein Hinweis auf ein nicht existierendes
  Werkzeug wäre Prompt-Rauschen.
- **Muss/Soll:** nur Textstärke (Overlay-Zeile); kein Tool-Gating — die
  Direktive ist kein Recht (ADR-0044).

## Umsetzung

1. **Resolver** `placeholders/resolvers/memory.py`: `MemoryPromptResolver`
   + öffentliche Funktion `memory_prompt_block(policy) -> str` als EINZIGE
   Quelle der Modus-/Direktive-Texte. Ersetzt `memory_note` in `tools.py`;
   auch die Laufzeit-Sektion in `PersonaService._memory_runtime_section`
   nutzt sie (ein Wortlaut überall).
2. **Renderer:** `RenderContext.has_explicit_memory: bool = False`;
   `render_template_body` scannt Blocks (inkl. children/inline) auf
   `kind='memory'` und setzt das Flag vor der Expansion.
3. **tools-overview:** Auto-Append nur noch `if not ctx.has_explicit_memory`.
4. **Registry + Katalog:** REGISTRY-Eintrag `memory`, `kind_catalog`-Eintrag
   (target_id ungenutzt, nie Miss), Export.
5. **Seed-Templates:** `memory`-Placeholder-Block nach `tools-overview` in
   agent_builder, conversational_coach, customer_support, knowledge_worker,
   workflow_starter (agent_builder_lite hat kein tools-overview — bewusst
   ausgelassen). `BUILDER_CONTENT_VERSION` 8→9 (managed agent_builder wird
   per Start-Sync verteilt; die 4 Default-Templates erreichen neue
   Workspaces via Seed, Bestand behält den Auto-Append-Fallback).
6. **Web (Sub-Agent, apps/web):** `PlaceholderBlock`-Kind-Union + Pill-Stil,
   Slash-Menü-Eintrag „Gedächtnis", Tests.
7. **Tests:** Resolver-Matrix (4 Modi × 2 Direktiven, off leer + kein Miss),
   Suppressions-Test (Template mit Placeholder → tools-overview ohne
   Anhang; ohne Placeholder → Anhang wie bisher), Katalog-Eintrag,
   bestehende Wortlaut-Assertions auf die neue Copy umgestellt.

## Akzeptanzkriterien (aus dem Briefing, angepasst)

- auto rendert Automatisch-Block; off rendert nichts und keinen Miss.
- read_only enthält keine Schreib-Aufforderung; suggest benennt die
  Pending-Schleuse (Freigabe durch den Workspace-Besitzer).
- required/recommended ändert nur die Verbindlichkeits-Zeile.
- Kein Modus verspricht Tools, die der Agent nicht sieht (durch geteilte
  SSoT strukturell garantiert).
- Templates ohne Placeholder rendern unverändert (inkl. Auto-Append).

## DoD

ruff/format/mypy, volle pytest-Suite mit Coverage-Gate; Web lint/tsc/
test:coverage/build; PR (Draft) + Subscription.
