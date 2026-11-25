# ADR-0064 — `main` dauerhaft grün: Branch aktuell vor dem Merge, Pflicht-Review, Arbeitsregeln

- Status: **Accepted** (Owner, 2026-11-25) für die Punkte in Abschnitt 2.
  Abschnitt 4 (wer das Pflicht-Review liefert) ist **offen**.
- Datum: 2026-11-25
- Gemessen gegen: `gh api repos/luetzey/who2be/rulesets/16707501` am
  2026-11-25 und `gh pr list --state open` am selben Tag.
- Bezug: [`docs/branch-protection-main.md`](../branch-protection-main.md)
  (Ruleset, Begründung „loose“ und „0 Reviews“, die diese ADR ablöst),
  [`docs/auto-merge-agenten.md`](../auto-merge-agenten.md) (Gate 1).
- Karte: t_fa6963c2.

## 1. Kontext

Das Ruleset `16707501` auf dem Default-Branch hat heute vier Regeln. Zwei davon
sind für diese ADR wichtig, und beide waren 2026-09-22 bewusst so gesetzt:

| Feld | Ist (2026-11-25) | Begründung damals |
| --- | --- | --- |
| `strict_required_status_checks_policy` | `false` („loose“) | Bei 11 offenen PRs wäre „strict“ eine Nachzieh-Tretmühle. Umstellen, sobald die Zahl offener PRs einstellig und stabil ist. |
| `required_approving_review_count` | `0` | Es gibt keinen zweiten Menschen, Review kommt aus dem Board (`@reviewer`). |
| Required Check | `all-green` | unverändert richtig |
| `bypass_actors` | leer | unverändert |

„Loose“ prüft `all-green` gegen den Head des PR, nicht gegen das, was nach dem
Merge auf `main` liegt. Zwei PRs, die je für sich grün sind, können zusammen
`main` rot machen. Das Review-Gate ist reine Disziplin, kein Server hält es.

Die Annahme „wir stellen um, wenn es einstellig ist“ hat nicht getragen. Die
Zahl offener PRs ist nicht gesunken, sondern gestiegen: In Welle 2 staute
sich die Arbeit, am 2026-11-25 waren **21 PRs** offen. Viele davon waren fertig,
aber nicht gemergt. Sie liegen hinter `main`, ihre grünen Läufe veralten, und
jeder Merge macht den Rest wieder unsicher. Den Stau löst „loose“ nicht. Es
verschiebt ihn nur auf den Moment nach dem Merge, und dann ist `main` rot.

## 2. Entscheidung (Owner, 2026-11-25)

Yannick hat am 2026-11-25 über Atlas mit „Ja bitte“ entschieden:

1. **Branches müssen vor dem Merge aktuell sein.** Im Ruleset gilt
   `strict_required_status_checks_policy: true` („Require branches to be up to
   date before merging“). Eine Merge Queue wäre die bessere Mechanik, gibt es
   aber für Repos eines persönlichen Kontos nicht. Deshalb bleibt es bei
   „strict“.
2. **Mindestens ein Pflicht-Review.** `required_approving_review_count: 1`.
3. **Dieselben Regeln gelten für `who2be-website`.**

Dazu zwei Arbeitsregeln, die keine Servereinstellung abbildet:

- **Rot wird am selben Tag behoben.** Was auf `main` oder in einem offenen PR
  rot ist, wird am selben Tag repariert. Danach erst kommt neue Arbeit.
- **Höchstens 3–5 fertige PRs offen.** Ist die Grenze erreicht, wird zuerst
  gemergt oder geschlossen und erst dann neu geöffnet.

Die Ruleset-Änderung nimmt Yannick als Admin selbst vor. Sie ist nicht Teil
dieser ADR und nicht Teil des PR, mit dem sie ins Repo kommt.

## 3. Begründung und Folgen

**Warum „strict“ jetzt trotz vieler PRs.** Die Tretmühle, vor der
`branch-protection-main.md` gewarnt hat, gibt es. Ihre Ursache ist aber die
Zahl offener PRs, nicht „strict“. Die Arbeitsregel „höchstens 3–5“ setzt genau
dort an. Bei 3–5 PRs kostet ein Nachziehen je Merge wenige CI-Läufe. „Loose“
dagegen kostet einen roten `main`, und den bezahlen alle offenen PRs.

