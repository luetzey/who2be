# Branch-Protection für `main`

**Status: umgesetzt am 2026-09-22, serverseitig nachgemessen am 2026-09-24.** Dieses
Dokument war ursprünglich ein Vorschlag; er ist angenommen und angewendet. Es bleibt als
Entscheidungsgrundlage stehen — es begründet, warum genau ein Required Check und welcher.
Die Nutzlast in §„Nutzlast, die angewendet wurde" ist Beleg, kein offener Auftrag; die
Karte P3b, die das Einschalten beauftragte, ist geschlossen (als Dublette archiviert,
gültig waren `t_b0233031` / `t_25a1e9f2`). Es gibt zu diesem Ruleset keine offene Aufgabe.

Gemessener Ist-Zustand, `gh api repos/luetzey/who2be/rulesets/16707501` am **2026-09-24**
(gekürzt auf die entscheidenden Felder):

```json
{
  "id": 16707501, "name": "rule 1", "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "pull_request", "parameters": {
        "required_approving_review_count": 0,
        "allowed_merge_methods": ["merge", "squash", "rebase"] } },
    { "type": "required_status_checks", "parameters": {
        "strict_required_status_checks_policy": false,
        "required_status_checks": [{ "context": "all-green" }] } }
  ],
  "bypass_actors": [], "current_user_can_bypass": "never",
  "updated_at": "2026-09-22T22:04:14+02:00"
}
```

Vier Regeln also, nicht zwei; `all-green` ist der **einzige** Required Check, Modus „loose"
(`strict_… : false`), und das Ruleset greift ausschließlich auf dem Default-Branch
(`~DEFAULT_BRANCH`). `required_linear_history` ist bewusst **nicht** enthalten (§4).

> **Was das Ruleset nicht tut: Review erzwingen.** `required_approving_review_count: 0` —
> die `pull_request`-Regel verlangt einen PR, aber **keine** Approval. Wer wissen will, was
> serverseitig gilt, darf das nicht mit der Review-Pflicht im Team verwechseln: die ist
> Disziplin (Board-Rolle `@reviewer`), keine Servereinstellung. Ein Agent könnte seinen
> eigenen PR technisch durchbekommen, wenn `all-green` grün ist; dass er es nicht tut, ist
> Arbeitsregel, nicht Mechanik. Begründung für die 0 siehe §3.

Grundlage: Recherchebericht `workflow-idee-code-review-2026-09-22.md`, Abschnitt P3, sowie die
dort zitierte GitHub-Dokumentation zu Rulesets.

## Ausgangslage (Zustand vor dem Einschalten, 2026-09-22)

Diese Tabelle ist **Historie** — sie beschreibt den Stand *vor* der Änderung vom
2026-09-22. Der heutige Stand steht im Ruleset-Auszug oben.

| Fakt | Wert damals (2026-09-22, vor dem Einschalten) |
|---|---|
| Ruleset `16707501` ("rule 1"), `enforcement: active` | genau zwei Regeln: `deletion`, `non_fast_forward` (heute: vier, zusätzlich `pull_request` und `required_status_checks`) |
| Required Checks | **damals keine** — heute `all-green`, siehe Auszug oben |
| `bypass_actors` | **leer** — das Ruleset gilt auch für den Owner (heute unverändert leer) |
| Erlaubte Merge-Methoden | Merge-Commit, Squash und Rebase, alle drei aktiv (heute unverändert) |
| Branch nach Merge löschen | aktiv |

