# Feinschliff 3b: Filter (n) und Tags +n unter md (t_648b4527, Audit A11/A13)

## Ziel / Completion-Condition
- A11: Unter `md` zeigen ListFilterBar (Agents, Personas, Resources, System-Prompts,
  Tools, Feedback) und PlaybookListToolbar Suche + Status sichtbar; Tag/Typ/Agent/
  Sprache/Gruppieren liegen hinter einem Knopf "Filter (n)" (n = aktive Zusatzfilter,
  ohne Gruppieren, weil Anzeige-Praeferenz statt Filter). Ab `md` unveraendert.
- A13-Rest: Unter `md` zeigen Detailkoepfe (Resource, Tool, Persona) und Listen-Karten
  (Resources, Tools, Personas) hoechstens 3 Tags, dann einen Knopf "+n", der im Fluss
  aufklappt. Ab `md` alle Tags wie bisher. Playbook-Liste: W6=b bleibt (keine Aenderung).
- Messbar: Personas-Liste 390 px erster Eintrag (Audit y=695) sinkt; Resource-Detail
  390 px Tabs-Oberkante (762 nach #767) sinkt; 1280 px unveraendert.

## Vorentschiedene Weichen
- "+n" = Button im Fluss (W3=a-Muster, Empfehlung der Karte; PM hat "+3" fuer Listen
  vorgegeben). Auf Listen-Karten liegt der Knopf ueber dem Stretched-Link (`relative z-10`).
- Technik: eingeklappte Tags `hidden md:inline-flex` -> unter md aus A11y-Tree, ab md da.
  "+n"-Knopf `md:hidden`. Kein JS-Breakpoint (mobile-first wie DetailHeader "Mehr").
- Filter-Knopf: Toggle im Fluss mit aria-expanded/aria-controls (wie DetailHeader "Mehr"),
  kein Popover. Facetten-Raster `hidden md:grid`, offen `grid`.
- Wiederverwendbare Komponente `components/data/TagList.tsx` (eine Quelle, Pattern-Drift vermeiden).

## Schnitt (<= 8 Dateien je PR)
- PR A (A11): ListFilterBar.tsx (+test), PlaybookListToolbar.tsx (+test), de.json, en.json,
  changelog-Fragment = 7.
- PR B (Tags): TagList.tsx (+test), ResourceDetailPage, ToolDetailPage, PersonaDetailPage,
  ResourcesPage, ToolsPage, PersonasPage, changelog = 9 -> i18n-Keys in PR A mit anlegen
  waere toter Schluessel (i18n-Waisen-Check) -> PR B laeuft nach PR A, Keys in PR B:
  dann 11 Dateien. Schnitt B1: TagList + test + 3 Detailseiten + de/en + changelog = 8;
  B2: 3 Listen-Seiten + changelog = 4 (nach B1).

## Verifikation
Web-DoD Node 22: lint, tsc -b, i18n:check, test:coverage; Rot-Probe je neuer Zusicherung;
Screenshots 390/1280 hell/dunkel vorher/nachher; e2e-mobile in CI gruen gegen Head.
