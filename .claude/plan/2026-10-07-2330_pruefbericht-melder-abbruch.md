# Prüfbericht: Melder je Ergebnis, Abruf bricht bei Unmount ab (t_7b8dd593)

Status: aktiv · Branch `who2be/t_7b8dd593-web-pr-fbericht-nennt-melder-agent-model` · Basis origin/main 70562e80

## Ziel
Zwei Phase-B-Reste in `apps/web/src/components/version/TestResultsPanel.tsx`:
1. Jede Ergebniszeile nennt in ihrer Kopfzeile den Melder (Agentname bzw. Person) und das Modell, falls vorhanden.
2. Späte Antworten des Berichtsabrufs (nach Unmount oder Versionswechsel) setzen keinen State.

## Weichen (aus dem Repo belegt)
- Agentname: zuerst aus `report.agents` (id → agent_name), sonst einzeln `api.getAgent(id)`, 403/404 → „Unbekannter Agent“. Gleiches Muster wie #822 (`useMemoryApi.ts` lookupAgents). Nie eine UUID.
- Person: vorhandene `userLabel` (Mitgliederliste). Weder Agent noch Person: „Melder unbekannt“ (API-Token ohne Agentbindung meldet ohne beide IDs, `attestation_for`).
- Abbruch: `getTestReport` nimmt kein Signal an. Daher Generationszähler (`useRef`), den der Effekt-Cleanup hochzählt; Antworten einer älteren Generation verwerfen. Gleiches Prinzip wie das `cancelled`-Flag beim Mitglieder-Abruf, nur auch für `reload()` gültig.
- Panel-Hinweis „Vom Client gemeldet …“ bleibt; die Detailzeile (Selbstauskunft · Modell · Zeit) bleibt.

## Dateien (Budget 8, geplant 5)
TestResultsPanel.tsx, TestResultsPanel.a11y.test.tsx, de.json, en.json, changelog.d/test-report-reporter.fixed.md

## Verifikation
Node 22: `npx tsc -b`, `npm run lint`, `npm run i18n:check`, `npm run test:coverage`, `npm run build`, `npm run license:check`. Rot-Probe: Versionswechsel-Test ohne Generationsprüfung rot. Fotos 1280/390 hell/dunkel + measure.json.
