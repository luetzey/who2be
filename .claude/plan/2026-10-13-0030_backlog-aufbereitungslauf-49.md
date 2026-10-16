# Backlog-Aufbereitungslauf 49 — 2026-10-13

- Status: **abgeschlossen** (Issue-Korrekturen + Umsortierung; kein Produktivcode)
- Auftrag: jedes offene Issue gegen die Norm *Agent-ready Arbeitspaket* prüfen,
  repo-belegbare Lücken selbst schließen und mit Beleg ins Issue schreiben,
  Urteilsfragen als Kommentar mit drei Optionen und Empfehlung vorlegen,
  danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren
- Basis: `main` @ `79a8e171` — **0 Commits seit der Lauf-48-Basis**
- Vorgänger: Lauf 48 (`2026-10-12-0030_backlog-aufbereitungslauf-48.md`, PR #945,
  offen als Draft)

## 1. Befund in einem Satz

**`main` hat sich seit Lauf 48 nicht bewegt — und genau das macht den Lauf
aussagekräftig:** jeder Repo-Messwert ist byte-identisch, und trotzdem waren
**vier Sätze in zwei `agent-ready`-Issues falsch**, **zwei Zahlen verrottet** und
**zwei Begründungen aus Lauf 48 auf Prämissen gebaut, die nicht mehr gelten**.
Ursache ist in allen Fällen dasselbe: **vier neue PRs (#945–#948), die drei als
frei gemeldete Sammelpunkte wieder belegt haben, ohne dass jemand Code
geschrieben hat.**

## 2. Methode

Kein Playbook ladbar — der MCP-Server `Who2Be---Coder` liefert über `ToolSearch`
keine Werkzeuge (**vierter Lauf in Folge**). Persona und Playbook-Katalog lagen
im System-Prompt vor, `fetch_playbook`/`fetch_resource` (die Norm selbst,
`73a86231`), `search_memory`/`save_memory` und `record_usage`/`submit_feedback`
nicht. Der Lauf ist nach dem in #442 kodifizierten Verfahren gefahren.

Messung sequenziell, ein Schreiber je Baum (Web und Python sind verschiedene
Stacks und liefen nebeneinander). Vier right-sized Sub-Agents (Sonnet — reine
Mess- und Abgleicharbeit gegen eine feste Rubrik bzw. belegte Text-Ersetzung,
keine Design-Entscheidung; das rechtfertigt das kleinere Modell), dazu zwei für
die Schreibvorgänge. **Die Rückläufe sind nicht ungeprüft übernommen worden** —
zwei Zahlen waren falsch und sind selbst nachgemessen (siehe §4).

## 3. Selbst erledigt

### 3.1 Vier falsche Tatsachenbehauptungen in #849 und #923

Beide Issues behaupteten, `.github/workflows/ci.yml` sei „von **keinem** der
**14** offenen PRs belegt" — je zweimal, im Kopfblock und unter
§Zusätzliche Grenzen. **Seit dem 2026-10-12 hält PR #947 die Datei**
(dependabot, Gruppe `actions-all`). Das ist die Adresse von **#849 UND #923 UND
Welle D UND Welle E**, also der Startbedingung von Position 1 und 3.

Korrigiert — und zugleich entschärft, weil gemessen:

```
git diff --stat <merge-base> pr/947 -- .github/workflows/ci.yml
 .github/workflows/ci.yml | 30 +++++++++++++++---------------
 1 file changed, 15 insertions(+), 15 deletions(-)
```

**Netto null Zeilen**, reiner SHA-Tausch an drei Actions (`astral-sh/setup-uv`
v10.2.0 → v10.3.0, `actions/upload-artifact`, `actions/setup-node`).
**Kein `ci.yml`-Zeiger verschiebt sich, die 1212 Zeilen bleiben.**

Die engste Stelle ist nachgerechnet statt geschätzt: #947 ändert `:923`, der
Einfügepunkt von #849 im Job `audit` liegt hinter `runs-on:` auf `:919` — vier
Zeilen Abstand, zwei unveränderte dazwischen. Zweitengste Stelle: Job `web`
(`runs-on:` `:229` gegen `:235`). Job-Köpfe und `runs-on:`-Zeilen über
`yaml.safe_load` gezählt, nicht über `grep`.

### 3.2 Zwei verrottete Zahlen in #632 und #633

- **Die OSV-Frist.** „Restlaufzeit 21 Tage" war am 2026-10-13 **20**. Sie steht
  ab jetzt als **Datum** (`ignoreUntil = 2026-11-02T00:00:00Z`,
  `apps/web/osv-scanner.toml:11`), die Tageszahl nur als Zusatz mit Messdatum.
  **In einem Lauf, in dem `main` 0 Commits gelaufen ist und jeder Repo-Wert
  byte-identisch blieb, war das der einzige verrottete Wert im Bestand** — und
  Regel 106 fängt ihn nicht, weil sie gegen den Arbeitsbaum prüft und dieser
  Wert dort nicht steht. → **Regel 110.**
- **Eine falsch bezeichnete Zählmethode.** Beide Bodies leiteten die E2E-Körper
  aus zwei verschiedenen `grep`-Methoden in einer Rechnung ab:

  ```
  grep -cE '^\s*test\(' e2e/scroll-guard.spec.ts   -> 14
  grep -c   'test('     e2e/scroll-guard.spec.ts   -> 15
  e2e/scroll-guard.spec.ts:665:    if (!expectedName.test(probe.name ?? '')) {
  ```

  Die lose Zählung zählt einen **Regex-Aufruf** mit. Verankert sind es über acht
  Specs **34** Zeilen (2/2/6/3/4/2/14/1); die Schleife auf `:236` expandiert
  `:237` zu zwei Körpern → **35**. **Die Zusammensetzung „12 von 15" stimmt
  (14 Zeilen + 1 Expansion = 15 Körper), die Bezeichnung „15 Treffer" war
  falsch.** Korrigiert, beide Methoden im Body benannt.

### 3.3 Der Nachtrag an #435, den Lauf 48 offen gelassen hat

Lauf 48 hat die Korrekturen gemessen und ausdrücklich nicht geschrieben.
Nachgetragen: `auth-js` **2.117.3** und Pin `^2.117.3`, Fragmente **304**,
Collection **3526** (135 Billing-Zeilen), mypy **602**, Coverage
**88,92 / 82,94 / 85,42 / 90,65** bei **259** Dateien / **2236** Tests, OSV als
Datum, `docker info` **25.** Lauf, und die gewechselte Datei-Sperre an
`apps/web/package.json`.

### 3.4 Zwei Prämissen von Lauf 48 widerlegt

- **#674 ist nicht mehr im Konflikt.** Lauf 48 begründete „schließen" mit
  `merge-tree` → rc 1. Nach einem Dependabot-Rebase auf `aa8fb22e`: **rc 0**,
  **0 Commits hinter `main`**. **Eine Sperre, die aus einem Zustand folgte, hat
  sich ohne Antwort gelöst** (Regel 87) — im Gegensatz zu #823, dessen Sperre
  aus einer Entscheidung folgt und sich deshalb nie von allein löst.
- **#849 stand auf Position 1 mit einer Begründung, die nicht mehr greift.**
  „Kleinstes Paket ohne jede Vorbedingung" — die Vorbedingungsfreiheit ist weg.
  #632 rückt davor, weil Kriterium 3 („Fundament vor Fläche") auf #632 **belegt**
  zutrifft (es öffnet #633, eine harte Abhängigkeit) und auf #849 nicht. Mit
  Rückfallregel im Queue-Issue: mergt #947, gilt wieder #849 → #632.

### 3.5 Ein Fund als Paket geschnitten: #949

`scripts/ci/assert_skips_within_budget.py:128` meldet
`JUnit-XML nicht gefunden: {pfad} — lief pytest ueberhaupt?`. Das Skript wird in
`ci.yml` **zweimal** aufgerufen: `:210` mit `junit-python.xml` (pytest, korrekt)
und **`:268` mit `apps/web/junit-web.xml`, das `vitest` auf `:255` erzeugt**.
**Im Job `web` läuft kein pytest.** Der Docstring (`:3-13`) und die
Argument-Hilfe (`:111`) begründen alles über pytest.

**Die Kosten sind in diesem Lauf eingetreten:** ein Mess-Agent hat den roten
`web`-Job von #674 als „pytest ist nicht gelaufen" zurückgemeldet. Datei **183**
Zeilen, zuletzt #591, **über alle achtzehn PRs frei und auf `main` unbewegt** —
das einzige neue Paket dieses Laufs ohne jede Datei-Sperre. Angelegt als
`agent-ready` `size/S`.

### 3.6 #442 neu geordnet und in Wellen gruppiert

Reihenfolge, Wellen A–L, Kollisionen, Sammelpunkte und die Weichen-Tabelle neu
gegen den Stand vom 2026-10-13. Dazu vier neue Regel-Vorschläge (110–113).
Zehn Dauerposten sind aus §Funde ohne Issue gestrichen und stehen nur noch unter
§Kollisionen (Pflege-Regel 10).

## 4. Zwei Sub-Agent-Zahlen waren falsch und sind selbst nachgemessen

| Gemeldet | Gemessen | Wie |
|---|---|---|
| #674: `TS2339` in **9** Dateien unter `features/workarea/pages/` | **71** Dateien rufen `toHaveNoViolations` auf, **51** davon `*.a11y.test.tsx`, **7** unter `features/workarea/pages/` | `grep -rl toHaveNoViolations apps/web/src apps/web/e2e \| wc -l` |
| #947: **18** Check-Runs | **15** (14 × `success` + 1 × CodeQL `neutral`, **0 skipped**) | `get_check_runs` selbst nachgeschlagen |

Die erste Zahl stammte aus einem **abgeschnittenen Log-Auszug**; Lauf 48 hatte
dieselbe Größe mit „rund 55" geschätzt. **Beide Male war die belastbare Zahl im
Arbeitsbaum verfügbar, nicht im Log.** → **Regel 112.**

**Daraus folgt die korrigierte Ursache von #674:** nicht „rund 55 kaputte
Testdateien", sondern **eine** Typ-Augmentation —
`apps/web/src/test/vitest-axe.d.ts` (699 Bytes) registriert die Matcher auf
`@vitest/expect#Matchers` und sagt im eigenen Kommentar ausdrücklich
„für Vitest 3". **Kleine Fläche, 71 Leser.** ⚠️ **Ein zweiter Grund bleibt
ungemessen:** der Job `web` scheitert vorher daran, dass `junit-web.xml` nicht
erzeugt wird (Regel 49/63). Deshalb ist Weiche 12 ausdrücklich **nicht** als
„#674 wird damit grün" formuliert.

## 5. Braucht eine Owner-Antwort

Zwei neue Weichen, je mit drei Optionen und Empfehlung im Body von #442:

- **Weiche 11 — #947 belegt `ci.yml`: in welcher Reihenfolge?** Empfehlung **A**
  (#947 zuerst mergen; es ist zeilenneutral, kostet also keine
  Zeiger-Neumessung, und räumt die Adresse von zwei Warteschlangen-Paketen frei).
- **Weiche 12 — #674: schließen oder reparieren?** Empfehlung **C** (die
  Typ-Augmentation zuerst auf `main` Vitest-5-fest machen, dann #674 per
  Branch-Update). **Das Schließen fremder PRs bleibt beim Owner.**

Die zehn bestehenden Weichen sind nicht erneut gestellt (Regel 9), nur im Stand
fortgeschrieben. Zwei davon haben sich durch diesen Lauf verändert:
**Weiche 2** (mergt #947, wird jeder heute gate-aktuelle Lauf gate-alt) und
**Weiche 1** (in einem Zeitraum ohne Merges sammelt Option A keine Evidenz —
wer schneller entscheiden will, braucht Option C).

## 6. Messwerte

Node **v22.22.0**, `main` @ `79a8e171`:

| Kommando | Ergebnis |
|---|---|
| `npm run lint` | Exit 0, **90** problems, 0 errors, 8 Regeln, **7** `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe **0 Bytes** |
| `npm run test:coverage` | Exit 0, **259** Dateien, **2236** Tests — 88,92 / 82,94 / 85,42 / 90,65 |
| `npm run i18n:check` | Exit 0, keine neue Waise, **160** bekannte |
| `uv run ruff check .` | Exit 0, 0 Funde |
| `uv run mypy .` | Exit 0, 0 Funde in **602** Dateien |
| `uv run pytest --collect-only -q` | **3526** Tests, **135** Billing-Zeilen |
| `changelog_fragments.py check` | Exit 0, **304** Fragmente (ohne Pipe, Regel 94) |
| `docker info` | **Exit 1** (25. Lauf in Folge) |
| `git rev-parse --is-shallow-repository` | `true` → nach `--unshallow` **1541** Commits (12. Lauf) |
| `grep -c timeout-minutes .github/workflows/ci.yml` | **0** (über `yaml.safe_load` für alle 12 Jobs bestätigt) |

**Alle Werte byte-identisch zu Lauf 48** — `main` ist 0 Commits gelaufen.

🟢 **Die Installations-Falle aus Regel 109 ist nicht wieder eingetreten.** Das
`npm install` des Session-Hooks (697 Pakete) hat gereicht; alle vier Web-Gates
grün, **kein `rm -rf node_modules` nötig**. Der Fehlschlag von Lauf 48 hing also
an einem veralteten `node_modules`, nicht am Vite-Bump. **Die Gegenmaßnahme ist
damit bestätigt, die Ursache präzisiert.**

## 7. Vier neue Regel-Vorschläge

- **110** — Eine Frist in Tagen verrottet jeden Tag ohne jede Dateiänderung;
  Regel 106 fängt sie nicht, weil sie im Arbeitsbaum nicht steht. Als **Datum**
  schreiben.
- **111** — Zwei Schreibwege zum selben Feld sind nicht äquivalent: ein REST-
  `PATCH` über diese Umgebung hängt eine Attributions-Fußzeile an den **Body**,
  `issue_write` nicht. Gemessen an sieben Schreibvorgängen: #849/#923/#435 (je
  `PATCH`, keine Fußzeile im gesendeten Text) tragen danach je **eine**,
  #632/#633/#949 (je `issue_write`) **keine** — und die drei kommen **wieder**,
  nachdem dieser Lauf sie gezielt entfernt und byte-genau zurückgeschrieben hat.
  ⚠️ **Mit einer Falle, in die dieser Lauf selbst getreten ist:** #442 ist über
  **denselben** `PATCH` geschrieben und trägt **keine** angehängte Fußzeile,
  woraus zunächst geschlossen wurde, der Transport sei unschuldig. **Er ist es
  nicht — #442 enthält den Fußzeilen-Text zweimal im eigenen Fließtext, und die
  Gegenstelle entdedupliziert.** Dieselbe Transportart, zwei Ergebnisse, beide
  korrekt. **Lehre fürs Verfahren: ein Beleg, der aus einer Abwesenheit besteht,
  braucht die Prüfung, ob etwas diese Abwesenheit erzeugt** (Regel 105 auf sich
  selbst angewandt).

- **114** — Ein Schreibvorgang, dessen Nutzlast ein Modell erzeugen muss, kann
  auf halber Strecke abbrechen und hinterlässt dann **nicht** den alten Stand,
  sondern einen abgeschnittenen neuen. Siehe §9.
- **112** — Ein Ersetzungs-Anker über einen harten Zeilenumbruch trifft nie
  (fünf von fünf Ankern dieses Laufs), und eine Fehlerzahl aus einem
  abgeschnittenen Log liest sich als Gesamtmenge (9 bzw. „rund 55" gegen
  gemessene **71**).
- **113** — Ein freier Sammelpunkt ist ein Momentwert, und der schnellste
  Belegungs-Mechanismus im Repo ist **Dependabot**: drei von Lauf 48 als frei
  gemeldete Punkte waren binnen 36 Stunden ohne eine `main`-Bewegung wieder
  belegt.

## 8. Nicht getan

Kein Code angefasst, kein Issue geschlossen, kein Label gewechselt, kein PR
gemergt oder geschlossen, kein Board angefasst (Agenten haben dafür kein
Werkzeug). **Das Schließen fremder PRs (#674, #682/#683/#686) und das Mergen
bleiben Owner-Schritte.** Angelegt wurde ein Issue: **#949**.

## 9. Zwei Vorfälle beim Schreiben — beide gemessen, beide behoben

### 9.1 🔴 #442 war zwischenzeitlich auf 15 % abgeschnitten

Der **zweite** Schreibvorgang an #442 (100 049 Zeichen, gegenüber dem ersten
erfolgreichen von 97 180 nur um eine eingefügte Tabellenzeile gewachsen) ist
**mitten im Tool-Aufruf abgebrochen**. Er hat nicht den alten Stand stehen
gelassen, sondern einen abgeschnittenen neuen:

```
IST  Zeichen: 15324
SOLL Zeichen: 100049
abgeschnitten nach: 'ocker info` → **Exit 1**, **25. Lauf**). ✅ **Keine
  Datei-Sperre über alle achtzehn PRs** — `apps/web/e2e/**`, `LoginPage'
fehlende Zeichen: 84725
```

**Weg waren alle zwölf Weichen, alle dreizehn Wellen, die Kollisionsliste, die
Sammelpunkte und alle 113 Pflege-Regeln** — und der Rest sah wohlgeformt aus.
**Das trifft genau das Issue, das jeder Agent als erstes lädt:** ein Lauf, der
danach gestartet wäre, hätte eine Warteschlange ohne Reihenfolge, ohne Regeln
und ohne Kollisionsliste gelesen, ohne es zu merken.

**Behoben:** byte-genau aus der Quelldatei wiederhergestellt — über den Weg, bei
dem niemand den Inhalt neu erzeugt (`-F body=@datei`), und danach gegengeprüft:

```
IST 103527 SOLL 103527 identisch: True
sha256 gleich: True
endet korrekt: True
```

→ **Regel 114.** Die dreiteilige Gegenmaßnahme steht im Queue-Issue: große
Nutzlast aus einer Datei, nach jedem Schreiben **Länge gegen die Quelle** und
das **Ende** prüfen (die geänderte Stelle war hier in Ordnung), und bei einem zu
kurzen Body sofort aus der Quelle wiederherstellen.

### 9.2 Drei Fußzeilen, die absichtlich stehen bleiben

Die Schreibvorgänge an #849, #923 und #435 liefen über einen REST-`PATCH` (der
Grund war gut: ein bis zu 42 KB großer Body byte-genau aus einer Datei statt von
Hand in einen Tool-Aufruf getippt). Dieser Weg hängt eine Attributions-Fußzeile
an den **Body**; `issue_write` tut das nicht — #632, #633 und #949 tragen keine.
**Dieser Lauf hat die drei gezielt entfernt und byte-genau zurückgeschrieben;
danach trugen alle drei wieder genau eine.** Sie bleiben deshalb stehen: sie über
den `issue_write`-Weg zu entfernen hätte drei weitere Groß-Schreibvorgänge
gekostet, und was die wert sind, sagt §9.1.

**Die Ursachen-Analyse hat dabei einen Zwischenstand gehabt, der falsch war, und
der ist hier festgehalten, weil er die Lehre trägt:** weil #442 über denselben
`PATCH` geschrieben wurde und **keine** angehängte Fußzeile trägt, schien der
Transport zunächst unschuldig. Er ist es nicht — **#442 enthält den
Fußzeilen-Text zweimal im eigenen Fließtext, und die Gegenstelle
entdedupliziert.** Dieselbe Transportart hat zwei verschiedene Ergebnisse
erzeugt, und beide sind korrekt. **Ein Beleg, der aus einer Abwesenheit besteht,
braucht die Prüfung, ob etwas diese Abwesenheit erzeugt** — Regel 105 auf die
eigene Prämissen-Korrektur angewandt.
