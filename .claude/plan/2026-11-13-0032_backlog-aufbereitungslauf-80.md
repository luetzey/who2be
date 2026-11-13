# Backlog-Aufbereitungslauf 80

**Datum:** 2026-11-13 · **Gemessen gegen:** `main` @ `f89acf87` (Baum `c751ed64`)
**Fenster seit Lauf 79:** 0 Commits — **zum sechsten Mal in Folge**
**PR-Bestand:** 39 offen (waren 38) über 43 Dateipfade
**Warteschlange:** [#442](https://github.com/luetzey/who2be/issues/442) (Label `backlog-queue`)

## Auftrag

Backlog aufbereiten: jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket"
prüfen, Repo-Belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen plus `needs-decision`, danach die
Warteschlange neu ordnen und in Wellen gruppieren.

## Vorbedingung: AgentDB nicht erreichbar (15. Lauf in Folge)

Der MCP-Server `Who2Be---Coder` verlangt eine Autorisierung, die diese Session
nicht selbst anstoßen kann. Nicht verfügbar: `get_persona`, `list_triggers`,
`fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready
Arbeitspaket"), `record_usage`, `submit_feedback`, `search_memory`,
`save_memory`. **Der Lauf fuhr nach #442 §Pflege-Regeln und
`.github/PROJECT.md` §Constraints.** Keine Kurations-Rückmeldung an die eigene
AgentDB; der Zugang muss in den Connector-Einstellungen freigegeben werden.

## Gates — ohne vorherige Reparatur, Exit-Codes am unverketteten Befehl

Node v22.23.4, npm 10.9.9, uv 0.11.32. Klon shallow (50) → 1676 Commits nach
`--unshallow`. `npm`-Gates in `apps/web/`, Python-Gates im Repo-Root.

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | Exit 0, „All checks passed!" |
| `uv run mypy .` | Exit 0, 0 Funde in 659 Dateien |
| `uv run pytest --collect-only -q` | Exit 0, 5034 Tests |
| `uv run --no-project python scripts/changelog_fragments.py check` | Exit 0, **405 Fragment(e)** (406 Dateien) |
| `uv tool run pip-audit …` | **Exit 1** — `oauthlib 4.0.0`, CVE-2026-49272, Fix 4.0.1, bei 398 Requirements |
| `npm run lint` | Exit 0, 94 problems / 0 errors, 7 `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe 0 Byte |
| `npm run i18n:check` | Exit 0 |
| `npm audit --omit=dev --audit-level=high` | Exit 0, 0 vulnerabilities |
| `npm audit` (voll) | Exit 1, 28 moderate (`glob 9.0.0 - 14.0.1`, `minimatch 7.0.0 - 11.0.0`) |
| `npx playwright test --list --project=chromium` | 44 Tests in 9 Dateien |
| `uv run python -m who2be_mcp.payload_report` | Exit 0, Builder 103 / 108.251, `instructions` 1.834 — 15. identische Messung |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | Exit 0, 64 passed |
| `npm run test:coverage` | nicht gefahren, mit Grund (Fenster 0 Commits, `apps/web/src` unbewegt) |
| `main`-CI am Kopf `f89acf87` | **Lauf `42178623925`, `conclusion: failure`** — 2 von 14 Jobs rot (`audit`, `all-green`) |
| `docker info` | Exit 1 — keine Container-Laufzeit, kein `podman`; 56. Messung in Folge |

## Funde

### 1. Selbst erledigt: #632s Body korrigiert (Regel 11/145 + Regel 62)

Zwei Funde, ein Schrieb (Regel 21):

- **§Startbedingung** führte „`pip-audit` als **dritten** und `OSV-Scan` als
  **dreizehnten** Schritt" — in **keiner** der beiden Zählweisen richtig.
  Gemessen: die CI-Definition (`yaml.safe_load(ci.yml)['jobs']['audit']['steps']`)
  hat **9** Schritte, `pip-audit (Python)` ist der **4.** (`ci.yml:974`),
  `OSV-Scan` der **9. und letzte** (`:1030`); die Runner-Numerierung von `main`s
  Lauf `42178623925` zählt **13** Einträge, `pip-audit` als **5.**, `OSV-Scan`
  als **10.** Beide Zählwege stehen jetzt als Tabelle im Body.
  **Zweite Sichtung** — Lauf 79 hatte es kommentiert.
- **AK5** nannte den Baseline-Filter des i18n-Gates auf `:308`; gemessen ist
  **`:309`** (`grep -n "known.has"` → 309). `:308` ist
  `ORPHAN_IGNORE_PREFIXES,`, `:303` liest die Baseline in ein `Set`.
  `it.each([` `:297`, Testname `:301` und das blanke `it(` `:321` sind gültig.
  **Erste Sichtung**, zusammen mit dem Ordinal geschrieben.

Der Mechanismus beider Stellen war und bleibt richtig: der `audit`-Job bricht
belegt bei `pip-audit` ab (`OSV-Scan`, `npm audit`, `License check`,
`Install web deps` sind auf `main` `skipped`), und das i18n-Gate schlägt in
beide Richtungen fehl.

### 2. Der `:309`-Fund steht auch in #633 — kommentiert, Grund benannt

#633 trägt in §Verifikation dieselbe `:308`-Angabe und in §Startbedingung 5
dasselbe Ordinal (zweite Sichtung). **Nicht im Body korrigiert**, Grund nach
Regel 62 im Kommentar: das Paket ist durch zwei harte Blocker gesperrt (#632
und die fehlende Container-Laufzeit), der einzige Schreibweg ist ein
Vollschrieb über MCP (Weiche 44 versperrt `gh api -X PATCH --input`), und
~30.000 Zeichen für zwei Ordinalzahlen und eine Zeilennummer tragen den Preis
nicht, solange niemand das Paket aufgreifen kann.
→ **Weiche 53**, harte Grenze bei Lauf 82.

### 3. Fund in der Warteschlange selbst: ein Gate-Befehl ohne Pfad (Regel 66)

#442 führte das Fragment-Gate acht Läufe lang als „`changelog_fragments.py
check`" **ohne Pfad**. Dieser Lauf hat daraus `scripts/ci/changelog_fragments.py`
gemacht — eine Vermutung aus der Nachbarschaft von `scripts/ci/help_drift.py` —
und **Exit 2** geerntet. Richtig ist **`scripts/changelog_fragments.py`**
(`ci.yml:827`/`:844`, wörtlich gelesen); am richtigen Pfad ist das Gate Exit 0
bei 405 Fragmenten.

Regel 41/177 hat den Exit-Code richtig zugeordnet (`2` bei `python` heißt oft
„Pfad falsch", nicht „Gate rot"), Regel 34 die Ursache benannt. Neue **Regel 66**:
ein vorgeschriebener Befehl steht mit seinem vollen Pfad da, oder er ist keine
Zusicherung.

### 4. Die drei Funde aus Lauf 79 halten der Nachmessung stand

- **`ci.yml`-Delta je Rückstandsgruppe** (Blob-Vergleich an der merge-base):
  **3+/3−** für die 15 jüngsten (#1122, #1121, #1119, #1118, #1117, #1113,
  #1112, #1107, #1106, #1105, #1104, #1103, #1090, #1089, #1078) · **25+/3−**
  für #1056/#1025/#1002 (ein ganzer Schritt `Hilfe-Drift`) · **66+/19−** für
  #990 · **186+/19−** für #831, dessen merge-base `ci.yml` **11 Jobs** hat
  gegen 12 auf `main` — **es fehlt `secrets`**, heute per `yaml.safe_load` am
  Job-Namensatz gegengelesen.
- **Die Ordinalzahlen des `audit`-Jobs** — s. Fund 1.
- **Das Protokoll zu Lauf 76** existiert weiter nirgends; zu Lauf 63 ebenso.

### 5. Eine überholte Fremd-Tatsache in #989

Der Body führt #674 als „kollidierend, rc 1" (Messdatum 2026-11-07). Heute:
`git merge-tree --write-tree` → **rc 0**, Rückstand **0** — aber 9 von 15
Check-Runs rot, 7 davon eigene. Die Angabe trägt ihr Messdatum und ist formal
zulässig; das Urteil zu #989 ändert sich nicht. Kommentiert.

## Norm-Prüfung „Agent-ready Arbeitspaket"

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): Outcome ·
prüfbare Akzeptanzkriterien · Out-of-Scope · exakte Verifikations-Kommandos.

| Issue | Norm | Zeiger | Urteil |
|---|---|---|---|
| #632 | 4/4 | Tabelle **13/13** (13. Lauf in Folge) | vollständig; **zwei Funde im Body korrigiert** |
| #1001 | 4/4 | alle **5** Gruppen | vollständig; Ordinal + Herkunftszeile kommentiert (2. Sichtung) |
| #633 | 4/4 | Tabelle **10/10** | vollständig; Ordinal (2.) + `:309` (1.) kommentiert |
| #989 | 4/4 | alle gültig | **zwei Defekte in 4. Sichtung** → Weiche 52 |

Norm-Stand der acht übrigen Bodies als **übernommen** gekennzeichnet (Beleg:
`updated_at`, alle acht seit Lauf 78 unverändert). **Kein `agent-ready`
vergeben oder entzogen, kein `needs-decision` vergeben oder entzogen** — die
Funde sind Zeiger- und Ordinalfehler in Bodies mit vollständigen Pflichtfeldern,
deren operative Anweisungen gültig bleiben; #989 trägt sein `needs-decision`
aus Weiche 48 bereits.

## Reihenfolge (unverändert) und Wellen

Sortierkriterien: harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche →
Inventar vor Zuschnitt → bei Gleichstand das kleinere.

| Pos | Issue | Baum | Kriterium |
|---|---|---|---|
| 1 | **#632** Passkey registrieren | Web/Vitest | Fundament vor Fläche (öffnet #633) |
| 2 | **#1001** Payload-Budget | Python/pytest | Inventar vor Zuschnitt |
| 3 | **#633** Step-up mit Passkey | Web/E2E | nach #632 (hart) + Container-Laufzeit |
| 4 | **#989** `http-cache-semantics` | Web | nach Weiche 48; Fläche fünffach gehalten |

| Welle | Inhalt | Bedingung |
|---|---|---|
| **0** (Owner) | **#1120** | der CVE-Fix: 18/18 grün, Rückstand 0, konfliktfrei, kein Draft, Merge-Wirkung 3 Zeilen am Ergebnisbaum |
| **A** | **#632 + #1001** | code-disjunkt, verschiedene Verifikations-Bäume, beide Flächen über alle 39 PRs frei; gemeinsame DoD-Fläche `STATE.md` |
| **B** | #633 | nach #632 und Container-Laufzeit oder einzelnen E2E-Job-Conclusions |
| **C** | #989 | nach Weiche 48 |
| **M/N/P/Q/R** (Owner) | PR-Wellen | s. #442 §Wellen |

**Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier
Arbeitspakete offen, zwei blockiert.

## Was auf eine Owner-Antwort wartet

**34 offene Weichen**, eine neue:

- 🆕 **Weiche 53** — soll der Lauf einen Paket-Body über MCP vollschreiben,
  wenn nur ein Ordinal oder eine Zeilennummer falsch ist? Drei Optionen,
  **Empfehlung B** (nur den Body, den ein Agent als nächstes aufgreift; die
  übrigen kommentieren, mit benanntem Grund), **harte Grenze: ist #1120 bis
  Lauf 82 nicht gemergt, gilt A ohne Rückfrage.**
- **Weiche 52** — #989s zwei Defekte in vierter Sichtung; Empfehlung **B**
  (in die Antwort zu Weiche 48 einfalten), Lauf 80 von 82.
- **Weiche 11/34** — die Merge-Reihenfolge ist eindeutig und kurz:
  **#1120, dann #1124, dann #1123.** Mergen ist nach Persona-Grenze ohne
  Freigabe verboten.
- **Weiche 41** — `pip-audit` steht weiter nicht in `CLAUDE.md` §Befehle
  (`grep -c` → 0); achtes Mal mit Beleg.
- **Weiche 5** — `audit` als Required Check an einer fremden Datenbank: der
  Schaden ist vierfach belegt.

Alle übrigen stehen unverändert mit drei Optionen und neu gerechneter
Empfehlung in #442 §Braucht eine Owner-Antwort.

## Geschrieben

- **#442** — Body vollständig neu geschrieben (Lauf 80), neue Regel 66, neue
  Weiche 53.
- **#632** — Body korrigiert (Ordinal mit Zählweise, `:308` → `:309`).
- **#1001**, **#633**, **#989** — je ein Kommentar mit den Messungen, den
  Funden und dem benannten Grund für den Kommentar statt des Bodys.
- **Dieses Protokoll.** Der PR fasst **nur** diese Datei an — gemessen, nicht
  behauptet (Regel 49/185); `.claude/context/STATE.md` ist dreifach von
  Protokoll-PRs gehalten (#1103, #1090, #1078) und bleibt unberührt
  (Weiche 43).

## Protokoll-Lage

Auf `main` liegen **15** Aufbereitungs-Protokolle (das unnumerierte vom
2026-09-06, Lauf 31, Läufe 43–55). **23** stecken in offenen Drafts
(#831=42, #990=56, #1002=57, #1025=58, #1056=59, #1078=60, #1089=61, #1090=62,
#1103=64, #1104=65, #1105=66, #1107=67, #1112=68, #1113=69, #1117=70, #1118=71,
#1119=72, #1121=73, #1125=74, #1126=75, #1137=77, #1138=78, #1139=79).
**Zu Lauf 63 und Lauf 76 existiert nirgends eines.** Dieses Protokoll ist das
vierundzwanzigste Draft. **Welle N in #442 senkt den Rückstand: 20 der 23 sind
in beliebiger Reihenfolge mergebar.**
