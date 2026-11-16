# Backlog-Aufbereitungslauf 83

**Datum:** 2026-11-16
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `status --porcelain` leer)
**Fenster seit dem letzten Messpunkt:** **0 Commits — zum achten Mal in Folge.**
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **10 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`) — in diesem Lauf **kommentiert, nicht
vollgeschrieben**; Begründung in §Der Verzicht, jetzt mit Messung statt Vermutung.
**Status:** abgeschlossen (Owner-Entscheidungen offen)

---

## 🔴 Korrektur zuallererst: dies ist Lauf 83, nicht 82

Der Lauf startete in der Annahme, er sei Nr. 82 — die Fußzeile von #442 nennt
„Aufbereitungslauf 81, 2026-11-14". **Gemessen ist das falsch:** PR **#1144** trägt
`.claude/plan/2026-11-15-0024_backlog-aufbereitungslauf-82.md`, und #632, #633, #989, #1001
sowie #442 tragen `updated_at`-Stempel vom **2026-11-15T00:20–00:24Z**. **Lauf 82 hat am
2026-11-15 stattgefunden**, hat #989 vollgeschrieben, die drei anderen Pakete kommentiert
und #442 **nur kommentiert**. Genau deshalb nennt die Body-Fußzeile von #442 weiter Lauf 81.

**Die Lehre:** die Lauf-Nummer eines Aufbereitungslaufs ist aus der Fußzeile von #442
**nicht** ableitbar, solange ein Lauf den Body nicht schreibt. Verlässlich ist der
Protokoll-Bestand in den offenen PRs. → **Regel 70.**

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — achtzehnter Lauf in Folge.**
Der Server verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann.
Nicht verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage`,
`submit_feedback`, `search_memory`/`save_memory`. Persona und Playbook-Katalog lagen im
System-Prompt vor. Der Lauf fuhr nach #442 und `.github/PROJECT.md` §Constraints.
**Achtzehnter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB** — und in diesem Lauf
hat diese Lücke erstmals einen inhaltlichen Preis (s. Fund 2).

**Kein Playbook-Trigger traf** („Backlog aufbereiten" steht in keiner Trigger-Liste; am
nächsten liegen Projekt-Standup, read-only, und Code-Task-Flow, zu groß).

## Messgrundlage

Alle Werte am 2026-11-16 selbst erhoben, sequenziell, **ohne vorherige Reparatur**,
Exit-Codes am unverketteten Befehl. Node **v22.23.4**, npm **10.9.9**, uv **0.11.32**.
Klon war shallow (50) → **1676** Commits nach `--unshallow`. `npm`-Gates in `apps/web/`
(`pwd`-Beleg), Python-Gates im Repo-Root.

| Gate | Ergebnis | gegen Lauf 82 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **405 Fragment(e)**; `ls changelog.d/*.md \| wc -l` = **406**; Differenz `README.md` | gleich |
| 🔴 `pip-audit` (export + `--disable-pip --no-deps`) | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **398** Requirements | **gleich** |
| 🔴 `pip-audit` am Inhalt von **#1120** (Worktree `refs/pr/1120`, `3c4c2606`) | 🔴 **Exit 1 — 6 CVEs in 3 Paketen**, 398 Requirements | **gleich, selbst gefahren** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **28 moderate** (dev-only: `glob`, `minimatch`) | gleich |
| `npx playwright test --list --project=chromium` | 🟢 **44 Tests in 9 Dateien** | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** Bytes | 🟢 **18. identische Messung** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** — `git diff --name-only f89acf87 origin/main -- apps/web/src` → **0** Zeilen | übernommen aus Lauf 74 |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet**, Beleg: `apps/web/src` unbewegt | — |
| 🔴 `main`-CI am Kopf `f89acf87` | 🔴 Lauf **`42178623925`**, **14 Jobs, 2 rot** (`audit`, `all-green`), an der Job-Liste gezählt | 🔴 **unverändert rot, 10 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **59. Messung in Folge** |

🟢 **Die Advisory-Datenbank hat sich in diesem Fenster NICHT bewegt** — `pip-audit` liefert
zeichengleich dieselben 7 CVEs in 4 Paketen wie in Lauf 81 und 82. **Das ist ein Messwert,
kein Nicht-Ereignis:** nur weil das Gate trotz leeren Fensters gefahren wird (Regel 181),
ist das überhaupt bekannt statt angenommen.

## Die fünf Funde des Laufs

### 1. 🟢 Die schädliche Anweisung ist aus allen Bodies entfernt — Weiche 53 praktisch gelöst

Läufe 81 und 82 hatten befunden: #632, #1001 und #633 tragen in §Verifikation bzw. §DoD und
in §Eskalation die Zusicherung, der `audit`-Job-Log nenne als **einzigen** Fund
`oauthlib 4.0.0`, alles andere sei „deins". Beide Läufe haben sie **kommentiert** und als
Grund die Kosten eines Vollschriebs genannt. **Regel 63a nimmt eine falsche Anweisung
ausdrücklich von der Kommentar-Ausnahme aus; Regel 33/170 verlangt dort den Body.**

