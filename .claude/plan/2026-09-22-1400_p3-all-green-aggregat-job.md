# P3 — Aggregierter `all-green`-Job als einziger kuenftiger Required Check

Karte: `t_b0233031` · Branch: `who2be/t_b0233031-p3-branch-protection-fuer-main-ein-aggre`
Grundlage: `/home/luetzey/recherche/workflow-idee-code-review-2026-09-22.md`, Abschnitt P3 + Schritt 1 + Quellenanhang.

## Zeitpunkt-Gate (Karte: "erst wenn PR #560 gemergt ist")

Gemessen bei Start: `#560` offen (MERGEABLE, kein Draft). **Kein Block**, Begruendung als
Karten-Kommentar hinterlegt: die Elternkarte hat die Wartebedingung ausdruecklich auf die
*Repo-Konfiguration* eingeengt (P3b, `t_61c8d42c`, wartet auf den Owner), der PM-Kommentar auf
dieser Karte bestaetigt Vorfahrt an `ci.yml`, und AK3 verlangt das Ruleset ohnehin nur als
**Dokument**. Ein nicht-required Job blockiert keinen offenen PR.

## Gemessener Ausgangsstand

| Fakt | Wert | Beleg |
|---|---|---|
| Jobs in `ci.yml` | `changes`, `python`, `web`, `compose-smoke`, `e2e`, `e2e-billing-cloud`, `audit` | Datei selbst gelesen, nicht aus dem Bericht |
| Aggregat-Job | existiert **nicht** | dito |
| Ruleset 16707501 | `active`, nur `deletion` + `non_fast_forward` | PM-Messung, unveraendert |
| `HEAD` vs `origin/main` | Vorfahr, 23 Commits zurueck, `ci.yml` **identisch** | `git merge-base --is-ancestor`, `git diff --stat` |
| Kollision an `ci.yml` | PR #518 (Dependabot, Step-Version) und **PR #581** (P4-Skip-Budget, aendert den `python`-Job) | `gh pr view --json files` |

`#581` ist neu gegenueber der PM-Messung und beruehrt `ci.yml` ebenfalls. Kein Strukturkonflikt
(dort Steps im `python`-Job, hier ein neuer Job am Dateiende), aber der Owner muss die Reihenfolge
kennen.

## Der Kern: warum eine generische "kein Job ist rot"-Pruefung nicht reicht

Die naive Auswertung lautet "kein Vorgaenger hat `failure`". Sie ist in genau diesem Repo falsch,
weil `skipped` hier **zwei voellig verschiedene Dinge** heisst:

1. **Legitim:** die Doku-Allowlist im `changes`-Job hat `code=false` ergeben, die fuenf schweren
   Jobs sind bewusst uebersprungen. Das ist der Normalfall bei Doku-PRs und muss **gruen** sein.
2. **Gefaehrlich:** der `changes`-Job selbst ist rot. Dann werden alle von ihm abhaengigen Jobs
   ebenfalls `skipped` — nicht weil sie nicht noetig waren, sondern weil das Tor kaputt ist. Eine
   Auswertung, die `skipped` pauschal durchwinkt, wird hier **gruen, ohne dass irgendetwas
   geprueft wurde**. Genau die Sorte stilles Gruen, gegen die die Karte geschrieben ist.

Beide Faelle sehen in `needs.*.result` **identisch** aus. Unterscheidbar sind sie nur an einer
zusaetzlichen Information: `needs.changes.result` und `needs.changes.outputs.code`.

Daraus die Regel, die der Job implementiert — **erwartungsbasiert statt verbotsbasiert**:

* `changes` **muss** `success` sein. Sonst rot, ohne weitere Pruefung. (Schliesst Fall 2.)
* `audit` haengt an keinem Pfadfilter und **muss** `success` sein.
* Die fuenf gegateten Jobs werden gegen ein **erwartetes** Ergebnis geprueft, das aus
  `code` folgt:
  * `code == 'true'` → jeder Job muss `success` sein. `skipped` ist hier ein Fehler.
  * `code == 'false'` → jeder Job muss `skipped` sein. (Fall 1, legitim.)
  * alles andere → fail-closed, `success` verlangt.

Ein `cancelled` oder `failure` faellt damit in jedem Zweig durch, ohne dass es eigens aufgezaehlt
werden muss. Eine Liste erlaubter Ergebnisse waechst still mit neuen Conclusion-Werten; eine Liste
*erwarteter* Ergebnisse nicht.

## Job-Name

Job-Id **`all-green`**, `name:` bewusst identisch gesetzt, damit der Eintrag in der Checks-Liste
exakt `all-green` heisst. Bericht, Z. 89: Required Checks werden per exakter Namensgleichheit
gebunden — ein spaeterer Rename bricht jeden offenen PR. Der Name steht deshalb ab jetzt fest und
wird in P3b woertlich abgetragen.

`needs:` enthaelt **alle sieben** Jobs, `changes` eingeschlossen — ohne ihn waere Fall 2 blind.

## Empirische Belege (AK2) — Plan

Drei Laeufe, alle als PR **gegen den Feature-Branch**, nicht gegen `main` (dann ist die
Merge-Base der Branch-Head und der Diff enthaelt die `ci.yml`-Aenderung nicht, was fuer den
Doku-Fall Voraussetzung ist):

* **Beleg A1 (gefaehrlicher Fall, billig):** `changes` faellt absichtlich hart aus → fuenf Jobs
  `skipped`, `audit` gruen → `all-green` muss **rot** sein. Das ist der Lauf, den ein naiver
  Aggregat-Job gruen faerben wuerde.
* **Beleg A2 (gewoehnlicher Fall):** `audit` faellt absichtlich aus, voller Lauf → `all-green`
  muss **rot** sein.
* **Beleg B (Doku-Allowlist):** reiner Doku-Diff → `code=false`, fuenf Jobs `skipped`,
  `all-green` muss **gruen** sein.

Beleg-Branches werden danach nicht geloescht (Team-Regel: Remote-Branch-Loeschung ist
Owner-Sache), die PRs werden geschlossen und im Handoff verlinkt.

## Ruleset-Vorschlag (AK3–AK5)

Neues Dokument `docs/branch-protection-main.md`, **nicht angewendet**. Je Regel: was sie
verhindert, was sie kostet, was sie fuer Agenten heisst. Offener Punkt, den das Dokument
entscheiden muss: *Require linear history* verbietet Merge-Commits und damit den `--no-ff`-Weg,
den dieses Team zur Konfliktaufloesung tatsaechlich benutzt (zuletzt `t_fc770076`, Merge-Commit
`35536a4c`). Die Karte erlaubt eine Empfehlung nur, wenn dieser Widerspruch aufgeloest wird.

## Out of Scope

Ruleset aktivieren. Bestehende Jobs oder Pfadfilter umbauen. Merge Queue. `CLAUDE.md:152/:234`
(`npx tsc --noEmit`) — bekannt falsch, zieht der Owner selbst nach.
