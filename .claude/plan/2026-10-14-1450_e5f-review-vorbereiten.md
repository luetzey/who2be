# E5f — Review vorbereiten (Lage aus dem Dossier) + Route am Agenten

Karte t_eca6a63a · Basis origin/main b792ab60 · Spec phase-e-web-neuschnitt-2026-10.md §1, §2, §4, §7.1 (geht vor),
E5-Delta §0.1, §0.3, §3, §8, §9.1 (Inhalte). PM-Entscheidung Weg A (9 Dateien).

## Completion-Condition
- Route `/w/:ws/agents/:agentId/reviews/prepare?cases=<id,…>` steht in `routes.tsx` vor `:sessionId`; Test: `prepare` matcht nicht als Review-ID.
- Agent kommt aus der Route (`getAgent`), kein Select. viewer → `replace` auf `?tab=evolution`, ohne einen einzigen API-Request; Rolle unbekannt → nichts laden.
- ① Rückmeldungen aus `listCases({agent_id, status:[triaged,open,reopened]}, {limit:20})`, zwei `fieldset` (Eingeordnet oben, Noch nicht eingeordnet + Hilfesatz), Sortierung Schwere absteigend, dann Datum; „Weitere laden“ per Cursor (gesperrt während des Ladens). Auswahl in `cases` (replace), nur UUIDs. Ab 4 Auswahl Hinweis `role=status`, kein Verbot.
- ② „Lage“ aus genau einem `getDossier(agentId)`: Offene Rückmeldungen (Zähler vom Server), Rate je Version als `<table>` (UI rechnet nur „je 100“, `insufficient` → „zu wenig Nutzung“), Zugriffe als Label-Wert-Paare, frühere Änderungen (max. 5, Link ins Sheet, „Alle Reviews mit …“). Leer → „Keine Daten“. Keine Folge-Requests je Element (kein N+1). Laden: 4 Skeletons; Fehler: ErrorAlert + Retry, ① und ③ bleiben bedienbar.
- ③ Kopierblock über `BuilderPromptCopy` (variant `brand`, `onCopied`) mit `prepare.prompt` + `prepare.promptCases`, nur Agent-Name/-ID, Fall-UUIDs, Werkzeugnamen. Nach dem Kopieren Satz + Link „→ Weiterentwicklung“.
- 390 px: Lage als Akkordeon (`details`, „Offene Rückmeldungen“ offen), Tabelle als Karten, fixierte Leiste „Startsatz kopieren ({{count}} …)“ plus `scroll-padding-bottom` am Wurzelelement.
- `BuilderPromptCopy`: Default unverändert (`outline`, kein Callback nötig).

## Dateien (9)
api/types.ts · api/client.ts · features/evolution/pages/ReviewPreparePage.tsx · ReviewPreparePage.test.tsx · app/routes.tsx ·
features/evolution/components/BuilderPromptCopy.tsx · de.json · en.json · changelog.d/review-vorbereiten.added.md

## Verifikation
`npm run lint`, `npx tsc -b`, `npm run test:coverage` (Skip-Budget), `npm run build`, e2e-mobile; Fotos 1280/390 hell/dunkel editor+viewer + measure.json.
Mutationen: viewer-Gate, Request-Grenze, Server-Zähler, Kopiertext ohne Inhalte, variant, onCopied, Route-Reihenfolge.
