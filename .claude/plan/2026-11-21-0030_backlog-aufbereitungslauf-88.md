# Backlog-Aufbereitungslauf 88

**Datum:** 2026-11-21
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `deps(compose): bump caddy in /deploy/monitor`, #1097)
**Fenster seit dem letzten Messpunkt (Lauf 87):** 🔴 **0 Commits, zum dreizehnten Mal in Folge** —
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **15 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), in diesem Lauf kommentiert, nicht vollgeschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung. Danach die Warteschlange neu ordnen (harte Abhängigkeit → Owner-Vorgabe →
Fundament vor Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere) und in Wellen
gruppieren. Bericht in drei Blöcken.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — die Sitzung hält die Anmeldung,
der Server weist sie ab.** Der erneute Verbindungsversuch über eine `ToolSearch`-Abfrage mit dem
Servernamen wurde abgelehnt. Nicht verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage`,
`submit_feedback`, `search_memory`/`save_memory`.

Persona und Playbook-Katalog lagen im System-Prompt vor; der Lauf fährt deshalb nach dem Body von
#442 (§Pflege-Regeln) und nach `.github/PROJECT.md` §Constraints — dort stehen die vier
Pflichtabschnitte der Norm. **Kein Playbook-Trigger traf** (der stehende Aufbereitungslauf ist
keiner der katalogisierten Trigger). **Keine Kurations-Rückmeldung an die eigene AgentDB, erneut.**

## Messgrundlage

Alles am 2026-11-21 auf `main` @ `f89acf87` erhoben, **ohne vorherige Reparatur** (Regel 120),
Exit-Codes am **unverketteten** Befehl (Regel 36/94/172), `npm`-Gates in `apps/web/` mit
`pwd`-Beleg (Regel 13/164), sequenziell. Node **v22.23.5**, npm **10.9.9**, uv **0.11.32**,
CPython **3.11.18**. Klon war shallow (50) → **1676** Commits nach `--unshallow` (Regel 90).
`git status --porcelain` leer, `git rev-list --count f89acf87..origin/main` → **0**,
`HEAD^{tree}` = **`c751ed64`** (bitgleich zu Lauf 87).

| Gate | Ergebnis | gegen Lauf 87 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**; `ls changelog.d/*.md \| wc -l` = **406** (Differenz `README.md`) | gleich |
| 🔴 `pip-audit` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **125** Requirements / **124** Namen | gleich |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **27 moderate, 0 high**; Wurzeln ausschließlich `GHSA-3g3m-2fjr-6pw4` (glob) + `GHSA-g3hv-75wg-m249` (minimatch) | gleich |
| `npx playwright test --list --project=chromium` | **44** Tests in **9** Dateien | gleich |
| `payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** B | 🟢 **23. identische Messung** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 30/160) — Fenster 0 Commits, `apps/web/src` unbewegt, Baum bitgleich | wie Lauf 87 |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet** (selbst gefahren in Lauf 84, Baum seither bitgleich) | — |
| 🔴 **`main`-CI am Kopf `f89acf87`** | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen; rot sind `audit` und `all-green` | 🔴 **unverändert rot, 15 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **64. Messung in Folge** |

**Fundstellen selbst nachgemessen:** `.github/workflows/ci.yml` **1259** Zeilen, Job `audit` an
**`:959`**, `pip-audit` `name:` an **`:974`** / `run:` an **`:975`**, Schritt
`OSV-Scan (Web-Lockfile …)` an **`:1030`**; `python-version` in **allen drei** Workflows
**0×** (`ci.yml` 0, `deploy.yml` 0, `release.yml` 0); `apps/web/osv-scanner.toml` **26** Zeilen,
`IgnoredVulns` **2×**, beide `ignoreUntil = 2026-11-30T00:00:00Z` (`:11` und `:19`).

### 🟢 Zweiter, unabhängiger Beleg für Regel 71 — aus einem anderen Messweg

Der Verifikations-Block von #1150 führt „**398** ZEILEN" gegen „125 Requirements". Dieser Lauf hat
den Export mit **anderen Flags** gefahren (`uv export --no-hashes --all-packages
--no-emit-project` statt `--format requirements-txt --no-emit-workspace --group billing`):

```
wc -l                -> 407      # Lauf 87 / #1150: 398
grep -c '=='         -> 125      # identisch
distinct names       -> 124      # identisch
```

🔴 **Die Zeilenzahl ist nicht einmal über zwei legitime Export-Aufrufe desselben Locks stabil,
die Paketzahl schon.** Regel 71 war bisher an einem Messweg belegt (Zeilen ≠ Pakete); jetzt ist
sie an **zwei** belegt, und zwar an der stärkeren Variante: die zitierte Zahl ändert sich mit
einem Schalter, der den geprüften Gegenstand nicht ändert. **Verbindlich bleiben 125 / 124.**

## PR-Bestand

🔴 **50 offene PRs** _(waren 49)_, zusammen **55** bewegte Dateipfade _(waren 54)_, **74**
Pfad-Vorkommen _(waren 73)_. Scope je PR über `git merge-base` + `git diff --name-only` mit
Nicht-leer-Prüfung, Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über
`git rev-list --count` — **alle 50 selbst gerechnet.**

- 🟢 **Die Differenz 49 → 50 ist vollständig erklärt: +#1154** (Protokoll Lauf 87, der Vorlauf).
  Er bewegt **genau eine** Datei — nachgezählt, und damit auch das +1 bei Pfaden und Vorkommen.
  **Keine Abgänge.**
- 🟢 **Alle 50 mergen konfliktfrei** (`rc 0`), **keiner bewegt 0 Dateien.**
- 🔴 **Seit dem 2026-11-06 ist kein PR gemergt — 15 Tage, dreizehntes leeres Fenster.**
- **Rückstand auf `main`:** **0** → 30 PRs · **10** → 8 · **15** → 4 · **19** → 2 · **33** →
  #1078 · **48** → #1056 · **73** → #1025 · **89** → #1002 · **114** → #990 · **237** → #831.
  _(30+8+4+2+6 = 50, addiert.)_
- 🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02 geschrieben** — **50 Tage**,
  dreifach gehalten (#1103, #1090, #1078). **Basis für ein abschließendes Paket: #1103.**

### Datei-Sperren — gegen alle 50 PRs, am vollen Pfad, Existenz zuerst belegt

| Pfad | Träger |
|---|---|
| 🔴 `apps/web/package.json` · `apps/web/package-lock.json` | **#1147, #1130, #1129, #1124, #674** |
| 🔴 `apps/web/osv-scanner.toml` | **#1124** _(entfernt beide `[[IgnoredVulns]]`)_ |
| 🔴 `uv.lock` | **#1148, #1142, #1141, #1120** |
| 🔴 `.claude/context/STATE.md` | **#1103, #1090, #1078** |
| 🔴 `.github/PROJECT.md` | **#1105** |
| 🔴 `apps/api/Dockerfile` · `apps/mcp/Dockerfile` | **#1146** |
| 🔴 `.github/workflows/deploy.yml` | **#1127** |
| 🟢 `apps/web/src/**` · `apps/web/e2e/**` | 🟢 **KEIN** der 50 PRs |
| 🟢 `docs/mcp-payload-budget.md` · `payload_report.py` · `test_tool_payload_budget.py` | 🟢 **FREI** — die drei Hebel von #1001 |
| 🟢 die fünf `pyproject.toml` · `.github/dependabot.yml` | 🟢 **FREI** — die Fläche von #1150 |
| 🟢 `.github/workflows/ci.yml` | 🟢 **FREI** |

⚠️ **`apps/mcp/**` als Glob ist KEINE freie Fläche** (#1146 hält `apps/mcp/Dockerfile`) — die
Korrektur aus Lauf 84 gilt, am vollen Pfad wiederholt; für #1001 ändert sie nichts.

### 🟢 Wellen-Bilanz nach Regel 77 — geht erstmals mit dem Zugang auf

Lauf 87 hat Regel 77 aus einer Lücke gezogen (#1127 war in keiner Welle). Diesmal maschinell
gerechnet, Vereinigung gegen Bestand:

```
Welle 0:3  M:11  N:31  Q:1  R:3  S:1   Summe 50 | eindeutig 50
Doppelt zugeordnet: keine
Offen: 50 | ohne Welle: keine | zugeordnet aber nicht offen: keine
```

🟢 **50 von 50, keine Dublette, keine Lücke** — #1154 ist in N eingereiht. Die Regel hat am
ersten Lauf nach ihrer Einführung gehalten.

---

## Die drei Funde des Laufs

### 1. 🔴 Das Grün von #1120 ist eine Momentaufnahme vom 2026-11-09 — und wird seit fünf Läufen als Zusage gelesen

#442 und die Läufe 85–87 führen **#1120** als „seit dem 2026-11-05 offen und **18/18 grün** bei
Rückstand 0", also als den einen Merge, der nur noch einen Klick braucht. **Heute an den
Check-Runs und am Job-Log nachgemessen — und die Zusage trägt nicht.**

| Messung | Ergebnis |
|---|---|
| #1120, alle 18 Check-Runs | 🟢 **success**, `audit` abgeschlossen **2026-11-09T07:02:15Z**, `all-green` **07:18:13Z** |
| #1120 Rückstand auf `main` | **0** |
| 🔴 `pip-audit` **heute** auf demselben Baum | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** |

🔴 **Am 2026-11-09 war `pip-audit` grün, weil es zu diesem Zeitpunkt nur eine einzige CVE gab —
und #1120 ist genau deren Fix.** Belegt am Job-Log von **#1124** vom 2026-11-06
(`job 127774423452`, Schritt 5):

```
2026-11-06T07:39:28Z Found 1 known vulnerability in 1 package
                     oauthlib 4.0.0   CVE-2026-49272   4.0.1
##[error]Process completed with exit code 1.
```

**Drei Tage später, mit #1120s eigenem `oauthlib`-Bump im Baum, war nichts mehr zu finden.** Die
CVEs zu `dnspython`, `opentelemetry-api` und `soupsieve` sind **danach** erschienen — belegt an
den Eröffnungsdaten ihrer Träger (#1141 und #1142 am **2026-11-13**, #1150 am **2026-11-17**).

🔴 **Das Grün beschreibt also den 2026-11-09, nicht das Repo.** Wird #1120 heute gemergt, findet
`pip-audit` auf `main` anschließend **6 CVEs in 3 Paketen** (7 minus die eine `oauthlib`-CVE),
und `main`-CI bleibt rot — mit einem frisch gemergten PR, dessen Badge Grün sagt.

**Und die Korrektur hält in beide Richtungen** (Regel 32), je nachdem wie das Ruleset prüft:

| Modus | Folge für #1120 | Folge für die Zusage „ein Klick" |
|---|---|---|
| **loose** (`strict_required_status_checks_policy: false`) | GitHub akzeptiert das alte Grün, der Merge geht durch | 🔴 **mechanisch richtig, inhaltlich irreführend** — `main` ist danach weiter rot |
| **strict** | Der Check müsste gegen den aktuellen `main` neu laufen und wäre **rot** | 🔴 **auch die Mechanik trägt nicht** — nicht mergebar |

⚠️ **Grenze dieses Funds, ausdrücklich benannt:** der Modus steht als **loose** in der
eingecheckten Ruleset-Nutzlast (`docs/branch-protection-main.md`, Messung vom **2026-09-24**,
Ruleset `16707501`, `all-green` als einziger Required Check). **Heute nicht nachgemessen** — ein
Live-Read bräuchte `gh api repos/luetzey/who2be/rulesets/16707501`, und das Toolset dieser Session
trägt für `gh` nur die Suche. 🟢 **Die Korrektur ist von dieser Lücke unabhängig:** beide Modi
widerlegen die Lesart „grün heißt fertig", nur mit verschiedener Begründung.

**Die verallgemeinerte Form steht unten als Regel 79.**

### 2. 🔴 #1124 ist rot an einer fremden Schuld — und sein eigenes Gate hat nie gelaufen

#1124 (`fix(web): glob 14 / minimatch 11 via overrides, OSV-Ausnahmen entfernt`) ist der Fix für
**Weiche 46**. Lauf 87 hat pro Knoten belegt, dass er die Advisory-Bereiche an **allen zehn**
betroffenen Deklarationen verlässt. Heute an den Check-Runs und am Schritt-Protokoll gelesen:

| Messung | Ergebnis |
|---|---|
| #1124, Check-Runs | **18** gesamt, **16 grün**, 🔴 rot: **`audit`** und **`all-green`** |
| Rückstand auf `main` · Konfliktfreiheit | **0** · `rc 0` |
| 🔴 Grund der Röte, am Log | `pip-audit` fand **`oauthlib 4.0.0`** — ein Paket, das #1124 **nicht anfasst** |
| 🔴 Schritte 6–10 des Jobs `audit` | **`setup-node`, `Install web deps`, `npm audit`, `License check`, `OSV-Scan` — sämtlich `skipped`** |

🔴 **Der OSV-Scan ist der Schritt, der #1124s ganze Behauptung prüfen würde — und er ist nie
gelaufen.** Nicht einmal. Er wird übersprungen, weil `pip-audit` vor ihm abbricht, und zwar an
einer Abhängigkeit aus `main`. 🟢 **Gegenprobe an der Definition, nicht nur am Lauf** (Regel
10/155): der Job trägt an keinem seiner neun Definitions-Schritte eine `if:`-Bedingung auf
`changes.outputs.web` — die fünf Übersprungenen fallen allein wegen Schritt 5 weg.

**Damit ist #1124s zentrale Aussage CI-ungeprüft**, und das ist ab heute terminiert:

| Termin | Abstand |
|---|---|
| `ignoreUntil = 2026-11-30T00:00:00Z` für **beide** `[[IgnoredVulns]]` | 🔴 **9 Tage** |
| `osv-scanner.toml:5-7` über sich selbst | „No entry without an expiry date; **when it expires the scan turns red again**" |

🔴 **Am 2026-11-30 bekommt der `audit`-Job eine zweite, unabhängige Ursache für Rot** — die
beiden Advisories, die `npm audit` heute als die **einzigen** Wurzeln seiner 27 moderate-Funde
nennt (`GHSA-3g3m-2fjr-6pw4`, `GHSA-g3hv-75wg-m249`). **Der Fix dafür liegt seit dem 2026-11-06
fertig und konfliktfrei in #1124 — und kann bis dahin nicht grün werden, weil Welle 0 davor
liegt.**

### 3. 🔴 Die Zielversion in #1150 ist zum dritten Mal in drei Läufen überholt

| Lauf | Datum | `soupsieve` latest auf PyPI | Stand im Body von #1150 |
|---|---|---|---|
| 86 | 2026-11-19 | **4.1.1** → korrigiert auf **4.1.2** | `4.1.1` |
| 87 | 2026-11-20 | **4.1.2** (zweite Quelle) | `4.1.1` |
| **88** | **2026-11-21** | 🔴 **4.1.3** | `4.1.1` |

Messweg benannt (Regel 176): `https://pypi.org/pypi/soupsieve/json` → `info.version` = **4.1.3**,
jüngste Releases `… 4.0.1, 4.1, 4.1.1, 4.1.2, 4.1.3`.

🟢 **Die Akzeptanzkriterien von #1150 sind davon nicht betroffen** — AK1 verlangt
„**`4.1.1` oder höher**", und das ist gegen eine wandernde Obergrenze robust formuliert.
🔴 **Betroffen ist allein der Verifikations-Block**, der `# erwartet: "4.1.1"` als festen Wert
führt: ein Agent, der ihn wörtlich nimmt, liest ein korrektes `4.1.3` als Abweichung.

🔴 **Die Lehre ist nicht „die Zahl nochmal heben".** Drei Läufe, drei Werte, ein unveränderter
Baum: **eine Fremdversion gehört nicht als Literal in einen Verifikations-Block, sondern als der
Befehl, der sie ermittelt.** → **Regel 80**.

---

## Norm-Prüfung „Agent-ready Arbeitspaket" — alle 13 offenen Issues

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

**Lesestand ehrlich getrennt** (Regel 42/189): **#1150 ist in diesem Lauf vollständig und wörtlich
gelesen.** Die übrigen elf Paket-Bodies sind von einem eigenen Sub-Agenten wörtlich gelesen und
gegen die vier Felder geprüft worden (Modellwahl **Sonnet**: mechanisches Lesen und
Mustervergleich, keine Urteilsbildung — das kleinste Modell, das die Aufgabe trägt). **#442 ist
die Liste selbst.**

| Issue | Labels | Outcome | AK | Out-of-Scope | „In"? | Verifikation | Urteil |
|---|---|---|---|---|---|---|---|
| **#632** | `agent-ready` `size/S` | ✅ `### Fertig heißt` | ✅ 5 | ✅ `**Out:**` | ✅ | ✅ exakte Kommandos | 🟢 **4/4** |
| **#1001** | `agent-ready` `size/S` | ✅ `## Fertig heißt` | ✅ 5 | ✅ `**Out of Scope:**` | ✅ | ✅ exakte Kommandos | 🟢 **4/4** |
| **#633** | `agent-ready` `size/S` | ✅ `### Fertig heißt` | ⚠️ 6 | ✅ `**Out:**` | ✅ | ✅ exakte Kommandos | 🟢 **4/4** |
| **#989** | `agent-ready` `size/S` `needs-decision` | ✅ `## Fertig heißt` | ⚠️ 6 | ✅ `**Out of Scope:**` | ✅ | ✅ exakte Kommandos | 🟢 **4/4** |
| **#1150** | `needs-decision` `size/S` | ✅ `## Fertig heißt` | ✅ 5 | ✅ `## Scope` | ✅ | ✅ `## Verifikation (exakte Kommandos)` | 🟢 **4/4**, bewusst ohne `agent-ready` |
| **#540** | `needs-decision` `size/M` | ✅ `### Fertig heißt` | ⚠️ 7 | ✅ `### Out of scope` | ❌ | ✅ exakte Kommandos | **4/4**, kein „In" |
| **#435** | `epic` `size/M` | ⚠️ nur inline `**Fertig heißt:**` | ⚠️ 6 | ✅ `**Out:**` | ✅ | ✅ bash-Block | **4/4 formal**, Tracking |
| **#542** | `needs-decision` `human-only` `size/M` | ❌ | ✅ 5 | ✅ `### Out of scope` | ❌ | ⚠️ nur für Option A/C | **3/4** |
| **#454** | `human-only` | ✅ `### Fertig heißt` | ✅ 5 | ✅ `### Out of Scope` | ❌ | ⚠️ Abschnitt **ohne** Befehl („Kein Testkommando — die Verifikation ist die Produktions-Smoke-Reise") | **3/4**, `human-only` |
| **#535** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 3 | ✅ `### Out of scope` | ❌ | ❌ | **2/4**, Tracking |
| **#428** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 5 | ✅ `### Out of scope` | ❌ | ❌ | **2/4**, Tracking |
| **#338** | `human-only` | ❌ | ❌ (Checkboxen O1–O4) | ❌ | ❌ | ❌ | **0/4**, Checkliste |
| **#442** | `needs-decision` `backlog-queue` | — | — | — | — | — | diese Liste |

🟢 **Unverändert gegenüber Lauf 87 in jeder Zeile** — die fünf Norm-vollständigen Pakete sind
norm-vollständig, die Tracking-Epics und `human-only`-Issues unverändert lückenhaft. **Echt
nummeriert sind nur #989 und #1001**; alle übrigen führen ihre Kriterien als `- [ ]`-Checkboxen,
gezählt wurden die Top-Level-Einträge.

### 🟢 Zwei Gegenproben, die die Paket-Bodies entlasten

Beide Behauptungen, die Lauf 85 als falsch gefunden hatte, sind in **allen** betroffenen Bodies
heute als **Korrektur** geführt, nicht als lebende Aussage:

- **„#1120 bringt `pip-audit` auf Exit 0"** — in #632, #633, #989 und #1001 je ausdrücklich
  widerlegt, und zwar mit **genau dem Wert, den dieser Lauf unabhängig gerechnet hat**:
  „#1120 allein macht `audit` NICHT grün — **Exit 1, 6 CVEs in 3 Paketen**." 🟢 **Das ist 7
  minus die eine `oauthlib`-CVE**, zeichengleich zu meiner Messung. In #540, #542, #454, #435,
  #535, #428, #338 kommt #1120 nicht vor.
- **„398 Requirements"** — vier Treffer, **alle** in der korrigierten Form („398 ist die
  Zeilenzahl, nicht die Paketzahl; 125 Requirements / 124 Namen"). Lauf 83/86 hat das wirklich in
  die Bodies geschrieben.

🔴 **Daraus folgt die Zuordnung von Fund 1:** die **Pakete** führen #1120 korrekt. Die Lesart
„#1120 ist 18/18 grün bei Rückstand 0, ein Klick" steht in **#442** und in den Lauf-Kommentaren
85–87 — **ohne ihr Messdatum.** Nach Regel 4 (die Warteschlange trägt die Reihenfolge, nicht die
Tatsachen) gehört die Korrektur deshalb in **#442**, und dort steht sie.

⚠️ **Eine Restunschärfe, benannt und nicht behoben:** #633 §Verweise sagt über #1120 „solange er
offen ist, ist `audit` für JEDEN PR rot". Das war am 2026-11-06 richtig (eine CVE, ein Träger)
und ist heute zu eng — rot ist der Job an **vier** Paketen, von denen #1120 eines deckt. **Eine
Zeile in einem 47k-Body; für den nächsten Vollschrieb von #633 vorgemerkt**, zusammen mit der
Ein-Zeichen-Drift an Position 3123, die Lauf 87 dort protokolliert hat (Regel 78).

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines entzogen.**

🔴 **Ein `size/M`-Issue wird nie durch Nachtragen von Feldern startbar** (§Constraints) — #428,
#435, #535, #540, #542 brauchen Zuschnitt, kein Refinement.

⚠️ **Die „6/7 AK"-Markierungen bleiben kein belegter Verstoß:**
`grep -rn '2–5\|2-5\|bis 5' .github/PROJECT.md` → **kein Treffer**, **vierundzwanzigster Lauf
ohne lesbare Quelle für die Obergrenze** (Weiche 55 offen; die Norm selbst liegt in der AgentDB
und war diesen Lauf nicht erreichbar).

---

## Reihenfolge

**Unverändert gegenüber Lauf 87 — und das ist gemessen, nicht übernommen:** das Fenster hat
**0 Commits**, kein PR ist gemergt, keine harte Abhängigkeit hat sich gelöst, kein Blocker ist
weggefallen, kein Issue ist zu- oder abgegangen (13 offen, wie Lauf 87).

Kriterien in dieser Ordnung: **harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche →
Inventar vor Zuschnitt → bei Gleichstand das kleinere.**

**#632 → #1001 → #633 → #989.**

| Pos | Issue | Größe | Baum | Kriterium | Lage |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | ✅ **startbar** — 🟢 keiner der **50** PRs fasst `apps/web/src/**` an |
| **2** | **#1001** Payload-Budget (ADR-0058 P4b, Rest) | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar** — alle drei Hebel frei |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web/E2E | **1** harte Abhängigkeit | 🔴 nach **#632** **und** Container-Laufzeit (`docker info` Exit 1, **64.**) **oder** ein CI-Lauf mit **einzeln** gelesenen E2E-Conclusions |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | Owner-Vorgabe fehlt | 🔴 erst **Weiche 48**, dann die Fläche (`package-lock.json` **fünffach**) |

**Nicht in der Warteschlange:** #442 (ist die Liste) · #428/#435/#535 (Tracking-Epics, tragen
keine eigene Arbeit) · #338/#454/#542 (`human-only`) · #540 (`needs-decision`, Weiche 17 —
🟢 **der Mechanismus-Teil ist erledigt**, Lauf 87 Fund 1) · **#1150** (`needs-decision`, Welle-0-
und damit Owner-Arbeit) · die **50** offenen PRs (ein PR ist kein Issue, Regel 34a/65a).

## Wellen — was gemeinsam startbar ist

Gemeinsam startbar ist, was **datei-disjunkt** ist und sich **nicht gegenseitig blockiert**.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + #1150** | Die vier Schritte zu `pip-audit` Exit 0, reihenfolge-frei. 🔴 **#1150 braucht zuerst A/B/C.** 🔴 **Neu: Welle 0 liegt auf dem kritischen Pfad einer Frist am 2026-11-30** (Fund 2) · 🔴 **neu: #1120s Grün ist vom 2026-11-09** (Fund 1) |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle **50** PRs frei. ⚠️ Gemeinsame DoD-Fläche `STATE.md` (dreifach gehalten) — wer zweiter fertig wird, rebasiert auf **#1103** |
| **B** | **#633** | nach #632 (hart) **und** Container-Laufzeit **oder** CI mit einzeln gelesenen E2E-Conclusions |
| **C** | **#989** | erst Weiche 48. 🟢 Entlastet: #1124 verlässt die Bereiche an allen Knoten (Lauf 87 Fund 3) |
| 🔴 **M** _(Owner)_ | Welle 0 → **#1124** → **#1148** → **#1132–#1136 / #1149** → **#1146** → Domain-Doku (#1106 **oder** #1122) | 🔴 **#1124 ist ab heute terminiert: 9 Tage** (Fund 2) und kann vor Welle 0 nicht grün werden → **Weiche 58**. #1149 überschneidet #1134 und #1132 — nacheinander messen. **#1106/#1122 nicht beide** (Weiche 49), **und einer muss kommen** (Betreiber-Host) |
| **N** _(Owner)_ | **31 Protokoll-PRs** in beliebiger Reihenfolge | #1154 _(neu)_, #1153, #1152, #1151, #1145, #1144, #1143, #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — je genau eine Datei außer **#1105** (zwei) und **#1152** (drei). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | Rückstand 15 / 33 / 237 |
| **Q** _(Owner, entscheidbar)_ | **#674** | 🟢 konfliktfrei, **0** hinter `main`. 🔴 eigene Checks rot. **Empfehlung: schließen** |
| **R** _(Owner)_ | **#1129, #1130, #1147** | zwei Major plus Gruppen-PR auf der Fläche von #1124. **Nach #1124, einzeln** |
| **S** _(Owner, einzeln)_ | **#1127** | `docker/login-action` 4.7.0 → 4.8.0, Fläche genau `.github/workflows/deploy.yml` — berührt kein Paket dieser Warteschlange |

🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier `agent-ready`, zwei
davon blockiert. **Zum dreizehnten Mal unverschoben.**

---

## 🔴 Weiche 58 _(neu)_ — wie #1124 vor den 2026-11-30 kommt

**Lage, gemessen:** #1124 ist konfliktfrei, 0 hinter `main`, 16 von 18 Checks grün. Rot sind
`audit` (an **fremder** Schuld: `oauthlib`) und `all-green`. Sein eigenes Gate, der OSV-Scan, ist
**nie gelaufen**. Die beiden Ausnahmen, die er entfernt, verfallen in **9 Tagen**; danach hat
`audit` eine zweite Rot-Ursache. `audit` grün zu bekommen verlangt **alle vier** Welle-0-Pakete,
und das vierte (#1150) hängt an einer unbeantworteten Owner-Frage.

| | Option | Weg | Preis | Wirkung |
|---|---|---|---|---|
| **A** | **#1150 jetzt beantworten**, Welle 0 vollständig mergen, dann #1124 neu laufen lassen und mergen | 1 Owner-Antwort (A/B/C), 4 Merges, 1 Re-Run | 🔴 In **9 Tagen** müssen vier Merges und ein CI-Lauf durch. Die Antwort muss **jetzt** kommen | 🟢 **Der einzige Weg, auf dem #1124s OSV-Scan VOR dem Merge läuft** — die Behauptung wird geprüft, nicht angenommen. Gate bleibt unangetastet |
| **B** | **Weiche 5 entscheiden:** `audit` aus `all-green` lösen (eigener, nicht blockierender Check) | 1 Änderung an `ci.yml` / am Ruleset | 🔴 Ein rotes `audit` blockiert danach nichts mehr — genau die Eigenschaft, die es zum Gate macht. Und `ci.yml` ist frei, aber die Änderung ist Gate-Mechanik, kein Paket | #1124 und die übrigen 49 PRs werden unabhängig von `pip-audit` mergebar; die Frist ist gerettet |
| **C** | **#1124 per Owner-Bypass vorziehen**, `pip-audit` danach | Ruleset-Eingriff | 🔴 ⚠️ **Möglicherweise mechanisch nicht verfügbar:** die eingecheckte Nutzlast führt `bypass_actors: []` und `current_user_can_bypass: "never"` (Messung 2026-09-24, heute nicht nachgemessen — s. Fund 1 §Grenze). Und es mergt einen PR, dessen eigenes Gate nie lief | Frist gerettet, Prüfung nicht |

**Empfehlung: A** — als einzige Option läuft #1124s OSV-Scan **vor** dem Merge, die Aussage
„beide Ausnahmen entbehrlich" wird damit belegt statt geglaubt, und das Gate bleibt wie es ist.
Sie verlangt genau eine Owner-Handlung, die ohnehin die dringendste offene ist.

🔴 **Mit datiertem Rückfall:** liegt die A/B/C-Antwort zu #1150 **bis zum 2026-11-25** nicht vor,
reicht die Restlaufzeit für vier Merges plus Re-Run nicht mehr — **dann ist B der pragmatische
Weg**, und zwar bewusst als Gate-Entscheidung, nicht als Notlösung. **C nur, wenn B abgelehnt
wird und der Bypass tatsächlich verfügbar ist.**

## Was dieser Lauf geschrieben hat

**Als Kommentar, mit benanntem Grund:**

- **#442** — das Lauf-88-Protokoll: Messgrundlage, die drei Funde, Reihenfolge, Wellen inkl.
  Bilanz 50/50, **Weiche 58** mit drei Optionen und datiertem Rückfall.
- **#1150** — die dritte Versions-Drift (**4.1.3**), der zweite Beleg für Regel 71 aus einem
  anderen Messweg, und wie Fund 1 und 2 seine §Startbedingung treffen: **seine Antwort liegt auf
  dem kritischen Pfad einer Frist in 9 Tagen.**

🔴 **Kein Body ist in diesem Lauf vollgeschrieben — mit Grund, und der Grund ist gemessen.**
Lauf 87 hat alle vier `agent-ready`-Bodies neu geschrieben und danach maschinell zurückgelesen:
**drei kamen zeichengleich an, einer (#633) mit einem unbeabsichtigt geänderten Wort** bei 47.187
Zeichen. Was sich seither an diesen Bodies überholt hat, ist der PR-Bestand (**49 → 50**) und ein
Tagesabstand — also genau die strukturell wandernden Zahlen, die Lauf 87 gestern erst gehoben hat.
**Ein zweites Abtippen von vier Bodies mit 25k–47k Zeichen für ein `+1` ist der Fall, vor dem
Regel 78 warnt.** Die inhaltlich scharfe Korrektur dieses Laufs betrifft **kein** Paket-Body,
sondern #442 und #1150 — und dort steht sie.

⚠️ **Eine Stelle bleibt bewusst offen:** der Verifikations-Block von #1150 führt
`# erwartet: "4.1.1"`. Der Wert ist zum dritten Mal überholt, aber die Owner-Antwort A/B/C wird
diesen Abschnitt ohnehin anfassen; eine Korrektur jetzt wäre ein Vollschrieb für eine Zeile, die
in wenigen Tagen neu geschrieben wird. **Im Kommentar zu #1150 benannt, damit sie nicht verloren
geht.**

## Neue Regeln

**79.** 🆕 **Ein grüner Check an einem offenen PR ist eine Aussage über seinen Laufzeitpunkt,
nicht über heute — und bei Gates gegen eine externe Datenbank verfällt er still.** #1120 trug
18/18 Grün vom 2026-11-09 und wurde fünf Läufe als „ein Klick" geführt; am selben Baum findet
`pip-audit` heute 7 CVEs, weil drei Advisories nach dem Lauf erschienen sind. **Messweg: zu jedem
„grün und mergebar" das `completed_at` des Checks gegen das Alter der geprüften Datenquelle
lesen.** Ein Badge ohne Datum ist keine Zusage.

**80.** 🆕 **Eine Fremdversion gehört nicht als Literal in einen Verifikations-Block, sondern als
der Befehl, der sie ermittelt.** `soupsieve` stand in drei aufeinanderfolgenden Läufen mit drei
verschiedenen „erwarteten" Werten (4.1.1 / 4.1.2 / 4.1.3) an einem unveränderten Baum. Robust
formuliert ist nur, was #1150s AK1 schon tut: „**4.1.1 oder höher**". **Folge: `# erwartet:`-Zeilen
auf Fremdversionen durch den ermittelnden Befehl plus eine untere Schranke ersetzen.**

**81.** 🆕 **Ein rotes Gate verdeckt den Zustand der Schritte nach ihm — und damit ausgerechnet
den Nachweis des PRs, der es reparieren soll.** #1124s OSV-Scan ist in **keinem** Lauf jemals
ausgeführt worden, weil `pip-audit` davor an einem fremden Paket abbricht. **Folge: wer einem PR
zutraut, ein Gate zu heilen, prüft zuerst, ob der beweisende Schritt in seinem CI-Lauf überhaupt
`conclusion != skipped` hatte.**

---

## Belege dieses Laufs

- Messpunkt `f89acf87`, Baum `c751ed64`, Fenster 0 Commits, 1676 Commits nach `--unshallow`
- 50 offene PRs, 55 Pfade, 74 Vorkommen — alle selbst gerechnet; Wellen-Bilanz 50/50 maschinell
- Job-Logs gelesen: `127774423452` (#1124, `audit`, 2026-11-06) und `129025862253` (#1120,
  `audit`, 2026-11-09)
- Check-Runs gelesen: #1124 (18, zwei rot), #1120 (18, alle grün)
- `main`-CI `42178623925`, `status` und `conclusion` getrennt gelesen
- PyPI `soupsieve` → `info.version` 4.1.3
- Norm: #1150 selbst wörtlich gelesen; elf weitere Bodies über einen Sonnet-Sub-Agenten
- Kommentiert: **#442**, **#1150** · **kein** Body vollgeschrieben (Regel 78, Grund protokolliert)
