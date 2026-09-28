- `SECURITY.md` und `SUPPORT.md` beschreiben jetzt den öffentlichen Zustand
  des Repos statt den privaten Zustand vor dem Public-Switch.

  `SECURITY.md` nannte die Private Security Advisories als Weg „sobald das
  Repo öffentlich ist" und bis dahin die E-Mail. Das Repo ist seit 2026-08-20
  öffentlich, Private Vulnerability Reporting ist an (gemessen 2026-09-28 per
  `gh api repos/luetzey/who2be/private-vulnerability-reporting` →
  `enabled: true`). Der Text nennt jetzt diesen Weg samt direktem Link aufs
  Meldeformular; die E-Mail bleibt als Ausweich für alle ohne GitHub-Konto.

  `SUPPORT.md` schickte Fragen in ein leeres Issue mit Präfix `question:` und
  empfahl Discussions nur „falls aktiviert". Sie sind aktiviert
  (`gh repo view luetzey/who2be --json hasDiscussionsEnabled` → `true`),
  Fragen gehen jetzt dorthin, mit Verweis auf die Kategorien Q&A und Ideas.
  Die Auswahlseite für neue Issues (`.github/ISSUE_TEMPLATE/config.yml`) führt
  deshalb einen eigenen Kontaktlink auf die Discussions; der Link auf
  `SUPPORT.md` bleibt als Übersicht.

  In `.claude/context/STATE.md` stand in den Owner-Schritten noch, Secret- und
  Push-Protection sowie Private Vulnerability Reporting seien zu bestätigen —
  alle drei sind an und dort jetzt mit Messdatum abgehakt.
