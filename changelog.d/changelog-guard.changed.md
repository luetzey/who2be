- Das Fragment-Verfahren fuer den CHANGELOG wird jetzt in CI erzwungen.

  Der neue Job `changelog-guard` weist jeden PR ab, der `CHANGELOG.md` direkt
  aendert, ohne dabei ein Fragment unter `changelog.d/` zu loeschen — die
  Signatur eines `collect`-Laufs beim Release. Er haengt bewusst an keinem
  Pfadfilter: ein PR, der nur den CHANGELOG anfasst, gilt dem `changes`-Job als
  Doku-PR, ein Gate in den schweren Jobs haette genau den Zielfall verfehlt.
  Die Entscheidung trifft `scripts/changelog_fragments.py guard`, unter pytest.

  `CONTRIBUTING.md` und `changelog.d/README.md` nennen dazu die Regel fuer
  Alt-PRs: CHANGELOG-Hunk verwerfen, denselben Text wortgleich als Fragment.
