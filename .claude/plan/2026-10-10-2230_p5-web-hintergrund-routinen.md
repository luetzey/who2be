# P5: Web-Abschnitt Hintergrund-Routinen (Kanban t_fcaf7913)

Grundlage: ADR-0057 §7 (mit Nachtrag 2026-10-10), Route `GET /v1/system/routines` (P4c, #915).

## Entscheidungen

- Ort: Seite Konto (`/settings/account`). Die Routinen gelten für die ganze Instanz,
  nicht für Org oder Workspace, und Betreiber ist eine Eigenschaft des Users. Deshalb
  steht der Abschnitt auf der Konto-Seite und nicht unter Organisation oder Workspace.
  Er bekommt keinen eigenen Navigationseintrag, damit es bei 403 auch keinen Eintrag
  zu verstecken gibt (PM-W7).
- Das Web kennt die Allowlist nicht. Es fragt die Route an und rendert bei jeder
  Antwort ausser 200 und 503 nichts, auch kein Lade-Skelett. 503 kommt nur nach dem
  Betreiber-Gate (ungültiger Override) und wird deshalb als Fehler gezeigt.
- Zeiten: Ortszeit vorn, UTC sichtbar in Klammern (auf Touch gibt es kein Hover).
  Der Cron-Ausdruck trägt den Hinweis „(UTC)“.
- Hook liegt in `RoutinesPanel.tsx` (eine Datei weniger, Dateibudget).

## Dateien (10, Budget 10)

types.ts, client.ts, client.contract.test.ts, RoutinesPanel.tsx, RoutinesPanel.test.tsx,
RoutinesPanel.a11y.test.tsx, AccountPage.tsx, de.json, en.json, changelog.d-Fragment.
Der Hook liegt im Panel, sonst wären es 11. types.ts und der Contract-Test sind nötig,
weil die Repo-Konvention Typ-Spiegel und Drift-Check je API-Methode verlangt.

## Verifikation

`npx tsc -b`, `npm run lint`, `npm run i18n:check`, `npm run test:coverage`, Fotos
1280/390 hell/dunkel plus measure.json (`.shots/t_fcaf7913/`, nicht committet).
