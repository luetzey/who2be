# Backlog-Aufbereitungslauf 81 — Protokoll

**Datum:** 2026-11-14 · **Basis:** `main` @ `f89acf87` (Baum `c751ed64`) ·
**Fenster seit Lauf 80: 0 Commits, zum siebten Mal in Folge** · **42 offene PRs**
_(waren 39)_ über **44** Dateipfade.

## Der Lauf in fünf Sätzen

1. **Die Lage hat sich geändert, und zwar nicht zum Guten: `pip-audit` meldet
   heute 7 CVEs in 4 Paketen, nicht mehr eine.** Neu sind `dnspython 2.9.0`
   (CVE-2026-128089), `opentelemetry-api 1.45.1` (CVE-2026-126360) und
   **vier CVEs auf `soupsieve 2.9.2`** (CVE-2026-126190/126191/126192/126193).
   Der Baum ist bitgleich — die Advisory-Datenbank hat sich bewegt, nicht das
   Repo (Regel 176/181).
2. **Damit ist die zentrale Aussage der letzten acht Läufe überholt: „#1120 ist
   ein Klick und das Gate ist grün" stimmt nicht mehr.** Selbst gemessen am
   Inhalt von #1120: `pip-audit` **Exit 1**, **6** verbleibende CVEs.
3. **Der vollständige grüne Weg ist heute gemessen und er ist kurz:**
   #1120 + #1141 + #1142 mergen (alle drei einzeln konfliktfrei, sequenziell
   sauber) **plus** ein `uv lock --upgrade-package soupsieve` (42+/11− in
   `uv.lock`). Danach `pip-audit` **Exit 0**, „No known vulnerabilities found".
