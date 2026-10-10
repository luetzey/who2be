# Navigation W2-b: Agent-Überblick (Aufgaben-Zeile, Kacheln, Arbeitsbereiche)

Karte: t_c4b3707b · Spec: navigation-transparenz-design-2026-10 §3.2 · Owner A2a/A6a
Basis: origin/main @ 67ee310a (W2-a1 Tabs, W2-a2 Klapp-Regel, W2-api A4/A6 gemergt).

## Outcome

Tab „Überblick“ der Agent-Seite zeigt von oben: Aufgaben-Zeile (nur > 0),
„Auf einen Blick“ (Kacheln als Links), darunter ab `lg` nebeneinander
Zusammensetzung und Arbeitsbereiche.

## Kacheln (Rollen nach Tabelle §3.2, Abweichungen begründet)

| Kachel | Quelle | Rolle | Ziel |
|---|---|---|---|
| Rückmeldungen offen | `countCases(agent)` open+reopened+triaged+in_progress | ab viewer (Server filtert eigene) | `/feedback?tab=cases&agent=` (Weiterentwicklung ist aus) |
| Feedback zu Bausteinen | `feedback-overview?agent_id&days=30` | **editor+** (PM-Entscheidung W2 in t_c84f1dd3: Endpunkt bleibt editor+) | `/feedback?tab=signals&agent=` |
| Gedächtnis | `countMemories({agent_id,status:active},[status,health])` | editor+ | `?tab=memory` |
| Muster | `listPatterns(agent)` | editor+ | `/feedback?tab=patterns&agent=` |
| Prüffälle | `listTestCases({agent_id,status:active})` | editor+ (Server verlangt editor) | `?tab=tests` |
| Nutzung | – | folgt in U4 | – |

- Rolle unbekannt (lädt): nur viewer-Kacheln.
- 0 → „0“ + „Noch keine“; Fehler je Kachel → „–“ + „Nicht verfügbar“, kein Banner.
- Prüffälle-Untertitel „zuletzt n/m bestanden (laut Client)“ braucht einen
  Report je Version; entfällt hier (Folge mit U4/W3), Kachel zeigt nur die Zahl.

## Aufgaben-Zeile

`InboxSummary` + `useInboxCounts(agent.id)`, Ziel `/inbox?agent=<id>`; bei 0,
Laden oder Fehler keine Zeile.

## Arbeitsbereiche

`GET /agents/{id}/work-areas` (A4). Je Bereich Icon, Name als Link, rechts
„eigener“ bzw. „geteilt · Lesen|Lesen & schreiben · +n Agenten“. Fuß-Hinweis,
Leerzustand nach §3.2/§9.

## Dateien (Budget 8 ohne Plan)

1. `apps/web/src/features/agents/components/AgentOverview.tsx` (neu)
2. `apps/web/src/features/agents/components/AgentOverview.test.tsx` (neu)
3. `apps/web/src/features/agents/pages/AgentDetailPage.tsx`
4. `apps/web/src/api/client.ts`
5. `apps/web/src/api/types.ts`
6. `apps/web/src/i18n/locales/de.json`
7. `apps/web/src/i18n/locales/en.json`
8. `changelog.d/t-c4b3707b-agent-overview.added.md`

## Verifikation

`npm run lint`, `npx tsc -b`, `npm run i18n:check`, `npm run test:coverage`,
e2e scroll-guard (mobile) soweit Stack lokal verfügbar; Fotos 1280/390 hell/dunkel
mit measure.json.
