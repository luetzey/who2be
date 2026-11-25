# Auto-Merge für Agenten

Ein Agent mergt nicht. Er **fordert Auto-Merge an**: GitHub führt den Merge
selbsttätig aus, sobald alle Required Checks grün sind — und nur dann. Dieses
Dokument beschreibt den einen erlaubten Weg dorthin.

Alles hier mit **gemessen** Markierte stammt aus einem Lauf gegen dieses Repo bzw.
gegen die echte Approval-Engine dieser Maschine am 2026-09-23.

## Die drei Gates — sie ersetzen die Kommandosperre

Bis heute war die Absicherung gegen ungewollte Merges ein **Verbot**: die
Deny-Regeln der Agenten sperren jedes merge-ausführende Kommando. Das Verbot bleibt
unverändert bestehen. Was dazukommt, ist ein kontrollierter Weg daneben — und ab
dem Moment, in dem ein Agent Auto-Merge anfordern darf, sind nicht mehr das Verbot,
sondern **diese drei Gates** die Sicherung:

1. **Review freigegeben.** Auto-Merge wird erst nach einer erteilten Freigabe
   angefordert. Heute ist dieses Gate organisatorisch: Das Ruleset führt
   noch `required_approving_review_count: 0`, also hängt es daran, dass niemand
   vorher anfordert. Laut [ADR-0064](adr/0064-main-dauerhaft-gruen.md) wird
   der Wert auf `1` gesetzt. **Sobald das Ruleset umgestellt ist, erzwingt
   GitHub Gate 1 serverseitig.** Ein PR ohne Freigabe wird dann auch mit
   angefordertem Auto-Merge nicht gemergt. Wer die Freigabe liefert, ist noch
   offen (ADR-0064, Abschnitt 4). Die Regel „erst nach Freigabe anfordern“ gilt
   unabhängig davon weiter.
2. **`all-green` ist grün.** Der Aggregat-Job aus `.github/workflows/ci.yml` urteilt
   über alle CI-Jobs und ist der einzige Required Check. Begründung, warum genau
   einer und warum dieser: [`branch-protection-main.md`](branch-protection-main.md).
3. **Der Required Check ist aktiv.** Gate 2 wirkt nur, weil das Ruleset auf dem
   Hauptzweig `all-green` als `required_status_checks` führt. Ohne diese Regel wäre
   jeder PR sofort mergebar, und Auto-Merge würde nicht verzögern, sondern sofort
   durchgreifen.

Bis zur Ruleset-Umstellung ist Gate 1 das schwächste, weil es kein Server
erzwingt. Deshalb die Regel unten: anfordern **erst nach** freigegebenem Review,
nie vorher, nie „damit es schon mal läuft".

## Branch aktuell halten („strict“)

Laut [ADR-0064](adr/0064-main-dauerhaft-gruen.md) verlangt das Ruleset, dass
der Branch vor dem Merge auf dem Stand von `main` ist
(`strict_required_status_checks_policy: true`, „Require branches to be up to
date“). Für den Auto-Merge-Weg heißt das:

- **Vor dem Anfordern von Auto-Merge bzw. vor dem Merge den Branch auf `main`
  nachziehen.** Den Merge von `origin/main` in den PR-Branch macht der Agent,
  ohne Rebase und ohne Force-Push. Danach läuft `all-green` neu.
- `mergeStateStatus: BEHIND` bedeutet: Nachziehen fehlt. Der PR wird nicht
  gemergt, auch nicht mit angefordertem Auto-Merge. GitHub zieht ohne Merge
  Queue nicht selbst nach.
