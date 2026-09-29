# Navigation in Gruppen: Building blocks / Operations (Karte t_2d762bd6, Audit E2-B)

Stand: 2026-09-29, Basis `origin/main` 71b47391.

## Ziel / Completion-Condition

Desktop-Sidebar und Phone-Sheet zeigen dieselbe Gruppierung:

1. (ohne Ueberschrift) Dashboard, Agents
2. "Building blocks" / "Bausteine": System prompts, Personas, Playbooks, Resources, External tools
3. "Operations" / "Betrieb": Work area, Feedback
4. (ohne Ueberschrift) Settings

Fertig heisst: Unit-Tests pruefen Gruppenzuordnung + Ueberschrift-/Listen-Struktur
in Sidebar UND Sheet (Rot-Probe belegt), axe gruen, `localeParity` gruen,
E2E-Navigation auf `chromium` + `mobile-320` gruen, CI gruen gegen Head-SHA.

## Ist-Stand

- `apps/web/src/components/layout/AppShell.tsx`: flaches `NAV_ITEMS` (10 Eintraege),
  `renderNavLinks` rendert `NavLink`s direkt im `<nav>` — weder Liste noch Ueberschrift.
- Sidebar und Sheet teilen `renderNavLinks` → eine Quelle, bleibt so.
- Keine E2E-Spec deckt die App-Navigation ab.

## Entscheidungen (aus dem Repo belegt)

- **Datenmodell:** `NAV_GROUPS: { id, labelKey?, items }[]` statt flacher Liste; eine
  Quelle fuer beide Flaechen (Single Source of Truth). Routen unveraendert.
- **Semantik:** je Gruppe ein `<ul>` mit `<li>`; betitelte Gruppen tragen ein
  `<h2 id>` (Eyebrow), das die Liste per `aria-labelledby` benennt. Unbetitelte
  Gruppen sind nur `<ul>`. IDs je Flaeche (Sidebar/Sheet) getrennt, weil beide
  gleichzeitig im DOM stehen.
- **Typo:** Eyebrow aus design-language §3.3/§3.4: `text-xs font-medium uppercase
  tracking-wide text-muted-foreground` (gleiche Klassen wie die bestehende Brand-Zeile
  der Sidebar), `px-3` fluchtend mit den Link-Texten.
- **i18n:** `layout.nav.groups.buildingBlocks` / `layout.nav.groups.operations`, EN
  "Building blocks"/"Operations", DE "Bausteine"/"Betrieb" (DE-UI uebersetzt die
  Nav-Labels bereits, z. B. "Einstellungen", "Arbeitsbereich").
- **E2E:** neue Spec `e2e/navigation.spec.ts`, Selektoren ueber `data-testid`
  (Repo-Regel journeys.spec.ts), Desktop: Sidebar; <md: Sheet oeffnen. Prueft
  Gruppenreihenfolge und Ziel-Navigation, `expectNoHorizontalScroll` im Sheet.

## Dateien (Budget 8)

1. `apps/web/src/components/layout/AppShell.tsx`
2. `apps/web/src/components/layout/AppShell.test.tsx`
3. `apps/web/src/components/layout/AppShell.a11y.test.tsx`
4. `apps/web/src/i18n/locales/en.json`
5. `apps/web/src/i18n/locales/de.json`
6. `apps/web/e2e/navigation.spec.ts` (neu)
7. `changelog.d/nav-groups.changed.md` (neu)
8. dieser Plan

## Schritte

1. [x] Vorher-Screenshots (hell/dunkel, 1440 + 390 + 320, Sheet offen) vom Stack auf main
2. [x] AppShell auf Gruppen umbauen + i18n EN/DE
3. [x] Unit-/A11y-Tests + Rot-Probe (7 Mutationen, jede rot)
4. [x] E2E-Spec, lokal alle vier Profile gegen neu gebauten Stack (12/12);
       E2E-Rot-Probe gegen Build mit Mutation M1 (Gruppierung + Tastatur rot)
5. [x] Nachher-Screenshots + Kontrast der Eyebrow gemessen
6. [x] DoD Web: lint, tsc -b, test:coverage, i18n:check, build; Changelog-Fragment
7. [ ] PR, CI gruen gegen Head-SHA, Review-Handoff

## Ergebnisse

- Eyebrow `text-muted-foreground` auf Sidebar `bg-muted/40`: hell 4,58:1, dunkel
  7,08:1; im Sheet (`bg-background`): hell 4,74:1, dunkel 7,66:1 — identisch mit
  den inaktiven Nav-Links (gleiches Token), >= 4,5:1.
- Sheet auf 320 x 568: Inhalt 658 px (vorher 574 px) — das Sheet scrollt wie
  vorher (`overflow-y-auto`), kein horizontaler Scroll.
- `localeParity.test.ts` deckt nur `common.errors` ab; die Paritaet der neuen
  Keys sichert `npm run i18n:check` (Rot-Probe: fehlender DE-Key -> exit 1).
- Lokal: Node 26 bricht jsdom-`localStorage` (auch auf main); CI und lokale
  Laeufe hier mit Node 22 wie `ci.yml`.
