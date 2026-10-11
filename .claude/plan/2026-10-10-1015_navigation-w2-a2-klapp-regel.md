# Navigation W2-a2: Klapp-Regel der Zusammensetzung entfernen

Karte: t_3b72bed0 · Spec: navigation-transparenz-design-2026-10 §3.1 · Owner A2a ·
Vorgänger: W2-a1 (#904, t_6e48b9ac)

## Outcome

Die Karte „Zusammensetzung“ ist auf jeder Breite offen. Unter `md` gibt es
keinen Schalter `agent-hierarchy-toggle` mehr; die Regel aus t_42bff43b
entfällt, weil die Karte im Tab „Überblick“ hinter der Tab-Leiste steht.

## Entscheidungen

- P7/M9 bleibt: unter `md` 4 Playbooks + „N weitere anzeigen“ (je 8).
- `hierarchy.summary*` (de/en) gelöscht; i18n:check ohne neue Waisen.
- scroll-guard M2: gleiche Grenzen wie vorher (Tab-Oberkante ≤ 1,2 bei 320,
  ≤ 0,9 auf breiteren Phones), jetzt an der benannten Seiten-Tab-Leiste
  gemessen; zusätzlich auf jedem Profil: kein Schalter, kein `[hidden]`/
  `[aria-expanded]` in der Karte, Persona- und System-Prompt-Link sichtbar,
  Tab-Leiste im DOM vor der Karte, Überblick ausgewählt; Desktop 14 Playbooks.
  Entfallen: Schalterhöhe ≥ 44 px und Fokus nach Klick (Schalter existiert nicht mehr).

## Verifikation

`npm run lint`, `npx tsc -b`, `npm run i18n:check`, `npm run test:coverage`,
e2e scroll-guard M2 auf allen Profilen, Fotos 390/1280 hell/dunkel + measure.json.
