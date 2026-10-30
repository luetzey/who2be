# Backlog-Aufbereitungslauf 66 — 2026-10-30

**Gegen `main` @ `14234887`** (`1423488782c0bcb5f11e584b88cb7775f88225ee`).
Fenster seit dem Messpunkt von Lauf 65: **0 Commits** — der Baum ist bitgleich
mit dem von Lauf 64 **und** 65, also der **dritte** Lauf am identischen Baum.
**0 PRs gemergt, 0 Pakete gestartet, 0 Issues geschlossen, 0 Weichen
beantwortet.**

Ergebnis in #442 (Warteschlange, Body ersetzt) und als Kommentar dort
(Weiche 38). Diese Datei ist das Protokoll, nicht die Reihenfolge.

## Funde

### 1. Lauf 65 hat seine eigene Korrektur nur halb ausgefuehrt (Regel 153)

Lauf 65 hat als Fund 2 aufgeschrieben, dass #632 und #633 eine Anweisung
trugen, die `main` rot macht („einen neuen axe-Fall nur mit explizitem
Timeout"). Er hat in beiden Bodies **§Zusaetzliche Grenzen** korrigiert — und
in #632 dieselbe falsche Anweisung an **drei weiteren** Stellen stehen
gelassen: im datierten Kopf-Zitatblock, in **§Eskalation** und in
**§Verweise**. In #633 stand sie weiter im Kopf-Zitatblock.

Danach sagte #632 an einer Stelle das Richtige und an drei Stellen das
Falsche. **§Eskalation ist der Abschnitt, den ein Agent liest, wenn ein Test
kippt** — also genau der Pfad, auf dem die falsche Fassung gewinnt. Ein Body,
der beides sagt, ist schlechter als einer, der einheitlich falsch ist.

**Behoben:** alle vier Stellen in #632, alle vier in #633. Beide
Kopf-Zitatbloecke tragen jetzt einen `HISTORISCHER KOPFBLOCK — NICHT
befolgen`-Marker, der die veralteten Werte einzeln benennt.

### 2. Das Datum, mit dem Lauf 65 den Fund belegt hat, war falsch (Regel 154)

Lauf 65 datiert den Schliess-Zeitpunkt von #975 auf den **2026-10-28** und
schreibt das in beide Bodies und in #442. Gemessen:

- `gh api repos/luetzey/who2be/issues/975 -q .closed_at` → **`2026-10-20T05:06:03Z`**
- `git log --follow -- apps/web/src/test/a11y.test.ts` → **`56a3fc4f`,
  2026-10-20**, „fix(web): axe-Test-Timeout zentral im a11y-Helfer statt nur
  per Glob (#975) (#987)"

**Acht Tage Differenz.** Die Anweisung war nicht einen Tag falsch, sondern
**neun**. Die „zehn Tage" aus Lauf 65 waren zufaellig fast richtig, ihr Datum
nicht. Ein Fund ueber verrottete Referenzen, der sein eigenes Datum nicht
nachmisst, belegt sich nicht.

### 3. Zwei rote PRs sind durch die Zaehlung gefallen, einer sitzt an der Engstelle

Lauf 65 nennt „drei rot" (#674, #1100, #1080). Gemessen am 2026-10-30 ueber
alle 24 offenen PRs (`check-runs` am Head, positiv auf
`failure`/`timed_out` gefiltert): **fuenf**.

| PR | rote Checks | rot seit | Rueckstand |
|---|---|---|---|
| #674 | 8 (`web`, `e2e`, `e2e-mobile`x3, `compose-smoke`, `e2e-billing-cloud`, `all-green`) | 2026-10-26 | 4 |
| #1100 | `audit`, `all-green` | 2026-10-27 | 1 |
| #1080 | `audit`, `all-green` | 2026-10-24 | 18 |
| **#1078** | `audit`, `all-green` | **2026-10-24** | 18 |
| **#831** | `audit`, `all-green` | **2026-10-06** | 222 |

Beide neuen waren zu Lauf 65 schon rot — sie sind nicht neu rot geworden, sie
sind nicht gezaehlt worden. **#1078 ist einer der drei `STATE.md`-Traeger:**
die Schreibsperre auf der Datei, die jedes Paket laut DoD anfasst, ist nicht
„drei Merges", sondern **zwei Merges und ein Branch-Update**.

### 4. Aufbereitungslauf 63 hat kein Protokoll hinterlassen (Weiche 38)

Kein PR mit dem Titel (offen und geschlossen geprueft), kein Commit auf
irgendeiner Ref (`git log --all`). Das erklaert, was Lauf 65 offenlassen
musste („fuer das Paar 63 ↔ 64 bleibt es unentscheidbar"): es fehlten nicht
die Absolutzahlen, es fehlt **der ganze Lauf**.

Dazu der Rahmen: **der letzte gemergte Protokoll-PR ist #983 (Lauf 55),
gemergt am 2026-10-20.** Auf `main` liegen 15 Protokoll-Dateien, die juengste
ist `2026-10-19-0030_backlog-aufbereitungslauf-55.md`. Seit zehn Tagen
erreicht kein Protokoll mehr `main`; zehn liegen offen, drei halten
`STATE.md`, eines fehlt ganz.

### 5. Die falsche Praemisse stand mit einer selbst falschen Begruendung im Repo (Regel 155)

Lauf 65 hat gezeigt, dass die Frist `ignoreUntil = 2026-11-02` ein
Nicht-Ereignis ist. Dieser Lauf hat gefunden, **warum neun Laeufe sie als
Owner-Vorgabe gelesen haben**: `apps/web/osv-scanner.toml:5-7` behauptet
wortwoertlich „*No entry without an expiry date; when it expires the scan
turns red again and the finding has to be re-evaluated with current data.*"

**Der Nachsatz beschreibt `osv-scanner` falsch.** Ein abgelaufener Ignore
hoert auf zu filtern, er erzeugt keinen Fund. Rot wird der Scan nur, wenn es
wieder einen Fund gibt. In #989 als Zusatz zu AK2 verdrahtet — die Datei steht
ohnehin im Scope und ist ueber alle 24 PRs frei.

### 6. Der Advisory-Rueckzug ist zweifach unabhaengig bestaetigt (Weiche 37)

Weiche 37 fordert fuer jede Tatsache ausserhalb des Repos einen benannten
Messweg und ein Messdatum. Eingeloest auf einem **vom Lauf 65 unabhaengigen**
Weg:

| Messweg | Ergebnis 2026-10-30 |
|---|---|
| `POST registry.npmjs.org/-/npm/v1/security/advisories/bulk` mit `{"http-cache-semantics":["4.2.0"]}` | **`{}`** |
| `npm audit` in `apps/web/` | **Exit 0, 0 vulnerabilities** |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** |
| `GET registry.npmjs.org/http-cache-semantics` | **`4.3.0` ist `dist-tags.latest`** |
| `apps/web/package-lock.json:6296` | weiter **`4.2.0`** |

### 7. Determinismus bei n = 3 — und die Laufzeit ist Rauschen

Dritter Lauf am bitgleichen Baum, **alle vier Coverage-Absolutpaare wieder
bitgleich** (13163/14642, 9179/10933, 3793/4369, 12049/13132), bei
**336,71 s** statt 282,28 s. **Zaehler sind belastbar, Laufzeiten nicht.**

## Gates (beide Baeume, Exit-Codes ohne Pipe, `npm` in `apps/web/`)

Node v22.22.0, Klon shallow (50) → 1661 Commits nach `--unshallow`.

| Gate | Ergebnis |
|---|---|
| `npm run test:coverage` | Exit 0, **282** Dateien / **2849** Tests, 336,71 s |
| Coverage | 89,89 / 83,95 / 86,81 / 91,75 |
| `npm run lint` | Exit 0, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe 0 Byte |
| `npm run i18n:check` | Exit 0, **156** bekannte Waisen; `de`/`en` je **3.365** Schluessel |
| `npm audit` (voll) | Exit 0, 0 vulnerabilities |
| `uv run ruff check .` | Exit 0 |
| `uv run mypy .` | Exit 0, **655** Dateien |
| `uv run pytest --collect-only -q` | **4971** Tests |
| `changelog_fragments.py check` | Exit 0 |
| `payload_report` | **103** / **108.251** Bytes, `instructions` 1.732 (siebte identische Messung) |
| `docker info` | **Exit 1** — keine Container-Laufzeit, kein `podman` (**42.** Messung in Folge) |

`main` @ `14234887`: 24 Check-Runs `success`, 1 `skipped` (`deploy`), 0 rot.

## Reihenfolge (Ergebnis)

1. **#632** Passkey registrieren — Kriterium 3 (Fundament vor Flaeche)
2. **#989** `http-cache-semantics` → 4.3.0 — Kriterium 5 (das kleinere)
3. **#633** Step-up mit Passkey — hart nach #632, plus Container-Laufzeit

Wartestand: **#1001** (Flaeche in PR #1101). Nicht in der Warteschlange:
#442, #428/#435/#535 (Tracking), #338/#454/#542 (`human-only`), #540
(`needs-decision` + Umgebung).

**Wellen:** A = #632 allein · B = #989 nach A · C = Merges (Klicks) ·
D = #633 nach A · E = #1001 nach dem Merge von #1101. **Zum dritten Lauf in
Folge kein Parallel-Paar** — A, B und D liegen alle im Vitest-Baum, und der
Python-Baum hat kein startbares Paket, solange #1101 offen ist.

## Geaenderte Artefakte

- **#442** — Body ersetzt (Warteschlange, Gates, Datei-Sperren, Norm-Pruefung
  mit neuer Gueltigkeits-Spalte, Wellen, 23 Weichen, Regel 153–155) plus
  Kommentar mit Weiche 38 (drei Optionen, Empfehlung C).
- **#632** — sieben Stellen korrigiert (axe-Regel in Kopfblock/§Eskalation/
  §Verweise, #975-Datum, #959/#949 als geschlossen, `ci.yml` 1212 → 1259,
  Coverage-Zeiger `:81-85` → `:100-103`), Kopfblock markiert.
- **#633** — vier Stellen korrigiert (axe-Regel im Kopfblock, #975-Datum,
  `STATE.md`-Traeger inkl. rotem #1078, Position von #632), Kopfblock
  markiert.
- **#989** — AK2 um die Kommentar-Korrektur erweitert, Nachtrag mit dem
  zweiten, unabhaengigen Messweg und der Wurzel-Begruendung.
- **`.github/PROJECT.md`** — §Reihenfolge auf Lauf 66 gebracht: #989 und
  #1001 ergaenzt, **#624** als geschlossen entfernt (es stand seit dem
  2026-09-29 falsch als „nicht starten" drin), GoTrue-Zeiger auf `v2.197.0`
  nachgemessen, in §Constraints **#402** und **#431** als geschlossen
  richtiggestellt und die Gueltigkeits-Regel ergaenzt.

Alle vier Issue-Bodies wurden per `gh api --input` geschrieben (Regel 144) und
mit `cmp` **byte-exakt** zurueckgelesen; die Attributions-Fusszeile steht in
jedem genau einmal.

## Bewusst nicht angefasst

**`.claude/context/STATE.md`.** Die DoD verlangt die Pflege dieser Datei, aber
sie wird von drei offenen Protokoll-PRs gehalten (#1103, #1090, #1078) — ein
vierter Traeger macht die Sperre schlimmer, nicht besser, und genau das ist
Fund 3 dieses Laufs. Der juengste Stand liegt in **#1103** (gruen, 0 Commits
hinter `main`, konfliktfrei); er ist der erste Merge, der die Sperre loest.
Siehe Weiche 18 und Weiche 38.