4. **Der Zuwachs im PR-Bestand ist diesmal NICHT nur der Lauf selbst** —
   Weiche 51 ist in dieser Runde widerlegt: von 39 auf 42 sind **zwei** Zuwächse
   Sicherheits-Fixes (#1141, #1142), einer das Protokoll von Lauf 80 (#1140).
5. **Alle vier `agent-ready`-Bodies tragen eine Anweisung, die seit heute
   schädlich ist:** „der `audit`-Job-Log nennt als **einzigen** Fund
   `oauthlib 4.0.0` — nennt er etwas anderes, ist es **deins**". Heute nennt der
   Log **vier** Pakete. Wer der Anweisung folgt, sucht im eigenen Paket einen
   Fehler, den es nicht gibt.

## Gates — ohne vorherige Reparatur, Exit-Codes am unverketteten Befehl

Node **v22.23.4**, npm **10.9.9**, uv **0.11.32**. Klon war shallow (50) auf
**1676** Commits nach `--unshallow`. `npm`-Gates in `apps/web/` (`pwd`-Beleg),
Python-Gates im Repo-Root, jede sequenziell.

| Gate | Ergebnis | gegen Lauf 80 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `uv run --no-project python scripts/changelog_fragments.py check` | **Exit 0**, **405** Fragment(e); `ls changelog.d/*.md \| wc -l` auf **406** (`README.md`) | gleich |
| `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | **Exit 1** — **7 CVEs in 4 Paketen** bei **398** Requirements | **verschlechtert: war 1 CVE in 1 Paket** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | **Exit 1**, **28 moderate** (`glob 9.0.0 - 14.0.1`, `minimatch 7.0.0 - 11.0.0`, dev-only) | gleich |
| `npx playwright test --list --project=chromium` | **44 Tests in 9 Dateien** (billing 5, consent-overlay 2, editor-profiles 6, journeys 6, navigation 3, public 4, review-gate 2, **scroll-guard 15**, status-actions-viewport 1) | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** Bytes | **16. identische Messung** |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | **Exit 0**, **64 passed** | gleich |
| `npm run test:coverage` | **nicht gefahren, mit Grund** — Fenster **0 Commits**, `git diff --name-only f89acf87 origin/main -- apps/web/src` auf **0** Zeilen | übernommen aus Lauf 74 |
| Coverage | **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet** | — |
| **`main`-CI am Kopf `f89acf87`** | Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen — **2 von 14** Jobs rot (`audit`, `all-green`), an der Job-Liste gezählt | **unverändert rot, 8 Tage** |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` | **57. Messung in Folge** |

Zeichengleiche Baum-Gates an einem bitgleichen Baum sind die Erwartung, kein
Befund: `rev-list --count f89acf87..origin/main` auf **0**, Baum `c751ed64`,
`status --porcelain` leer. **Advisory-gefütterte Gates sind trotz des leeren
Fensters gefahren** (Regel 45/181) — und genau das hat den teuersten Fund dieses
Laufs geliefert.

## Der Fund des Laufs: `pip-audit` meldet 7 CVEs in 4 Paketen

```
Found 7 known vulnerabilities in 4 packages
Name              Version ID              Fix Versions
----------------- ------- --------------- ------------
dnspython         2.9.0   CVE-2026-128089 2.9.2
oauthlib          4.0.0   CVE-2026-49272  4.0.1
opentelemetry-api 1.45.1  CVE-2026-126360 1.45.2
soupsieve         2.9.2   CVE-2026-126192 2.10.0
soupsieve         2.9.2   CVE-2026-126190 4.0.0
soupsieve         2.9.2   CVE-2026-126193 3.0.2
soupsieve         2.9.2   CVE-2026-126191 3.0.2
```

### Träger je CVE — drei haben einen PR, einer hat nichts

| Paket | CVE | Fix | PR | Lage |
|---|---|---|---|---|
| `oauthlib` 4.0.0 | CVE-2026-49272 | 4.0.1 | **#1120** | 18/18 Checks grün (Stand 2026-11-09), 0 hinter `main`, konfliktfrei |
| `dnspython` 2.9.0 | CVE-2026-128089 | 2.9.2 | **#1141** | neu am 2026-11-13, 12 grün / 2 rot (`audit`, `all-green`) / 1 `neutral` = 15 |
| `opentelemetry-api` 1.45.1 | CVE-2026-126360 | 1.45.2 | **#1142** | neu am 2026-11-13, 12 / 2 / 1 = 15 |
| `soupsieve` 2.9.2 | 4 CVEs | ab 4.0.0 deckt alle | **KEINER** | kein PR, kein Issue, **Produktiv-Abhängigkeit** |

**Herkunft von `soupsieve`:** transitiv über `beautifulsoup4 4.15.0`
(`uv.lock:318-324`, `soupsieve` als Dependency an `:322`), deklariert als
`beautifulsoup4>=4.12` in `apps/api/pyproject.toml:14`, benutzt in
`apps/api/src/who2be_api/services/wa_ingest.py` (WorkArea-Ingest, ADR-0048).
**Das ist keine Dev-Abhängigkeit.**

### Die Merge-Wirkung ist gemessen, nicht geschätzt

```
$ T=$(git merge-tree --write-tree origin/main refs/pr/1120)
$ git diff --stat origin/main $(git commit-tree $T -p origin/main -m probe)
 uv.lock | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)
```

#1141 und #1142 ebenso: je **3 Insertions / 3 Deletions** in `uv.lock`.

**#1120 allein macht das Gate NICHT grün** — am Inhalt von #1120 selbst
gemessen (eigener Worktree, eigener Export):

```
$ uv tool run pip-audit --disable-pip --no-deps -r <reqs von refs/pr/1120>
Found 6 known vulnerabilities in 3 packages   # EXIT=1
```

**Der vollständige Weg, in einem Worktree durchgespielt:** `origin/main` +
Merge #1120 + #1141 + #1142 (**je rc 0**, keine Konflikte trotz gemeinsamer
Datei `uv.lock`) ergibt `oauthlib 4.0.1`, `dnspython 2.9.2`,
`opentelemetry-api 1.45.2` — und

```
Found 4 known vulnerabilities in 1 package    # soupsieve, EXIT=1
```

**Erst der vierte Schritt schließt es:**

```
$ uv lock --upgrade-package soupsieve
Updated soupsieve v2.9.2 -> v2.10, v4.1
 uv.lock | 53 ++++++++++++++---------
 1 file changed, 42 insertions(+), 11 deletions(-)
$ uv tool run pip-audit --disable-pip --no-deps -r <reqs>
No known vulnerabilities found                # EXIT=0
```

**Der `soupsieve`-Bump ist von den drei PRs unabhängig** — allein auf `main`
gefahren ist er zeichengleich **42+/11−**, und die verbleibenden drei CVEs sind
genau die der drei PRs. **Die vier Schritte sind reihenfolge-frei.**
**Die Zielversionen existieren auf dem Index** (`pip index versions soupsieve`
auf `4.1, 4.0.1, 4.0, 3.0.4, 3.0.3, 3.0.2, 2.10, 2.9.2, …`), die Auflösung ist
per Python-Marker gespalten (`2.10` / `4.1`) — kein Pin nötig.

## In Review — 42 offene PRs _(waren 39)_

Scope je PR über `git merge-base` + `git diff --name-only` (Nicht-leer-Prüfung),
Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über
`git rev-list --count`. **Alle 42 heute selbst gerechnet.**

- **Alle 42 mergen konfliktfrei** (rc 0), alle 42 merge-bases rechnen,
  **keiner bewegt 0 Dateien**.
