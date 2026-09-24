# Branch-Protection für `main` — Vorschlag

**Status: umgesetzt am 2026-09-22.** Das Ruleset `16707501` fuehrt seither
`pull_request` und `required_status_checks` mit `all-green` als einzigem
Required Check, `enforcement: active`, `bypass_actors` leer (gemessen
2026-09-23). Dieses Dokument bleibt als Entscheidungsgrundlage stehen: es
begruendet, warum genau ein Required Check und welcher. Die Nutzlast in
§„Fertige Nutzlast fuer P3b" ist Beleg, kein offener Auftrag.

Grundlage: Recherchebericht `workflow-idee-code-review-2026-09-22.md`, Abschnitt P3, sowie die
dort zitierte GitHub-Dokumentation zu Rulesets. Gemessener Repo-Zustand: 2026-09-22.

## Ausgangslage (Zustand vor dem Einschalten, 2026-09-22)

| Fakt | Wert |
|---|---|
| Ruleset `16707501` ("rule 1"), `enforcement: active` | genau zwei Regeln: `deletion`, `non_fast_forward` |
| Required Checks | **keine** |
| `bypass_actors` | **leer** — das Ruleset gilt auch für den Owner |
| Erlaubte Merge-Methoden | Merge-Commit, Squash und Rebase, alle drei aktiv |
| Branch nach Merge löschen | aktiv |

Force-Push und Löschen von `main` sind damit bereits gesperrt. Was fehlt, ist die Verbindung
zwischen „CI ist grün" und „darf gemergt werden": **CI ist heute formal nirgends verpflichtend.**

## Warum genau ein Required Check, und welcher

Die naheliegende Konfiguration — jeden CI-Job einzeln als Required eintragen — ist in diesem
Repo nachweislich falsch, aus zwei entgegengesetzten Gründen:

* **Ein übersprungener Job gilt als Erfolg.** Fünf der sieben Jobs hängen an der Doku-Allowlist
  des `changes`-Jobs und melden bei einem Doku-PR `skipped`. GitHub wertet `skipped` bei Required
  Checks wie `success` — der Check wäre grün, ohne dass irgendetwas lief.
* **Ein nicht gestarteter Job blockiert für immer.** Umgekehrt bleibt ein Required Check, den ein
  PR gar nicht auslöst, dauerhaft auf „Waiting for status to be reported" stehen. Die
  GitHub-Dokumentation rät deshalb ausdrücklich davon ab, überspringbare Workflows als Required
  zu fordern.

Deshalb: **genau ein** Required Check, der Aggregat-Job **`all-green`** aus
`.github/workflows/ci.yml`. Er läuft mit `if: always()`, kennt alle sieben Jobs in `needs:` und
urteilt selbst, statt sich auf GitHubs Auslegung von `skipped` zu verlassen. Er ist
pfadfilter-fest und muss beim Umbau der CI nicht in den Repo-Einstellungen nachgezogen werden.

> **Der Name ist die Schnittstelle.** Der Check heißt in der Checks-Liste exakt `all-green`
> (Job-Id und `name:` sind bewusst identisch). Required Checks binden per exakter
> Namensgleichheit — eine spätere Umbenennung des Jobs macht **jeden offenen PR unmergebar**,
> bis das Ruleset nachgezogen ist. Rename und Ruleset-Änderung gehören immer zusammen.

## Die Regeln im Einzelnen

### 1. Require status checks to pass — `all-green`, Ausprägung „loose"

* **Verhindert:** dass ein PR mit rotem oder gar nicht gelaufenem CI auf `main` landet. Macht
  aus einem *fehlenden* Check einen *blockierenden* Zustand statt eines unsichtbaren.
* **Kostet:** „Loose" verlangt nicht, dass der Branch vor dem Merge auf dem Stand von `main` ist.
  Die dokumentierte Kehrseite: ein Check kann nach dem Merge fehlschlagen, wenn `main`
  inzwischen inkompatibel geändert wurde.
