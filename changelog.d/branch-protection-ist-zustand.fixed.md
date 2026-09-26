- `docs/branch-protection-main.md` beschreibt jetzt den Ist-Zustand des
  Rulesets `16707501` statt einen Vorschlag.

  Das Dokument trug im Titel weiter „— Vorschlag", waehrend der Status-Block
  darunter bereits „umgesetzt" sagte, und behauptete an drei Stellen in der
  Gegenwartsform das Gegenteil des Servers: „CI ist heute formal nirgends
  verpflichtend", „Heute findet er keine konfigurierten Required Checks",
  „Fertige Nutzlast fuer P3b". Gemessen am 2026-09-24 per
  `gh api repos/luetzey/who2be/rulesets/16707501` fuehrt das Ruleset vier
  Regeln (`deletion`, `non_fast_forward`, `pull_request`,
  `required_status_checks`), `enforcement: active`, Bedingung
  `~DEFAULT_BRANCH`, `all-green` als einzigen Required Check im Modus „loose"
  und `bypass_actors` leer. Der gekuerzte API-Auszug steht jetzt mit Messdatum
  im Dokument und deckt jede dort genannte Zahl.

  Ausdruecklich benannt ist dabei `required_approving_review_count: 0`: das
  Ruleset erzwingt **kein** Review. Serverseitig verpflichtend sind nur PR
  statt Direkt-Push und ein gruenes `all-green`; die Review-Pflicht im Team ist
  Disziplin, keine Servereinstellung. Wer die Datei liest, um zu wissen was der
  Server durchsetzt, konnte das bisher verwechseln.

  Die Ausgangslage-Tabelle bleibt als Historie stehen, ist aber je Zeile als
  Stand *vor* dem Einschalten gekennzeichnet — die Zeile „Required Checks |
  keine" nennt jetzt den heutigen Wert mit. Der Verweis auf die Karte P3b ist
  als geschlossen markiert statt als offener Auftrag.

  Mitgezogen wurde daraufhin jede weitere Stelle im Repo, die den
  Branch-Protection-Status als offen fuehrte — gesucht ueber den Begriff selbst
  statt ueber einzelne Wortlaute, deutsch wie englisch:
  `docs/standards-review-2026-07-20.md` (GIT-1 in §2.11 und die
  Owner-Entscheidungsliste in §4), `.claude/context/STATE.md` (Owner-Checkliste
  und §Bekannte Probleme), `.claude/context/DECISIONS.md` (die offene geerbte
  Annahme des CI-Doku-Gates, per datiertem Nachtrag aufgeloest),
  `.github/PROJECT.md` (#338 O2) und `ROADMAP.md` (Owner steps). Offen bleiben
  dort ueberall korrekt die uebrigen Punkte — Auto-delete, Merge-Strategie,
  Description + Topics, CLA-Assistant.

  Ebenfalls ueberholt, aber bewusst nicht direkt korrigiert: der Satz in
  `CHANGELOG.md` zur `[Unreleased]`-Sektion, ein Vorschlag fuer das Ruleset
  liege in `docs/branch-protection-main.md` und sei *not applied*. Die Datei
  wird laut `CONTRIBUTING.md` nicht direkt bearbeitet, und der CI-Job
  `changelog-guard` weist jeden PR ab, der es doch tut. Der Widerruf steht
  deshalb hier: **das Ruleset ist seit 2026-09-22 angewendet** — beim naechsten
  `collect` landet diese Richtigstellung in derselben `[Unreleased]`-Sektion
  wie die ueberholte Aussage.

  Datierte Rueckblicke bleiben unangetastet: die Laufberichte in
  `.claude/context/STATE.md` (Messung 2026-08-21), die Planarchive unter
  `.claude/plan/`, die Score-Tabelle des Audits vom 2026-07-20 und der
  Migrations-Rueckblick in `docs/frontend/migration-plan.md` beschreiben den
  Stand ihres jeweiligen Zeitpunkts und waren damals richtig.