- Hat das Nachziehen einen Konflikt gelöst, ist der Stand neu. Erst kommt ein
  erneutes Review, dann wird angefordert (siehe
  [Auto-Merge war aktiv und ist plötzlich weg](#auto-merge-war-aktiv-und-ist-plötzlich-weg)).
- Nachziehen ohne Konflikt erzeugt einen neuen Head-SHA, also den
  Nachzieh-Commit. Die Freigabe gilt laut Checkliste für den exakten Head.
  Deshalb bestätigt der Reviewer den neuen Head: Der Nettodiff gegen `main`
  ist inhaltlich derselbe wie am freigegebenen Stand. Dafür muss `all-green`
  noch nicht durchgelaufen sein. Den Lauf sichern Gate 2 und 3 serverseitig.
- Nach dem Nachziehen laufen die Checks. Der PR ist dann nicht `CLEAN`, und
  die Anforderung wird angenommen. `expectedHeadOid` zeigt auf den
  Nachzieh-Commit. Das Kommando unten liest ihn selbst aus.
- Nachgezogen wird per „Update branch“ bzw. `gh pr update-branch <PR>`
  (Merge, kein Rebase) oder lokal per Merge von `origin/main`. Den Knopf zeigt
  GitHub für jeden zurückliegenden PR nur, wenn die Repo-Einstellung
  `allow_update_branch: true` gesetzt ist („Always suggest updating pull
  request branches“). Ohne sie gibt es ihn nur, solange „strict“ gilt. Am
  2026-11-25 stand sie auf `false`. Laut ADR-0064 wird sie vor „strict“
  eingeschaltet.
- PRs, die `apps/web/package-lock.json` ändern, werden **streng
  nacheinander** gemergt. Den nächsten erst nachziehen, wenn der vorige auf
  `main` liegt. Für mehrere solche PRs gleichzeitig wird kein Auto-Merge
  angefordert.
- Auch **Dependabot-PRs** brauchen die Pflicht-Freigabe, sobald das Ruleset
  `required_approving_review_count: 1` führt. `@dependabot rebase` zieht nach,
  ersetzt aber kein Review.

Solange das Ruleset noch „loose“ führt, ist Nachziehen Empfehlung, keine
Bedingung.

## Wer anfordern darf

Auto-Merge wird **nur nach freigegebenem Review** angefordert. Ein Agent, der seine
eigene Arbeit gerade fertiggestellt hat, fordert nicht selbst an — Freigabe und
Merge-Auslösung gehören nicht in dieselbe Hand.

> **Offene Owner-Entscheidung:** Welche Rolle konkret anfordert (@reviewer direkt
> nach der Freigabe, @pm nach der Freigabe, oder ausschließlich der Owner), ist noch
> nicht entschieden. Bis zur Entscheidung gilt: anfordern nur auf ausdrückliche
> Anweisung des Owners. Diese Zeilen werden ersetzt, sobald die Antwort vorliegt.

Der Grund, warum die Frage überhaupt offen ist und nicht beiläufig beantwortet wird:
Der Owner mergt als Squash. Dabei verlieren datei-gleiche und gestapelte PRs ihre
Verwandtschaft zum bereits gemergten Inhalt und kippen auf `CONFLICTING`, obwohl
inhaltlich nichts widerspricht. Wer anfordert, bestimmt damit die Merge-Reihenfolge
— und die kennt nur, wer alle offenen Pakete einer Welle sieht.

## Strukturelle Grenze — vor dem Planen lesen

Unser Review verlangt grüne Checks gegen den exakten Head-SHA. Ist das erfüllt,
ist der PR `CLEAN` — und genau dann lehnt GitHub Auto-Merge ab (`clean status`).
**Im normalen Ablauf Review-nach-CI greift Auto-Merge also nie.** Es hilft nur,
wenn nach der Freigabe noch Checks laufen (z. B. nach `update-branch` oder
Basiswechsel). Eine Nachtschicht „Reviewer fordert Auto-Merge an" staut deshalb
trotzdem nach dem ersten Paket je Kette — so am 2026-09-28 gemessen (#698/#699).
Wer Durchsatz über Nacht braucht, muss das dem Owner vorher so sagen und
Alternativen nennen (Owner mergt vor dem Schlafen, gestapelte PRs,
Owner-Freigabe für PM-Merge).

Mit „strict“ ([ADR-0064](adr/0064-main-dauerhaft-gruen.md)) wird der Fall
häufiger, in dem nach der Freigabe noch Checks laufen. Jeder PR muss vor dem
Merge nachgezogen werden, und danach läuft `all-green` neu. Den Stau löst das
nicht: Mergt ein anderer PR zuerst, liegt der Branch wieder zurück.

## Vor dem Aufruf — Checkliste

- [ ] Das Review ist **freigegeben**, nicht nur angefordert.
- [ ] Die Freigabe gilt für genau den aktuellen Head-SHA
      (`gh pr view <PR> --json headRefOid`). Auto-Merge ersetzt das Review-Gate
      nicht und verkürzt es nicht. `mergeStateStatus == CLEAN` ist **keine**
      Vorbedingung — bei `CLEAN` lehnt GitHub ab, das ist Fall (a).
- [ ] Der PR ist offen und hat keine ungelösten Konflikte.
- [ ] Der Branch ist auf `main` nachgezogen (`mergeStateStatus` nicht
      `BEHIND`), sobald das Ruleset „strict“ führt. Siehe
      [Branch aktuell halten](#branch-aktuell-halten-strict).
- [ ] `all-green` läuft noch (`gh pr checks <PR>`). Ist er auf dem Head schon
      grün, lehnt GitHub mit `clean status` ab — dann Fall (a) unter
      [Fehlerbilder](#pull-request-is-in-clean-status), Merge geht an den Owner.
- [ ] Das Ruleset auf dem Hauptzweig ist aktiv und führt `all-green`
      (`gh api repos/luetzey/who2be/rulesets`).
- [ ] `allow_auto_merge` ist `true`
      (`gh api repos/luetzey/who2be --jq .allow_auto_merge`).

## Das Kommando

Ein Kommando, `<PR>` durch die PR-Nummer ersetzen. Es ermittelt Node-Id und
Head-SHA selbst und ruft dann die Mutation auf:

```bash
PR=<PR>; gh api graphql -f query='mutation($id:ID!,$oid:GitObjectID!){enablePullRequestAutoMerge(input:{pullRequestId:$id,mergeMethod:SQUASH,expectedHeadOid:$oid}){clientMutationId}}' -F id="$(gh pr view "$PR" --json id --jq .id)" -F oid="$(gh pr view "$PR" --json headRefOid --jq .headRefOid)"
```

Erfolg sieht so aus:

```json
{"data":{"enablePullRequestAutoMerge":{"clientMutationId":null}}}
```

### Warum `expectedHeadOid` nicht weggelassen wird

Das Feld bindet die Anforderung an **genau den Commit**, den der Reviewer gesehen
hat. Ohne es mergt GitHub auch einen Stand, der nach der Freigabe noch dazukam —
Gate 1 leckt dann still. Pusht jemand nach der Anforderung neu, schlägt der
Auto-Merge fehl, statt ungeprüften Code auf den Hauptzweig zu bringen. Das ist der
gewünschte Ausgang, kein Defekt.

### Warum `SQUASH`

Deckungsgleich mit der heutigen Merge-Praxis des Repos. Eine andere Methode hier zu
wählen, würde die Historie des Hauptzweigs uneinheitlich machen.

### Die Felder sind belegt, nicht erinnert

Per Introspektion des Schemas geprüft (gemessen, lesend):

```bash
gh api graphql -f query='query($n:String!){__type(name:$n){inputFields{name type{kind name ofType{name}}}}}' -F n=EnablePullRequestAutoMergeInput
```

`EnablePullRequestAutoMergeInput`: `pullRequestId: ID!` (einziges Pflichtfeld),
`mergeMethod: PullRequestMergeMethod` (`MERGE`, `SQUASH`, `REBASE`),
`expectedHeadOid: GitObjectID`, `commitHeadline: String`, `commitBody: String`,
`authorEmail: String`, `clientMutationId: String`.

## Status abfragen

```bash
gh pr view <PR> --json state,mergeStateStatus,autoMergeRequest
```

- `autoMergeRequest: null` → Auto-Merge ist **nicht** aktiv.
- `autoMergeRequest: {"enabledBy": …, "mergeMethod": "SQUASH"}` → aktiv.
- `mergeStateStatus: "BLOCKED"` bei gesetztem `autoMergeRequest` → genau der
  erwünschte Wartezustand: angefordert, Checks noch nicht grün.
- `state: "MERGED"` → GitHub hat ausgeführt.

## Wieder abschalten

```bash
gh api graphql -f query='mutation($id:ID!){disablePullRequestAutoMerge(input:{pullRequestId:$id}){clientMutationId}}' -F id="$(gh pr view <PR> --json id --jq .id)"
```

`DisablePullRequestAutoMergeInput` kennt nur `pullRequestId: ID!` und
`clientMutationId` (gemessen, Introspektion) — insbesondere **kein**
`expectedHeadOid`.

## Fehlerbilder und ihre Deutung

### `Pull request is in clean status`

Der PR ist bereits sofort mergebar — es gibt nichts zu verzögern, und GitHub nimmt
die Anforderung deshalb nicht an. Dafür gibt es zwei Ursachen, und sie verlangen
Verschiedenes. Erst unterscheiden, dann handeln:

```bash
PR=<PR>; read -r BASE SHA < <(gh pr view "$PR" --json baseRefName,headRefOid --jq '"\(.baseRefName) \(.headRefOid)"'); echo "ruleset-checks: $(gh api "repos/luetzey/who2be/rules/branches/$BASE" --jq '[.[]|select(.type=="required_status_checks")|.parameters.required_status_checks[].context]|join(",")')"; echo "all-green@head: $(gh api "repos/luetzey/who2be/commits/$SHA/check-runs?check_name=all-green" --jq '[.check_runs[].conclusion]|join(",")')"
```

`rules/branches/<base>` liefert nur die Regeln, die auf dem Zielbranch **wirklich
greifen** (aktive Rulesets, passendes Ziel). Ein inaktives Ruleset oder ein
falscher Zielbranch fällt hier also auf, ohne dass man die Ruleset-Konfiguration
selbst lesen muss.

| Ausgabe | Fall | Bedeutung | Handlung |
|---|---|---|---|
| `ruleset-checks: all-green`, `all-green@head: success` | **(a) Checks schon grün** | Gate 3 ist da. Der PR ist mergebar, weil `all-green` auf genau diesem Head bereits `SUCCESS` ist. Auto-Merge ist hier nicht möglich — es gäbe nichts abzuwarten. | Nicht erneut anfordern. Den Merge an den **Owner** übergeben (PR-Nummer und geprüfter Head-SHA). Auf der Karte vermerken: Auto-Merge nicht angefordert, Grund `clean status` bei grünen Checks. |
| `ruleset-checks:` leer oder ohne `all-green` | **(b) Gate 3 fehlt** | Der Required Check greift auf diesem PR nicht (Ruleset inaktiv, falscher Zielbranch, Check-Name umbenannt). | Nicht anfordern, nicht mergen. Befund melden (Ausgabe der Diagnose mitschicken). |
| jede andere Kombination | unklar | Passt zu keinem der beiden Fälle. | Wie (b): melden, nicht raten. |

Fall (a) ist im Alltag der häufige: Das Review gibt erst frei, wenn die Checks auf
dem exakten Head-SHA grün sind — genau dann ist der PR `CLEAN`. Auto-Merge greift
also nur, wenn nach der Freigabe noch Checks laufen (z. B. nach `update-branch`
oder einem Basiswechsel). So gemessen am 2026-09-28 an #698 und #699: Ruleset
aktiv mit `all-green`, `all-green` auf dem Head `SUCCESS`, Anforderung abgelehnt,
Merge durch den Owner.

**Nicht tun, in beiden Fällen:** den PR stattdessen direkt mergen, auch nicht „nur
dieses eine Mal". In Fall (a) ist der PR zwar mergebar, der merge-ausführende Weg
bleibt aber gesperrt (siehe [Was gesperrt bleibt](#was-gesperrt-bleibt)) — die
Meldung ist keine Einladung, ihn zu umgehen. In Fall (b) fehlt genau die
Sicherung, die den Auto-Merge überhaupt verantwortbar macht.

### `Resource not accessible by integration` / Rechte-Ablehnung

Der benutzte Token hat keine Write-Rechte auf dem Repo. Auto-Merge aktivieren darf
nur, wer schreiben darf.

**Nicht tun:** einen anderen Token suchen oder Scopes erweitern. Fehlende Rechte
sind hier eine Aussage über die Rolle, kein technisches Hindernis — melden und
stoppen.

### Auto-Merge war aktiv und ist plötzlich weg

GitHub deaktiviert Auto-Merge selbsttätig, wenn jemand ohne Write-Rechte auf den
Head-Branch pusht oder der Base-Branch gewechselt wird. Mit `expectedHeadOid`
kommt der häufigere Fall dazu: ein neuer Commit nach der Anforderung lässt den
Auto-Merge fehlschlagen.

**Nicht tun:** kommentarlos neu anfordern. Der PR hat einen Stand, den niemand
freigegeben hat — erst Review, dann erneut anfordern.

### Der PR wird nicht gemergt, obwohl die Anforderung steht

Solange `all-green` nicht `SUCCESS` ist, passiert nichts. Das ist der Normalbetrieb,
kein Hänger. `gh pr checks <PR>` zeigt, worauf gewartet wird.

**Nicht tun:** den Check als Required entfernen, um „es freizugeben".

## Was gesperrt bleibt

Die Deny-Regeln der Agenten sperren weiterhin **jeden merge-ausführenden Weg**
(gemessen 2026-09-23 mit `hermes approvals test --json`, einer Dry-Run-Auswertung,
die nichts ausführt):

| Weg | Verdikt |
|---|---|
| `gh api graphql … enablePullRequestAutoMerge(…)` | **allow** — der Weg dieses Dokuments |
| `gh pr merge … --auto …` | **user-deny** |
| `gh api graphql … mergePullRequest(…)` | **user-deny** |
| `gh api -X PUT repos/…/pulls/<PR>/merge …` | **user-deny** |
| `gh api repos/…/merges …` | **user-deny** |

`gh pr merge --auto` ist **kein gleichwertiger Weg** zu dem Kommando oben, auch
wenn es dasselbe Ziel hat. Wer darauf läuft, hat die Regel getroffen — nicht einen
Fehler gefunden. Die Sperre wird nicht umformuliert, nicht umgangen, nicht
gelockert; das gilt auch, wenn der GraphQL-Weg gerade nicht funktioniert.

Selbst nachmessen, ohne etwas auszuführen:

```bash
hermes approvals test --json -- gh api graphql -f query='mutation($id:ID!){enablePullRequestAutoMerge(input:{pullRequestId:$id,mergeMethod:SQUASH}){clientMutationId}}' -F id=PR_x
```

## Owner-Abschnitt: Repo-Einstellung

Auto-Merge muss auf Repo-Ebene erlaubt sein. Gesetzt am 2026-09-23:

```bash
gh api -X PATCH repos/luetzey/who2be -F allow_auto_merge=true
```

Lesend verifizieren:

```bash
gh api repos/luetzey/who2be --jq '{allow_auto_merge,allow_squash_merge,allow_merge_commit,allow_rebase_merge}'
```

Erwartet: `allow_auto_merge: true`. Steht die Einstellung wieder auf `false`,
scheitert jede Anforderung, bevor irgendein Gate greift.

Vor der Umstellung auf „strict“ ([ADR-0064](adr/0064-main-dauerhaft-gruen.md))
zusätzlich „Always suggest updating pull request branches“ einschalten:

```bash
gh api -X PATCH repos/luetzey/who2be -F allow_update_branch=true
gh api repos/luetzey/who2be --jq .allow_update_branch   # erwartet: true
```

## Belegt, nicht behauptet

Der Weg wurde an einem echten PR in beide Richtungen gezeigt — **PR #593**, dem
PR, mit dem dieses Dokument selbst ins Repo kam:

| Zeitpunkt | Ereignis |
|---|---|
| 2026-09-22T20:41:55Z | Auto-Merge angefordert; `mergeStateStatus: BLOCKED`, `state: OPEN` |
| 2026-09-22T20:50:17Z | `all-green` meldet `conclusion: success` |
| 2026-09-22T20:50:29Z | GitHub mergt selbsttätig; `state: MERGED`, `mergeCommit b28c2ebd` |

Achteinhalb Minuten lang stand die Anforderung, ohne dass gemergt wurde — das
ist die Negativrichtung: ein PR mit noch nicht grünem `all-green` wird nicht
gemergt, egal wer den Auto-Merge angefordert hat. Zwölf Sekunden nach dem grünen
Check lag der Merge vor, ohne dass ein Kommando dazwischen lief.

Vollständige Messwerte: `.claude/plan/2026-09-23-0030_auto-merge-mechanik.md`.
