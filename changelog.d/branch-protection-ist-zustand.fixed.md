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
  als geschlossen markiert statt als offener Auftrag. Mitgezogen:
  `docs/standards-review-2026-07-20.md` fuehrte GIT-1 („Keine
  Branch-Protection auf `main`") unverandert als offenen Owner-Befund; dort
  steht jetzt der Erledigungsvermerk mit Verweis auf das Doku-Dokument.
