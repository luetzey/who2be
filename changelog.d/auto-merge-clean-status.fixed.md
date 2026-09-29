- `docs/auto-merge-agenten.md`: Das Fehlerbild `Pull request is in clean status`
  unterscheidet jetzt zwei Fälle, die vorher als „fast immer fehlt Gate 3“
  zusammengefasst waren. (a) `all-green` ist auf dem Head schon grün, das
  Ruleset greift: Auto-Merge ist nicht möglich, der Merge geht an den Owner.
  (b) Das Ruleset greift nicht: Gate 3 fehlt, das wird gemeldet.

  Eine lesende Diagnosezeile trennt beide Fälle. Sie fragt die wirksamen Regeln
  des Zielbranches ab und dazu den Status von `all-green` auf dem Head-SHA.
  Die Checkliste verlangt jetzt „`all-green` läuft noch“ statt „läuft oder ist
  grün“. Direktes Mergen bleibt in beiden Fällen gesperrt.