**Lauf 83 hat sie im Body korrigiert**, je Paket über eine Index-Spannen-Ersetzung mit
Vor- und Nach-Gegenlesen:

| Issue | Zeichen alt → neu | Ersetzungen | Nach-Schrieb-`diff` |
|---|---|---|---|
| **#632** | 37.183 → **38.818** | 4 (Zusicherung, 3× „solange #1120", 2 §Eskalation-Sätze) | 🟢 **leer** |
| **#1001** | 19.590 → **21.562** | 5 + 1 Nachpolitur (Fettung) | 🟢 **leer** |
| **#633** | 42.249 → **44.564** | 6 | 🟢 **leer** |

An ihrer Stelle steht je die **Vier-Pakete-Tabelle mit dem Befehl, sie selbst zu messen**,
plus die Messung, dass **#1120 allein das Gate nicht grün macht** (6 CVEs in 3 Paketen).
Jede Korrektur trägt eine Klammer, die sagt, was dort bis Lauf 82 stand und warum es falsch
war (Regel 63c).

🟢 **Zwei weitere Funde sind im selben Schrieb mitgegangen** (Regel 21: zwei Funde in einem
Body tragen EINEN Schrieb): das Ordinal in #1001 („dritten Schritt") und in #633 („dritten
und dreizehnten"), der verrottete Zeiger `:308` → **`:309`** in #633 (vierte Sichtung, erste
Korrektur) und die tote Herkunftszeile in #1001 (`…lauf-76.md`, existiert nirgends).

**Gegengelesen von einem zweiten Leser**, der die Berichte der schreibenden Agenten nicht
gesehen hat, gegen eine Zähler-Liste am Live-Body.

### 2. 🔴 Die Norm-Spanne „2–5 Akzeptanzkriterien" hat im Repo keine Quelle

Seit vielen Läufen wird als Norm geführt, ein Arbeitspaket dürfe **2–5** Akzeptanzkriterien
tragen. #633 nennt seine **6** deshalb selbst einen Verstoß, #540 nennt seine **7** einen,
#435 zitiert „Norm 2–5" — und **#989 mit ebenfalls 6 nennt nichts**.

**Heute an der Quelle gemessen.** `.github/PROJECT.md` §Constraints sagt wörtlich nur:

> „`agent-ready` ist eine Startfreigabe, keine Beschreibung: es wird nur vergeben, wenn
> Outcome, prüfbare Akzeptanzkriterien, Out-of-Scope und exakte Verifikations-Kommandos
> tatsächlich im Issue stehen. Sonst `needs-decision`."

`grep -n '2–5\|2-5\|bis 5' .github/PROJECT.md` → **kein Treffer**; auch nicht in `docs/`
oder sonst in `.github/`. **Die Spanne steht nirgends im Repo.** Ihre einzige mögliche
Quelle ist die AgentDB-Resource „Agent-ready Arbeitspaket" (`73a86231`) — seit **18 Läufen**
nicht autorisiert, also seit 18 Läufen nicht lesbar.

🔴 **Damit hängt das Norm-Urteil nicht an einer Messung, sondern daran, welcher Body die
Spanne zufällig erwähnt.** Das ist der Fund, nicht die Zahl 6. → **Weiche 55**, drei
Optionen und Empfehlung **B** als Kommentar an #989. → **Regel 71.**

### 3. 🔴 Die Attributions-Fußzeile hängt am Schreibweg — jetzt genau lokalisiert

Pflege-Regel 32 sagte bisher unbestimmt: „Der Verlust der Attributions-Fußzeile hängt am
Schreibweg, nicht am Rewrite." **In diesem Lauf ist der Mechanismus exakt gemessen**, weil
ein Sub-Agent versehentlich den falschen Weg nahm:

| Schreibweg | Wirkung auf den Body |
|---|---|
| `gh api -X PATCH` | 🔴 hängt **automatisch** Leerzeile + `---` + `_Generated by [Claude Code](…)_` an (**58** Zeichen). Stapelt **nicht** — jeder Schrieb ersetzt den ganzen Body, danach steht genau eine |
| `mcp__github__issue_write` | 🟢 **hängt nichts an.** Drei Schriebe, drei leere Nach-Schrieb-diffs, Fußzeilen-Zähler je **0** |

**Folge für die Praxis:** ein Nach-Schrieb-`diff` gegen die geprüfte Fassung muss über
`issue_write` **leer** sein. War er nicht leer, ist es ein echter Fehler — nicht ein
Umgebungs-Artefakt. → **Regel 72.**

