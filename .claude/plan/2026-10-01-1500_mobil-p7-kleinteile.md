# Mobil P7: Kleinteile — Aktivität, Hierarchie, „Verwendet in“, Artefakt-Blöcke

Karte t_327ab6b1 · Spec `/home/luetzey/recherche/mobile-spec-2026-09-29.md`
M6 (Namen), M10; PM-Zusatz (Kommentar 2026-09-29): AgentHierarchyView unter md
höchstens 8 Playbooks + „{{count}} weitere anzeigen“ (Muster M9).
Basis: origin/main 5616fee5. P6b (#745, `useShowMore`) ist NICHT gemergt.

## Completion-Condition

- M6-Tabelle: keine `truncate` mehr ohne Tap-Weg in den vier Dateien;
  `ActivityRow` (Verstoß) umbricht; `AgentHierarchyView:64/106` und
  `UsedByList` brechen um (Links → höchstens 2 Zeilen über `.w2b-clamp`,
  `--clamp:2`, wie Spec M6.1 erlaubt). Gemessen: Kürzungsinventar dieser
  Ansichten = 0 Ellipsen ohne Link.
- AgentHierarchyView: unter md höchstens 8 Playbooks im Seitenfluss +
  Knopf `common:actions.showMoreCount`; Tab-/Inhaltsoberkante Agent bei 320
  gemessen (Ziel laut PM ≤ 1,2 Bildschirme — hängt auch an P2 ExpandableText,
  wird gemessen und berichtet).
- ArtifactDetailPage: unter md Anker-Knopf unter dem Block (`flex-col`,
  `self-end`), Textspalte volle Breite; Seite bei 320 ≤ 6 Bildschirme (vorher 8,0).
- Vitest mit Rot-Probe, Web-DoD (lint, tsc -b, i18n:check, test:coverage,
  build, license:check), E2E `scroll-guard.spec.ts` erweitert, Changelog-
  Fragment, ≤ 8 Dateien, CI grün.

## Entscheidungen

- **Kein `useShowMore` aus #745**: Branch nicht gemergt, Abzweigen von
  ungemergtem Branch verboten. AgentHierarchyView braucht weder Suche noch
  schrittweises Nachladen über 8er-Schritte zwingend; Muster M9 sagt „jeweils
  8 weitere“. Umsetzung lokal mit `useState` + `useIsMobile` (gleiche
  Semantik: 8er-Schritt, Fokus auf ersten neuen Eintrag, `aria-live` mit
  `common:list.shownOfTotal`). Restpunkt: nach Merge von #745 auf
  `useShowMore` umstellen (Folgekarte, SSoT).
  → Datei-Budget: kein neuer Hook, damit bleibt der PR bei ≤ 8 Dateien.
- **Breakpoint per `useIsMobile`** (Anzahl gerenderter Einträge ist Logik).
- **ActivityRow**: Satz umbrechen (`wrap-anywhere`), Zeit unter md in eigene
  Zeile? Nein — `time` bleibt `flex-none` rechts; Text bricht um. Kein Link
  vorhanden, daher keine Zeilenbegrenzung (Spec M6.1).
- **ArtifactDetailPage**: `flex-col md:flex-row`, Knopf `self-end md:self-start`.

## Schritte

1. [ ] Vorher-Messung (eigener Stack w2b327, Ports 57xxx).
2. [ ] Umsetzung vier Dateien.
3. [ ] Tests + Rot-Proben, E2E-Erweiterung.
4. [ ] Nachher-Messung, Screenshots hell/dunkel, DoD, Changelog, PR.