- **Rückstand auf `main`:** **0** auf #1142, #1141, #1140, #1139, #1138, #1137,
  #1136, #1135, #1134, #1133, #1132, #1131, #1130, #1129, #1128, #1127, #1126,
  #1125, #1124, #1123, #1120, #674 (**22**) · **10** auf #1122, #1121, #1119,
  #1118, #1117, #1113, #1112, #1106 (**8**) · **15** auf #1107, #1105, #1104,
  #1103 · **19** auf #1090, #1089 · **33** auf #1078 · **48** auf #1056 ·
  **73** auf #1025 · **89** auf #1002 · **114** auf #990 · **237** auf #831.
- **Der Zuwachs 39 auf 42 ist vollständig erklärt und diesmal überwiegend
  fremd:** **+#1140** (Protokoll Lauf 80, der Lauf selbst), **+#1141**,
  **+#1142** (zwei dependabot-PRs vom 2026-11-13T21:08, **beide
  Sicherheits-Fixes**). **Weiche 51 ist in dieser Runde widerlegt** — der Lauf
  war nicht der einzige Zuwachs. **Nichts gemergt, nichts geschlossen —
  achter Tag.**
- **Protokoll-Lage:** auf `main` liegen **15** Aufbereitungs-Protokolle (das
  unnumerierte vom 2026-09-06, Lauf **31**, Läufe **43–55**). **24** stecken in
  offenen Drafts (42, 56–62, 64–75, 77–80). **Zu Lauf 63 UND zu Lauf 76
  existiert nirgends eines** — heute über `git ls-tree -r origin/main
  .claude/plan/` **und** über die Dateilisten aller 42 PRs gemessen. Dieser Lauf
  legt das **fünfundzwanzigste** Draft dazu.
- **Die Herkunftszeile von #1001 nennt `…aufbereitungslauf-76.md` — eine
  Datei, die es nirgends gibt** (dritte Messung). #989 nennt `…-74.md`, die nur
  im offenen Draft #1125 liegt.
