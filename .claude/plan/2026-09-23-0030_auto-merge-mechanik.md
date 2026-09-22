# Auto-Merge-Mechanik: Repo-Einstellung, erlaubter Agenten-Weg, Dokumentation

Karte: `t_8eb1cce4` · Branch: `who2be/t_8eb1cce4-auto-merge-mechanik-repo-einstellung-der`

## Outcome

Ein Agent kann nach freigegebenem Review **Auto-Merge anfordern**, ohne selbst zu
mergen. Der Weg ist gemessen, an einem echten PR in beide Richtungen belegt und in
`docs/auto-merge-agenten.md` dokumentiert, verlinkt aus `CONTRIBUTING.md`.

## Vorbedingung — geprüft, erfüllt

`gh api repos/luetzey/who2be/rulesets/16707501` (2026-09-23, lesend):

- `enforcement: "active"`, `conditions.ref_name.include: ["~DEFAULT_BRANCH"]`
- Regel `required_status_checks` mit `required_status_checks: [{"context": "all-green"}]`,
  `strict_required_status_checks_policy: false`
- Regel `pull_request` mit `required_approving_review_count: 0`
- Regeln `deletion`, `non_fast_forward`

Gate 3 steht also. Kein Grund zu blocken.

## Schritt 1 — Repo-Einstellung

Ist-Zustand (gemessen 2026-09-23): `allow_auto_merge: false`, `allow_squash_merge: true`,
`allow_rebase_merge: true`, `allow_merge_commit: true`, `delete_branch_on_merge: true`.

Ohne `allow_auto_merge: true` ist die Mutation gar nicht aufrufbar. Die Karte weist
das Setzen ausdrücklich dieser Karte zu („Pruefe den Ist-Zustand und setze ihn, falls
noetig"). Also `PATCH /repos/luetzey/who2be` mit `allow_auto_merge=true`.

`allow_rebase_merge` wird **nicht** angefasst: das Ruleset erlaubt heute alle drei
Merge-Methoden, eine Verengung wäre eine eigene Entscheidung und steht nicht auf
dieser Karte.

## Schritt 2 — den erlaubten Kommandoweg messen

Dry-Run gegen die echte Bewertungsfunktion (`hermes approvals test --json`, führt
nichts aus). Gemessen 2026-09-23:

| Kommando | Verdikt |
|---|---|
| `gh api graphql … enablePullRequestAutoMerge(…)` ohne `expectedHeadOid` | **allow** |
| `gh api graphql … enablePullRequestAutoMerge(…)` mit `expectedHeadOid` | **allow** |
| `gh api graphql … mergePullRequest(…)` | **user-deny** |
| `gh api -X PUT repos/…/pulls/N/merge …` | **user-deny** |
| `gh api repos/…/merges …` | **user-deny** |
| `gh pr merge … --auto …` | **user-deny** (bereits vom Tool-Guard hart abgewiesen) |

Ergebnis: Der GraphQL-Weg kommt durch, **jeder** merge-ausführende Weg bleibt gesperrt.
Keine Deny-Regel wird angefasst.

Zusätzlich: Feldnamen und Typen von `EnablePullRequestAutoMergeInput` und
`DisablePullRequestAutoMergeInput` per Introspektion belegen (lesend), nicht aus dem
Gedächtnis.

`mergeMethod: SQUASH` — deckungsgleich mit der Praxis des Owners.
`expectedHeadOid` gehört ins Hauptkommando: ohne das Feld mergt GitHub auch einen
Stand, der nach der Freigabe noch dazukam. Das ist die einzige Stelle, an der das
Review-Gate sonst leckt.

## Schritt 3 — Beleg an einem echten PR, in beide Richtungen

Testgegenstand ist der PR dieser Karte selbst (reiner Doku-PR, unkritisch).

1. PR öffnen, Auto-Merge per GraphQL anfordern, während `all-green` noch läuft.
   Beleg: `autoMergeRequest` ist gesetzt, `state: OPEN`.
2. **Negativrichtung:** solange `all-green` nicht `SUCCESS` ist, bleibt der PR offen.
   Beleg: `mergeStateStatus: BLOCKED` bei gesetztem `autoMergeRequest`, PR ungemergt.
3. **Positivrichtung:** sobald `all-green` grün ist, mergt GitHub selbsttätig.
   Beleg: `state: MERGED`, `mergedBy` und `mergeCommit` aus der API.

## Schritt 4 — Dokumentation

Neu: `docs/auto-merge-agenten.md`

- Die drei Gates (Review freigegeben, `all-green` grün, Required Check aktiv) und der
  Satz, dass sie ab jetzt an die Stelle der Kommandosperre treten.
- Das **eine** kopierbare Kommando mit Platzhalter für die PR-Nummer, inklusive
  Ermittlung von `pullRequestId` und `expectedHeadOid`.
- Checkliste vor dem Aufruf.
- Fehlerbilder mit Deutung — jedes mit der Aussage, was **nicht** zu tun ist.
- Was gesperrt bleibt und warum ein Deny-Treffer kein Fehler ist.
- Abschalten (`disablePullRequestAutoMerge`) und Statusabfrage.
- Owner-Abschnitt: Repo-Einstellung, lesende Verifikation.

`CONTRIBUTING.md` bekommt einen kurzen Abschnitt mit Verweis auf das Dokument.

## Schritt 5 — DoD

Reiner Doku-PR, kein Code. Deshalb:

- `uv run python scripts/check_code_refs.py .` → Exit 0 (Pflicht, sobald Doku Code zitiert)
- `uv run python scripts/changelog_fragments.py check`
- CHANGELOG-Fragment unter `changelog.d/`, nicht in die Sammeldatei
- `all-green` in CI grün

## Grenzen dieser Karte

- Keine Deny-Regel lockern, entfernen oder umformulieren.
- Kein direkter Merge, kein Push auf den Hauptzweig.
- Kein `dev`-Branch, kein Merger-Workflow, keine Bot-Identität.
- Keine Änderung an `.github/workflows/`, `CLAUDE.md`, `AGENTS.md`.

## Auf Zuruf angenommen

Die Rollenfrage („wer darf Auto-Merge anfordern") lag in der inzwischen archivierten
Schwesterkarte `t_484c6326` und ist dort unbeantwortet geblieben. Diese Karte verlangt
nur „nur nach freigegebenem Review". Das Dokument hält deshalb die **Bedingung** fest
(freigegebenes Review) und markiert die **Rollenzuordnung** sichtbar als offene
Owner-Entscheidung, statt sie stillschweigend selbst zu treffen.
