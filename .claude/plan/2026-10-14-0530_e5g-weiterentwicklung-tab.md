# E5g: Agent-Tab „Weiterentwicklung“ (Karte t_9303d8c4)

Grundlage: Neuschnitt-Spec `phase-e-web-neuschnitt-2026-10.md` §3.1–3.5, §3.7, §3.8,
Zuschnitt §7.1 Zeile E5g (ersetzt den alten Karteninhalt „Abschnitt Gespräche“,
PM 2026-10-10). Verlauf/Generationen (§3.6) gehört nach E5k.

## Completion-Condition
- Flag `EVOLUTION_TAB_ENABLED` entfernt, Tab sichtbar, `#sessions` → `?tab=evolution`.
- Tab-Zähler `cases_open + follow_ups_due` (editor), bei 0 / viewer keiner.
- Tab-Inhalt editor: Anleitung (`details`), `<ol>` ①–④, „Änderungen“ (offen, aus ≤ 10 Reviews), „Reviews“ (Cursor).
- viewer: nur ① + Erklärsatz, keine Requests an feedback-sessions/patterns. `role === null`: nichts, keine Requests.
- Kopf-Aktionen unverändert (Test).
- axe je Zustand eigenes `it()` (editor mit Daten, editor leer, viewer).
- `npx tsc -b`, lint, vitest (coverage), build, i18n:check grün; Fotos 1280/390 hell/dunkel + measure.json.

## Dateien (7, Grenze 8)
1. features/agents/pages/AgentDetailPage.tsx
2. features/agents/pages/AgentDetailPage.test.tsx
3. components/evolution/AgentEvolutionTab.tsx (neu; unter `components/`, weil das Cross-Feature-Gate `features/agents` → `features/evolution` verbietet, Muster `AgentMemoryCard`)
4. components/evolution/AgentEvolutionTab.test.tsx (neu)
5. i18n/locales/de.json
6. i18n/locales/en.json
7. changelog.d/web-agent-evolution-tab.added.md

## Entscheidungen im Rahmen der Spec
- Eine Quelle je Wert (PM 2026-10-14): Zahl in ④ und Tab-Zähler aus `useInboxCounts`, Fällig-Markierung je Review-Zeile aus `due_measure_count`; `followUp.ts` nur an der einzelnen Änderung.
- `useInboxCounts` läuft einmal in der Seite und wird an den Tab gereicht (kein zweiter Abruf).
- Reviews und Änderungen teilen die erste Seite `listSessions({agent_id}, {limit: 10})`.
- Versionsnummer im Änderungs-Titel entfällt: die Liste liefert nur `version_id`, eine Nummer kostete je Änderung einen Abruf.
- „betrifft auch“ entfällt (Spec erlaubt das ohne Platzhalter).
- „Review vorbereiten“ zeigt auf `/agents/:id/reviews/prepare` (E5f baut die Seite).

## Stand
- Erledigt: alle Punkte der Completion-Condition. tsc, lint (0 Fehler), vitest --coverage (262 Dateien, 2311 Tests), build, license:check, i18n:check grün.
- Fotos: `.shots/t_9303d8c4/` (8 PNG + measure.json, alle scrollWidth == clientWidth).