**Was „strict“ im Alltag heißt.** Vor dem Merge (und vor dem Anfordern von
Auto-Merge) wird der Branch auf `main` nachgezogen, per
„Update branch“ bzw. Merge von `origin/main` in den PR-Branch, ohne Rebase und
ohne Force-Push. Danach läuft `all-green` neu. Erst dieser Lauf zählt.

**Nebeneffekt für Auto-Merge.** Nach dem Nachziehen laufen die Checks noch.
Der PR ist dann nicht `CLEAN`, und Auto-Merge lässt sich anfordern. Die
strukturelle Grenze aus `auto-merge-agenten.md` (Review nach CI, also `CLEAN`,
also keine Anforderung möglich) betrifft dann seltener den Normalfall.
Mergt aber ein anderer PR dazwischen, liegt der Branch wieder zurück, und
GitHub zieht ohne Merge Queue nicht selbst nach. Auto-Merge wartet dann, bis
jemand erneut nachzieht.

**Review-Einstellungen, die dazu passen müssen.** Damit das Nachziehen eine
erteilte Freigabe nicht jedes Mal entwertet, bleiben
`dismiss_stale_reviews_on_push: false` und `require_last_push_approval: false`
so, wie sie heute stehen. Ein Nachzieh-Merge ohne Konflikt ändert inhaltlich
nichts am PR. Gibt es einen Konflikt, ist das Ergebnis ein neuer Stand und
braucht ein neues Review (Regel aus `CONTRIBUTING.md`, „After resolving a
conflict: read the net diff“).

**Vor „strict“: „Always suggest updating pull request branches“
einschalten.** Die Repo-Einstellung `allow_update_branch` steht heute auf
`false` (gemessen 2026-11-25, `gh api repos/luetzey/who2be --jq
.allow_update_branch`). Laut GitHub-Doku („Managing suggestions to update pull
request branches“) bietet die PR-Seite das Nachziehen ohne die Einstellung nur
an, wenn der Zielbranch „up to date“ verlangt **und** der Branch zurückliegt.
Vor der Umstellung, also beim Abbau des Staus, bliebe sonst nur Nachziehen
per Hand oder per `@dependabot rebase`. Mit der Einstellung kann jeder mit
Schreibrecht jeden zurückliegenden PR per Knopf aktuell machen, unabhängig vom
Ruleset. Deshalb wird `allow_update_branch: true` **vor** „strict“ gesetzt
(Befund der PR-Triage, Karte t_5beb7cc9).

**Lockfile-PRs von `apps/web` nacheinander.** PRs, die
`apps/web/package-lock.json` ändern, werden streng nacheinander gemergt. Erst
der nächste wird nachgezogen, nachdem der vorige auf `main` liegt. Zwei
Lockfile-Änderungen, die je für sich grün sind, ergeben zusammen nicht
verlässlich einen gültigen Lockfile. Nachziehen erzeugt dort oft Konflikte,
und die müssen neu aufgelöst werden.

**Auch Dependabot-PRs brauchen die Freigabe.** Mit
`required_approving_review_count: 1` kommt kein Dependabot-PR mehr ohne
Freigabe auf `main`. Wer das Pflicht-Review liefert (Abschnitt 4), liefert es
also auch für die Dependency-Updates. Bei der Zahl der Dependabot-PRs ist das
ein spürbarer Teil der Last.

**Gate 1 wird serverseitig.** Mit `required_approving_review_count: 1` erzwingt
GitHub die Freigabe. Bisher war das organisatorisch. Bis Abschnitt 4
entschieden ist, ist das aber noch nicht wirksam, siehe dort.

## 4. Offen: Wer liefert das Pflicht-Review?

**Diese Weiche ist nicht entschieden.** Die ADR beschreibt die Optionen, sie
wählt keine.

