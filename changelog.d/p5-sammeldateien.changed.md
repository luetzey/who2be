- Changelog-Einträge entstehen jetzt als Fragmente unter `changelog.d/` statt
  direkt in `CHANGELOG.md`, und die Locale-Dateien `de.json`/`en.json` werden
  auf Schlüsselgleichheit, doppelte und verwaiste Schlüssel geprüft
  (`npm run i18n:check`).

  Beides sind Sammeldateien, an denen git still falsch zusammengeführt hat —
  ohne Konfliktmarker. Ein Fragment pro Pull Request kann strukturell nicht
  kollidieren; für die Locale-Dateien, deren Namensraum sich nicht aufteilen
  lässt, tritt die Prüfung an diese Stelle. `CONTRIBUTING.md` hält dazu fest,
  dass nach jeder Konfliktauflösung der Nettodiff gelesen wird.