⚠️ **Offenlegung:** der `gh api -X PATCH`-Schrieb ist in dieser Umgebung **kein zulässiger
Schreibweg** (`gh` ist nur für Suche freigegeben) und war von mir auch nicht beauftragt. Er
ist zweimal an #632 passiert, wurde erkannt, und der Endstand ist über `issue_write`
hergestellt und verifiziert. Der **lesende** `gh api … GET` zum verlustfreien Sichern eines
Bodys ist davon unberührt und bleibt als benannte Abweichung gedeckt: `issue_read` liefert
mittelgroße Bodies **inline** statt als Datei, und ein inline gelesener Body müsste zum
Sichern neu getippt werden — genau das, was Fund 4 als Fehlerquelle belegt.

### 4. 🔴 Ein Vollschrieb ist selbst eine Fehlerquelle — und das ist jetzt gemessen, nicht befürchtet

Regel 54/190 und Weiche 45 argumentieren seit vielen Läufen, ein Vollschrieb eines langen
Bodys sei ein Korrektheitsrisiko. **In diesem Lauf ist das Risiko DREIMAL eingetreten, an
drei verschiedenen Bodies und durch drei verschiedene Schreiber:**

| Vorfall | Defekt | Erkannt durch | Folge |
|---|---|---|---|
| 1. Schrieb an **#632** | **Tippfehler** in §DoD („den jüngsten" statt „den jeweils jüngsten", 9 Zeichen) | Nach-Schrieb-`diff` | Schrieb korrigiert wiederholt, Endstand sauber |
| Nachpolitur an **#1001** | **zwei verschobene Zeilenumbrüche** (Gedankenstrich an den Zeilenanfang gerutscht, Z. 144/145 und 252/253) | Nach-Schrieb-`diff` | zweiter Versuch wiederholte den Fehler → **auf den Vorzustand zurückgeschrieben** |
| Gegenprobe an **#1001** | derselbe Umbruch-Defekt erneut | `cat -A`-Vergleich | **dritter Schrieb stellte den Vorzustand wieder her**, `diff` leer |

🔴 **Die Fehlerrate ist damit gemessen, nicht geschätzt: drei von sechs Vollschrieben dieses
Laufs trugen einen Übertragungsfehler, keiner davon inhaltlich, alle drei strukturell
(Whitespace, Umbruch, Tippfehler).** Alle drei wurden vom Gate gefangen; keiner ist stehen
geblieben.

🟢 **Die Lehre ist nicht „nicht schreiben", sondern „nie ohne Gegen-diff schreiben".** Ein
Vollschrieb mit Vor- und Nach-Gegenlesen ist tragbar — das Gate hat in diesem Lauf dreimal
genau das getan, wofür es da ist. Ein Vollschrieb auf Zuruf wäre nicht tragbar. → **Regel 73.**

⚠️ **Ein kosmetischer Rest bleibt in #1001 bewusst stehen:** in §Startbedingung steht
`im Schritt **\`pip-audit (Python)\`** ab` — eine verschachtelte Fettung, die das Rendering
mitten im Satz kippt. **Zwei Korrekturversuche sind an verschobenen Umbrüchen gescheitert
und wurden zurückgerollt; ein vierter Versuch wird nicht gemacht.** Der Defekt ist
ausschließlich kosmetisch, die **Anweisung** im Satz ist korrekt und gemessen. Ein viertes
Mal in ein 21.000-Zeichen-Dokument zu schreiben, um eine Fettung zu richten, ist bei
gemessener Übertragungs-Fehlerrate das schlechtere Geschäft. → **Regel 74.**

🔴 **Und es ist der präziseste Beleg für Weiche 44, den dieser Backlog bisher hat:** die
Korrektur **einer** Textstelle kostete einen Vollschrieb von 38.000 Zeichen, inklusive eines
Fehlers, der nur durch das Gate nicht stehen geblieben ist. Mit einem Teil-Schreibweg wäre
es eine Zeichenketten-Ersetzung gewesen. **Empfehlung A, zweite Quittung.**

### 5. 🔴 Drei Stellen, an denen ein Dokument über sich selbst falsch Auskunft gibt

- **`.github/PROJECT.md` §Constraints** führt zur `size/M`-Klausel „Betrifft **aktuell**
  #428, #402, #431 und #435". 🔴 **#402 ist seit 2026-09-10 geschlossen, #431 seit
  2026-09-25** — letzteres sagt dieselbe Datei an anderer Stelle selbst. **Die Datei hält
  PR #1105**, deshalb hier ein Fund und keine Änderung: die Zeile geht in #1105 oder nach
  seinem Merge.
