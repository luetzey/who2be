# Backlog-Aufbereitungslauf 82

**Datum:** 2026-11-15
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `status --porcelain` leer)
**Fenster seit dem letzten Messpunkt:** **0 Commits — zum achten Mal in Folge.**
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **9 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`) — in diesem Lauf **kommentiert, nicht
vollgeschrieben**; Begründung in §Der Verzicht, der selbst ein Befund ist.
**Status:** abgeschlossen (Owner-Entscheidungen offen)

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte
Abhängigkeit, Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand
das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — siebzehnter Lauf in Folge.**
`ToolSearch` liefert keines seiner Werkzeuge; der Server verlangt eine Autorisierung, die
diese Session nicht selbst anstoßen kann. Persona und Playbook-Katalog lagen im
System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und
`search_memory` nicht. Der Lauf fährt deshalb nach dem Body von #442 und nach
`.github/PROJECT.md` §Constraints. **Siebzehnter Lauf ohne Kurations-Rückmeldung an die
eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-15 auf `main` @ `f89acf87` erhoben, sequenziell (ein Schreiber je
Baum), Node **v22.23.4**, npm **10.9.9**, uv **0.11.32**, **ohne vorherige Reparatur**,
**Exit-Codes am unverketteten Befehl**. Klon war shallow (50) → **1676** Commits nach
`git fetch --unshallow`. `npm`-Gates in `apps/web/` (`pwd`-Beleg), Python-Gates im
Repo-Root.

| Gate | Ergebnis | gegen Lauf 81 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **405 Fragment(e)**; `ls changelog.d/*.md \| wc -l` = **406**, Differenz `README.md` | gleich |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **398** Requirements | **gleich** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **28 moderate** (dev-only: `glob`, `minimatch`) | gleich |
| `npx playwright test --list --project=chromium` | 🟢 **44 Tests in 9 Dateien** | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** Bytes | 🟢 **17. identische Messung** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** — `git diff --name-only f89acf87 origin/main -- apps/web/src` → **0** Zeilen | übernommen aus Lauf 74 |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet** | — |
| 🔴 `main`-CI am Kopf `f89acf87` | 🔴 **Lauf `42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen — **2 von 14 Jobs** rot (`audit`, `all-green`) | 🔴 **unverändert rot, 9 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **58. Messung in Folge** |

🟢 **Zeichengleiche Baum-Gates sind an einem bitgleichen Baum die Erwartung, kein Befund.**
🔴 **Die Ausnahme gilt weiter: advisory-gefütterte Gates werden trotz leeren Fensters
gefahren** — in diesem Lauf hat sich die Advisory-Datenbank **nicht** weiterbewegt, aber
genau diese Messung ist der einzige Weg, das zu wissen statt es anzunehmen.

## Die vier Funde des Laufs

### 1. 🟢 Welle 0 hält — und `#1120 allein` ist jetzt gemessen, nicht gerechnet

In einem Worktree auf `origin/main`, sequenziell:

```
merge #1120 rc=0 ; merge #1141 rc=0 ; merge #1142 rc=0
  -> uv.lock 9+/9-  (je PR 3+/3-)
uv lock --upgrade-package soupsieve
  Updated soupsieve v2.9.2 -> v2.10, v4.1.1    # uv.lock 42+/11-
  -> pip-audit: "No known vulnerabilities found"  EXIT=0  (400 Requirements)
```

Dazu zwei Gegenproben, die Lauf 81 nur gerechnet hatte:

| Messung | Ergebnis |
|---|---|
| `pip-audit` am Inhalt von **#1120 allein** | 🔴 **Exit 1 — 6 CVEs in 3 Paketen** |
| `soupsieve`-Bump **allein** auf `main` | 🔴 **Exit 1 — 3 CVEs in 3 Paketen** (genau die drei PR-Pakete) |

**Damit ist die Reihenfolge-Freiheit der vier Schritte an beiden Enden belegt**, und die
Aussage „nach #1120 ist das Gate grün" ist an ihrem eigenen Gegenstand widerlegt.
⚠️ **Eine Abweichung gegen Lauf 81, die zeigt, dass hier gemessen und nicht
fortgeschrieben wird:** `soupsieve` löst heute nach **`2.10` / `4.1.1`** auf (Lauf 81:
`2.10` / `4.1`) — der Index hat sich bewegt, der Diff-Umfang nicht.
🔴 **Schritt 4 hat weiter keinen Träger** → Weiche 54.

### 2. 🔄 Weiche 52 ist eingelöst — vier Korrekturen stehen im Body von #989

Lauf 81 hatte die harte Grenze auf **Lauf 82** gesetzt. Geschrieben über MCP
(`issue_write`, Vollschrieb), jede Korrektur heute selbst gemessen:

1. **Fragment-Zahl `406` → `405`** an allen drei Stellen (AK3, §Verifikation,
   §Startbedingung), mit der Differenz benannt. **Sechste Sichtung, erste Korrektur.**
2. **Das CVE-Bild:** aus „eine lebende CVE" ist die Vier-Pakete-Tabelle geworden, samt der
   Messung, dass #1120 allein 6 CVEs in 3 Paketen stehen lässt.
3. **#674 als „kollidierend, rc 1"** → gemessen **rc 0, 0 hinter `main`**
   (`git merge-tree --write-tree`); sein Problem sind die eigenen Checks.
4. **Der tote Protokoll-Pfad** in der Fußzeile → ersetzt durch die PR-Nummern, die die
   Protokolle tragen (#1125, #1143).

🔴 **Benannt, aber NICHT entschieden: der Widerspruch §DoD gegen AK5 um `STATE.md`.**
Die Auflösung gehört Weiche 43, nicht einem Agenten-Alleingang — sie steht jetzt als
markierte offene Stelle im Body statt als stiller Widerspruch.
🟢 **Nach dem Schrieb gegengelesen** (zweiter Leser, mechanische Prüfliste): vier
Pflichtabschnitte vorhanden, 6 AK, `406` nur noch in Sätzen, die es gegen 405 stellen,
Body endet regulär, toter Pfad weg. ⚠️ **Attributions-Fußzeile 0×** — sie fehlte in #989
auch vorher (Weiche 19).

### 3. 🔴 Die Überschreibung in #442 war in einem Punkt zu pauschal

Der Block sagt: „**Alle vier** offenen `agent-ready`-Bodies tragen diesen Satz."
**Wörtlich gegengelesen: #989 trug ihn nie wörtlich** — dort stand die Behauptung nur
sachlich (`# heute: EXIT=1 (oauthlib)` plus Prosa in §Startbedingung). Wörtlich steht er in
**#632** (§Verifikation), **#1001** (§DoD) und **#633** (§Verifikation), je mit einer
Variante in §Eskalation.

**Der Fund ist nicht, dass die Überschreibung falsch war — sie greift inhaltlich in allen
vier.** Der Fund ist, dass diese Liste „trägt diesen Satz" geschrieben hat, wo „trägt diese
Behauptung" gemessen war. **Eine Mess-Behauptung über vier Dokumente wird pro Dokument
belegt, nicht als Menge** (Regel 57/192). Nach dem heutigen Schrieb trifft die
Überschreibung drei Bodies, nicht vier.

### 4. 🔴 Zwei Protokolle existieren nirgends — und das kostet jetzt messbar

`git log --all --diff-filter=A` über `main` **und alle 43 gefetchten PR-Heads**:
**zu Lauf 63 und Lauf 76 existiert nirgends ein Protokoll.** Auf `main` liegen **15**
`aufbereitungslauf`-Dateien, die jüngste ist Lauf 55; die Protokolle 56–81 liegen in
**25** offenen Draft-PRs.

🔴 **Der Nebeneffekt ist heute zum ersten Mal spürbar:** die Ordinale in den Paket-Bodies
(„zweite Sichtung", „dritte Sichtung") sind **aus dem Repo nicht prüfbar**. Ein Lauf kann
sie nur fortschreiben — genau die Praxis, die Regel 4 verbietet. → Regel 61, Weiche 10/18.

## Norm-Prüfung „Agent-ready Arbeitspaket" — 4 von 4 vollständig

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**. Je Issue von
einem eigenen Prüfer gegen den Baum gemessen, jeder Zeiger einzeln.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ `### Fertig heißt` | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **65/66** | 🔴 schädlicher Satz + `uv.lock:1848` → **kommentiert** |
| **#1001** | ✅ `## Fertig heißt` | ✅ 5 | ✅ `**Out of Scope:**` | ✅ | 🟢 **29/30** | 🔴 schädlicher Satz + toter Protokoll-Pfad → **kommentiert** |
| **#633** | ✅ `### Fertig heißt` | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 **18/19** | 🔴 schädlicher Satz + `:309` (3. Sichtung) → **kommentiert** |
| **#989** | ✅ `## Fertig heißt` | ✅ 6 | ✅ `**Out of Scope:**` | ✅ | 🟢 **14/16**, zwei heute behoben | 🔄 **Body geschrieben** |

⚠️ **`**Out:**` statt `**Out of Scope**` in #632/#633 bleibt eine Schreibvariante, keine
Lücke** — zum 21. Mal von Hand gegengelesen.

**Neue Zeiger-Funde dieses Laufs:**

| Issue | Behauptung | Gemessen |
|---|---|---|
| #632 | `uv.lock:1848` = Wheel-URL von `oauthlib` | 🔴 `:1848` ist **`wheels = [`**, die URL steht auf **`:1849`** |
| #1001 | Protokoll `.claude/plan/2026-11-09-0030_…lauf-76.md` | 🔴 existiert **nirgends** (nicht auf `main`, in keinem PR) |
| #633 | Baseline-Filter `audit.test.ts:308` | 🔴 `:308` ist `ORPHAN_IGNORE_PREFIXES,`; der Filter steht auf **`:309`** (3. Sichtung) |

🟢 **Eine Gegenprobe hat eine Falschmeldung ausgeräumt:** die Angabe in #1001, `STATE.md`
sei auf `main` zuletzt am 2026-10-02 (`e39d05eb`) angefasst worden, war in einem flachen
Klon als „Commit nicht auffindbar" gemeldet worden. Nach `--unshallow` löst `e39d05eb` auf
(`git cat-file -t` → `commit`, 2026-10-02T16:19:26+02:00, heute **43** Tage).
**Ein flacher Klon widerlegt keinen Zeiger — das war ein Messfehler, kein Fund.**

**Norm-Stand der acht übrigen Bodies — als übernommen gekennzeichnet**, Beleg der
Übernehmbarkeit ist `updated_at` (keiner jünger als 2026-10-27): Outcome fehlt in **#542**,
**#535**, **#428**; Verifikations-Abschnitt fehlt in **#535** und **#428**; **#454** hat ihn
mit „Kein Testkommando"; **#338** trägt keine Abschnitts-Überschriften (0 von 4);
Scope-„In" fehlt in #542, #540, #535, #454, #338. **#540** trägt alle vier und bleibt
`needs-decision`. **#435** trägt Outcome nur inline. **Bewusst nicht umgebaut** (Weiche 4).

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines
entzogen.**

## Reihenfolge — unverändert, neu gemessen

**#632 → #1001 → #633 → #989.** Nichts im Fenster konnte eine Position verschieben.

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen | `size/S` | Web/Vitest | **3** Fundament vor Fläche | ✅ startbar |
| **2** | **#1001** Payload-Budget (Rest P4b) | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ startbar |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web/E2E | — | ⛔ #632 + Container-Laufzeit |
| **4** | **#989** `http-cache-semantics` | `size/S` | Web | — | ⛔ Weiche 48 + fünf Schreiber auf der Fläche |

**Nicht in der Warteschlange:** #442 (die Liste) · #428/#435/#535 (Tracking-Epics) ·
#338/#454/#542 (`human-only`) · #540 (`needs-decision`, Weiche 17) · die **43** offenen PRs
(kein Issue).

## Wellen — was gemeinsam startbar ist

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | #1120 + #1141 + #1142 + `uv lock --upgrade-package soupsieve` | Die vier Schritte zu `audit` grün, reihenfolge-frei, heute vollständig durchgemessen. **Vor allem anderen** |
| 🟢 **A** | **#632 + #1001** | Echtes Parallel-Paar: Web/Vitest gegen Python/pytest, code-disjunkt. ⚠️ gemeinsame DoD-Fläche `STATE.md` → auf #1103 rebasieren |
| **B** | #633 | nach #632 (hart) **und** Container-Laufzeit oder einzeln gelesenen E2E-Conclusions |
| **C** | #989 | erst Weiche 48; Fläche hält fünf Schreiber |
| **M** _(Owner)_ | Welle 0 → #1124 → #1123 → #1131–#1136 → Domain-Doku | #1131 überschneidet #1134; #1106/#1122 nicht beide (Weiche 49) |
| **N** _(Owner)_ | **22 Protokoll-PRs** in beliebiger Reihenfolge, danach seriell #1103 → #1090 → #1078 | je genau eine Datei außer #1105 (zwei). Bestand **25** |
| **P** _(Owner)_ | #1107, #1078, #831 durch Branch-Update heilen | Rückstand 15 / 33 / **237**; #831 zusätzlich ohne `secrets`-Job. Erst nach Welle 0 |
| **Q** _(Owner)_ | #674 | rc 0, 0 hinter `main` — **Empfehlung B (schließen)**, 9 von 15 Checks rot |
| **R** _(Owner)_ | #1128, #1129, #1130 | zwei Major, dieselbe Fläche wie #1124. Einzeln, nacheinander |

🟢 **Die Disjunktheit von Welle A ist heute gegen alle 43 PRs am vollen Pfad belegt:
kein einziger offener PR fasst `apps/web/src/**`, `apps/mcp/**` oder `apps/api/src/**`
an.** 🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her — zum achten Mal
in Folge unverschoben.**

## Der Verzicht, der selbst ein Befund ist

**Der Body von #442 ist in diesem Lauf NICHT vollgeschrieben worden.** Er ist **70.018
Zeichen** lang, davon **~38.000** akkumulierter Entscheidungs- und Regeltext (34 Weichen mit
Optionen und Begründung, 69 Pflege-Regeln). `issue_write` ersetzt den Body **vollständig**;
einen Teil-Schreibweg gibt es nicht (Weiche 44 unbeantwortet, `gh api -X PATCH --input` in
dieser Session kein zulässiger Weg).

**Ein Vollschrieb hieße, 38.000 Zeichen Owner-Entscheidungen von Hand neu zu tippen, um ein
Datum, eine PR-Zahl und eine geschlossene Weiche zu aktualisieren** — bei einem Abbruch
mitten im Schrieb wäre die einzige maßgebliche Reihenfolge-Quelle des Projekts beschädigt
(Regel 54/190).

🟢 **Was den Verzicht tragbar macht, ist gemessen und nicht angenommen: die Reihenfolge hat
sich nicht bewegt.** Veraltet sind im Body ausschließlich Metadaten (Datum, 42 statt 43 PRs,
Weiche 52 als offen, „alle vier Bodies" statt drei). Der Lauf-82-Stand steht vollständig als
Kommentar an #442, mit Vorrangregel: **für Lauf-82-Zahlen gilt der Kommentar, für
Reihenfolge und Weichen-Optionen der Body.**

🔴 **Das ist die präziseste Begründung für Weiche 44, die dieser Lauf liefern kann: der
Teil-Schreibweg kostet hier vier `sed`-Ersetzungen, sein Fehlen kostet entweder 38.000
nachgetippte Zeichen oder einen Body, der einen Tag hinterherläuft.** Empfehlung **A**.

## Offene Weichen — 34 (Weiche 52 geschlossen, keine neue)

Heute neu gerechnet, Empfehlungen unverändert; präzisiert: **54** (`soupsieve`) **A**,
Begründung durch die Index-Bewegung `4.1` → `4.1.1` stärker · **44** (Teil-Schreibweg) **A**,
zweite Quittung · **41** (`pip-audit` in `CLAUDE.md`) **C**, `grep -c` → **0**, zehntes Mal ·
**5** (`audit` im Required Check) — Schaden jetzt **sechsfach** belegt, neu: ein grünes
`audit` auf #1120, das nichts mehr beweist · **18** (Kadenz) **C** — das achte leere Fenster
hat keinen Advisory-Fund gebracht, aber drei Zeiger-Funde **und eine zu pauschale
Mess-Behauptung in der Liste selbst**.

## Was dieser Lauf geschrieben hat

| Ziel | Art | Inhalt |
|---|---|---|
| **#989** | **Body** (Vollschrieb) | vier gemessene Korrekturen; `STATE.md`-Widerspruch markiert, nicht entschieden |
| **#632** | Kommentar | Norm 4/4, 65/66 Zeiger, `uv.lock:1848`, schädlicher Satz, Startfreigabe Pos. 1 |
| **#1001** | Kommentar | Norm 4/4, 29/30 Zeiger, toter Protokoll-Pfad, `payload_report` 17. Messung, Pos. 2 |
| **#633** | Kommentar | Norm 4/4, 18/19 Zeiger, `:309` (3. Sichtung), zwei Blocker, Welle B |
| **#442** | Kommentar | vollständiger Lauf-82-Stand, Reihenfolge, Wellen, Weichen, Verzicht begründet |
| dieses Protokoll | PR | Lauf 82 |

## Nächste Schritte (Owner)

1. 🔴 **Welle 0 fahren** — #1120 + #1141 + #1142 mergen und `uv lock --upgrade-package
   soupsieve` (Weiche 54, Empfehlung A). Entsperrt `audit` für `main` und alle 43 PRs.
2. 🔴 **Weiche 44 freigeben** (Teil-Schreibweg für Issue-Bodies) — ohne ihn bleibt jeder
   Fund in einem Paket-Body entweder teuer oder nur kommentiert.
3. 🔴 **Weiche 48** beantworten (Reihenfolge Welle 0 → #1124 → #989) und **Weiche 43**
   (`STATE.md` in der DoD) — beide blockieren #989.
4. **Welle N abarbeiten:** 25 Protokoll-PRs, davon 22 in beliebiger Reihenfolge. Danach
   zeigen die Protokoll-Verweise und Ordinale der Paket-Bodies wieder auf etwas.
5. **#674 schließen** (Weiche 12) und **#1106 oder #1122** mergen (Weiche 49, Betreiber-Host
   auf `main`).
