# Backlog-Aufbereitungslauf 91

**Datum:** 2026-11-24
**Messpunkt:** `main` @ `78352c7` (`deps(security): dnspython 2.9.2, opentelemetry-api 1.45.2, soupsieve 4.1.3`, #1159)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 90.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — dreiundzwanzigster Lauf in Folge.**
Der Server verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann; ein
erneuter Verbindungsversuch über den Server-Namen wurde abgelehnt. Persona und
Playbook-Katalog lagen im System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"), `record_usage`,
`submit_feedback` und `search_memory`/`save_memory` nicht. Der Lauf fuhr nach dem Body von #442
und `.github/PROJECT.md` §Constraints. **Kein Playbook-Trigger ladbar, keine
Kurations-Rückmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-24 auf `main` @ `78352c7` erhoben, sequenziell, Node **v22.23.5**,
npm **10.9.9**, uv **0.11.32**, CPython **3.11.18**, **ohne vorherige Reparatur** (Regel 120),
**Exit-Codes am unverketteten Befehl** (Regel 36/94/172). Klon war shallow (50) → **1678**
Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests |
| `changelog_fragments.py check` | **Exit 0**, **406** Fragmente; `ls` **407** (Differenz `README.md`) |
| `pip-audit` am vollen Export | 🟢 **Exit 0**, **126** Requirements bei **400** Zeilen |
| Positiv-Kontrolle `soupsieve==2.10` ohne Marker | 🔴 **Exit 1, 3 CVEs** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** |
| `npm audit` (voll) | ⚠️ **Exit 1**, **27 moderate, 0 high** |
| `npx playwright test --list --project=chromium` | **44 Tests in 9 Dateien** |
| `payload_report` | Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** — 25. identische Messung |
| `test_tool_payload_budget.py` | **Exit 0**, 64 passed |
| `npm run test:coverage` | ⚪ nicht gefahren, mit Grund (Fenster 0 Commits; `web`-Job am selben Kopf grün) |
| `main`-CI am Kopf | Lauf **`45060144554`**, **14 Jobs, 14× success**, an der Job-Liste addiert |
| `docker info` | 🔴 **Exit 1** — **65. Messung in Folge** |

## PR-Bestand

**20 offene PRs** (waren 19). Scope je PR über `git merge-base` + `git diff --name-only`,
Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über `git rev-list --count`,
Checks über die Check-Runs am Head mit namentlichem Filter.

- 🟢 **Alle 20 mergen konfliktfrei**, keiner bewegt 0 Dateien.
- **Differenz erklärt:** **−4** (#1127, #1134, #1147, #1149) **+5** (#1161–#1165).
- **Rückstand:** 0 → sechs · 1 → vier · 2 → neun · 17 → #1105.
- **Rot-Bilanz, je PR gegen das Grün von `main` (2026-11-22T19:20) datiert:** 6 ohne Rot,
  **2 eigen-rot** (#1164, #1162), **12 mit geerbtem `audit`+`all-green`-Rot**.
- Einzige Datei-Kollision unter den 20: `docker-compose.cloud.yml` (#1165 und #1132).

## Die vier Funde des Laufs

### 1. 🔴 Ein Zähler ohne Akteur hat vier Weichen-Antworten getragen

Lauf 90 hat „2 gemergt, **35 ohne Merge geschlossen**" gemessen, die Zahl dem Owner
zugeschrieben und daraus vier Weichen als „durch Handlung beantwortet" gelesen. Dieser Lauf hat
die vier Abgänge seines Fensters **je PR mit Akteur** gemessen:

| PR | geschlossen | von | Begründung |
|---|---|---|---|
| #1127 | 2026-11-23T05:16:05Z | `dependabot[bot]` | „updatable in another way" |
| #1147 | 2026-11-23T05:17:30Z | `dependabot[bot]` | „updatable in another way" |
| #1149 | 2026-11-23T05:29:28Z | `dependabot[bot]` | „updatable in another way" |
| #1134 | 2026-11-23T05:29:33Z | `dependabot[bot]` | **„Superseded by #1165."** |

**Keiner ist eine Owner-Handlung.** Welcher Anteil der 35 Schließungen des 2026-11-22 vom Owner
kam, ist nicht gemessen — und genau darauf ruht die Empfehlung der Weiche 68. → **Regel 87**.

### 2. 🔴 Zwei eigen-rote PRs, beide mit einzeiliger Ursache

**Zum ersten Mal seit Welle 0 ist ein Rot nicht geerbt.** Beide `completed_at` liegen **nach**
dem Grün von `main` (Regel 79).

**#1164** (`web-minor-patch`, 19 Updates, Nachfolger von #1147) — `python`-Job, Schritt 12:

```
FAILED packages/models/tests/test_blocknote_markdown_golden.py::test_blocknote_version_matches_lockfile
        AssertionError: assert '0.57.0' == '0.56.0'
1 failed, 5033 passed
```

Der Test liest `apps/web/package-lock.json` und vergleicht gegen
`BLOCKNOTE_VERSION = "0.56.0"` (`packages/models/src/who2be_models/blocknote_markdown.py:58`).
Sein Kommentar nennt den Zweck selbst (ADR-0058 §3.3): „Ein Update reisst hier, bis jemand
REPRESENTABLE/NON_REPRESENTABLE_BLOCK_TYPES neu geprueft hat." 🔴 **Ein Gruppen-PR, der
`@blocknote/*` mitnimmt, kann deshalb grundsätzlich nicht von allein grün werden** — und
`@blocknote/*` steht in keiner `ignore`-Liste, während React und Mantine dort genau aus diesem
Grund stehen (`.github/dependabot.yml:76-87`). → **Weiche 69**.

**#1162** (`python:3.14-slim` → `3.15-slim`) — sieben rote Checks, `compose-smoke` Schritt 5:

```
Caused by: Failed to download and build `httptools==0.8.0`
  build/lib.linux-x86_64-cpython-315/...
  error: command 'gcc' failed: No such file or directory
process "/bin/sh -c uv sync --frozen" exit code: 2     (Ziele api UND mcp)
```

An PyPI gemessen: **`httptools 0.8.0`** (`uv.lock:1040`) liefert cp39–cp314, **kein cp315**;
**`0.9.0` liefert cp315**. 🔴 **Der Versuch kehrt zurück:** #1146 trug denselben Bump, wurde am
2026-11-22T19:11 geschlossen, dependabot hat ihn **18 Stunden später** als #1162 erneut
eröffnet — die Gruppe `docker-images` hört auf `minor`+`patch` (`dependabot.yml:199-202`).
→ **Weiche 70**.

### 3. 🔴 Die Fläche einer Weichen-Antwort war zu klein gemessen

Lauf 90 führt Option A der Weiche 67 als „fünf `pyproject.toml` (je `:5`) + `uv lock`. Fläche
**frei**". Gemessen: `uv lock` schreibt `uv.lock`, und `uv.lock` hält **#1148** — einziger
Träger, **0** hinter `main`, grün, mergebar. **Die Antwort ist nicht „fünf Zeilen", sondern
„#1148 mergen, dann fünf Zeilen".** Gegengeprüft, ob #1148 die Arbeit miterledigt:
`git show refs/pr/1148:uv.lock` → `:2719` **2.10**, `:2732` **4.1.3** — zwei Blöcke wie auf
`main`. **Derselbe Engpass trifft Weiche 70** (der `httptools`-Fix liegt ebenfalls im Lock).
→ **Regel 88**.

### 4. 🔴 Vier Paket-Bodies hielten Flächen für frei, die es nicht mehr sind

Keine verrotteten Zahlen, sondern **Freigaben** — eine falsche Freigabe schickt einen Agenten
in eine belegte Datei (Regel 63a).

| Behauptung | gemessen |
|---|---|
| „`ci.yml` ist FREI" (#632, #633, #989) | **#1163** hält `ci.yml` + `deploy.yml` — 🟢 **ohne Zeilenverschiebung** (3 Ein-Zeilen-Hunks, 1259 Zeilen vorher und nachher) |
| „`src/api/**` FREI" (#633) | **#1157** schreibt `client.ts`, `client.contract.test.ts`, `types.ts` |
| „`apps/mcp/**` Treffer 0" (#1001) | **#1160** (`server.py`, `tools/content.py`), **#1162** (Dockerfile); die drei Hebel bleiben frei, aber #1160 verschiebt die Draht-Größe 108.251 |
| „#1147 lebender Halter" (#632, #633, #989) | geschlossen; Halter ist **#1164** — und der ist eigen-rot |
| „Compose: #1132–#1136 plus #1149" (#633) | #1134/#1149 zu; Träger sind #1132, #1133, #1135, #1136, **#1165** |

## Selbstfunde

- ⚠️ **Diese Liste hat einen Pfad geprüft, den es nicht gibt:** `orphan-baseline.json` statt
  `apps/web/src/i18n/orphan-baseline.json`. Das Urteil (frei) hält am vollen Pfad, **die
  Messung war keine** — Regel 34/66 sagt genau das über den selbst getippten Pfad. Die Bodies
  von #632/#633 schreiben ihn vollständig; der Fehler gehört allein #442.
- ⚠️ **Fünf Pfade der heutigen PR-Datei-Liste existieren im Arbeitsbaum nicht** (Plan-Dateien,
  die erst die PRs anlegen). Die Existenzprüfung gehört an den Baum, **gegen den** gemessen
  wird. → Zusatz zu **Regel 88**.
- 🔴 **Lauf 90 hat die Norm von #535 und #428 um einen Punkt zu gut bewertet** — beide sind
  **1/4**, nicht 2/4: neben Outcome und Verifikation fehlt auch jedes Kriterium mit Schwelle.
- 🔴 **Lauf 90s ADR-Zeiger waren falsch** (als „übernommen" gekennzeichnet, also offengelegt):
  ADR-0061 führt W61-1 auf `:292`, W61-2 auf `:219`, W61-3 auf `:238` — nicht `:377`/`:390`.

## Norm-Stand über alle 13 offenen Issues

Die vier Pflichtabschnitte stehen **vollständig in jedem `agent-ready`-Issue** und in #1150 und
#540. Für die sechs nicht aufgreifbaren wurde nach **Weiche 57 A** nur Abschnitts-Vollständigkeit
und falsche Aussagen geprüft — das hat zwei echte Funde gebracht (OSV-Frist `2026-11-02` in
#428 **und** #435, gemessen `2026-11-30`; vier geschlossene PRs als lebende Sperren in #435)
und keinen Zeiger-Friedhof.

| Urteil | Issues |
|---|---|
| **4/4** | #1001, #632, #633, #989, #1150, #540 (formal), #454 (formal), #435 (formal) |
| **2/4** | #542 (Outcome fehlt — und die Frage ist entschieden, Weiche 63) |
| **1/4** | #535, #428 (Outcome und Verifikation fehlen, kein AK mit Schwelle) |
| **0/4** | #338 (Checkliste O1–O4) |

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines entzogen.**
⚠️ **#989 trägt beides** (`agent-ready` + `needs-decision`) und sagt im Body „ohne diese Antwort
nicht starten" — der Widerspruch ist im Body benannt, die Labels sind nicht angefasst (Owner).

## Was dieser Lauf selbst erledigt hat

**Vier Bodies im Body korrigiert, alle über MCP, je ein eigener Schreiber mit dem Originaltext
vor sich, jeder maschinell gegengelesen** (Regel 78):

| Issue | Zeichen vorher → nachher | Gegenlese |
|---|---|---|
| **#1001** | 21.725 → **23.665** | 🟢 **`equal True`** |
| **#989** | 29.212 → **30.764** | 🟢 zeichengleich bis auf **ein** `\n` (Server-Normalisierung) |
| **#632** | 39.588 → **41.497** (zwei Schriebe) | 🟢 zeichengleich bis zur Fußzeile |
| **#633** | 42.314 → **43.842** | 🟢 zeichengleich bis zur Fußzeile |

🟢 **Der Eigenfehler von Lauf 90 ist nicht wiederholt worden.** Vier von vier Schreibern haben
die Grenze gehalten; der Unterschied zum Vorlauf liegt im Auftrag: der erlaubte Weg stand **vor**
jeder Optimierung, mit dem ausdrücklichen Satz, dass bei Kollision die Optimierung weicht
(Regel 86). 🔴 **Der Preis: #632 und #633 haben ihre Attributions-Fußzeile verloren** (je 1 → 0)
— Regel 169, jetzt sechsfach belegt. 🟢 **Ein Schreiber hat eine Lücke in der Korrekturliste
gefunden** (#632 trug `ci.yml ist frei` auch in §Verweise) und sie nach Rückfrage im selben Body
geschlossen (Regel 153).

**Vier Kommentare** für das, was ein Agent nicht aufgreifen kann:

- **#1150** — Weiche 67 mit gemessener Reihenfolge (#1148 zuerst), AK1–AK5 einzeln,
  Positiv-Kontrolle, 9 widerlegte Aussagen, der Nachbarbefund #1162/`httptools`.
- **#540** — alle sieben Kriterien einzeln (4 erfüllt, K4 am abweichenden Ort, K2 teilweise,
  K1 blockiert), **4 falsche Kästchen**, 3 widerlegte Aussagen, 16 nachgemessene Zeiger,
  `ci.yml` jetzt von #1163 gehalten, **#1165 verschiebt den zitierten Caddy-Pin**.
- **#428** — OSV-Frist `2026-11-02` gegen gemessene `2026-11-30`, ADR-0061 `Accepted` gegen den
  Out-of-Scope-Verweis, Kinderstand 8/7, Norm 1/4.
- **#435** — vier geschlossene PRs als lebende Sperren, `ci.yml` 1212 → 1259, OSV-Frist,
  W1 belegt (GoTrue v2.197.0 dreifach), #1164 eigen-rot.

**Nicht angefasst, mit Grund:** #535, #454, #542, #338 — gegenüber den Kommentaren von Lauf
89/90 nichts Neues gemessen. 🔴 **Dritter Lauf in Folge; nach Regel 62 ist das eine
Entscheidung, keine Lücke** und gehört zu Weiche 57.

**#442** neu geschrieben: Reihenfolge, Wellen, Sperr-Tabelle, Norm-Tabelle, Funde, Weichen-Delta
(alle 44 bestehenden Nummern im Wortlaut erhalten), Regeln 1–88.

## Reihenfolge — unverändert, und das ist das Ergebnis

Im Fenster ist kein Issue geschlossen, keines neu, keine Weiche beantwortet, keine Fläche
bewegt. **Es gibt nichts, was eine Position verschieben könnte** — vierter Lauf in Folge.

| Pos | Issue | Kriterium | Zustand |
|---|---|---|---|
| 1 | **#1001** Payload-Budget | 4 (Inventar vor Zuschnitt) | startbar, einziges ohne Owner-Antwort. ⚠️ **#1160 vorher lesen** |
| 2 | **#632** Passkey registrieren | 3 (Fundament vor Fläche) | **Weiche 59** |
| 3 | **#633** Step-up mit Passkey | 1 (harte Abhängigkeit) | nach #632; CI-Weg offen |
| 4 | **#989** `http-cache-semantics` | 5 | Weiche 48 → #1124 → Fläche |

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | #1001 allein | Python/pytest; Hebel frei. #1160 verschiebt die Draht-Größe |
| **A2** | #632 | nach Weiche 59; danach echt parallel zu A |
| **B** | #633 | nach #632 |
| **C** | #989 | Weiche 48 → #1124 → Fläche |
| **M0** _(Owner)_ | **#1148** | ein Klick; **löst Weiche 67 UND 70 auf** |
| **M1** _(Owner)_ | **#1160** | 18/18 grün nach dem Grün von `main`; **vor #1001** |
| **M** _(Owner, Frist 6 Tage)_ | #1124 → #1129 → #1130; **#1164 erst nach Weiche 69** | Branch-Update von #1124 zuerst |
| **M2** | #1122 | Betreiber-Host (Weiche 39) |
| **M3** | #1163 (grün) · #1162 (**nach M0**) | beide allein |
| **M4** | #1165 gegen #1132 seriell; #1133/#1135/#1136 unabhängig | Caddy-Pin wandert auf 2.11.9 |
| **R** | #1157, #1158 | Rot geerbt → Branch-Update; nach #1160 das Drift-Gate neu lesen |
| **N** | #1161, #1156, #1152, #1105 | Weiche 68 |
| **W67 / W69 / W70** | je ein kleines Paket | W67 und W70 nach M0 |

🟢 **Lückenprüfung (Regel 77):** 1+1+4+1+2+5+2+4 = **20** von **20**.

## Neue Regeln

- **87 — Ein Zähler ohne Akteur ist keine Messung einer Handlung.** Messweg: je PR den Akteur
  der `closed`-Zeile und den letzten Kommentar lesen, nicht nur `state`/`merged`/`closed_at`.
- **88 — Die Fläche einer Antwort umfasst jede Datei, die ihr Befehl schreibt.** Plus Zusatz:
  die Existenzprüfung gehört an den Baum, gegen den gemessen wird.

## Offen an den Owner

**37 Weichen** (47 Inhaltszeilen, Zählweise in #442), zwei neu. Die vier mit dem größten Hebel:

1. **M0/#1148 mergen** — ein Klick, und zwei offene Weichen (67, 70) bekommen ihre Fläche frei.
2. **Weiche 69 (neu)** — `@blocknote/*` in die `ignore`-Liste wie React/Mantine. Empfehlung **A**.
3. **Weiche 70 (neu)** — `httptools` auf 0.9.0; danach geht #1162 von allein grün. Empfehlung **A**.
4. **Weiche 46** — #1124, Frist **2026-11-30**, in 6 Tagen. Branch-Update zuerst.

## Belege dieses Laufs

- Queue-Issue: #442 (Body neu geschrieben, maschinell gegengelesen)
- Im Body korrigiert: #1001, #989, #632, #633
- Kommentiert: #1150, #540, #428, #435
- Nicht angefasst, mit Begründung: #535, #454, #542, #338, #442-Weichenzeilen (Wortlaut erhalten)