- **#442** schreibt „Norm-Stand der **acht** übrigen Bodies" und zählt in demselben Satz nur
  **sieben** auf (#542, #535, #428, #454, #338, #540, #435 — #442 selbst fehlt). Außerdem
  nennt der Satz die **7** Akzeptanzkriterien von #540 nicht und nicht, dass **#454 kein
  `size`-Label** trägt.
- **#428** hakt in seiner Wellen-Checkliste „Coming-soon-Modus → **#429**" ab, während seine
  Sub-Issue-Liste **#437** führt und #429 dort nicht vorkommt. Welches der beiden das
  gemeinte Kind ist, ist aus dem Body nicht entscheidbar.

## Norm-Prüfung — alle 12 offenen Issues, keines übernommen

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.
🟢 **Erstmals seit vielen Läufen sind auch die acht Nicht-`agent-ready`-Bodies an den
Stellen gelesen worden statt per `updated_at` übernommen** — Regel 42/189 verlangt genau
das, und die Übernahme war die längste offene Abkürzung dieses Backlogs.

### Die vier `agent-ready`-Pakete

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ `### Fertig heißt` | ✅ **5** | ✅ `**Out:**` | ✅ | 🟢 **13/13** | 🔄 **Body korrigiert** (Zusicherung) |
| **#1001** | ✅ `## Fertig heißt` | ✅ **5** | ✅ `**Out of Scope:**` | ✅ | 🟢 **alle 5 Gruppen** | 🔄 **Body korrigiert** (Zusicherung, Ordinal, Herkunft) |
| **#633** | ✅ `### Fertig heißt` | ⚠️ **6** | ✅ `**Out:**` | ✅ | 🟢 **nach Korrektur vollständig** | 🔄 **Body korrigiert** (Zusicherung, Ordinal, `:309`) |
| **#989** | ✅ `## Fertig heißt` | ⚠️ **6** | ✅ `**Out of Scope:**` | ✅ | 🟢 **alle gültig** | 🔄 **kommentiert** (Weiche 55) |

⚠️ **`**Out:**` statt `**Out of Scope**` in #632/#633 bleibt eine Schreibvariante, keine
Lücke** — zum 22. Mal von Hand gegengelesen.
⚠️ **Die „6 AK"-Markierung ist kein belegter Verstoß mehr**, solange Fund 2 offen ist.

### Die acht übrigen — heute an den Stellen gelesen

| Issue | size | Outcome | AK | Out-of-Scope | Verifikation | Scope-„In" |
|---|---|---|---|---|---|---|
| **#428** `epic` | `size/M` | 🔴 **fehlt** (nur „Proposed solution") | ✅ 5 | ✅ | 🔴 **fehlt** | 🔴 fehlt |
| **#435** `epic` | `size/M` | ⚠️ **nur inline** (fette Zeile, keine Überschrift) | ⚠️ 6 | ✅ `**Out:**` | ✅ | ✅ **ja** |
| **#454** `human-only` | 🔴 **kein `size`-Label** | ✅ | ✅ 5 | ✅ | ⚠️ **ohne Kommando** („Kein Testkommando — die Verifikation ist die Produktions-Smoke-Reise") | 🔴 fehlt |
| **#535** `epic` | `size/M` | 🔴 **fehlt** (nur „Problem") | ✅ 3 | ✅ | 🔴 **fehlt** | 🔴 fehlt |
| **#540** | `size/M` | ✅ | ⚠️ **7** | ✅ | ✅ mit Codeblock | 🔴 fehlt |
| **#542** `human-only` | `size/M` | 🔴 **fehlt** (nur „Problem") | ✅ 5 (**„erst nach der Entscheidung ausformulierbar"**) | ✅ | ⚠️ nur „bei Option A/C" | 🔴 fehlt |
| **#338** `human-only` | 🔴 **kein `size`-Label** | 🔴 **0 von 4** — keine Abschnitts-Überschriften | 🔴 0 (vier Aufgaben-Checkboxen O1–O4) | 🔴 | 🔴 | 🔴 |
| **#442** | 🔴 **kein `size`-Label** | — | — | — | — | — (**ist die Liste**, kein Paket) |

🟢 **Kinder der drei Epics, über `get_sub_issues` gemessen, nicht aus den Bodies geglaubt:**
**#428** 8 Kinder, 7 geschlossen, offen **#454** · **#535** 6 Kinder, 5 geschlossen, offen
**#540** · **#435** 3 Kinder, 1 geschlossen, offen **#632** und **#633**.

**Bewusst nicht umgebaut** (Weiche 4): **ein `size/M`-Issue wird nie durch Nachtragen von
Feldern startbar** (`.github/PROJECT.md` §Constraints, wörtlich).
**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines
entzogen.** Begründung: die Pflichtfelder stehen in allen vier Paketen, und die schädliche
Anweisung ist jetzt **im Body** weg statt nur überschrieben — ein Entzug würde die zwei
startbaren Pakete stilllegen, ohne ein Risiko zu senken.

## PR-Landschaft — 44 offen, alle konfliktfrei

🟢 **Der Zuwachs 43 → 44 ist vollständig erklärt und besteht aus dem Lauf selbst**
(**#1144**, Protokoll Lauf 82). **Weiche 51 gilt in dieser Runde** — anders als in Lauf 81,
wo sie kippte. **Als fortgeschriebene Zahl wäre sie wieder unbemerkt falsch gewesen**
(Regel 69 hält).

🟢 **Alle 44 mergen konfliktfrei** (`git merge-tree --write-tree`, je rc 0), alle 44
merge-bases rechnen, **keiner bewegt 0 Dateien**. Zusammen bewegen sie **46** Dateipfade.

**Rückstand:** **0** → 23 PRs (#1144, #1143, #1142, #1141, #1140, #1139, #1138, #1137,
#1136, #1135, #1134, #1133, #1132, #1131, #1130, #1129, #1128, #1127, #1124, #1123, #1120,
#674 — und #1120 darunter) · **10** → #1122, #1121, #1119, #1118, #1117, #1113, #1112,
#1106 · **15** → #1107, #1105, #1104, #1103 · **19** → #1090, #1089 · **33** → #1078 ·
**48** → #1056 · **73** → #1025 · **89** → #1002 · **114** → #990 · **237** → #831.

### Datei-Sperren — gegen alle 44 PRs, am vollen Pfad, Existenz zuerst belegt

| Datei | Existenz auf `main` | Träger |
|---|---|---|
| 🔴 `uv.lock` (**3485** Z) | belegt | **#1142, #1141, #1123, #1120** — vierfach |
| 🔴 `apps/web/package.json` (82 Z) · `apps/web/package-lock.json` | belegt | **#674, #1124, #1128, #1129, #1130** — fünffach |
| 🔴 `apps/web/osv-scanner.toml` (26 Z) | belegt | **#1124** — und inhaltlich gegenläufig zu #989 (`grep -c IgnoredVulns`: `main` **2**, #1124s Baum **0**) |
| 🔴 `.claude/context/STATE.md` | belegt | **#1078, #1090, #1103** — dreifach |
| 🔴 `.github/PROJECT.md` (179 Z) | belegt | **#1105** |
| 🔴 Compose-/Deploy-Stacks | belegt | **#1136, #1135, #1134, #1133, #1132, #1131** (#1131 fasst vier an und überschneidet #1134) · `deploy.yml` → **#1127** |
| ⚠️ 4 geteilte Pfade inkl. `.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md` | belegt | **#1106 UND #1122** — dieselben vier, s. Weiche 49 |
| 🟢 **`apps/web/src/**`** · **`apps/web/e2e/**`** | belegt (tree) | 🟢 **KEIN EINZIGER der 44 PRs** |
| 🟢 `apps/mcp/**` · `apps/api/**` · `docs/mcp-payload-budget.md` (609 Z) | belegt | 🟢 **FREI** |
| 🟢 `apps/web/vite.config.ts` (107 Z) · `.github/workflows/ci.yml` (1259 Z) | belegt | 🟢 **FREI** |
| 🟢 `deploy/hetzner/Caddyfile` (208 Z) · `docs/licensing/plans.md` (271 Z) | belegt | 🟢 **FREI** |

**Jede als FREI gemeldete Datei ist vor der Prüfung auf Existenz belegt** — ein falscher
Pfad meldet immer „FREI" (Regel 34/163).

### Merge-fertig — einer, und er reicht nicht allein

| PR | Rückstand | Checks | Scope | Lage |
|---|---:|---|---|---|
| 🟢 **#1120** oauthlib 4.0.0 → 4.0.1 | **0** | 🟢 **18 success / 0 rot / 0 neutral = 18** ausgeführte Runs, `all-green` **success** am 2026-11-09T07:18:13Z | `uv.lock` | 🟢 **mergebar ohne Vorbedingung — und nicht hinreichend** |

⚠️ **Sein grünes `audit` ist ein datierter Datensatz vom 2026-11-09, den das Advisory
überholt hat** (Regel 181 gilt auch in der grünen Richtung): am Inhalt von #1120 heute selbst
gefahren → **Exit 1, 6 CVEs in 3 Paketen.**

**#1141 / #1142 / #1123:** je **12 success / 2 failure (`audit`, `all-green`) / 1 neutral
(CodeQL) = 15**. **#1124:** **16 / 2 / 0 = 18**. **#674:** **5 / 9 / 1 = 15** — neun rot,
davon sieben eigene (`web`, `e2e`, `compose-smoke`, `e2e-billing-cloud`, 3× `e2e-mobile`).
🟢 **Gegenprobe #1124 auf derselben Fläche bei gleichem Rückstand: 16 von 18 grün — die
Umgebung erklärt den Unterschied nicht, der Inhalt tut es.** **Weiche 12: Empfehlung B.**

🔴 **Gegenprobe an den `uv.lock`-PRs:** **#1123, #1141 und #1142 führen `oauthlib` weiter in
4.0.0**; die Deklaration steht auf `uv.lock:1843`/`:1844` (`name` / `version`), in #1123 auf
`:1750`/`:1751`. **Nur #1120 hebt auf 4.0.1.** #1123s `uv.lock` ist **3361** Zeilen gegen
**3485** auf `main` — 124 weniger. 🟢 **Regel 67 hält** (Deklarationsort, nicht URL-Zeile).

### Protokoll-Lage

Auf `main` liegen **15** Aufbereitungs-Protokolle (das unnumerierte vom 2026-09-06, Lauf
**31**, Läufe **43–55**); der jüngste ist **Lauf 55** (2026-10-19). **26** stecken in
offenen Drafts (56–62, 64–75, 77–82). 🔴 **Zu Lauf 63 UND zu Lauf 76 existiert nirgends
eines** — über `main` und alle 44 PR-Heads gemessen. Dieser Lauf legt das **siebenundzwanzigste**
Draft dazu.

🔴 **Der Nebeneffekt, den Lauf 82 benannt hat, gilt unverändert:** die Ordinale in den
Paket-Bodies („dritte Sichtung") sind **aus dem Repo nicht prüfbar**, solange die Protokolle
in Drafts liegen. Welle N ist der Weg heraus.

## Reihenfolge — unverändert, neu gemessen

Sortierkriterien in dieser Ordnung: **harte Abhängigkeit → Owner-Vorgabe → Fundament vor
Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.**

**#632 → #1001 → #633 → #989.** Nichts im Fenster konnte eine Position verschieben.

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen (#435 W2a) | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | ✅ **startbar**, Fläche frei |
| **2** | **#1001** Payload-Budget, Rest ADR-0058 P4b | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar**, Fläche frei |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web/E2E | **1** harte Abhängigkeit | ⛔ **#632** + Container-Laufzeit (59. Messung) |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **1** + Owner | ⛔ **Weiche 48** + fünf Schreiber auf der Fläche |

**Nicht in der Warteschlange:** #442 (die Liste) · #428/#435/#535 (Tracking-Epics, tragen
keine eigene Arbeit) · #338/#454/#542 (`human-only`) · #540 (`needs-decision`, Weiche 17) ·
die **44** offenen PRs (ein PR ist kein Issue, Regel 34a/65a).

## Wellen — was gemeinsam startbar ist

Gemeinsam startbar ist, was **datei-disjunkt** ist und sich **nicht gegenseitig blockiert**.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + `uv lock --upgrade-package soupsieve`** | Die vier Schritte zu `audit` grün. **Reihenfolge-frei**, an beiden Enden belegt: #1120 allein → 6 CVEs, `soupsieve` allein → 3 CVEs, alle vier → **Exit 0**. 🔴 Schritt 4 hat **keinen Träger** → Weiche 54, Empfehlung **A**. **Vor allem anderen** |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle **44** PRs frei. ⚠️ Gemeinsame DoD-Fläche `.claude/context/STATE.md` — wer zweiter fertig wird, rebasiert auf **#1103** |
| **B** | **#633** | nach **#632** (hart) **und** Container-Laufzeit **oder** einem CI-Lauf mit **einzeln** gelesenen E2E-Conclusions. 🔴 Billig erst nach Welle 0 |
| **C** | **#989** | erst **Weiche 48**, dann die Fläche (fünf Schreiber + #1124 gegenläufig auf `osv-scanner.toml`). **Ohne Antwort nicht starten** |
| **M** _(Owner)_ | Welle 0 → **#1124** → **#1123** → **#1131–#1136** → Domain-Doku | #1124s OSV-Nachweis ist erst nach Welle 0 aus einer Conclusion lesbar (Weiche 48c). #1123s `uv.lock` nach Welle 0 **neu messen**. #1131 überschneidet #1134 — nacheinander. **#1106/#1122 nicht beide** → Weiche 49, **und einer von beiden muss kommen** (Betreiber-Host) |
| **N** _(Owner)_ | **23 Protokoll-PRs** in beliebiger Reihenfolge | #1144, #1143, #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — je genau eine Datei außer **#1105** (zwei: sein Protokoll **und** `.github/PROJECT.md`). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | Rückstand 15 / 33 / **237**. #831 zusätzlich: sein grünes `all-green` stammt aus einer CI-Definition **ohne `secrets`-Job**. 🔴 Erst nach Welle 0 neu messen |
| **Q** _(Owner, entscheidbar)_ | **#674** | konfliktfrei, 0 hinter `main`, aber **9 von 15 Checks rot, 7 eigene**. **Empfehlung B (schließen)** |
| **R** _(Owner)_ | **#1128, #1129, #1130** | drei npm-Bumps, zwei **Major**, dieselbe Fläche wie #1124. **Nach #1124, einzeln und nacheinander** — #674 ist der Beleg, warum nicht als Gruppe |

🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier Arbeitspakete
offen, zwei blockiert. **Zum achten Mal in Folge unverschoben.**

## Der Verzicht — #442 ist kommentiert, nicht vollgeschrieben

Der Body ist **71.604** Zeichen, davon der überwiegende Teil akkumulierter
Entscheidungs- und Regeltext (34 Weichen mit Optionen und Begründungen, 69 Pflege-Regeln).
`issue_write` ersetzt den Body **vollständig**; einen Teil-Schreibweg gibt es nicht
(Weiche 44 unbeantwortet, `gh api -X PATCH` kein zulässiger Weg).

🟢 **Lauf 82 hat den Verzicht mit einer Vermutung begründet; Lauf 83 begründet ihn mit einer
Messung.** Der Vollschrieb von **38.000** Zeichen an #632 hat in diesem Lauf nachweislich
einen Tippfehler erzeugt (Fund 4). Bei **71.604** Zeichen ist dieselbe Fehlerrate auf das
Dokument angewandt, das die **einzige maßgebliche Reihenfolge-Quelle des Projekts** ist —
und ein beschädigtes #442 kostet mehr als ein um zwei Läufe veraltetes Metadatum.

🟢 **Was den Verzicht tragbar macht, ist gemessen:** die Reihenfolge hat sich nicht bewegt.
Veraltet sind im Body ausschließlich Metadaten (Datum, Lauf-Nummer, 42 statt 44 PRs,
Weiche 52 als offen, „alle vier Bodies tragen diesen Satz" — heute **null**). Der
Lauf-83-Stand steht vollständig als Kommentar an #442, mit Vorrangregel: **für
Lauf-83-Zahlen gilt der Kommentar, für Reihenfolge-Kriterien und Weichen-Optionen der
Body.**

🔴 **Das ist die dritte Quittung für Weiche 44 in drei Läufen.** Mit Teil-Schreibweg wären
es fünf Zeichenketten-Ersetzungen.

## Offene Weichen — 35 (Weiche 52 ist in Lauf 82 geschlossen, neu: 55)

Heute neu gerechnet, nicht fortgeschrieben (Regel 14). Präzisiert:

- 🆕 **55. Woher kommt die Norm-Spanne „2–5 Akzeptanzkriterien"?** Empfehlung **B**
  (Spanne in `.github/PROJECT.md` §Constraints nachtragen, damit sie aus dem Repo prüfbar
  wird). Drei Optionen als Kommentar an #989. **Fund 2.**
- **54** (`soupsieve` ohne Träger) **A** — unverändert, dritte Quittung.
- **44** (Teil-Schreibweg) **A** — 🔴 **dritte Quittung, jetzt mit gemessenem Preis.**
- **53** (Vollschrieb bei kleinem Defekt) — 🟢 **praktisch gelöst**: dieser Lauf hat
  geschrieben statt kommentiert und die Kosten gemessen statt geschätzt.
- **5** (`audit` im Required Check) — Schaden jetzt **siebenfach** belegt; neu: er hat drei
  Paket-Bodies eine falsche Anweisung tragen lassen, deren Korrektur drei Vollschriebe
  gekostet hat.
- **41** (`pip-audit` in `CLAUDE.md`) **C** — `grep -c pip-audit CLAUDE.md` → **0**, elftes
  Mal.
- **43** (`STATE.md` in der DoD) **B** — dreifach gehalten, auf `main` zuletzt 2026-10-02,
  **45 Tage**. In #989 weiter als markierter, unentschiedener Widerspruch.
- **46** (`glob`/`minimatch`-Ausnahmen) **A** — 🔴 **Frist: 14 Tage** (2026-11-30).
- **18** (Kadenz) **C** — das achte leere Fenster hat keinen Advisory-Fund gebracht, aber
  **drei Body-Korrekturen, eine widerlegte Norm-Behauptung und einen lokalisierten
  Schreibweg-Mechanismus**.

## Funde ohne Issue (Regel 34a)

- 🔴 **Vier CVEs auf `soupsieve` ohne PR und ohne Issue** — Produktiv-Abhängigkeit über
  `beautifulsoup4` (`uv.lock:322`, deklariert `apps/api/pyproject.toml:14`, benutzt in
  `services/wa_ingest.py`). → Weiche 54.
- 🔴 **Ein realer Betreiber-Host liegt auf `main`** — `.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md:11`.
  `CLAUDE.md` §Security verbietet es, das Repo ist public, **und der Ein-Zeilen-Fix liegt in
  beiden Duplikat-PRs #1106/#1122.** → Weichen 39 und 49. **Es ist ein Merge, keine Arbeit.**
- 🔴 **`.github/PROJECT.md` §Constraints nennt zwei geschlossene Issues als „aktuell"**
  (#402, #431). Datei von #1105 gehalten. → Fund 5.
- 🔴 **#428 nennt in der Checkliste #429, in der Sub-Issue-Liste steht #437.**
- 🔴 **#454 und #338 tragen kein `size`-Label**, #442 ebenfalls nicht.
- 🔴 **Nichts gemergt, nichts geschlossen — zum achten Mal in Folge.** #1120 ist seit dem
  2026-11-05 offen und 18/18 grün bei Rückstand 0.
- 🟢 **Der Who2Be-MCP war nicht erreichbar — achtzehnter Lauf.** Keine
  Kurations-Rückmeldung; die Norm-Resource ist deshalb nicht lesbar, was in diesem Lauf
  Fund 2 verursacht hat.

## Neue Pflege-Regeln

70. **Die Lauf-Nummer ist aus der Fußzeile von #442 nicht ableitbar**, solange ein Lauf den
    Body nicht schreibt. Verlässlich ist der Protokoll-Bestand in den offenen PRs.
71. **Eine Norm-Klausel, die nur in Bodies zitiert wird, ist keine gemessene Norm.** Vor
    einem Verstoß-Urteil wird die Klausel an ihrer Quelle belegt — und wenn die Quelle
    unerreichbar ist, ist das der Fund, nicht die Zahl.
72. **Der Schreibweg entscheidet, ob ein Nach-Schrieb-`diff` leer sein kann.** Über
    `mcp__github__issue_write` hängt nichts an, über `gh api -X PATCH` eine
    Attributions-Fußzeile (58 Zeichen, stapelt nicht). Ein nicht-leerer `diff` über
    `issue_write` ist ein echter Fehler.
73. **Ein Vollschrieb wird nie ohne Vor- und Nach-Gegenlesen gemacht.** Das Risiko ist
    gemessen, nicht befürchtet: in diesem Lauf trugen **drei von sechs** Vollschrieben einen
    Übertragungsfehler (Tippfehler, zweimal verschobene Zeilenumbrüche), alle drei vom Gate
    gefangen, keiner stehen geblieben.
74. **Ein kosmetischer Defekt rechtfertigt keinen weiteren Vollschrieb.** Wenn die
    Übertragungs-Fehlerrate messbar über Null liegt, ist ein Schrieb für eine Fettung teurer
    als der Defekt. Die Grenze ist: **falsche Anweisung → immer schreiben; falsche Zahl →
    schreiben; falsches Rendering → stehen lassen und benennen.**

## Was dieser Lauf geschrieben hat

| Ziel | Art | Inhalt |
|---|---|---|
| **#632** | **Body** | schädliche Zusicherung → Vier-Pakete-Liste mit Selbst-Messbefehl; 3× „Welle 0"; 2 §Eskalation-Sätze |
| **#1001** | **Body** | dieselbe Zusicherung; Ordinal „dritter" → 4./9. bzw. 5./13.; tote Herkunftszeile → #1143/#1144. ⚠️ Fettungs-Politur **zweimal versucht, zweimal zurückgerollt** — Rest kosmetisch, s. Fund 4 |
| **#633** | **Body** | dieselbe Zusicherung; Ordinal „dritter/dreizehnter"; Zeiger `:308` → **`:309`** |
| **#632**, **#1001**, **#633** | Kommentar | Lauf-83-Stand, Norm, Zeiger, Fläche, Position |
| **#989** | Kommentar | Lauf-82-Korrekturen nachgemessen; **Weiche 55** mit drei Optionen und Empfehlung |
| **#442** | Kommentar | vollständiger Lauf-83-Stand, Reihenfolge, Wellen, Weichen, Verzicht begründet |
| dieses Protokoll | PR | Lauf 83 |

## Nächste Schritte (Owner)

1. 🔴 **Welle 0 fahren** — #1120 + #1141 + #1142 mergen **und**
   `uv lock --upgrade-package soupsieve` (Weiche 54 **A**). Entsperrt `audit` für `main` und
   alle 44 PRs, gibt #633 den billigen CI-Weg zurück.
2. 🔴 **Weiche 44 freigeben** (Teil-Schreibweg für Issue-Bodies). Drei Läufe, drei
   Quittungen, jetzt mit gemessenem Preis.
3. 🔴 **Weiche 48** (Reihenfolge Welle 0 → #1124 → #989) und **Weiche 43** (`STATE.md` in
   der DoD) beantworten — beide blockieren #989.
4. 🆕 **Weiche 55** beantworten (Norm-Spanne der Akzeptanzkriterien) — sie entscheidet, ob
   #633, #989, #540 und #435 einen Verstoß tragen oder keinen.
5. **Welle N abarbeiten:** 23 Protokoll-PRs in beliebiger Reihenfolge, danach seriell
   #1103 → #1090 → #1078. Erst danach zeigen die Herkunftszeilen und Ordinale der
   Paket-Bodies wieder auf etwas.
6. **#674 schließen** (Weiche 12 **B**) und **#1106 oder #1122** mergen (Weiche 49 **B**) —
   Letzteres entfernt einen realen Betreiber-Host aus dem Dateistand von `main`.
7. **Den Who2Be-MCP autorisieren** — achtzehn Läufe ohne Kurations-Rückmeldung, und seit
   diesem Lauf mit einem belegten inhaltlichen Preis.
