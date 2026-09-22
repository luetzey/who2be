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
   angefordert. Dieses Gate ist organisatorisch, nicht technisch — GitHub erzwingt
   es hier nicht, weil das Ruleset `required_approving_review_count: 0` führt.
   Es hängt daran, dass niemand vorher anfordert.
2. **`all-green` ist grün.** Der Aggregat-Job aus `.github/workflows/ci.yml` urteilt
   über alle CI-Jobs und ist der einzige Required Check. Begründung, warum genau
   einer und warum dieser: [`branch-protection-main.md`](branch-protection-main.md).
3. **Der Required Check ist aktiv.** Gate 2 wirkt nur, weil das Ruleset auf dem
   Hauptzweig `all-green` als `required_status_checks` führt. Ohne diese Regel wäre
   jeder PR sofort mergebar, und Auto-Merge würde nicht verzögern, sondern sofort
   durchgreifen.

Gate 1 ist das schwächste, weil es kein Server es erzwingt. Deshalb die Regel unten:
anfordern **erst nach** freigegebenem Review, nie vorher, nie „damit es schon mal
läuft".

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

## Vor dem Aufruf — Checkliste

- [ ] Das Review ist **freigegeben**, nicht nur angefordert.
- [ ] Der PR ist offen und hat keine ungelösten Konflikte.
- [ ] `all-green` läuft oder ist grün (`gh pr checks <PR> `).
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

Der PR ist bereits sofort mergebar — es gibt nichts zu verzögern. Praktisch heißt
das fast immer: der Required Check greift auf diesem PR nicht (Ruleset inaktiv,
falscher Zielbranch, Check-Name nachträglich umbenannt).

**Nicht tun:** den PR stattdessen direkt mergen, auch nicht „nur dieses eine Mal".
Die Meldung besagt, dass **Gate 3 fehlt** — also genau die Sicherung, die den
Auto-Merge überhaupt verantwortbar macht. Stattdessen: das Ruleset prüfen und den
Befund melden.

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

## Belegt, nicht behauptet

Der Weg wurde an einem echten PR in beide Richtungen gezeigt: Anforderung sichtbar
als `autoMergeRequest`, kein Merge solange `all-green` nicht grün war, Merge durch
GitHub sobald er grün war. Die Belege stehen in
`.claude/plan/2026-09-23-0030_auto-merge-mechanik.md`.
