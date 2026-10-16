# Backlog-Aufbereitungslauf 52 (2026-10-16)

Prüfnorm: Resource **Agent-ready Arbeitspaket** (`73a86231`, Workspace).
Auftrag: jedes offene Issue gegen die Norm prüfen, Belegbares selbst entscheiden
und mit Beleg ins Issue schreiben, Urteilsfragen als Weiche mit drei Optionen und
Empfehlung zurückgeben, danach die Warteschlange (#442) neu ordnen und in Wellen
gruppieren.

**Basis:** `main` @ `979ef6d2`. Fenster seit der Lauf-51-Basis `5f251c2f`:
**1 Commit** über **14 Dateien** (#968, ADR-0053 E-MCP-2) — das ruhigste Fenster
seit Lauf 49.

> ⚠️ **Boot-Sequenz unvollständig, siebter Lauf in Folge:** der MCP-Server
> `Who2Be---Coder` liefert über `ToolSearch` **keine** Werkzeuge. Persona und
> Playbook-Katalog lagen im System-Prompt vor; `fetch_playbook`,
> `fetch_resource` (die Norm selbst), `record_usage` und `search_memory` nicht.
> Der Lauf fährt deshalb nach dem Body von #442 und den Plan-Dateien der
> Vorläufe. **Kein Playbook-Treffer bestätigbar** — der nächstliegende Katalog-
> Eintrag ist „GitHub-Artefakt anlegen & pflegen", er deckt den Refinement-Lauf
> aber nicht.

## Ausgangslage

Der Merge-Rat von Lauf 51 ist befolgt worden, und zwar in der empfohlenen
Reihenfolge: **#968 — der einzige Sach-PR des Bestands — ist am 2026-10-15
16:09 UTC gemergt** (`979ef6d2`, Lauf `38766629723` grün, 11,6 min).

Daraus folgt dreierlei:

1. **Fünf Sammelpunkte sind frei geworden:** `CLAUDE.md`, `README.md`,
   `ROADMAP.md`, `packages/models/src/who2be_models/tool_requirements.py`,
   `docs/mcp-payload-budget.md`.
2. **Der Doku-Posten „`CLAUDE.md:98` nennt 94" ist erledigt.** Gemessen:
   Registry **100** (`len(MCP_TOOL_REQUIREMENTS)`), `README.md:70` **100**,
   `ROADMAP.md:24` **100**, `CLAUDE.md:98` **100** — zum ersten Mal seit Läufen
   stimmen alle vier.
3. 🔴 **Und genau diese Einigkeit ist der Grund, warum der neue PR #977 rot ist**
   — siehe §Der zentrale Fund.

## Messwerte des Laufs

Sequenziell erhoben, ein Schreiber je Baum (Regel 31/76), Node **v22.22.0**,
**ohne vorherige Reparatur** (Regel 120).

| Messung | Wert | Vorlauf |
|---|---|---|
| `npm run test:coverage` | **Exit 0**, **267 Dateien / 2517 Tests**, **359,33 s** | 259/2236 → 267/2517; 289,64 s |
| → Statements / Branches / Functions / Lines | **89,47 / 83,68 / 86,13 / 91,20** | 89,47 / 83,6**7** / 86,13 / 91,20 |
| `npm run lint` | **Exit 0**, **90** Probleme, **0** Fehler, 8 Regeln, **7** `--fix`-bar | 90 / 0 (fünfter Stillstand) |
| `npx tsc -b` | **Exit 0**, Ausgabe leer | Exit 0 |
| `npm run i18n:check` | **Exit 0**, **160** bekannte Waisen | 160 |
| `uv run ruff check .` | **Exit 0**, 0 Funde | 0 |
| `uv run mypy .` | **Exit 0**, 0 Funde in **608** Dateien | 608 |
| `uv run pytest --collect-only -q` | **3643** Tests, **135** unter `packages/billing/` | 3614 / 135 |
| `changelog_fragments.py check` | **Exit 0**, **323** Fragmente | 322 |
| `npm audit --omit=dev --audit-level=high` | **0 vulnerabilities** | 0 |
| `docker info` | **Exit 1** — **28.** Lauf in Folge | Exit 1 |
| `ci.yml` | **1212** Zeilen, **12** Jobs, **0** mit `timeout-minutes`, `all-green` an **11** | identisch |
| Klon | shallow `true` (50 Commits) → `--unshallow` **1561** · **15. Lauf in Folge** | 1560 |

**Korrektur gegen das Protokoll von Lauf 51:** der Branch-Coverage-Wert lautet
**83,68 %**, nicht 83,67 — `7994/9553 = 83,6805 %`, bei in `apps/web` **0×**
bewegtem Baum. Eine Rundung im Protokoll, keine Bewegung.

## Der zentrale Fund: ein PR, der an seinem eigenen Wächter scheitert (→ Weiche 16, Regel 123)

**#977** („test(docs): Werkzeugzahl nur noch in README/ROADMAP, CLAUDE.md ohne
Zahl", nicht Draft, **0** Commits hinter `main`, gate-aktuell) ändert genau zwei
Dateien:

- `changelog.d/claude-md-no-tool-count.changed.md`
- `packages/models/tests/test_doc_tool_count.py` — streicht `CLAUDE.md` aus
  `_DOC_CLAIMS` und fügt `test_claude_md_names_no_tool_count` hinzu, Regex
  `\d+\s+Tools\s+gesamt`.

**`CLAUDE.md` fasst er nicht an** — und `CLAUDE.md:98` trägt auf `main`
`**100 Tools gesamt**` (Datei **259** Zeilen).

**Selbst nachgestellt**, Test aus dem PR-Head gegen den heutigen Arbeitsbaum:

```
$ git checkout 24db1b2e -- packages/models/tests/test_doc_tool_count.py
$ uv run pytest packages/models/tests/test_doc_tool_count.py -q
..F
E  AssertionError: CLAUDE.md nennt eine Werkzeugzahl (['100 Tools gesamt']).
   Die Zahl steht nur in README.md und ROADMAP.md (Owner-Entscheidung
   2026-10-14) — in CLAUDE.md ohne Zahl formulieren, z. B. auf README.md
   verweisen.
1 failed, 2 passed in 1.34s
```

**CI sagt dasselbe:** Lauf `38771563993`, Job `python` **`failure`**,
`all-green` **`failure`**; die anderen **16** Checks grün, `secrets` vorhanden
(gate-aktuell).

**Warum das ein Fund und nicht nur ein roter PR ist:** der Diff enthält genau
das, was ein guter PR enthält — Test, Changelog-Fragment, ausformulierte
Begründung. **Die Lücke sieht man nicht am Diff, nur am roten Job.** Und die
Lücke ist Absicht: der PR begründet seine Zurückhaltung damit, dass „die Datei
nur der Owner schreibt, und jede neue Werkzeugfamilie dort eine
Owner-Rückfrage erzwungen hat". **Ihr Preis — ein unmergebarer PR auf
unbestimmte Zeit — ist im PR nirgends benannt.**

→ Als **Weiche 16** in #442 gestellt, mit drei Optionen und Empfehlung **A**
(der Owner nimmt die Zahl aus `CLAUDE.md:98`; eine Zeile, der PR wird von
allein grün, die Prämisse bleibt intakt). Als **Regel 123** verallgemeinert.

**Kein Kommentar auf #977.** Der PR gehört nicht diesem Lauf — er ist ein PR,
den dieser Lauf nur beobachtet; die Frage geht an den Owner (Bericht + #442),
nicht als Kommentar in einen fremden PR.

## Zweiter Fund: eine falsche Zählsonde in vier Issue-Bodies (→ Regel 124 a)

Lauf 51 hat in #975 **43** axe-Tests ohne eigenes Timeout ausgewiesen (und
**26** mit). Gemessen am 2026-10-16: **44 ohne, 25 mit.**

**Die Zahl selbst war nicht der Fehler, die Sonde war es.** Lauf 51 hat je
Datei `grep -c '}, 15_000)'` gezählt (**26** Treffer in den 25 Nicht-Glob-
Dateien) und von **69** abgezogen. Diese Sonde zählt Timeouts an
`it()`-Blöcken mit, die **kein** `await axe(` enthalten.

**Gegenbeleg, an einem Fall mit vorher bekanntem Ergebnis:**
`src/components/version/ActivateWithWarningDialog.test.tsx` trägt einen
axe-Test auf `:379` (gelesen: `it('hat keine axe-Verstöße im offenen Dialog',
async () => { … expect(await axe(dialog)).toHaveNoViolations() })`) und
**kein einziges** `}, 15_000)` — während eine lose Variante der Sonde
(`grep -cE '\}, *[0-9_]+\)'`) dort **3** meldet.

**Neu gezählt per Klammer-Matching je `it()`/`test()`-Aufruf** (Aufruf bis zur
schließenden Klammer gelesen, auf `await axe(` geprüft, letztes
Top-Level-Argument auf numerisch bzw. `*TIMEOUT*`):

| Messung | Wert |
|---|---|
| Dateien mit `await axe(` unter `apps/web/src` | **76** |
| davon `*.a11y.test.tsx` (Projekt `a11y`, 15 s) | **51** |
| davon außerhalb (Projekt `unit`, 5 s) | **25** |
| axe-Tests darin | **69** |
| mit explizitem Timeout | **25** |
| 🔴 **ohne** | **44**, in **20** Dateien |

🟢 **Gegenprobe bestanden:** die beiden Dateien des eingetretenen Falls stehen
in der Liste der 44 — `ReviewDetailPage.test.tsx:572` und
`ReviewPreparePage.test.tsx:546`.

**Niemand hätte die 43 bemerkt, weil sie nur um eins falsch war** — und ein
Wächter nach Option C, der dieselbe Sonde benutzt, hätte genau eine Stelle
durchgelassen. In #975, #632 und #633 korrigiert, in #442 als **Regel 124 a**
verallgemeinert.

## Dritter Fund: Reihenfolge richtig, Bedingung fehlt (→ Regel 124 b)

Lauf 51 hat `rm -rf node_modules && npm ci` **vor** der ersten Messung gefahren
und damit den Fall von #959 verhindert statt gemessen (Regel 120, gegen sich
selbst protokolliert).

**Dieser Lauf hat es richtig gemacht** — erste Handlung im Web-Stack war
`npm run test:coverage` auf der Installation des SessionStart-Hooks, ohne jede
Reparatur. Ergebnis: **Exit 0, 267 Dateien / 2517 Tests**, dazu `lint`, `tsc`
und `i18n:check` grün. **Der Fehlschlag ist nicht eingetreten.**

🔴 **Und das belegt trotzdem nichts.** Die auslösende Bedingung lag nicht vor:
`apps/web/package.json` und `apps/web/package-lock.json` sind im Fenster **0×**
bewegt (`git rev-list --count 5f251c2f..origin/main -- apps/web/package.json`
→ **0**) — npm musste **nichts neu auflösen**, und genau das Neu-Auflösen
optionaler, plattformabhängiger Pakete ist der Mechanismus aus npm/cli#4828.
Lauf 50 (Eintritt) hatte 6 Commits mit Web-Bewegung, Lauf 51 dreizehn mit,
dieser Lauf einen ohne.

**Regel 120 und Regel 115 sind zwei Bedingungen, nicht eine** — als
**Regel 124 b** festgehalten. Für #959 heißt das: der Befund ist
**bedingungsabhängig, nicht deterministisch**; der Beleg bleibt der aus Lauf 50
(in beide Richtungen gemessen), der Pfad im Hook ist unverändert offen
(`scripts/install_pkgs.sh:44`, kein `rm -rf`), und **#954 und #674 warten beide
darauf, `apps/web/package.json` zu bewegen.**

## Vierter Fund: der Schreibweg entfernt die Attributions-Fußzeile (→ Regel 125, neu)

**In beide Richtungen gemessen, an allen fünfzehn offenen Issues:**

| Gruppe | Fußzeilen `_Generated by [Claude Code]_` im Body |
|---|---|
| die **8** Bodies, die dieser Lauf über `issue_write` geschrieben hat (#975, #959, #949, #923, #849, #632, #633, #442) | **0 von 8** — vorher trug jeder genau eine (bzw. #442 keine) |
| die Bodies, die dieser Lauf **nicht** angefasst hat und die eine trugen (#435, #428, #535, #540) | **1 von 1**, unverändert |

**Der gesendete Text trug die Fußzeile in allen acht Fällen** (als letzte Zeile,
nach einem `---`). **Die Gegenstelle hat sie entfernt, nicht dedupliziert.**

Das korrigiert die Annahme aus Regel 111 („es sei denn, der gesendete Text trägt
sie schon: dann entdedupliziert die Gegenstelle") für diesen Schreibweg: bei
`issue_write` auf den **Body** wird sie **gestrichen**. Nichts ist dabei
abgeschnitten — jeder Body endet exakt an seiner letzten inhaltlichen Zeile
(`### Component` bzw. §Warum ein Issue und kein Board), und alle 25
Inhaltsproben sind grün.

⚠️ **Folge, die benannt gehört:** über `issue_write` ist die Fußzeile im
Issue-**Body** nicht herstellbar. Wer sie dort braucht, braucht einen anderen
Schreibweg. **Für Kommentare gilt der Befund nicht** — der Kommentar an #435
trägt seine Fußzeile.

→ Als **Regel 125** aufzunehmen; sie steht noch **nicht** im Body von #442
(sie ist nach dessen Schreibvorgang entstanden) und ist dort als Kommentar mit
Pointer auf diese Datei vermerkt. **Der nächste Lauf trägt sie in den Body nach.**

## Norm-Prüfung: alle 15 offenen Issues

Legende: **E** = im Repo belegt, vom Lauf entschieden · **U** = braucht Urteil,
bleibt `needs-decision` · **—** = Lauf endet dort.

| Issue | Labels | 4 Pflichtfelder | Befund | Ergebnis |
|---|---|---|---|---|
| **#975** | `web` `size/S` `needs-decision` | ✅ vollständig | **E** (Zahl) + **U** (Weiche 14) | Zahl **43 → 44** korrigiert, Zählmethode im Body; bleibt `needs-decision` |
| **#959** | `agent-ready` `size/S` | ✅ vollständig | **E** | Regel-120-Messung nachgetragen (Nicht-Eintritt + fehlende Bedingung), Basiswerte, PR-Zahl vereinheitlicht |
| **#949** | `agent-ready` `size/S` | ✅ vollständig | **E** | **drei verrottete Zahlen** korrigiert (304→**323**, 1541→**1561**, 3614→**3643**) + zwei widersprüchliche PR-Zahlen (15/16 → **16**) |
| **#923** | `agent-ready` `size/S` | ✅ vollständig | **E** | Befund wörtlich gegengeprüft, #947 16→**17** hinter `main`, Basiswerte |
| **#849** | `agent-ready` `size/S` | ✅ vollständig (6 AK, Norm 2–5 → Weiche 4) | **E** | Kriterium 3 mit **n = 1** ausdrücklich als dünn benannt; neues Argument aus der Suite-Schwankung (289 s / 359 s / 765 s) |
| **#632** | `agent-ready` `web` `size/S` | ✅ vollständig | **E** | **Positions-Widerspruch aufgelöst** (Body sagte „Position 1", #442 sagte 2 → Regel 4/17), OSV 18→**17 Tage**, Flächen-Bewegung, Basiswerte |
| **#633** | `agent-ready` `web` `size/S` | ✅ vollständig (6 AK, selbst ausgewiesen) | **E** | 1560→**1561**, PR-Zahl **16**, axe **44**, OSV zwei widersprüchliche Angaben (18/20) → **17 Tage** |
| **#435** | `web` `epic` `size/M` | ⚠️ teilweise (Tracking) | **E** (Label) | **`epic` nachgetragen** — hat #632/#633 als Kinder, Konvention `DECISIONS.md` 2026-09-05; #428/#535 führen es |
| **#540** | `size/M` `needs-decision` | ⚠️ teilweise | **U** | dreifach blockiert (Entscheidung, Verifizierbarkeit, Docker) — unverändert |
| **#428** | `epic` `backend` `web` `size/M` `needs-decision` | ⚠️ teilweise (Tracking) | **U** | Weiche 4 — unverändert |
| **#535** | `epic` `backend` `size/M` `needs-decision` | ⚠️ teilweise (Tracking) | **U** | Weiche 4; Kinder 6: 5 zu, 1 offen (#540) |
| **#442** | `needs-decision` `backlog-queue` | — | — | die Warteschlange selbst, neu geschrieben |
| **#542** | `size/M` `needs-decision` `human-only` | — | — | Lauf endet dort |
| **#454** | `human-only` | — | — | Lauf endet dort |
| **#338** | `human-only` | — | — | Lauf endet dort |

**Kein Issue hat `agent-ready` verloren oder bekommen.** Die Norm war in allen
sieben `agent-ready`-Bodies und in #975 vollständig erfüllt — **verrottet waren
nur Zahlen und eine Position**, nicht Felder.

## Nachgemessene Zeiger (Zeile UND Inhalt, Regel 97)

Alle gehalten:

`scripts/ci/assert_skips_within_budget.py` **183** (Meldung `:128`) ·
`.github/workflows/ci.yml` **1212** (`run_id` nur `:11`, Gruppe `:13`,
`cancel-in-progress` `:14`, Aufrufe `:210`/`:268`, `needs:` `:1090`,
Einträge `:1091-1101`, `:423`/`:503` wörtlich gelesen) ·
`deploy/hetzner/Caddyfile` **195** (`grep -cE '\brate\b'` → **0**) ·
`apps/api/src/who2be_api/core/config.py` **271** ·
`docs/licensing/plans.md` **271** (`:28` „100 MB", `:29` „10 GB") ·
`licensing/entitlement.py` **283** ·
`MfaSection.tsx` **297** · `e2e/helpers/auth.ts` **180** (`createUser` `:33`) ·
`SessionProvider.tsx` **267** (`mfaStepUpPending` `:57`) ·
`LoginPage.tsx` **394** (`completeMfaChallenge` `:38`) ·
`core/security.py` **891** (`require_aal2` `:202`) ·
`billing.spec.ts` **147** (`test.skip(` `:43`) ·
`audit.test.ts` **371** · `apps/web/vite.config.ts` **89** ·
`apps/web/package.json` **80** · `scripts/install_pkgs.sh` **49** (`:44`) ·
`deploy/hetzner/RUNBOOK.md` **2502** · `who2be/docker-compose.yml` **573** ·
`CLAUDE.md` **259** (`:98` = „100 Tools gesamt") ·
`vitest-axe.d.ts` **699 Bytes**, **77** Leser von `toHaveNoViolations` ·
`orphan-baseline.json` **160** Einträge (flaches Array, per `json.load`) ·
`apps/web/osv-scanner.toml:11` = `ignoreUntil = 2026-11-02T00:00:00Z` ·
`.github/dependabot.yml` — `valkey` nur als Kommentar `:115`, **kein**
Ignore-Eintrag (Weiche 15 unverändert).

**E2E-Testkörper neu hergeleitet** (Regel 106, nicht geerbt): **34** verankerte
`test(`-Zeilen über acht Specs (`scroll-guard` 14, `journeys` 6, `public` 4,
`navigation` 3, `billing` 2, `consent-overlay` 2, `review-gate` 2,
`status-actions-viewport` 1); die Schleife auf `scroll-guard.spec.ts:236`
expandiert `:237` zu zwei Körpern → **35**; `createUser` wird von **sechs** der
acht Specs gerufen → **26**. Einzige Direktive im Baum: `billing.spec.ts:43`.
**Ohne `E2E_EDITION=cloud`: 24 von 33.**

## PR-Bestand: 16 offen, alle konfliktfrei

Datei-Scope je PR über `BASE=$(git merge-base origin/main <head>)` mit
ausdrücklicher Nicht-leer-Prüfung, dann `git diff --name-only $BASE <head>`,
nach `git fetch --unshallow`. Konfliktfreiheit über
`git merge-tree --write-tree` je PR → **rc 0 für alle 16**.

| PR | hinter `main` | Dateien | Zustand |
|---|---|---|---|
| **#977** 🆕 | 0 | 2 | 🔴 **eigen-rot** (`python` + `all-green`), gate-aktuell → Weiche 16 |
| **#947** | 17 | 1 (`ci.yml`) | 🟢 grün, gate-aktuell, zeilenneutral → **als nächstes mergen** |
| **#954** | 17 | 2 (`package.json` + Lock) | 🟢 grün, gate-aktuell |
| **#955** | 17 | 1 (`uv.lock`) | 🟢 grün, gate-aktuell |
| **#976** 🆕 | 1 | 1 Plan-Datei | ⚪ Protokoll Lauf 51 (Draft) |
| #961 #950 #945 #924 #896 #870 #851 #841 #831 | 14 … 122 | je 1 Plan-Datei | ⚪ Protokolle 50–42; #831 rot (Weiche 5), gate-alt |
| **#823** | 125 | 4 | 🔴 Weiche 10, Draft, gate-alt |
| **#674** | 17 | 2 | 🔴 eigen-rot an **acht** Jobs, gate-aktuell → Weiche 12 |

**Eigen-rot: zwei** (war einer). **Protokoll-Rückstand: elf** (dieser Lauf legt
den zwölften dazu). **Sammelpunkte von PRs belegt: 13 von 47** (Lauf 51: 17 von
47) — der Rückgang hat genau einen Grund, den Merge von #968.

## Neue Reihenfolge

Kriterien unverändert: **1** harte Abhängigkeit · **2** Owner-Vorgabe ·
**3** Fundament vor Fläche · **4** Inventar vor Zuschnitt · **5** bei
Gleichstand das kleinere.

1. **#959** — der SessionStart-Hook _(Kriterium 3)_. Gehalten. Trägt die
   Verifikation von #632, #633 und #975. 🔴 Ehrlich: dieser Lauf hat das Gate
   ohne Reparatur grün gemessen — das senkt die Position **nicht** (Regel 115,
   Bedingung fehlte), verschiebt aber, was das Paket verspricht: es macht die
   Messung verlässlich, nicht jeden Lauf rot.
2. **#632** — Passkey registrieren _(Kriterium 3)_. Gehalten. Öffnet #633
   (Kriterium 1). **Der Positions-Widerspruch im eigenen Body ist aufgelöst.**
3. **#949** — der irreführende pytest-Satz _(Kriterium 5)_. Gehalten. Das
   einzige Paket **ohne jede Datei-Sperre**.
4. **#849** — `timeout-minutes` _(Kriterium 5, gebremst)_. Gehalten; den
   Gleichstand mit #949 bricht die Datei-Sperre von #947 (Regel 8). **Nach dem
   Merge von #947 rückt es vor #949.**
5. **#923** — der `concurrency`-Kommentar _(Kriterium 3, dann 5)_. Gehalten;
   dieselbe Datei-Sperre, **am besten im PR von Welle D.**
6. **#633** — Step-up mit Passkey _(Kriterium 1)_. Nach #632 plus Docker.

**Keine Position verschoben.** Begründung: das Fenster hat einen Commit, keine
Fläche hat den Träger gewechselt, und kein Gleichstandsbrecher ist weggefallen.

**Blockiert, nicht einplanbar:** #975 (Weiche 14), #540 (dreifach), #977
(Weiche 16, ein PR ohne Issue). **Nicht in der Reihenfolge, weil ohne Issue
oder ohne Antwort:** die Merges (Weiche 2/11), der Valkey-Rest (15), der
Caddy-Widerspruch (7), der Coverage-Boden (6), die MB/MiB-Zeile (9), die
`--fix`-baren Lint-Warnungen (8), #674 (12), `STATE.md`/`PROJECT.md` (10).

## Wellen

**Eine Welle wird nach ihrem VERIFIKATIONS-Baum geschnitten, nicht nach ihrer
Schreibfläche** — in diesem Lauf ausdrücklich in #442 ergänzt. #959 schreibt nur
ein Shell-Skript, verifiziert aber per `npm run test:coverage` und liegt damit
im Vitest-Baum.

| Welle | Pakete | Warum gemeinsam / warum nicht |
|---|---|---|
| **1** | **#959 (N) · #949 (M)** | Shell-Hook gegen Python/CI: datei-disjunkt **und** getrennte Verifikations-Bäume (Vitest gegen pytest). **Das echte Parallel-Paar.** |
| **2** | **#632 (A)** | Allein im Web-Stack — kollidiert mit N über den Vitest-Baum, deshalb **nach** Welle 1. |
| **3** | **#849 (C)**, danach **#923 + `audit`-Trennung (D)** | Beide schreiben `ci.yml`; sequenziell, und erst nach dem Merge von #947. **#923 gehört IN D, nicht daneben.** |
| **4** | **#633 (B)** | Nach #632, allein, braucht Docker. |

Weitere Wellen, alle an einer Weiche: **O** (#975, `vite.config.ts` + bis zu 20
Testdateien + Wächter) · **P** 🆕 (Weiche 16 — `CLAUDE.md`, eine Zeile) ·
**E** (Caddy) · **F** (7 Lint-Warnungen) · **G** (Coverage-Boden +
`__dirname`) · **H** (Branch-Updates und Merges) · **I** (Valkey-Rest) ·
**J** (MB/MiB) · **K** (Versionsversatz) · **L** (Vitest-5-Typ-Augmentation).

**Keine Welle:** C gegen D gegen E (dieselbe `ci.yml`) · **O gegen G**
(dieselbe `vite.config.ts` — ein PR für alle drei Posten) · F, G, K, L, **N**, O
gegen A oder B (derselbe Vitest-Baum) · B vor A (harte Abhängigkeit) ·
**M gegen P gegen I** (ein pytest-Baum) · #540 gegen alles · #823 gegen die
Protokoll-Merges.

## Was offen zurückgeht

**Vierzehn Weichen**, eine davon neu. Die dreizehn bestehenden werden nicht
erneut gestellt (Regel 9) — in #442 steht je Weiche nur, was sich an ihrem Stand
geändert hat.

- 🆕 **Weiche 16 — #977 ist rot an seinem eigenen Wächter.** Drei Optionen:
  **A** der Owner nimmt die Zahl aus `CLAUDE.md:98` (eine Zeile, PR wird von
  allein grün, Prämisse intakt) · **B** der PR ändert `CLAUDE.md` selbst (sofort
  grün, widerlegt aber im eigenen Diff seine Begründung) · **C** #977 schließen
  und `CLAUDE.md` in `_DOC_CLAIMS` lassen (Status quo, Preis bleibt eine
  Owner-Rückfrage je Werkzeugfamilie — genau das, wogegen der PR geschrieben
  wurde). **Empfehlung: A.**
- **Weiche 14 (#975)** — Optionen und Empfehlung **C** stehen unverändert im
  Body; nur die Zahl ist korrigiert (44 statt 43).
- **Weiche 15 (Valkey)** — unverändert gemessen: kein Ignore-Eintrag in
  `dependabot.yml`, `_VALKEY_PIN` weiter Major 8 hart.
- **Weichen 1, 2, 4, 5, 6, 7, 8, 9, 10, 11, 12** sowie **#540** und **#542** —
  Stand in #442 nachgezogen, keine neu gestellt.

**Zwei Fristen laufen:** die OSV-Ausnahme am **2026-11-02** (17 Tage) und der
Protokoll-Rückstand, der mit diesem Lauf auf zwölf wächst.

## Was der Lauf nicht tut

Kein Code an einem der Issues, kein Branch für ein Paket, kein Issue-Claim,
**keine neuen Issues** (das wäre „GitHub-Artefakt anlegen & pflegen" und braucht
bei #977 erst die Owner-Antwort), kein Zuschnitt, kein Kommentar in einem
fremden PR, kein Merge und kein Branch-Update. #454, #338 und #542 tragen
`human-only` — der Lauf endet dort.

## Ergebnis

Ausgeführt am 2026-10-16. **Gegen-Read über `list_issues` (Feld `body`) für alle
acht geschriebenen Bodies**: nichts abgeschnitten, jeder endet an seiner letzten
inhaltlichen Zeile, **25 von 25 Inhaltsproben grün** (Regel 114 b / 117 — Inhalt
geprüft, nicht Länge allein).

| Issue | Vorher | Nachher |
|---|---|---|
| #975 | 43 axe-Stellen, Lauf-51-Kopf | **44** Stellen + Zählmethode, Lauf-52-Kopf · bleibt `needs-decision` |
| #959 | Lauf-51-Kopf | Regel-120-Messung + Bedingungs-Befund, Basiswerte |
| #949 | 3 verrottete Zahlen, 2 widersprüchliche PR-Zahlen | alle fünf korrigiert |
| #923 | Lauf-51- + Lauf-50-Kopf | ein Kopf, #947 **17** hinter, Basiswerte |
| #849 | Lauf-51- + Lauf-50-Kopf | ein Kopf, n = 1 benannt, Schwankungs-Argument |
| #632 | „Position 1" (Widerspruch zu #442) | **Position 2**, OSV 17 Tage, Flächen-Bewegung |
| #633 | 1560 Commits, 43 axe, OSV 18/20 | **1561**, **44**, **17 Tage** |
| #435 | `enhancement` `web` `size/M` | **+ `epic`** (Kommentar mit Beleg) |
| #442 | Lauf-51-Stand, 13 Weichen, 122 Regeln | Lauf-52-Stand, **14** Weichen, Regeln **123/124**, Wellen N/M/A/C/D/B + **P** |

**Regeln 40–122 sind dabei nach Regel 10 auf ihren tragenden Satz gekürzt**
(Langfassungen in der Bearbeitungs-Historie von #442) — das hat den Body von
~85 000 auf **78 125** Zeichen gebracht und senkt das Risiko aus Regel 114.

**Noch nicht im Body von #442: Regel 125** (der Schreibweg entfernt die
Attributions-Fußzeile) — sie ist nach dessen Schreibvorgang entstanden und steht
als Kommentar mit Pointer auf diese Datei. **Der nächste Lauf trägt sie nach.**
