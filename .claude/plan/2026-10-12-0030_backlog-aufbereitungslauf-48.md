# Backlog-Aufbereitungslauf 48 (2026-10-12)

Prüfnorm: Resource **Agent-ready Arbeitspaket** (`73a86231`) — 🔴 **in diesem Lauf
nicht ladbar**, der MCP-Server `Who2Be---Coder` liefert über `ToolSearch` keine
Werkzeuge (dritter Lauf in Folge). Gefahren wurde nach dem in #442 kodifizierten
Verfahren und den dort geführten Pflege-Regeln 1–107.

Auftrag: jedes offene Issue gegen die Norm prüfen, Belegbares selbst entscheiden
und mit Beleg ins Issue schreiben, Urteilsfragen als Kommentar mit drei Optionen
und Empfehlung zurückgeben, danach die Warteschlange (#442) neu ordnen und in
Wellen gruppieren.

## Ausgangslage

`main` @ `79a8e171`, **19 Commits** seit der Lauf-47-Basis `3b4a1783` (#921–#941).
**Zwölf Issues offen, unverändert** — keines geschlossen, keines neu. **Vierzehn
offene PRs** (Lauf 47: 15): gemergt sind #922, #921, #825, #824 und #827, neu
sind #944, #943, #942 und #924.

Der Klon war zum elften Lauf in Folge shallow (50 → **1541** Commits nach
`--unshallow`, Regel 90).

## Der zentrale Fund: Lauf 47 hat eine Weiche mit der falschen Größe geschlossen

Lauf 47 erklärte die Concurrency-Weiche für beantwortet: über alle 40
`main`-Push-Läufe gelte `created_at == run_started_at`, kein `main`-Lauf warte je,
also könne ein Push keinen verdrängen — **der hängende Job sei der einzige
belegte Mechanismus, der auf `main` einen CI-Spruch kostet.**

**Gegenfall, gemessen in genau diesem Zeitraum:**

| Feld | Lauf `38167426986` (`de2ebcf6`, #933) | Lauf `37822973287` (#863) |
|---|---|---|
| `status` / `conclusion` | `completed` / **`cancelled`** | `completed` / **`cancelled`** |
| `created_at` vs. `run_started_at` | **identisch** (19:18:03Z) | **identisch** (18:16:15Z) |
| Laufzeit bis `updated_at` | **76 s** | **117 s** |
| `list_workflow_jobs` | **`total_count: 0`** | **`total_count: 0`** |

Dazu die Überlappung: `99de76b2` lief von 19:17:49 bis 19:30:42, `de2ebcf6` wurde
19:18:03 erzeugt, `79a8e171` 19:19:18 — **eine Sekunde vor** dem Abbruch des
mittleren. Der erste und der dritte sind `success`.

**Nicht die Messung von Lauf 47 war falsch, sondern ihr Schluss:**
`created_at == run_started_at` beschreibt den Start des **Laufs**, nicht die
Zuteilung seiner **Jobs**. Beide abgebrochenen Läufe sind in genau diesem Fenster
gestorben. Die entscheidende Größe war die **Job-Zahl**, und die hatte in vier
Läufen niemand abgefragt. → **Regel 108**.

**Ungemessen bleibt die Ursache** (Regel 49/63): `actor` und `triggering_actor`
sind beide `luetzey`, die API weist keinen Abbruch-Auslöser aus, und
`cancel-in-progress` wertet auf `main` nachgewiesen zu `false` aus
(`yaml.safe_load` → `${{ github.ref != 'refs/heads/main' }}`). Die
Ein-Sekunden-Nähe ist Korrelation, kein Mechanismus. **Weiche 1 in #442 ist
wieder offen, mit drei Optionen und Empfehlung A (nichts ändern, weiter messen) plus C
(Anbieter-Klärung).**

### Folge für #849

Der Befund (zwölf Jobs ohne `timeout-minutes`) ist unverändert belegt; Scope,
Werte, Kriterien und Startbarkeit bleiben. **Die Reichweite-Aussage ist
geschrumpft:** #849 macht den Hänger billig und schließt die Spruch-Lücke nicht.
Das ist Regel 104 zum vierten Mal am selben Gegenstand.

## Zweiter Fund: ein ungeprüfter Bump auf `main` — und eine Umgebung, in der zwei Gates lügen

`de2ebcf6` (#933) hat **18 Web-Pakete** gehoben (Vite 8.3.1 → 8.3.3, ESLint
10.11 → 10.12, Playwright 1.63 → 1.64, Radix-Minors, supabase-js 2.117.1 →
2.117.3) **und keinen eigenen CI-Spruch bekommen.** Validiert wurde der Bump erst
vom nächsten Push (`79a8e171`, eine Compose-Änderung), der den vollen Job-Satz
fuhr, weil `deploy/**` nicht auf der Doku-Allowlist steht — Job `web` mit Lint,
Typecheck, Test, A11y, Build, beide Bundle-Prüfungen, alle `success`.
**Bei einer reinen Doku-Änderung als Nachfolger wäre er ungeprüft durchgelaufen.**

Und dieselbe Änderung macht die Messung hier zunächst unmöglich:
`npm run test:coverage` und `npm run i18n:check` brechen in einer frischen
Cloud-Session mit `Cannot find native binding` /
`Cannot find module '@rolldown/binding-linux-x64-gnu'` ab — **Exit 1, null Tests
gefahren** —, während `npm run lint` und `npx tsc -b` grün melden, weil sie das
Binding nicht brauchen. Erst `rm -rf apps/web/node_modules && npm ci` macht alle
vier grün. → **Regel 109**.

Nebenbefund derselben Installation: `vitest` ist als `^4.1.10` deklariert und
installiert sich zu **4.1.11**, `@vitest/coverage-v8` bleibt **4.1.10** — der Lauf
warnt wörtlich „Running mixed versions is not supported and may lead into bugs".
Eigener Posten (Welle K), blockiert von #674.

## Norm-Prüfung aller zwölf offenen Issues

Pflichtteile: (a) Outcome · (b) prüfbare Akzeptanzkriterien mit Schwelle oder
Kommando · (c) Scope mit ausdrücklichem „In" und „Out of Scope" · (d) exakte
Verifikations-Kommandos.

| Issue | a | b | c | d | Summe | Konsequenz |
|---|---|---|---|---|---|---|
| #849 | ✅ | ✅ (6 Kriterien, alle mit Schwelle/Kommando) | ✅ | ✅ | **4/4** | `agent-ready`, Position 1 |
| #632 | ✅ | ✅ | ✅ | ✅ | **4/4** | `agent-ready`, Position 2 |
| #923 | ✅ | ✅ (5 Kriterien) | ✅ | ✅ | **4/4** | `agent-ready`, Position 3 |
| #633 | ✅ | ✅ (6, weist die Abweichung selbst aus) | ✅ | ✅ | **4/4** | `agent-ready`, Position 4 |
| #435 | ✅ | partial (6, **5** ohne Schwelle) | ✅ | ✅ | 3/4 | `size/M` → Regel 7 |
| #540 | ✅ | partial (7, **6** ohne) | partial (**„In" fehlt**) | ✅ | 2,5/4 | `size/M` + dreifach blockiert |
| #454 | ✅ | partial (5, **4** ohne) | partial (**„In" fehlt**) | partial (sagt selbst „kein Testkommando") | 2/4 | `human-only` |
| #542 | partial | partial (**5 von 5** ohne Kommando) | partial (**„In" fehlt**) | partial (gilt nur bei Option A/C) | 1,5/4 | `human-only` + `needs-decision` |
| #428 | **fehlt** | partial (5, keines mit Kommando) | partial (**„In" fehlt**) | **fehlt** | **1/4** | `size/M` → Zuschnitt |
| #535 | **fehlt** | partial (3, keines mit Kommando) | partial (**„In" fehlt**) | **fehlt** | **1/4** | `size/M` → Zuschnitt |
| #338 | **fehlt** | **fehlt** | **fehlt** | **fehlt** | **0/4** | `human-only`, vertretbar |
| #442 | — | — | — | — | — | die Warteschlange selbst |

**Querschnitt, dritter Lauf in Folge bestätigt: ein ausdrückliches Scope-„In"
fehlt in sechs von sieben** — nur #435 hat eines. **Alle lückenhaften außer
#454/#338 sind `size/M`** → Regel 7: Zuschnitt, kein Nachtragen von Feldern.

## Selbst entschieden und mit Beleg ins Issue geschrieben

Zehn Issue-Bodies plus ein Kommentar. Drei davon sind **Tatsachen-Korrekturen**,
keine Zahlen-Pflege:

1. **#923 — die Begründung des Issues ist umgedreht worden.** Der Body stützte
   sich auf Lauf 47s „kein `main`-Lauf wartet je". Jetzt steht dort die Messung,
   die das widerlegt — **und der Befund ist dadurch stärker**: `ci.yml:10-11`
   verspricht, `main` behalte seinen Lauf; zwei gemessene Fälle sagen das
   Gegenteil. **Akzeptanzkriterium 2 ist geschärft**, damit der neue Kommentar
   keine Zusage macht, die die Messung widerlegt. Das war die eine Stelle, an der
   Zahlen-Pflege nicht gereicht hätte: ein unverändertes Kriterium 2 hätte den
   ausführenden Agenten angewiesen, eine falsche Aussage in den Code zu schreiben.
2. **#428 — `.github/PROJECT.md` führt die Cloud-Edition nicht mehr als Out of
   Scope.** Der Body berief sich darauf. Gemessen: `PROJECT.md:7` nennt
   „Cloud-Launch & Alltagstauglichkeit" als **aktives Vorhaben**, `:15` als
   Outcome „mindestens einmal real deployt und verifiziert"; Out of Scope
   (`:160-163`) nennt nur Tarife/Preise, Rechnungs-PDFs/E-Rechnung und
   Multi-Region.
3. **#542 — der generische Billing-Webhook ruft den Dedupe-Ledger inzwischen
   auf.** Der Body führte das als offene Auflage („kein Dedupe-Ledger-Aufruf").
   Gemessen: `packages/billing/src/who2be_billing/router.py:223-224`
   (`PgProcessedEventRepository` / `processed.claim(...)`), Freigabe `:264`,
   Begründung `:165`, Plausibilitätsfenster `:252-258`; **Kind #452 ist
   geschlossen.** Offen bleiben Ablauffrist, Signatur-Zeitfenster und monotoner
   Upsert — als Auflage, nicht als Befund.

Dazu die Zeiger- und Zahlen-Reparaturen:

| Issue | verrottet | korrekt |
|---|---|---|
| #540 | Caddy-Pin `caddy:2.11.4-alpine` an **vier** Fundstellen | **`caddy:2.11.7-alpine`** auf `who2be/docker-compose.yml:439` (Zeile hält, Ursache #932) |
| #454 | `RUNBOOK.md` **2463** Zeilen | **2467** (Zeiger `:438` und `:1819-1829` unverschoben) |
| #428 | `BillingPanel.tsx:41` als Pro-Zeile | **`:42`** (`:41` ist die Free-Zeile) |
| #535 | Pro-Zeile `:41`, `findTier` `:46-48` | **`:42`**, **`:47-49`** |
| #435 | `auth-js` **2.117.1**, Pin `^2.117.1` | **2.117.3**, `^2.117.3` (#933) |
| #338 | „alle 19 `uses:` SHA-gepinnt" als Gegenwartszahl | **33** `uses:` in drei Workflows, alle gepinnt, keine ungepinnt |
| #428/#535/#435 | OSV-Restlaufzeit 22–26 Tage, Pfad `osv-scanner.toml:11` | **21 Tage**, **`apps/web/osv-scanner.toml:11`** |
| alle | Fragmente **289**, Collection **3461**, mypy **595** | **304** (`ls` 305), **3526**, **602** |

**Ein Fehlertyp ist neu:** der Caddy-Pin hat seine Zeile (`:439`) **und** die
Dateizeilenzahl (560) behalten — verrottet ist die **Version darin**. Regel 106
deckte bisher nur Zahlen, die ein Body als Basiswert ausgibt; sie gilt ab jetzt
auch für die Version in einem zitierten Pin.

**Nicht geschrieben:** der Body von **#435**. Die vorbereitete Fassung (36 KB,
18 belegte Ersetzungen) wurde verworfen, weil das Issue `size/M` ist und nach
Regel 7 ohnehin einen Zuschnitt braucht, nicht Feldpflege; die Korrekturen stehen
als Kommentar am Issue und in #442. Im nächsten Lauf nachzutragen.

## Urteilsfragen — zehn Weichen, eine wieder geöffnet, eine neu

Alle stehen mit drei Optionen und Empfehlung in #442:

1. 🔴 **Wieder offen:** Was bricht `main`-Läufe ab, die noch keinen Job erzeugt
   haben? **Empfehlung A** (nichts ändern, #849 bauen, bei jedem weiteren Fall
   `list_workflow_jobs` mitmessen) **plus C** (Anbieter-Klärung). B (Nachhol-
   Workflow) ist die teuerste Antwort auf einen Fall in 40 Läufen und verdeckt
   die Ursache weiter. **`cancel-in-progress` auf `main` bleibt unangetastet**
   (Regel 103).
2. 🆕 **Neu:** Werden #682/#683/#686 geschlossen, weil #944 Redis durch Valkey
   ersetzt? **Empfehlung A** (#944 mergen, dann die drei schließen). Gemessen:
   #944 ersetzt in **genau den drei Dateien** `image: redis:7-alpine` durch
   `valkey/valkey:8-alpine@sha256:…` und `redis-cli` durch `valkey-cli`.
   **Das Schließen fremder PRs ist destruktiv und bleibt beim Owner** — dieser
   Lauf hat es nicht ausgeführt.
3. Gate-alte grüne PRs mergen (Empf. B) · 4. Arbeitspaket-Vertrag für
   Tracking-Issues (Empf. B) · 5. `audit` im Required Check (Empf. A/C) ·
   6. Coverage-Boden (Empf. B) · 7. Caddy-Widerspruch (Empf. A) · 8. ESLint
   (Empf. B/C) · 9. MB/MiB (Ja/Nein) · 10. #823 frisch machen (Empf. A).

## Neue Reihenfolge

Kriterien unverändert: harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche
→ Inventar vor Zuschnitt → bei Gleichstand das kleinere.

1. **#849** — Timeouts in `ci.yml`. Zwölf eingefügte Zeilen, Datei frei **und**
   unbewegt, keine offene Entscheidung. Reichweite kleiner, Befund unverändert.
2. **#632** — Passkey registrieren. Öffnet #633. ⚠️ `features/settings/**` ist
   erstmals seit vier Läufen bewegt (#927), `locales` 5×.
3. **#923** — der `concurrency`-Kommentar. **Von 4 auf 3 vorgezogen**: Regel 8
   (ein blockiertes Paket hält kein startbares auf) — #633 hängt an #632 und an
   Docker, #923 an nichts. Und der Posten ist in diesem Lauf vom Schönheitsfehler
   zum Faktenfehler geworden.
4. **#633** — Step-up mit Passkey. Nach #632, plus Container-Laufzeit.
5. **`audit`-Trennung + #923 in einem PR** — Frist 2026-11-02, 21 Tage.
6. **Caddy-Widerspruch** — Betrieb 2.11.7, CI 2.8, ein Test verbietet unter 2.11.
7. **Die 7 `--fix`-baren Lint-Warnungen** — vier Dateien, frei und unbewegt.
8. **#540** — dreifach blockiert, jetzt mit zwei Datei-Sperren.

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | #632 (Web-Stack) | allein im Vitest-Baum; `npm ci` zuerst |
| **B** | #633 | nach #632, braucht Docker |
| **C** | #849 (`ci.yml`) | **A + C ist das echte Parallel-Paar** (zwei Stacks) |
| **D** | `audit`-Trennung **+ #923** | ein PR; nicht mit C |
| **E** | Caddy | nicht mit C oder D (`ci.yml`) |
| **F** | 7 Lint-Warnungen | nicht mit A/B/G/K (ein Vitest-Baum) |
| **G** | Coverage-Boden | nach Weiche 6 |
| **H** | Merges: **#944, #943 zuerst** (je 18/18 grün, 0 hinter `main`), dann #942, die Protokoll-PRs, #831 per Update | #823 nach Weiche 10, #944 nach Weiche 2 |
| **I** | #682/#683/#686 | 🔴 **jetzt Entscheidung statt Branch-Update** (Weiche 3) |
| **J** | MB/MiB-Zeile | ein Satz, nach einem Ja |
| **K** | 🆕 `vitest`/`coverage-v8`-Versatz | blockiert von #674 (Konflikt) |

Nie gleichzeitig: C/D/E (dieselbe `ci.yml`) · F/G/K gegen A/B (ein Vitest-Baum) ·
B vor A · #944 gegen #682/#683/#686 · #943 gegen #823 (`RUNBOOK.md`) ·
K vor dem Schließen von #674 · #540 gegen alles.

## Messwerte

Sequenziell erhoben, ein Schreiber je Baum; Web und Python sind verschiedene
Stacks und liefen nebeneinander. Node **v22.22.0**, **nach `npm ci` in
`apps/web`**.

| Messung | Lauf 48 | Lauf 47 |
|---|---|---|
| `npm run lint` | Exit 0, **90** problems, 0 errors, 8 Regeln, **7** `--fix`-bar | 90 / 8 / 7 |
| `npx tsc -b` | Exit 0, Ausgabe leer | Exit 0 |
| `npm run test:coverage` | Exit 0, **259 Dateien / 2236 Tests** | 258 / 2209 |
| Statements / Branches / Functions / Lines | **88,92 / 82,94 / 85,42 / 90,65** | 88,88 / 82,82 / 85,4 / 90,62 |
| `npm run i18n:check` | Exit 0, keine neue Waise, **160** bekannt | 160 |
| `uv run pytest --collect-only -q` | **3526** Tests, **135** Billing-Zeilen | 3461 / 135 |
| `uv run ruff check .` | Exit 0, 0 Funde | 0 |
| `uv run mypy .` | Exit 0, 0 Funde in **602** Dateien | 595 |
| `changelog_fragments.py check` | Exit 0, **304** Fragmente (`ls` 305) | 289 |
| `docker info` | **Exit 1** (24. Lauf) | Exit 1 |
| `grep -c timeout-minutes ci.yml` | **0** (über `yaml.safe_load` für alle 12 Jobs) | 0 |
| `ci.yml` | **1212** Zeilen, 0× bewegt seit #839 | 1212 / 0 |

Lint-Verteilung Regel für Regel identisch zu Lauf 47: `set-state-in-effect` 48,
`classnames-order` 18, `only-export-components` 12, `incompatible-library` 5,
`preserve-manual-memoization` 4, `use-memo`/`refs`/`exhaustive-deps` je 1.

Branch-Coverage steigt den **dritten** Lauf (Abstand zum Gate 79: **3,94**, war
3,82). Der Fehlermodus bleibt: ein Lauf kann Coverage verlieren und Exit 0 melden.

## Neue Pflege-Regeln

**108.** Ein Rohfeld kann die richtige Frage beantworten und die falsche Größe
messen — wer eine Weiche mit einem Feldpaar schließt, prüft erst, was das
Feldpaar tatsächlich zählt. Zu jedem Lauf ohne Spruch gehört
`list_workflow_jobs`.

**109.** Zwei von vier grünen Gates sind kein Beleg für eine intakte
Installation — und ein Werkzeug, dem ein natives Binding fehlt, meldet das als
Fehlschlag der Sache. In `apps/web` ist eine frische Installation Vorbedingung
jeder Messung.

Regel 106 ist um die Versions-Variante ergänzt: wer einen Pin zitiert, zitiert
eine Version, nicht eine Zeile.

## Verfahrensanmerkung zu diesem Lauf

Die Messung ist in drei parallele Arbeitspakete zerlegt worden (PR-Scope/CI je
PR · Zeiger-Audit #428/#535/#542/#338 · Zeiger-Audit #435/#540/#454), je als
Sub-Agent mit `sonnet` — die Pakete sind mechanisch und datei-disjunkt, ein
größeres Modell hätte keinen Mehrwert gebracht. **Ein Paket hat dabei zwei
Issue-Bodies (#540, #454) per Hand-Edit geschrieben, bevor die Weisung „nur
Dateien vorbereiten" ankam.** Der unveränderte Rest beider Bodies ist damit nicht
byte-verglichen. **Gegengeprüft ist dafür die Struktur** (Code-Fences paarig,
Abschnitte vollständig) **und jeder `pfad:zeile`-Zeiger beider Bodies maschinell
gegen den Arbeitsbaum**: #540 zehn Zeiger, 0 Problemfälle; #454 zwölf Zeiger,
0 Problemfälle am gültigen Pfad. Lehre für den nächsten Lauf: einem Sub-Agenten
die Schreibrechte erst gar nicht in den Auftrag schreiben, sondern nur den
Dateipfad verlangen.

## Was dieser Lauf NICHT getan hat

Kein Code angefasst, kein Issue geschlossen, kein Label gewechselt, keinen PR
gemergt oder geschlossen, nichts an `main` gepusht. Die destruktiven Schritte
(#674 schließen, die drei Redis-Bumps schließen, #823 schließen) stehen als
Empfehlung mit Begründung in #442 und bleiben beim Owner.
