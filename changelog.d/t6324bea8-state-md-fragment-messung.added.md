- `scripts/conflict_hotspots.py` misst, welche Dateien in offenen PRs und in der
  History **wirklich** Merge-Konflikte erzeugen, statt sie zu vermuten. Drei
  Unterkommandos: `hotspots` (offene PRs paarweise via `git merge-tree`, ändert
  nichts), `resolved` (in der History handverlesen aufgelöste Konflikte),
  `kind` (Anhängsel vs. Bestands-Umbau — nur Anhängsel lassen sich per
  Fragment-Verfahren beseitigen).

  Anlass war die Frage, ob `.claude/context/STATE.md` ein `state.d/` analog
  `changelog.d/` braucht. Die Messung sagt **nein**, aber differenzierter als
  erwartet: `STATE.md` ist an keinem der offenen PR-Konflikte beteiligt und
  mergt auch nicht still falsch — zwei Karten, die beide einen Nachtrag unter
  die `_Stand:_`-Zeile setzen, kollidieren dort allerdings doch, was dieser Lauf
  an sich selbst gemessen hat. Der Konflikt ist dabei sichtbar und trivial
  („beide behalten"), während vier von sechs Änderungen im Fenster
  Bestands-Umbauten sind, die ein Fragment strukturell nicht abbilden kann. Die
  eigentliche Last liegt in `.github/workflows/ci.yml` (4 von 5
  konfliktbehafteten PRs, alle am Job `e2e-mobile`) und in den Lockfiles.

  Zahlen, Urteil und Empfehlungen — einschließlich der für `DECISIONS.md`, wo
  die vermutete Append-only-Regel bereits gilt und zu 3/3 eingehalten wird — in
  `.claude/plan/2026-09-24-0701_state-md-fragment-verfahren-messung.md`.
