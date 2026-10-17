# Backlog-Aufbereitungslauf 53 — 2026-10-17

**Auftrag:** jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen,
Belegbares selbst ins Issue schreiben, Urteilsbedürftiges als Kommentar mit drei
Optionen und Empfehlung stellen (`needs-decision`), danach die Warteschlange
(Label `backlog-queue`, Issue #442) neu ordnen und in Wellen gruppieren.

**Basis:** `main` @ `a6027b88`. Fenster seit der Lauf-52-Basis `979ef6d2`:
**1 Commit** über **14 Dateien** (#979, ADR-0053 E4b) — alle unter `apps/api/`
plus ein `changelog.d/`-Fragment. **Der Web-Baum, `ci.yml` und `CLAUDE.md` sind
im Fenster 0× bewegt.**

> **Der MCP-Server der eigenen AgentDB war erneut nicht erreichbar** (achter Lauf
> in Folge): `Who2Be---Coder` liefert über `ToolSearch` keine Werkzeuge, also kein
> `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (die Norm
> „Agent-ready Arbeitspaket", `73a86231`), `record_usage`, `search_memory`.
> Persona und Playbook-Katalog lagen im System-Prompt vor; der Lauf fährt nach
> dem Body von #442.

---

## 1. Lage

### `main`

🟢 **Grün.** `all-green` = `success`, **24** Check-Runs am HEAD, **0** mit
`failure`/`timed_out` (Lauf `38953392933`, `completed`/`success`). Im Fenster
**genau ein** Push, **0** `cancelled` → **Weiche 1 bekommt zum dritten Fenster in
Folge keinen neuen Beleg**, weil die auslösende Bedingung (drei Pushes binnen
rund zwei Minuten) bei einem Push nicht vorliegen kann (Regel 115).

### Offene PRs: **18** _(waren 16)_

Datei-Scope je PR über `BASE=$(git merge-base origin/main <head>)` mit
ausdrücklicher Nicht-leer-Prüfung, dann `git diff --name-only $BASE <head>` —
nach `git fetch --unshallow` (50 → **1562** Commits; **16. Lauf in Folge** ein
shallow Klon). Konfliktfreiheit über `git merge-tree --write-tree` je PR:
**alle 18 → rc 0.** CI-Zustand über die Check-Runs am Head, `all-green`
**namentlich** herausgesucht, Conclusions **positiv** auf `failure`/`timed_out`
gefiltert (Regel 101); Gate-Alter über die Anwesenheit des Checks `secrets`.

| PR | Inhalt | Schreibt nach | `all-green` | Gate | hinter `main` | Klasse |
|---|---|---|---|---|---|---|
| 🆕 **#980** | Rate-Limit an der Kante per fail2ban (#540) | `ci.yml`, `Caddyfile`, `RUNBOOK.md`, 3 neue `deploy/hetzner/fail2ban/**`-Dateien, Fragment (**7**) | 🟢 **success**, 18 Checks, 0 `failure` | ✅ aktuell | **0** | 🟢 **merge-fertig, der einzige Sach-PR** |
| **#977** | Werkzeugzahl aus `CLAUDE.md` nehmen, Wächter dafür | `changelog.d/`, `test_doc_tool_count.py` (2) | 🔴 **failure** (`python` + `all-green`; 16 Checks grün) | ✅ aktuell | **1** | 🔴 **eigen-rot, Weiche 16** |
| **#947** | `actions-all`, 3 Updates | `ci.yml` | 🟢 **success**, 15 Runs, 0 `failure` | ✅ aktuell | **18** | 🟢 grün, zeilenneutral (15/15) |
| **#954** | web-minor-patch, 4 Updates | `apps/web/package.json` + Lock | 🟢 **success**, 15 Runs | ✅ aktuell | **18** | 🟢 grün, frei |
| **#955** | python-minor-patch, 5 Updates | `uv.lock` | 🟢 **success**, 15 Runs | ✅ aktuell | **18** | 🟢 grün, frei |
| 🆕 **#978** | Protokoll Lauf 52 | eine Plan-Datei | 🟢 **success**, 16 Checks | ✅ aktuell | **1** | ⚪ Protokoll (Draft) |
| **#976 #961 #950 #945 #924 #896 #870 #851 #841** | Protokolle 51–43 | je **eine** eigene Plan-Datei | 🟢 alle **success**, je 16 Checks | ✅ alle aktuell | 2 … 115 | ⚪ Protokoll, untereinander disjunkt |
| **#831** | Protokoll 42 | eine Plan-Datei | 🔴 **failure** (`audit` + `all-green`) | **alt** | **123** | 🔴 Weiche 5 |
| **#823** | verrottete Zeiger nachziehen | `STATE.md`, `.github/PROJECT.md`, `RUNBOOK.md` + Plan | 🟢 **success**, 17 Checks | **alt** | **126** | 🔴 Weiche 10 |
| **#674** | Vitest 4 → **5** (Major) | `apps/web/package.json` + Lock | 🔴 **failure** (8 Jobs) | ✅ aktuell | **18** | 🔴 eigen-rot, Weiche 12 |

🟢 **Vier PRs sind grün, gate-aktuell und konfliktfrei: #980 (0 hinter), #947,
#954, #955 (je 18 hinter).** 🔴 **Zwei sind eigen-rot** (#977, #674).
🔴 **Der Protokoll-Rückstand steht bei ELF** (#978, #976, #961, #950, #945,
#924, #896, #870, #851, #841, #831) **plus #823**; dieser Lauf legt den zwölften
dazu.

---

## 2. Der zentrale Fund des Laufs: #980

**#540 ist umgesetzt.** PR #980 (Owner-Session, 2026-10-16 19:31 UTC) baut das
Edge-Rate-Limit als **fail2ban auf Caddys bestehendem JSON-Access-Log** und nennt
im eigenen Body die Herkunft der Entscheidung: **„option A (owner decision
2026-10-16, ‚1.a')".**

**Damit ist die seit 2026-09-19 offene Mechanismus-Weiche von #540 beantwortet** —
und sie ist **außerhalb des Repos** beantwortet worden (Regel 119): kein
Repo-Scan findet sie, der einzige Ort, an dem sie steht, ist der PR-Body. **Dieser
Lauf schreibt sie deshalb in #540.**

### Was #980 messbar liefert

| Gemessen | Wert |
|---|---|
| Dateien / Zeilen | **7** Dateien, **573** Einfügungen, **0** Löschungen |
| CI | **18** Check-Runs, **alle** `success`, `all-green` `success` |
| Stand | **0** Commits hinter `main`, konfliktfrei (rc 0), kein Draft, gate-aktuell |
| `ci.yml` | **+9** Zeilen bei `:366` (ein Step in `compose-smoke`) → **1212 → 1221** |
| `Caddyfile` | **+8** Zeilen bei `:104` (nur Kommentar) → **195 → 203** |

🔴 **#980 ist NICHT zeilenneutral** — anders als #947 (15/15). Nach seinem Merge
wandert jeder `ci.yml`-Zeiger **hinter Zeile 375**, darunter das `needs:` von
`all-green` (`:1090-1101`). Unberührt bleiben `:8-14` (#923), `:122`,
`:210`/`:268` (#949) und `:351-368`.

### Was #980 nicht liefert — und das ist die neue Weiche

#540 trägt **sieben** Akzeptanzkriterien. #980 erfüllt fünf, eines teilweise und
eines gar nicht:

| # | Kriterium (gekürzt) | unter #980 |
|---|---|---|
| 1 | Flut einer IP wird **vor** dem `api`-Container abgewiesen — belegt durch **Fehlen der Requests im API-Log** | 🔴 **ausdrücklich out of scope** („needs a host with iptables and a running fail2ban") |
| 2 | Legitimer Verkehr nach der Sperrfrist wieder möglich | ⚪ Jail-Parameter gesetzt (1 h / 15 min), Wirkung nicht gefahren |
| 3 | `mcp.` ausgenommen, Health erreichbar | 🟢 im Filter belegt (Nicht-Treffer-Fälle, Mutation M2/M3) |
| 4 | Schwellen stehen in **`.env.example` oder im Caddyfile**, ohne Image-Neubau änderbar | ⚠️ Schwellen stehen in `deploy/hetzner/fail2ban/jail.d/who2be-caddy.conf` — **ohne Image-Neubau änderbar, aber an keinem der beiden genannten Orte** (Regel 19: melden, nicht umbauen) |
| 5 | `RUNBOOK.md` bekommt einen Entsperr-Abschnitt | 🟢 neuer Abschnitt + TOC-Eintrag |
| 6 | `test_headers.sh` läuft unverändert durch | 🟢 `test_headers_ci.sh` grün (29 geprüft, 1 übersprungen) |
| 7 | Bei A: bestehende `access.log` auswerten, kein zweites Logging | 🟢 nur ein Kommentar im Caddyfile, kein zweiter Writer |

**Auf `main` gegengeprüft:** `fail2ban` kommt repo-weit **genau einmal** vor, in
einer Plan-Datei (`.claude/plan/2026-09-26-1140_…:52`) — die Fläche von #980 ist
also tatsächlich neu, und `RUNBOOK.md` hat heute **keinen** Entsperr-Abschnitt
(`grep -niE "fail2ban|entsperr|unban"` trifft nur ein Volume-„entsperren" auf
`:279`). **Beides bestätigt den Zuschnitt von #980.**

→ **Weiche 17, neu:** wie wird #540 geschlossen, wenn sein tragendes Kriterium im
umsetzenden PR ausdrücklich außerhalb des Scopes liegt? Drei Optionen plus
Empfehlung stehen als Kommentar in #540 und im Body von #442.

### Nebenwirkung auf die Kollisionslage

| Fläche | vorher | jetzt |
|---|---|---|
| `.github/workflows/ci.yml` | #947 | **#947 UND #980** |
| `deploy/hetzner/Caddyfile` | frei | **#980** |
| `deploy/hetzner/RUNBOOK.md` | #823 | **#823 UND #980** |

🔴 **Welle E (der Caddy-Versions-Widerspruch) ist damit erstmals blockiert** —
beide ihrer Hauptflächen (`Caddyfile`, `ci.yml`) haben jetzt Träger. Und #980
verschärft den Widerspruch im eigenen Diff: sein Caddyfile-Kommentar begründet
Verhalten ausdrücklich „ab 2.11" (`mode`-Unterbefehl wird „unter 2.8 still
verworfen"), während CI die Datei weiter gegen **`caddy:2.8-alpine`** validiert
(`ci.yml:351`/`:352`/`:367`/`:368`) und der Betrieb auf
**`caddy:2.11.7-alpine`** läuft (`deploy/hetzner/who2be/docker-compose.yml:452`).

---

## 3. Weiche 16 (#977): die Prämisse ist widerlegt

#977 führt `test_claude_md_names_no_tool_count` ein und fasst `CLAUDE.md` nicht
an. **Lokal nachgestellt** (Testdatei aus dem PR-Head gegen den heutigen Baum):
**`1 failed, 2 passed`**, Assertion wörtlich

> `CLAUDE.md nennt eine Werkzeugzahl (['100 Tools gesamt']). Die Zahl steht nur in README.md und ROADMAP.md (Owner-Entscheidung 2026-10-14) — in CLAUDE.md ohne Zahl formulieren, z. B. auf README.md verweisen.`

Zwei Dinge, die dieser Lauf dazu **neu gemessen** hat:

1. **Die Richtungsentscheidung ist bereits gefallen** — die Assertion des PRs
   nennt selbst eine **Owner-Entscheidung vom 2026-10-14**: die Zahl lebt künftig
   nur in `README.md` und `ROADMAP.md`. Offen ist also nicht *ob*, sondern *wer*
   die eine Zeile in `CLAUDE.md:98` umformuliert.
2. 🔴 **Die Prämisse, mit der #977 seine Zurückhaltung begründet („die Datei
   schreibt nur der Owner, und jede neue Werkzeugfamilie hat dort eine
   Owner-Rückfrage erzwungen"), ist falsch — und zwar messbar.** `CLAUDE.md` ist
   in den letzten 30 Tagen von **9 Commits** bewegt worden, und **sechs** davon
   sind Feature-PRs, die die Werkzeugzahl **im eigenen Diff** nachgezogen haben:
   **#968** (`979ef6d2`), **#966** (`e9234bab`), **#854** (`c097d726`),
   **#802** (`676fc7e0`), **#715** (`be9f5b4a`), **#630** (`cee6478e`).
   **Keiner dieser PRs hat eine Owner-Rückfrage gebraucht** — der Wächter
   `test_documented_tool_count_matches_registry` hat den Nachzug mechanisch
   erzwungen, genau wie vorgesehen.

**Damit schrumpft Weiche 16 von einer Design-Frage auf eine Zuständigkeitsfrage.**
Alle vier Fundstellen nennen heute **100** (Registry `MCP_TOOL_REQUIREMENTS`
**100**, `README.md:70`, `ROADMAP.md:24`, `CLAUDE.md:98`), und
`uv run pytest packages/models/tests/test_doc_tool_count.py` ist auf `main`
**grün (3 passed)**.

**Empfehlung: B** — #977 zieht die eine Zeile in `CLAUDE.md:98` selbst mit. Das
ist eine Zeile, macht den PR sofort grün und beschädigt nichts: was der PR als
Preis vermeiden wollte (eine Owner-Rückfrage je Werkzeugfamilie), hat es in der
gemessenen Historie nie gegeben.

---

## 4. Selbst erledigt (belegt, keine Entscheidung nötig)

### 4.1 Eine Datei, auf die zwei Issues und die Warteschlange zeigen, existiert nicht

🔴 **`.github/workflows/_debounce-proof.yml` gibt es nicht.** Sie wurde am
2026-09-24 als temporärer Beweis-Workflow angelegt (`64f13d5b`,
„ci(proof): temporaerer Debounce-Beweis-Workflow") und ist seither gelöscht.
`git ls-files .github/workflows/` liefert heute **drei** Dateien: `ci.yml`,
`deploy.yml`, `release.yml`.

Genannt wird sie trotzdem als vorhanden in **#849:118**, **#923:152** und im
Body von **#442** („`timeout-minutes` in den anderen Workflows — `deploy.yml`,
`release.yml`, `_debounce-proof.yml`"). **An allen drei Stellen korrigiert.**

_Warum das durchkam:_ `scripts/check_code_refs.py` prüft nur `*.md` und läuft in
keinem Workflow (Regel 71) — und Issue-Bodies sieht es nie (Regel 70).

### 4.2 #540: ein Zeiger ist verrottet, und die Kopfblöcke waren gestapelt

🔴 **Der Caddy-Pin ist zum fünften Mal gewandert: `:439` → `:452`.**
`deploy/hetzner/who2be/docker-compose.yml` ist **573** Zeilen _(war 560)_, der
Service-Schlüssel `caddy:` steht auf `:446`, der Pin
`image: caddy:2.11.7-alpine` auf **`:452`**. Im Body an allen Fundstellen
korrigiert. **Regel 98 hat wieder getragen:** weil die Gesamtzeilenzahl
mitgeschrieben war, war die Wanderung sofort als solche erkennbar.

Gehalten: `Caddyfile` **195** Zeilen, `grep -cE "\brate\b"` → **0**, `max_size`
auf `:152` · `core/config.py` **271** Zeilen, `:83` = `rate_limit_write`, `:159`
= `ingest_max_bytes` · `core/rate_limit.py:47` = `get_remote_address` ·
`test_compose_hardening.py` **539** Zeilen, Testfunktion `:194`, Untergrenze
`assert (major, minor) >= (2, 11)` auf `:216` · `test_headers_ci.sh:47` und
`test_access_log_rotation.sh:43` (beide Default `caddy:2.8-alpine`) ·
`RUNBOOK.md` **2502** Zeilen.

**Regel 10 angewandt:** #540 trug noch die gestapelten Kopfblöcke der Läufe 51,
48 und 47. Ersetzt durch **einen** aktuellen Kopfblock.

### 4.3 #949: die drei Basiswerte sind nach genau einem Fenster wieder verrottet

| Stelle | stand da | gemessen 2026-10-17 |
|---|---|---|
| Akzeptanzkriterium 5, Fragment-Bestand | **323** | **324** |
| §Zusätzliche Grenzen, Commits nach `--unshallow` | **1561** | **1562** |
| §Verifikation, `pytest --collect-only` | **3643** | **3648** |
| §Zusätzliche Grenzen, offene PRs | **16** | **18** |
| §Basiswerte, `docker info`-Lauf | **28.** | **29.** |
| §Zusätzliche Grenzen, shallow-Klon-Lauf | **15.** | **16.** |

**Alle korrigiert.** Das ist der zweite Lauf in Folge, in dem genau diese drei
Werte um genau ein Fenster danebenliegen — sie sind **Bezugswerte eines
Akzeptanzkriteriums**, also kein Beiwerk (Regel 106).

### 4.4 #959, #632, #633: Bestandszahl und Frist nachgezogen

- „über alle **16** offenen PRs" → **18** (#959, #632).
- Die OSV-Frist steht als **Datum** (`apps/web/osv-scanner.toml:11`,
  `ignoreUntil = 2026-11-02T00:00:00Z`, wörtlich gelesen); die Tageszahl „17
  Tage" ist auf **16 Tage (Stand 2026-10-17)** gesetzt (Regel 110).
- #632: Schreibflächen `features/settings/**`, `i18n/locales/{de,en}.json`,
  `i18n/orphan-baseline.json` (**160** Einträge, als Liste gezählt) sind über
  alle 18 PRs **frei** und im Fenster **0×** bewegt. ⚠️ Momentwert (Regel 113).
  Datei-Sperre an `apps/web/package.json`: **#954 UND #674** — #632 fasst sie
  nicht an.
- #633: Blocker unverändert **genau zwei** — #632 (hart) und die
  Container-Laufzeit (`docker info` → **Exit 1**, **29. Lauf in Folge**). Keine
  Datei-Sperre über die 18 PRs; `apps/web/e2e/helpers/auth.ts` **180** Zeilen
  (`createUser` auf `:33`), `LoginPage.tsx` **394**, `SessionProvider.tsx`
  **267**, `api/types.ts` **2402**, alle im Fenster 0× bewegt.

### 4.5 Die 44 axe-Stellen — unabhängig gegengemessen

Regel 124 a verlangte eine direkte Gegenmessung der Zahl, die aus einer Differenz
entstanden war. **Durchgeführt mit einer zweiten, unabhängig geschriebenen Sonde**
(Klammer-Matching je `it()`/`test()`-Block, Treffer nur bei `await axe(` im
Rumpf, Timeout-Erkennung am letzten Argument):

```
Dateien mit await axe(:        76
  im Glob *.a11y.test.tsx:     51
  außerhalb:                   25
axe-Tests außerhalb des Globs: 69   (mit eigenem Timeout 25 | OHNE 44)
Dateien mit offenen Stellen:   20
```

🟢 **Bestätigt — 44 in 20 Dateien.** Die Korrektur aus Lauf 52 war richtig; die
Zahl steht in #975, #632, #633 und #442 jetzt zweifach belegt.

---

## 5. Messwerte des Laufs

Sequenziell erhoben, **ein Schreiber je Baum**, Node **v22.22.0**, **ohne
vorherige Reparatur** (Regel 120):

| Gate | Ergebnis |
|---|---|
| `npm run test:coverage` | ✅ **Exit 0**, **267 Dateien / 2517 Tests**, Dauer **342 s** |
| Coverage | **89,47** / **83,67** / **86,13** / **91,20** |
| `npm run lint` | ✅ **Exit 0**, **90 problems, 0 errors**, 8 Regeln, **7** `--fix`-bar |
| `npx tsc -b` | ✅ Exit 0, Ausgabe leer |
| `npm run i18n:check` | ✅ Exit 0, **160** bekannte Waisen |
| `uv run ruff check .` | ✅ **Exit 0, 0 Funde** |
| `uv run mypy .` | ✅ **Exit 0, 0 Funde in 608 Dateien** |
| `uv run pytest --collect-only -q` | **3648** Tests, **135** unter `packages/billing/` |
| `uv run python -c "import who2be_billing"` | ok _(ein blankes `python3 -c` ist die falsche Sonde — Regel 49)_ |
| `changelog_fragments.py check` | ✅ Exit 0, **324** Fragmente |
| `uv run pytest packages/models/tests/test_doc_tool_count.py` | ✅ **3 passed** |
| `docker info` | 🔴 **Exit 1** (**29. Lauf in Folge**, kein `podman`) |
| `ci.yml` | **1212** Zeilen, **12** Jobs, **0** mit `timeout-minutes` (über `yaml.safe_load` gezählt), `all-green` hängt an **11** |
| Registry | **100** Werkzeuge; `README.md:70` **100**, `ROADMAP.md:24` **100**, `CLAUDE.md:98` **100** |

**Lint-Verteilung identisch zum Vorlauf** (sechster Stillstand auf 90):
`set-state-in-effect` **48** · `classnames-order` **18** ·
`only-export-components` **12** · `incompatible-library` **5** ·
`preserve-manual-memoization` **4** · `use-memo`/`refs`/`exhaustive-deps` je **1**.

---

## 6. Funde ohne Issue

- 🔴 **Eine Coverage-Zahl schwankt ohne Baum-Änderung** _(NEU, Regel 125)_.
  Lauf 52 hat den Branch-Wert als **83,68 % (7994/9553)** ausgewiesen und damit
  Lauf 51 (83,67) ausdrücklich „korrigiert". Heute, bei **im Web-Baum vollständig
  unbewegtem Stand** (0 von 14 Dateien des Fensters liegen unter `apps/web/`),
  meldet dasselbe Kommando **83,67 % (7993/9553)**. **Ein Branch Unterschied,
  kein Commit dazwischen.** Damit ist der Abstand zur Schwelle 79
  **4,67** Punkte, nicht 4,68 — und eine auf zwei Dezimalen genannte
  Schwellen-Distanz ist ein Messwert, keine Konstante.
- 🔴 **Ein PR kann eine Weiche beantworten, ohne dass das Issue es erfährt**
  _(NEU, Regel 126)_. Die seit 27 Tagen offene Mechanismus-Weiche von #540 ist am
  2026-10-16 entschieden worden; der **einzige** Ort, an dem das steht, ist der
  Body von PR #980 („owner decision 2026-10-16, ‚1.a'"). #540 trug weiter
  `needs-decision` mit „dreifach blockiert" im Kopfblock. **Wer den Backlog nach
  Labels liest, hätte das Paket weiter als blockiert geführt.**
- 🔴 **Ein PR, der einen Wächter einführt und seinen Baum nicht in den geforderten
  Zustand bringt, ist rot an sich selbst — und seine Begründung kann falsch sein**
  _(hält, Regel 123, in diesem Lauf verschärft)_: die Prämisse von #977 ist an
  neun Commits widerlegt (§3).
- 🔴 **Eine gelöschte Datei überlebt in Issue-Bodies** _(NEU, siehe 4.1)_:
  `_debounce-proof.yml` in #849, #923 und #442.
- 🔴 **Das Aufbereitungs-Verfahren produziert PR-Rückstand** _(hält, Bestand
  **12**)_: elf Protokolle plus #823; dieser Lauf legt den zwölften dazu.
- 🔴 **Ein shallow Klon macht die Scope-Messung still falsch** _(hält, **16.**
  Lauf)_: `--is-shallow-repository` → `true`, 50 Commits; nach `--unshallow`
  **1562**.
- 🔴 **`vitest` und `@vitest/coverage-v8` laufen in verschiedenen Patch-Versionen**
  _(hält: **4.1.11** gegen **4.1.10**, am Werkzeug-Hinweis gelesen)_ — #674 löst
  es mit.
- 🔴 **Die `__dirname`-Deprecation in `apps/web/vite.config.ts:29`** _(hält,
  dreimal je Vitest-Lauf gemeldet)_ — gehört in denselben PR wie der
  Coverage-Boden und #975 Option A/C.
- 🟢 **Der MCP-Server-Ausfall ist der achte in Folge** — kein Kurations-Feedback
  (`record_usage`, `submit_feedback`) absetzbar, achter Lauf ohne Rückmeldung an
  die eigene AgentDB.
- **`scripts/check_code_refs.py` ist kein Gate** _(hält)_: in keinem Workflow
  aufgerufen, prüft nur `*.md`, sieht Issue-Bodies nicht. **Dieser Lauf hat sechs
  verrottete Werte und eine gelöschte Datei in Issue-Bodies gefunden, die kein
  Gate gesehen hätte.**
- **Keine Container-Laufzeit** _(hält, **29.** Lauf)_, **`CLAUDE.md:140` nennt
  `ruff format .`, CI fährt `--check`** (`ci.yml:122`) _(hält — die Datei ist
  frei, bis Weiche 16 entschieden ist)_, **Valkey-Ignore fehlt weiter in
  `.github/dependabot.yml`** (nur ein Kommentar auf `:115`), `_VALKEY_PIN`
  kodiert Major **8** hart (`test_dependabot_compose_coverage.py:174`) _(Weiche
  15)_.

---

## 7. Reihenfolge und Wellen

Rangfolge: **1** harte Abhängigkeit · **2** Owner-Vorgabe · **3** Fundament vor
Fläche · **4** Inventar vor dem, was es zuschneidet · **5** bei Gleichstand das
kleinere.

| # | Issue | Kriterium |
|---|---|---|
| 1 | **#959** SessionStart-Hook | 3 — trägt die Verifikation von #632, #633, #975 |
| 2 | **#632** Passkey registrieren | 3 — öffnet #633 |
| 3 | **#949** Skip-Budget-Meldung | 5 — einzige Adresse ohne jede Datei-Sperre |
| 4 | **#849** `timeout-minutes` | 5, gebremst — `ci.yml` jetzt von **#947 UND #980** gehalten |
| 5 | **#923** `concurrency`-Kommentar | 3, dann 5 — dieselbe Doppelsperre, gehört **in** Welle D |
| 6 | **#633** Step-up mit Passkey | 1 — nach #632, plus Container-Laufzeit |

**Unverändert gegenüber Lauf 52.** Das einzige, was sich bewegt hat, ist die
Begründung von Position 4 und 5: ihre Adresse ist nicht mehr einfach, sondern
doppelt belegt — und der zweite Träger (#980) verschiebt Zeiger.

Wellen, Kollisionen und Sammelpunkte stehen vollständig im Body von #442; neu
sind dort:

- **Welle E ist erstmals blockiert** (`Caddyfile` + `ci.yml` von #980).
- **Welle Q (neu)** — der verbliebene Wirkungsnachweis von #540, abhängig von
  Weiche 17.
- **Welle H bekommt eine neue Spitze:** **#980 zuerst** — es ist **0** Commits
  hinter `main`, braucht also **kein** Branch-Update, ist der einzige Sach-PR und
  trägt eine Sicherheits-Änderung. Danach #947 (Konfliktfreiheit nach dem Merge
  von #980 **neu** messen, weil #980 `ci.yml` wachsen lässt), dann #954, #955.

---

## 8. Regel-Vorschläge dieses Laufs

> **125.** **Eine Zahl kann sich ohne Commit ändern — ein Messwerkzeug ist keine
> Funktion seines Eingangs.** Der Branch-Coverage-Wert ist bei unbewegtem
> Web-Baum von 7994 auf 7993 gedriftet. Wer eine Schwellen-Distanz auf zwei
> Dezimalen nennt, nennt sie **mit Messdatum**, und wer eine solche Zahl
> „korrigiert", prüft vorher, ob sie überhaupt stabil ist. _49 sagt: Exit 0 ist
> kein Beleg. 124 a sagt: eine Zahl ist kein Beleg, solange die Sonde nicht
> dieselbe Menge zählt. **125 sagt: und manche Zahl ist auch dann kein Beleg,
> wenn die Sonde stimmt.**_
>
> **126.** **Eine Weiche kann in einem PR beantwortet werden, und das Issue
> erfährt es nicht.** #540 war 27 Tage blockiert, die Antwort stand am 28. Tag im
> Body von #980 — nicht im Issue, nicht in einem Label, nirgends im Repo.
> **Gegenmaßnahme:** zu jedem Lauf gehört der Abgleich *offene Weiche → offener
> PR, der sie berührt*; und wer eine Weiche außerhalb des Issues beantwortet
> bekommt, schreibt sie **ins Issue**, mit Herkunft und Datum (Regel 119 sagt
> *wo* die Antwort lebt — 126 sagt, dass man sie **suchen** muss).

---

## 9. Was dieser Lauf geschrieben hat

- **#540** — Kopfblöcke nach Regel 10 zusammengefasst, Owner-Antwort mit Herkunft
  eingetragen, Caddy-Pin `:439` → `:452` korrigiert, #980 als Umsetzung verdrahtet,
  Weiche 17 als Kommentar mit drei Optionen und Empfehlung.
- **#949** — sechs Bezugswerte korrigiert.
- **#849**, **#923** — die gelöschte `_debounce-proof.yml` richtiggestellt.
- **#959**, **#632**, **#633** — Bestandszahl 16 → 18, Frist als Datum, Flächen
  und Zeiger neu gemessen.
- **#977** — ein Kommentar: die Prämisse ist an neun Commits widerlegt.
- **#442** — Body neu: Lage, Reihenfolge, Wellen, Kollisionen, Sammelpunkte,
  Weichen 16/17.
