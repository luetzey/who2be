# C6b — S4 Not-Aus-Link und S4a-Satz (Karte t_768e1624)

Status: in Umsetzung → Review

## Grundlage

- Spec Gedächtnisverwaltung §11.1, Zeilen S4 und S4a; Texte §13.9.
- ADR-0053 6.4.1, letzter Absatz: Der Satz „Du kannst alles automatisch
  Freigegebene auf einmal zurücknehmen“ wird erst ausgeliefert, wenn der
  Web-Teil des Not-Aus gemergt ist. Erfüllt mit dem Not-Aus-Dialog
  (`features/memory/components/PullBackDialog.tsx`, `?pullback=1`).

## Zuschnitt (PM-Entscheidung auf der Karte, Variante C+A)

- Geliefert: AK 2 (Link „Automatisch Freigegebenes zurücknehmen…“ →
  `/memory?pullback=1`) und AK 3 (Satz in Dialog und dauerhafter Liste, de/en).
- Verschoben: AK 1, die Kennzahl „Letzte 7 Tage: n automatisch freigegeben ·
  m davon bestätigt“. `GET /memories/counts` kann „automatisch freigegeben“
  nicht zählen: Ein automatisch freigegebener und später bestätigter Eintrag
  ist von einem aus der Warteschlange freigegebenen nur in der Historie
  unterscheidbar, und nach Ereignissen filtert `counts` nicht. Ein
  Näherungswert würde bei ausgeschalteter Auto-Freigabe falsche Zahlen
  zeigen. Folgt nach einer Server-Karte (Filter `auto=true`).

## Schritte

1. Locale-Schlüssel `learning.autoPolicy.pullbackLink` (§13.9) und
   `learning.autoPolicy.limits.pullbackAll` (de/en).
2. `AutoApprovalStillHappens` in `AutoApprovalLimitsDialog.tsx`: eine Fassung
   für Dialog und Dauerliste.
3. Link in `MemoryApprovalSection.tsx` unter den Hinweisen, über
   `useWorkspacePath`.
4. Tests mit Rot-Probe: Link-Ziel, nur admin, Satz in Dialog/Sheet/Liste,
   Locale-Wortlaut und Wortliste.
5. Changelog-Fragment, Web-DoD unter Node 22, Fotos 1280/390 hell/dunkel.
