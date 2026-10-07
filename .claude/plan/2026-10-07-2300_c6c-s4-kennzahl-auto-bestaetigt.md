# C6c — S4-Kennzahl „Letzte 7 Tage: n automatisch freigegeben · m davon bestätigt“ (Karte t_d3464b31)

Status: in Umsetzung → Review

## Grundlage

- Gedächtnisverwaltungs-Spec §11.1 Zeile S4: Kennzahl als Link auf
  `/memory?tab=entries&health=unconfirmed`; Text §13.9
  (`learning.autoPolicy.lastWeek`, Platzhalter `{{auto}}`/`{{confirmed}}`).
- Lernschleife-Spec S4 (Wireframe 1280, Regel „Kennzahl … ist ein Link auf S2
  mit Filter Unbestätigt“).
- API: Filter `auto` an `GET /memories/counts` (C6a, #844).

## Formel (PM-Korrektur auf der Karte)

- n = counts(`auto=true&created_after=-7d`).total
- m = counts(`auto=true&status=active&created_after=-7d`).total
  − counts(`auto=true&health=unconfirmed&created_after=-7d`).total
- Per Not-Aus zurückgenommene (wieder `pending`) Einträge zählen in n, aber
  nicht in m. m wird auf ≥ 0 begrenzt (zwei getrennte Abfragen).
- Ohne `scope`: gezählt wird alles Sichtbare (fremdes Nutzergedächtnis liefert
  der Server nie, ADR-0053 3.1.1).

## Vorentschiedene Weichen

- n = 0: Spec kennt keine Sonderregel → Zeile steht mit „0 … · 0 …“. Sie zeigt
  ehrlich, dass nichts automatisch freigegeben wurde (auch bei Matrix aus).
- Laden/Fehler: Zeile fehlt (keine toten Elemente, Spec §2). Fehler blockiert
  die Matrix nicht.
- Zahlen über `Intl.NumberFormat(i18n.language)` wie im Not-Aus-Dialog.
- Kennzahl und Not-Aus-Link stehen als eine Gruppe direkt untereinander
  (Wireframe S4), statt mit dem Abschnittsabstand getrennt.

## Dateien (6)

1. `features/settings/components/MemoryApprovalSection.tsx`
2. `features/settings/components/MemoryApprovalSection.test.tsx`
3. `i18n/locales/de.json`, 4. `i18n/locales/en.json` — `autoPolicy.lastWeek`
5. `changelog.d/t-d3464b31-s4-kennzahl.added.md`
6. dieser Plan

## Tests (mit Rot-Probe)

- Fixture „auto aus, freigegebene Einträge vorhanden“: Server zählt mit
  `auto=true` 0 → „0 automatisch freigegeben · 0 davon bestätigt“.
- Fixture „auto aktiviert, dann per Not-Aus zurückgenommen“: n=3, active=2,
  unconfirmed=1 → m=1 (alte Formel n − unconfirmed hätte 2 ergeben).
- Abfrage-Parameter: `auto=true`, `created_after` ≈ jetzt − 7 Tage,
  `status=active` bzw. `health=unconfirmed`.
- Link-Ziel `/w/ws-1/memory?tab=entries&health=unconfirmed`.
- Zählfehler: keine Zeile, Matrix bleibt.

## Verifikation

Node 22: `npx tsc -b`, `npm run lint`, `npm run i18n:check`,
`npm run test:coverage`, `npm run build`, `npm run license:check`;
Fotos 1280/390 hell/dunkel + measure.json; CI all-green.