Force-Push und Löschen von `main` waren damit bereits gesperrt. Was damals fehlte, war die
Verbindung zwischen „CI ist grün" und „darf gemergt werden": **CI war bis zum 2026-09-22
formal nirgends verpflichtend.** Seither ist sie es — `all-green` ist Required Check auf
`main`, und ohne grünen Lauf auf dem exakten Head-SHA ist kein PR mergebar.

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
  offene PR nach *jedem* fremden Merge neu gebaut wird. Bei **11 offenen PRs** (Stand
  2026-09-22) ist das
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
  umgangen wird, ist schlimmer als keine. **Konsequenz, die man kennen muss:** das Ruleset
  erzwingt damit serverseitig **kein** Review (`required_approving_review_count: 0`, gemessen
  2026-09-24). Serverseitig verpflichtend ist ausschließlich: PR statt Direkt-Push, und
  `all-green` grün. Alles, was darüber hinaus an Review passiert, ist Team-Disziplin.
* **Für Agenten:** keine Änderung. Sie arbeiten bereits ausschließlich über Branch + PR.

### 4. Require linear history — **nicht empfohlen**, nicht eingeschaltet; Begründung unten

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

## Nutzlast, die angewendet wurde

Diese zwei Regeln wurden am 2026-09-22 zum bestehenden Ruleset `16707501` **ergänzt**;
`deletion` und `non_fast_forward` blieben unverändert. Der Block ist **Beleg und Historie**,
kein offener Auftrag — siehe den gemessenen Ist-Zustand am Kopf des Dokuments. (Die damalige
Vorbedingung — „erst ausführen, wenn der `all-green`-Job einmal auf `main` gelaufen ist",
sonst kennt GitHub den Check-Namen nicht und jeder offene PR hängt auf „Expected" — war zum
Zeitpunkt der Anwendung erfüllt.)

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

Nach dem Anwenden geprüft — und heute noch gültig: ein offener PR zeigt `all-green` in seiner
Checks-Liste als **Required**. Steht dort stattdessen „Expected — Waiting for status to be
reported", ist der Name
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
auf dem exakten Head-SHA. Vor dem 2026-09-22 fand er keine konfigurierten Required Checks und
verweigerte deshalb den Abschluss — in jener Welle musste der PM **zweimal** den Karten-Contract
per Hand auf `local-only` umstellen, um weiterarbeiten zu können.

Seit das Ruleset aktiv ist, greift der Mechanismus wieder und funktioniert wie gedacht:
`all-green` ist required, meldet auf jedem PR einen Status und ist für einen Doku-PR genauso grün
wie für einen Code-PR. Der Handgriff entfällt. Drei Dinge sind dabei zu beachten:

1. **Contract wieder auf PR-gebunden umstellen.** Die zwei per Hand auf `local-only` gesetzten
   Karten sind Altlast, kein Dauerzustand. Neue PR-Karten laufen seither wieder mit
   `completion_contract: OWNER/REPO`.
2. **Exact-Head ist streng.** Ein Push nach dem grünen Lauf entwertet den Check. Eine Karte, die
   nach dem CI-Lauf noch einen Commit nachschiebt, muss den Lauf abwarten — nicht den alten
   zitieren.
3. **Sieben-Tage-Fenster.** Ein PR, der länger als eine Woche liegt, braucht vor dem Abschluss
   einen frischen Lauf, auch wenn sich nichts geändert hat.

## Ausdrücklich nicht eingeschaltet

Diese Punkte waren nicht Teil des Vorschlags und sind entsprechend auch heute im Ruleset
nicht enthalten (Stand 2026-09-24):

* **Merge Queue** — löst ein Problem (gleichzeitige Merges entwerten sich gegenseitig), das bei
  einem mergenden Menschen nicht auftritt.
* **„Strict" Required Checks** — siehe Regel 1, erst bei einstelliger PR-Zahl sinnvoll; das
  Ruleset führt `strict_required_status_checks_policy: false`.
* **CODEOWNERS / Pflicht-Reviews** — es gibt keinen zweiten menschlichen Reviewer; das Ruleset
  führt `required_approving_review_count: 0`.
* **Einzelne CI-Jobs als Required Checks** — der dokumentierte Fehler, den diese Konfiguration
  vermeidet; required ist ausschließlich `all-green`.
* **`required_linear_history`** — bewusst nicht, Begründung in §„Der Widerspruch bei
  ‚Require linear history'".