- **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02
  geschrieben** (`e39d05eb`) — **43 Tage**, dreifach gehalten (#1103 bei 15,
  #1090 bei 19, #1078 bei 33). **Wer ein Paket abschließt, nimmt #1103 als Basis.**

### Merge-fertig — einer, und er reicht nicht mehr allein

Kriterium: konfliktfrei · `all-green` namentlich `success` · kein Draft.

| PR | Titel | Rückstand | Checks | Scope | Lage |
|---|---|---:|---:|---|---|
| **#1120** | `deps`: oauthlib 4.0.0 auf 4.0.1 | **0** | **18 / 18 grün** (18 + 0 rot + 0 `neutral` = 18, addiert) | `uv.lock` | **mergebar ohne Vorbedingung** |

**Sein grünes `audit` ist ein datierter Datensatz vom 2026-11-09 und von der
Advisory-Datenbank überholt** (Regel 181 gilt auch in der grünen Richtung):
am Inhalt von #1120 heute selbst gefahren ist `pip-audit` **Exit 1**.
**#1141 und #1142 sind deshalb nicht „auch noch rot", sondern tragen je einen
eigenen Teil des Fixes** — ihr `audit`-Rot ist zur Hälfte geerbt und zur Hälfte
ihr eigener, noch nicht behobener Rest.

### Gate-alt — 20 von 42, pro Gruppe belegt

Gemessen am **Blob-Vergleich** von `.github/workflows/ci.yml` an der merge-base
gegen `origin/main`, nicht am Commit-Abstand. **Die Menge deckt sich exakt mit
„Rückstand > 0".** Gate-**aktuell** sind die **22** PRs bei Rückstand 0.

| Gruppe | PRs | `ci.yml`-Delta | Jobs an der merge-base | Inhalt |
|---|---|---|---:|---|
| Rückstand **10–33** | #1122, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1106, #1105, #1104, #1103, #1090, #1089, #1078 (**15**) | **3+/3−** | 12 | 3× derselbe Action-SHA (`astral-sh/setup-uv` v10.3.0 auf v10.3.3) |
| Rückstand **48–89** | #1056, #1025, #1002 (**3**) | **25+/3−** | 12 | ein ganzer **Schritt** mehr: `Hilfe-Drift`, `scripts/ci/help_drift.py` |
| Rückstand **114** | #990 (**1**) | **66+/19−** | 12 | dazwischen |
| Rückstand **237** | #831 (**1**) | **186+/19−** | **11** | **es fehlt `secrets`** — heute per `yaml.safe_load` am Job-Namensatz gegengelesen: `main` 12 Jobs, #831s merge-base 11, Differenz genau `{secrets}` |

_`ci.yml` ist **1259** Zeilen, **12** Jobs; `changes:` `:21`, `python:` `:108`,
`web:` `:254`, `compose-smoke:` `:355`, `e2e:` `:422`, `e2e-billing-cloud:`
`:478`, `e2e-mobile:` `:563`, `backup-alarm:` `:659`, `changelog-guard:` `:780`,
`secrets:` `:846`, `audit:` `:959`, `all-green:` `:1113`; `test:a11y` `:325`,
die scharfen E2E-Kommandos `:463` und `:544`, `license:check` `:1029`, das
Fragment-Gate `:827` (guard) und `:844` (check) — alle heute wörtlich bestätigt._

### Der `audit`-Job, richtig gezählt

| Zählweg | `pip-audit` | `OSV-Scan` | Gesamt |
|---|---|---|---|
| **CI-Definition** (`yaml.safe_load(ci.yml)['jobs']['audit']['steps']`) | **4.** (`ci.yml:974`) | **9. und letzter** (`ci.yml:1030`) | **9** Schritte |
| **Runner-Numerierung** (`main`s Lauf `42178623925`) | **5.** | **10.** | **13** Einträge |

**Beide Wege heute erneut bestätigt.** An `main`s Job-Liste wörtlich gelesen:
`pip-audit (Python)` auf `failure`; `Install web deps`, `npm audit (Web,
prod-only, high+)`, `License check (Web · Deny-Liste)` und `OSV-Scan` sind
**`skipped`**. Der Job endet vor OSV.

## Datei-Sperren — gegen alle 42 PRs, am vollen Pfad, Existenz zuerst belegt

Die 42 PRs bewegen zusammen **44** Dateipfade _(waren 43 bei 39 PRs)_.

| Datei | Existenz | Träger |
|---|---|---|
| `apps/web/package.json` (**82** Z) · `apps/web/package-lock.json` | belegt | **#1130, #1129, #1128, #1124, #674 — fünffach** |
| `uv.lock` (**3485** Z) | belegt | **#1142, #1141, #1123, #1120 — VIERFACH** _(waren zwei)_ |
| `.claude/context/STATE.md` | belegt | **#1103, #1090, #1078** — dreifach |
| `apps/web/osv-scanner.toml` (**26** Z) | belegt | **#1124** — und inhaltlich gegenläufig zu #989 |
| `deploy/dokploy/docker-compose.yml` | belegt | **#1134 UND #1131** |
| Compose-Dateien der Deploy-Stacks | belegt | **#1136, #1135, #1134, #1133, #1132, #1131** (#1131 fasst vier an) |
| `.github/workflows/deploy.yml` (**251** Z) | belegt | **#1127** |
| `.github/PROJECT.md` (**179** Z) | belegt | **#1105** |
| `docs/cloud-erstinbetriebnahme.md` · `changelog.d/domain-move-checklist.added.md` · `.claude/plan/2026-10-31-0056_domain-umzug.md` · **`.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md`** | belegt | **#1106 UND #1122 — dieselben vier Pfade** |
| **`apps/web/src/**` (der ganze Vitest-Baum)** | existiert | **KEIN EINZIGER der 42 PRs** |
| **`apps/web/e2e/**`** | existiert | **FREI** |
| `docs/mcp-payload-budget.md` (**609** Z) · `apps/mcp/**` · `apps/api/**` | belegt | **FREI** |
| `apps/web/vite.config.ts` (**107** Z) · `.github/workflows/ci.yml` (**1259** Z) | belegt | **FREI** |
| `deploy/hetzner/Caddyfile` (**208** Z, `rate` **0×**) · `docs/licensing/plans.md` (**271** Z) | belegt | **FREI** |

**Jede als FREI gemeldete Datei ist vor der Prüfung auf Existenz belegt.**
**Die Sperren der beiden startbaren Pakete haben sich nicht verschoben.**

## Ein realer Betreiber-Host liegt auf `main` — und zwei PRs würden ihn entfernen

Heute präzise gemessen (`git grep` über `origin/main`, rechts geankert):
**genau ein Treffer in genau einer Datei.**

```
.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md:11:
Produktions-MCP (`mcp.<der reale Host>`) mit dem groessten vorhandenen
```

**`CLAUDE.md` §Security verbietet das ausdrücklich** — „Keine realen
Betreiber-Hosts im Repo. … auch nicht in Plan-/Kontextdateien unter `.claude/`.
… Grund: das Repo geht oeffentlich, und die History vergisst nichts." **Das Repo
ist public.**

**Beide offenen PRs #1106 und #1122 enthalten denselben Ein-Zeilen-Fix**
(realer Host auf `mcp.<DOMAIN>`), zeichengleich, je 1+/1−.
**Damit ist Weiche 49 („#1106 oder #1122?") nicht länger eine
Aufräum-Entscheidung, sondern das Einzige, was diesen Verstoß auf `main` hält.**
Die History ist ohnehin nicht zu reparieren; der Dateistand ist es.

## Norm-Prüfung „Agent-ready Arbeitspaket"

4 von 4 vollständig, alle Zeiger gültig — **und eine schädliche Anweisung in
allen vier**. Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints):
**Outcome** · **prüfbare Akzeptanzkriterien** · **Out-of-Scope** · **exakte
Verifikations-Kommandos**. Jeder Befund von Hand gegengelesen.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ja | ja, 5 | ja | ja | **13/13 gültig** | **schädliche Anweisung, Body geschrieben** |
| **#1001** | ja | ja, 5 | ja | ja | **alle 5 Gruppen gültig** | **schädliche Anweisung + Ordinal (3. Sichtung), Body geschrieben** |
| **#633** | ja | ja, 6 | ja | ja | **10/10 gültig** | **schädliche Anweisung + `:308` (2.) + Ordinal (3.), kommentiert, Grund benannt** |
| **#989** | ja | ja, 6 | ja | ja | **alle gültig** | **schädliche Anweisung + 406/405 (5. Sichtung) + DoD-gegen-AK5, kommentiert, Grund benannt** |

### Die eine Anweisung, die in allen vier falsch ist

> „**jeder Job außer `audit` und `all-green` ist grün**, und der `audit`-Job-Log
> nennt als einzigen Fund `oauthlib 4.0.0`. Nennt er etwas anderes, ist es
> **deins**."

**Heute nennt der Log vier Pakete.** Ein Agent mit leerem Kontext, der dieser
Anweisung folgt, liest `dnspython`, `opentelemetry-api` und `soupsieve` als
**eigenen** Schaden und sucht einen Fehler, den es in seinem Paket nicht gibt —
genau die Fehlerart, vor der dieselben Bodies in §Eskalation warnen.
**Das ist keine verrottete Zahl, sondern eine falsche Anweisung** (Regel 161),
und eine falsche Anweisung ist von der Kommentar-Ausnahme ausgenommen
(Regel 63a). **Das entscheidet Weiche 53 für diesen Fall, nicht die harte
Grenze:** geschrieben wird dort, wo ein Agent das Paket heute aufgreifen kann
(**#632** Position 1, **#1001** Position 2), kommentiert wird bei den zwei
gesperrten Paketen — **mit dem Grund im Kommentar**.

### Einzeln gegengemessene Zeiger (Auswahl)

`MfaSection.tsx` **297** / `.test.tsx` **284** / `.a11y.test.tsx` **45** ·
`SessionProvider.tsx` **267** (`mfaStepUpPending` `:57`, Aufrufer `:134`/`:222`) ·
`LoginPage.tsx` **399** (`completeMfaChallenge` `:39`, Aufruf `:172`) ·
`e2e/helpers/auth.ts` **199** · `i18n/audit.test.ts` **371**
(`it.each([` `:297`, **Baseline-Filter `:309`** — `:308` ist
`ORPHAN_IGNORE_PREFIXES,`, blankes `it(` `:321`) ·
`orphan-baseline.json` **156** (flache Liste) · `client.ts` **1849** ·
`types.ts` **2407** · `test/a11y.test.ts` **77** (Untergrenze `:74`) ·
`vite.config.ts` **107** (`thresholds:` `:99`, Werte `:100-103`, Glob `:20`
gegen `:90` **unterschiedlich**) · `package.json` **82** (`:8` mit
`">=22 <23"`, `license-checker-rseidelsohn` `^5.0.1` `:74`) ·
`package-lock.json` mit `http-cache-semantics` **4.2.0** an `:6313-6315`,
Elternrange `^4.1.1` `:7620` · `osv-scanner.toml` **26** Z, `IgnoredVulns`
**2**, „turns red again" 1× `:6`, `ignoreUntil` `:11`/`:19` ·
Waisen-Fragment **8** Z · `docs/mcp-payload-budget.md` **609** Z,
`104.777` an `:233`/`:292`/`:327`/`:487`, `108.262` an `:234`/`:331`,
`71.738` an `:236`/`:335`, Kopf `:254`, Tabelle `:260-265` **zeichengleich**
mit dem eigenen `payload_report`-Lauf, `instructions` **1.834** an
`:267`/`:309`; `180.000 − 108.251 = 71.749` nachgerechnet.

**Norm-Stand der acht übrigen Bodies — als übernommen gekennzeichnet**
(Beleg: `updated_at` seit Lauf 78 unverändert): Outcome fehlt in #542, #535,
#428; Verifikations-Abschnitt fehlt in #535 und #428; #454 hat ihn mit „Kein
Testkommando"; #338 trägt keine Abschnitts-Überschriften; Scope-„In" fehlt in
#542, #540, #535, #454, #338. #540 trägt alle vier und bleibt
`needs-decision`. **Kein `agent-ready` vergeben, keines entzogen; kein
`needs-decision` vergeben, keines entzogen.**

## Reihenfolge — unverändert, und das ist heute eine Aussage

**Sortierkriterien:** harte Abhängigkeit, dann Owner-Vorgabe, dann Fundament vor
Fläche, dann Inventar vor Zuschnitt, bei Gleichstand das kleinere.

| Pos | Issue | Größe | Baum | Kriterium | Lage |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren (#435 W2a) | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | **startbar**, Body heute korrigiert |
| **2** | **#1001** Payload-Budget-Rest (ADR-0058 P4b) | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | **startbar**, Body heute korrigiert |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web/E2E | nach #632 (hart) plus Container-Laufzeit | zwei Blocker |
| **4** | **#989** `http-cache-semantics` auf 4.3.0 | `size/S` | Web | nach **Weiche 48** plus fünffache Sperre | nicht starten |

**Nichts im Fenster konnte eine Position verschieben** — 0 Commits, keine
Sperre verschoben, kein Blocker gefallen.

## Wellen — was gemeinsam startbar ist

| Welle | Inhalt | Bedingung |
|---|---|---|
| **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + `uv lock --upgrade-package soupsieve`** | **Die vier Schritte, die `audit` grün machen** — heute vollständig durchgemessen, reihenfolge-frei, zusammen 3+/3− dreimal plus 42+/11−. **Drei haben einen PR, der vierte hat keinen** — s. Weiche 54 |
| **A** | **#632 + #1001** | Web/Vitest gegen Python/pytest, code-disjunkt, beide Schreibflächen über alle **42** PRs frei. Gemeinsame DoD-Fläche `STATE.md` — wer zweiter fertig wird, rebasiert (Basis **#1103**) |
| **B** | **#633** | nach **#632** (hart) und nach Container-Laufzeit **oder** einem CI-Lauf, dessen **einzelne** E2E-Job-Conclusions gelesen werden (`ci.yml:463`/`:544`). **Nach Welle 0 — nicht nach #1120 allein** |
| **C** | **#989** | Erst **Weiche 48**, dann die fünffache Sperre. **Ohne Antwort nicht starten.** Wer startet, zieht die drei `405`-Stellen und den DoD-gegen-AK5-Widerspruch in einem Zug nach |
| **M** _(Owner)_ | **Welle 0, dann #1124, dann #1123, dann Compose-Bumps, dann Domain-Doku** | **Welle 0 zuerst.** #1123 **nach** #1120/#1141/#1142 neu messen (dieselbe Datei, und #1123s `uv.lock` ist **3361** Z gegen **3485** auf `main`). Dann #1124, dessen OSV-Nachweis erst nach Welle 0 aus einer Check-Conclusion lesbar ist. Dann #1131–#1136 (#1131 überschneidet #1134 — nacheinander). **#1106/#1122 nicht beide** — s. Weiche 49 |
| **N** _(Owner)_ | **21 Protokoll-PRs in beliebiger Reihenfolge** | #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — paarweise konfliktfrei, je genau eine Datei außer #1105 (zwei). Danach **seriell** #1103, #1090, #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | alle drei rot aus echtem Rückstand (15 / 33 / 237). **#831** zusätzlich: grünes `all-green` aus einer CI-Definition **ohne `secrets`-Job**. **Erst nach Welle 0 neu messen** |
| **Q** _(Owner, entscheidbar)_ | **#674** | konfliktfrei, 0 hinter `main`. **9 von 15 Checks rot, 7 davon eigene** (`web`, `e2e`, `compose-smoke`, `e2e-billing-cloud`, 3× `e2e-mobile`; 5 grün, CodeQL `neutral`, also 5+9+1=15). **Empfehlung B (schließen)** |
| **R** _(Owner)_ | **#1128, #1129, #1130** | drei npm-Bumps, zwei davon Major, auf der Fläche von #1124/#674. **Nach #1124, einzeln und nacheinander** |

**Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier
Arbeitspakete offen, zwei blockiert.

## Neue Weiche

### 54. Wer hebt `soupsieve`, und in welchem PR?

**Es gibt für vier CVEs auf einer Produktiv-Abhängigkeit keinen PR und kein
Issue.** Dependabot hat für `dnspython` und `opentelemetry-api` je einen PR
geöffnet, für `soupsieve` nicht — es ist transitiv über `beautifulsoup4` und
hat im Repo keine eigene Deklaration.

- **A — Der Owner fährt `uv lock --upgrade-package soupsieve` zusammen mit dem
  Merge von #1120/#1141/#1142 als vierten Schritt.** Gemessen 42+/11− in einer
  Datei, reihenfolge-frei, danach `pip-audit` Exit 0. _Vorteil: `main` ist in
  einem Zug grün. Nachteil: ein Commit ohne PR-Review, oder ein fünfter PR auf
  `uv.lock`, das heute schon vier Träger hat._
- **B — Der nächste Aufbereitungslauf legt den Bump als eigenen PR ab.**
  _Vorteil: Review-Weg eingehalten, Beleg im PR-Body. Nachteil: `uv.lock`
  bekommt einen fünften Träger, und der PR kann nicht mergen, solange nichts
  gemergt wird — genau das Muster, das Weiche 51 beschreibt._
- **C — Dependabot-Konfiguration so erweitern, dass transitive Python-Pakete
  eigene PRs bekommen**, und bis dahin nichts tun. _Vorteil: löst die Ursache.
  Nachteil: löst den heutigen Fund nicht, und `main` bleibt rot._

**Empfehlung A.** Begründung: die drei anderen Fixes liegen als mergebare PRs
bereit, der vierte Schritt ist eine Datei und 42 Zeilen, und solange er fehlt,
bleibt `audit` rot — mit der Folge, dass **jeder** neue PR rot wird und die
Bodies aller vier Arbeitspakete eine Anweisung tragen müssen, die sich am
nächsten Advisory-Eintrag wieder überholt. **B ist die zweitbeste Wahl und wird
es, sobald der Owner sagt, dass er keinen Commit ohne PR will.** C gehört
unabhängig davon als eigenes Paket geschnitten.

## Funde ohne Issue

- **Vier CVEs auf `soupsieve` ohne PR und ohne Issue** _(NEU)_ — s. oben,
  Weiche 54.
- **Ein realer Betreiber-Host liegt auf `main`** _(NEU in dieser Präzision)_ —
  genau ein Treffer, genau eine Datei, `CLAUDE.md` §Security verbietet es, das
  Repo ist public, und der Ein-Zeilen-Fix liegt in **beiden** Duplikat-PRs
  (#1106, #1122). Siehe Weiche 39 und 49; Weiche 49 ist damit nicht länger
  kosmetisch.
- **#442 zitierte `oauthlib 4.0.0` an den falschen Zeilen** _(NEU, in dieser
  Liste selbst entstanden)_: der Queue-Body von Lauf 80 nannte `uv.lock:1846`
  und `:1848`. Gemessen und von Hand mit Zeilenzählung gegengelesen steht die
  Deklaration auf **`:1843`** (`name = "oauthlib"`) und **`:1844`**
  (`version = "4.0.0"`); `:1846` und `:1848` sind die **sdist-** und
  **wheel-URL**, die die Zeichenkette `oauthlib-4.0.0` lediglich *enthalten*.
  **Das ist Regel 130 auf einen Versions-Zeiger angewandt: ein Vorkommen ist
  kein Deklarationsort** — und es passierte an einem bitgleichen Baum.
  **#633 hatte es richtig** (`uv.lock:1843-1844`). **In #442 an der Quelle
  korrigiert** (Regel 63c).
- **#1106 und #1122 fassen eine vierte, fachfremde Datei an** _(NEU)_:
  `.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md`, die Plan-Datei
  des Payload-Budget-Inventars und damit **#1001**s Herkunft. Der Grund ist
  derselbe Host-Ersatz, also sachlich richtig — aber Lauf 80 führte die vier
  geteilten Pfade als „2 Plan-Dateien" ohne Namen, und **der Name ist hier die
  ganze Information**: eine Domain-Umzugs-Doku schreibt in die Plan-Datei eines
  fremden Arbeitspakets. **Für #1001 ohne Belang** (`docs/mcp-payload-budget.md`
  ist frei), aber beim Merge von #1106/#1122 zu erwarten.
- **Weiche 51 ist in dieser Runde widerlegt** — nach fünf Bestätigungen in
  Folge. Der Zuwachs 39 auf 42 trägt **zwei** fremde Sicherheits-PRs und nur
  **einen** Lauf-eigenen. **Die Lehre ist nicht, dass die Weiche falsch war,
  sondern dass eine fünfmal bestätigte Bilanz beim sechsten Mal kippen kann und
  deshalb jedes Mal neu gerechnet wird** (Regel 14/60).
- **Nichts gemergt, nichts geschlossen — zum siebten Mal in Folge.** #1120 ist
  seit dem 2026-11-05 offen und 18/18 grün. **In neun Läufen ist der PR nur
  besser geworden und die Lage nur schlechter: aus einer CVE sind sieben
  geworden.**
- **ADR-0061 führt W61-1 (`:377`), W61-2 (`:390`) und W61-3 (`:238`/`:368`)
  weiter als offen** — heute selbst gelesen. _(Lauf 80 nannte `:292` und
  `:219`; das sind Erwähnungen, nicht die Überschriften — Regel 130.)_
- **Der Who2Be-MCP war erneut nicht erreichbar — sechzehnter Lauf in Folge.**
  `Who2Be---Coder` verlangt eine Autorisierung, die diese Session nicht selbst
  anstoßen kann; `get_persona`, `list_triggers`, `fetch_playbook`,
  `fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"),
  `record_usage`, `submit_feedback` und `search_memory`/`save_memory` standen
  nicht zur Verfügung. **Der Lauf fuhr nach #442 und `.github/PROJECT.md`
  §Constraints.** **Keine Kurations-Rückmeldung an die eigene AgentDB** — der
  Zugang muss in den Connector-Einstellungen freigegeben werden.

## Was dieser Lauf geschrieben hat

1. **#632** — Body korrigiert: die vier CVEs in §Startbedingung, §Verifikation
   und §Eskalation; die Anweisung „einziger Fund `oauthlib`" ersetzt durch die
   vier namentlichen Pakete plus den Selbst-Messbefehl; Welle 0 statt „#1120
   allein"; PR-Bestand **42** über **44** Pfade mit Messdatum; `STATE.md`
   **43 Tage**.
2. **#1001** — Body korrigiert: dieselbe Anweisung; zusätzlich das Ordinal des
   `audit`-Jobs (**3. Sichtung**, jetzt mit beiden Zählweisen); #1120s
   Check-Zahl **18** statt 15; die Behauptung „`pip-audit` auf dem Ergebnisbaum
   auf Exit 0" ersetzt durch die heutige Messung; PR-Bestand **42** über **44**.
3. **#633** — kommentiert, Grund benannt (zwei harte Blocker): die schädliche
   Anweisung, `:308` auf **`:309`** (2. Sichtung), das Ordinal (3. Sichtung),
   `docker info` als **57.** Messung, `uv.lock` vierfach, „nach #1120 wird der
   Weg billig" auf **nach Welle 0**.
4. **#989** — kommentiert, Grund benannt (Weiche 48 unbeantwortet): die
   schädliche Anweisung, **406 auf 405** an drei Stellen (5. Sichtung), der
   DoD-gegen-AK5-Widerspruch, #674 heute **rc 0 und 0 hinter `main`** statt
   „kollidierend, rc 1", `glob`/`minimatch`-Frist **16 Tage**.
5. **#442** — Body vollständig neu: Reihenfolge, Wellen (Welle 0 jetzt
   vierteilig), 42 PR-Lagen, 44 Dateipfade, Gate-Tabelle, Weiche **54**,
   Weiche 51 als widerlegt gekennzeichnet, der `:1846`/`:1848`-Fund an der
   Quelle korrigiert.

## Neue Regeln

**67. Ein Versions-Zeiger in eine Lockfile wird am Deklarationsort gemessen,
nicht am Vorkommen.** Ein `grep` auf `<paket>-<version>` trifft sdist- und
wheel-URL; die Deklaration steht zwei bis fünf Zeilen davor. Der Queue-Body hat
acht Läufe lang die URL-Zeilen als Versions-Zeiger geführt. **Der Messweg ist
`grep -n -A1 'name = "<paket>"'`, nicht ein Namensfragment.**

**68. Ein Gate, das eine fremde Datenbank liest, kann zwischen zwei Läufen
mehr Funde bekommen, nicht nur andere.** Acht Läufe haben „die CVE" im Singular
geführt und daraus eine Anweisung („nennt der Log etwas anderes, ist es deins")
in vier Paket-Bodies geschrieben. **Eine Anweisung, die auf der Vollständigkeit
einer Advisory-Liste ruht, ist eine falsche Erlaubnis in Wartestellung**
(Regel 189) — zulässig ist nur die datierte Messung plus der Befehl zum
Selbst-Messen.

**69. Eine Bilanz, die fünfmal gehalten hat, wird beim sechsten Mal genauso
gerechnet wie beim ersten.** Weiche 51 („der einzige Zuwachs ist der Lauf
selbst") war fünf Läufe richtig und ist im sechsten falsch — und sie wäre als
fortgeschriebene Zahl unbemerkt falsch geblieben.