* **Warum trotzdem „loose":** „Strict" („Require branches to be up to date") erzwingt, dass jeder
  offene PR nach *jedem* fremden Merge neu gebaut wird. Bei aktuell **11 offenen PRs** ist das
  eine Tretmühle, die Actions-Minuten verbrennt und Agenten in Endlos-Nachzieh-Schleifen
  schickt. Auf „strict" umstellen, wenn die Zahl offener PRs einstellig und stabil ist.
* **Für Agenten:** spürbar nur indirekt — ein Handoff „CI grün" wird überprüfbar, statt geglaubt
  werden zu müssen. Agenten mergen ohnehin nicht.
* **Zwei Fallstricke aus der Dokumentation:** der Check muss auf dem **neuesten** Commit-SHA
  bestanden haben (ältere Läufe zählen nicht), und innerhalb der letzten **sieben Tage**
  erfolgreich gewesen sein. Ein lange liegender PR braucht also einen frischen Lauf.

### 2. Block force pushes

* **Verhindert:** dass jemand Commits von `main` entfernt, auf denen andere aufgebaut haben —
  laut Dokumentation die Ursache für „merge conflicts or corrupted pull requests".
* **Kostet:** nichts. Das Zurücknehmen eines Fehlers auf `main` läuft dann über einen
  Revert-Commit statt über Historien-Umschreiben, was ohnehin das sauberere Verfahren ist.
* **Für Agenten:** keine Änderung. Force-Push auf `main` ist für sie bereits durch die
  Arbeitsregeln gesperrt.
* **Hinweis:** faktisch bereits aktiv — die bestehende Regel `non_fast_forward` ist genau diese.
  Sie bleibt unverändert bestehen; hier steht sie nur der Vollständigkeit halber.

### 3. Require a pull request before merging — 0 erforderliche Reviews

* **Verhindert:** direkten Push auf `main`. Erst dadurch wirkt Regel 1 überhaupt: ohne PR-Zwang
  ließe sich jeder Required Check durch einen direkten Push umgehen.
* **Kostet — und das ist der Punkt, der leicht übersehen wird:** `bypass_actors` ist heute
  **leer**, das Ruleset gilt also auch für den Owner. Mit dieser Regel kann **niemand** mehr
  direkt auf `main` pushen, auch kein Ein-Zeilen-Hotfix. Wer diesen Weg offenhalten will, muss
  sich bewusst als Bypass-Actor eintragen — dann gilt die Sperre aber auch bei Versehen nicht
  mehr. Empfehlung: **keinen Bypass**, Hotfix über einen PR mit sofortigem Merge.
* **Warum 0 Reviews:** ein Pflicht-Review bräuchte einen zweiten Menschen. Den gibt es hier
  nicht, und ein Agent kann nicht sinnvoll approven. Die Review-Qualität kommt in diesem Team
  aus dem Board (`@reviewer`), nicht aus der GitHub-Mechanik. Eine Pflicht-Approval-Regel wäre
  eine Sperre, die der Owner täglich selbst umgehen müsste — und eine Regel, die routinemäßig
  umgangen wird, ist schlimmer als keine.
* **Für Agenten:** keine Änderung. Sie arbeiten bereits ausschließlich über Branch + PR.

### 4. Require linear history — **nicht empfohlen**, Begründung unten

## Der Widerspruch bei „Require linear history" — und warum die Auflösung ihren Preis nicht wert ist

Die Karte verlangt, diese Regel nur zu empfehlen, wenn der Widerspruch zum `--no-ff`-Weg
aufgelöst ist. Er ist auflösbar, aber die Auflösung kostet mehr, als die Regel einbringt.

**Was die Regel tut:** Sie verbietet Merge-Commits auf `main` und erzwingt damit Squash- oder
Rebase-Merge.

**Der scheinbare Widerspruch löst sich auf.** Der `--no-ff`-Weg dieses Teams zieht `main` **in
den Feature-Branch** (zuletzt Karte `t_fc770076`, Merge-Commit `35536a4c`, um einen Konflikt in
`docs/licensing/plans.md` additiv aufzulösen). Das ist ein Merge-Commit *im Branch*, nicht *auf
main* — die Regel betrifft ihn nicht. Ein Squash-Merge kollabiert den gesamten Branch
einschließlich seiner internen Merge-Commits zu einem Commit auf `main`. `--no-ff` zur
Konfliktauflösung und lineare Historie sind also vereinbar, **sofern über Squash gemergt wird**.

**Aber die Auflösung ist nicht kostenlos:**

1. **Rebase-Merge müsste abgeschaltet werden.** Er ist heute aktiv, und er spielt Branch-Commits
   einzeln neu ab — ein Branch, der einen `--no-ff`-Merge enthält, ist dafür nicht geeignet. Die
   Regel erlaubt Squash *und* Rebase; nur Squash ist mit unserem Konfliktverfahren verträglich.
   Bleiben beide aktiv, wartet eine Falle auf den nächsten Merge nach Konfliktauflösung.
2. **Der Owner müsste seine Merge-Gewohnheit ändern.** Gemessen an den letzten 40 Commits auf
   `main`: **9 davon sind echte Merge-Commits** („Merge pull request …", zwei Eltern), also rund
   jeder vierte Merge. Diese Regel macht genau diesen Weg unmöglich.
3. **Squash verliert die Commit-Granularität.** Ein PR mit nachvollziehbar getrennten Schritten
   wird zu einem Commit. Für ein Repo, dessen Plan-Dokumente und Handoffs auf einzelne Commits
   verweisen, ist das ein realer Verlust.

**Was die Regel dafür einbringt:** eine gerade Historie, etwas einfacheres `git bisect`. Kosmetik
und Komfort — kein Schutz. Der tatsächliche Schutz gegen Historien-Schäden ist Regel 2, und die
ist bereits aktiv.

**Empfehlung: jetzt nicht einschalten.** Drei Regeln lösen das reale Problem; die vierte tauscht
einen eingespielten Arbeitsweg gegen Aufgeräumtheit. Wenn der Owner die lineare Historie
trotzdem will, ist der Weg dorthin: erst Rebase-Merge deaktivieren, Squash als einzige Methode
lassen, das eine Release-Zyklus lang fahren — und dann erst die Regel scharf schalten.

## Fertige Nutzlast für P3b

Ergänzt das bestehende Ruleset `16707501` um zwei Regeln; `deletion` und `non_fast_forward`
bleiben unverändert. **Erst ausführen, wenn der `all-green`-Job einmal auf `main` gelaufen ist**
— sonst kennt GitHub den Check-Namen noch nicht und jeder offene PR hängt sofort auf „Expected".

```jsonc
// Anzuwenden auf die bestehenden Regeln, nicht als Ersatz:
{
  "type": "pull_request",
  "parameters": {
    "required_approving_review_count": 0,
    "dismiss_stale_reviews_on_push": false,
    "require_code_owner_review": false,
    "require_last_push_approval": false,
    "required_review_thread_resolution": false
  }
},
{
  "type": "required_status_checks",
  "parameters": {
    "strict_required_status_checks_policy": false,   // "loose", siehe Regel 1
    "required_status_checks": [
      { "context": "all-green" }                     // exakter Job-Name, nicht ändern
    ]
  }
}
```

Nach dem Anwenden prüfen: ein offener PR muss `all-green` in seiner Checks-Liste als **Required**
zeigen. Steht dort stattdessen „Expected — Waiting for status to be reported", ist der Name
falsch geschrieben oder der Job auf dem Ziel-SHA nie gelaufen.

### Ein Fall, der genau diese Meldung erzeugt und nichts mit dem Ruleset zu tun hat

Ein **konfliktbehafteter** PR löst gar keinen `pull_request`-Lauf aus: GitHub baut solche Läufe
auf dem Merge-Commit aus PR-Branch und Zielzweig, und den kann es bei einem Konflikt nicht
bilden. Beobachtet bei PR #584 — die Checks-Liste zeigte ausschließlich CodeQL (das auf `push`
läuft), die gesamte CI fehlte. Nach dem Nachziehen von `main` liefen alle Jobs.

Mit aktivem Required Check heißt das: ein Konflikt-PR hängt auf „Waiting for status to be
reported", bis jemand `main` nachzieht. Das ist **erwünscht** — ein Konflikt-PR soll nicht
mergebar sein —, aber die Meldung legt eine falsche Fährte (sie klingt nach Ruleset-Fehler). Wer
sie sieht, prüft zuerst `gh pr view <n> --json mergeable`.

## Was das für den Karten-Contract des Boards heißt

Der Abschlussmechanismus für PR-gebundene Karten verlangt grüne, **repository-required** Checks
auf dem exakten Head-SHA. Heute findet er keine konfigurierten Required Checks und verweigert
deshalb den Abschluss — in dieser Welle musste der PM **zweimal** den Karten-Contract per Hand
auf `local-only` umstellen, um weiterarbeiten zu können.

Sobald dieses Ruleset aktiv ist, greift der Mechanismus wieder und funktioniert wie gedacht:
`all-green` ist required, meldet auf jedem PR einen Status und ist für einen Doku-PR genauso grün
wie für einen Code-PR. Der Handgriff entfällt. Drei Dinge sind dabei zu beachten:

1. **Contract wieder auf PR-gebunden umstellen.** Die zwei per Hand auf `local-only` gesetzten
   Karten sind Altlast, kein Dauerzustand. Neue PR-Karten können ab dann wieder mit
   `completion_contract: OWNER/REPO` laufen.
2. **Exact-Head ist streng.** Ein Push nach dem grünen Lauf entwertet den Check. Eine Karte, die
   nach dem CI-Lauf noch einen Commit nachschiebt, muss den Lauf abwarten — nicht den alten
   zitieren.
3. **Sieben-Tage-Fenster.** Ein PR, der länger als eine Woche liegt, braucht vor dem Abschluss
   einen frischen Lauf, auch wenn sich nichts geändert hat.

## Ausdrücklich nicht Teil dieses Vorschlags

* **Merge Queue** — löst ein Problem (gleichzeitige Merges entwerten sich gegenseitig), das bei
  einem mergenden Menschen nicht auftritt.
* **„Strict" Required Checks** — siehe Regel 1, erst bei einstelliger PR-Zahl sinnvoll.
* **CODEOWNERS / Pflicht-Reviews** — es gibt keinen zweiten menschlichen Reviewer.
* **Einzelne CI-Jobs als Required Checks** — der dokumentierte Fehler, den dieser ganze Vorschlag
  vermeidet.