Das Problem: Alle Agenten-PRs laufen unter dem Konto `luetzey`. Das ist auch
Yannicks Konto. GitHub lässt den Autor eines PR seinen eigenen PR nicht
freigeben. „Yannick klickt selbst“ geht deshalb nicht, solange PRs unter
`luetzey` geöffnet werden. Eine Freigabe muss von einem zweiten Konto kommen.

| | Option A: Agenten bekommen einen Machine-User als Autor | Option B: Machine-User als Reviewer |
| --- | --- | --- |
| Was sich ändert | Agenten pushen und öffnen PRs unter einem eigenen Konto (etwa `who2be-agent`). `luetzey` ist nicht mehr Autor. | Agenten öffnen PRs weiter unter `luetzey`. `@reviewer` gibt unter einem eigenen Konto frei. |
| Wer freigibt | `luetzey`, also Yannick per Klick oder `@reviewer` mit Yannicks Token (Unterweiche) | das Reviewer-Konto |
| Für | Autor und Freigabe sind getrennt. Yannick kann selbst freigeben. Die Historie zeigt, was ein Agent geschrieben hat. | Am wenigsten Umbau: nur `@reviewer` braucht ein neues Token. |
| Gegen | Alle Agenten-Profile brauchen ein neues Token und eine neue Git-Identität. CLA- und Commit-Regeln für das Bot-Konto sind zu prüfen. | Ein Agent gibt einen Agenten frei. Der Server erzwingt damit eine Board-Rolle, aber keinen Menschen. |
| Gemeinsam | Ein zweites GitHub-Konto mit Schreibrecht auf beide Repos (GitHub erlaubt einen Machine-User je Person). Dessen Token ist ein neues Geheimnis, das gepflegt werden muss. | |

Weitere denkbare Wege, nur zur Vollständigkeit: eine GitHub App als Reviewer,
deren Freigaben für das Ruleset noch zu prüfen wären, oder Yannick als
Bypass-Actor. Der Bypass hebelt aber Punkt 2 der Entscheidung für genau den
Fall aus, der ihn betrifft.

**Folge für die Reihenfolge, solange die Weiche offen ist.** Stellt man
`required_approving_review_count` auf `1`, bevor ein zweites Konto freigeben
kann, ist kein PR mehr mergebar. Auch Yannicks eigene Klicks zählen dann nicht,
denn er ist über `luetzey` Autor jedes Agenten-PR. „Strict“ (Punkt 1) hängt
an dieser Weiche nicht und kann sofort gelten.

## 5. Verworfen

- **„Loose“ beibehalten, bis die PR-Zahl einstellig ist.** Das war der Stand
  seit 2026-09-22. Die Zahl ist nicht von selbst gesunken (21 offen am
  2026-11-25).
- **Merge Queue.** Wäre die richtige Mechanik für viele gleichzeitige PRs, ist
  für Repos eines persönlichen Kontos aber nicht verfügbar.
- **Ohne Pflicht-Review weiter.** Gate 1 bliebe dann Disziplin. Der Owner hat
  ausdrücklich ein Review verlangt, das der Server erzwingt.

## 6. Umsetzung

| Schritt | Wer | Stand |
| --- | --- | --- |
| Repo-Einstellung `allow_update_branch: true` („Always suggest updating pull request branches“), **vor** „strict“ | Yannick (Admin) | offen (heute `false`) |
| Ruleset `16707501`: `strict_required_status_checks_policy: true` | Yannick (Admin) | offen |
| Ruleset `16707501`: `required_approving_review_count: 1` | Yannick (Admin) | offen, erst nach Abschnitt 4 |
| Gleiche Regeln für `who2be-website` | Yannick / eigene Karte | offen |
| Doku: `auto-merge-agenten.md`, `branch-protection-main.md`, `AGENTS.md`, `CONTRIBUTING.md` | @coder (diese Karte) | mit dieser ADR |

Nachmessen, ob die Umstellung greift:

```bash
gh api repos/luetzey/who2be --jq .allow_update_branch
gh api repos/luetzey/who2be/rulesets/16707501 \
  --jq '.rules[] | select(.type=="pull_request" or .type=="required_status_checks") | .parameters | {required_approving_review_count, strict_required_status_checks_policy}'
```
