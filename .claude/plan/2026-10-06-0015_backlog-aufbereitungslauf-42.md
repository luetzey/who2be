# Backlog-Aufbereitungslauf 42

**Datum:** 2026-10-06 · **Basis:** `main` @ `6b8ef201` · **Vorgänger:** Lauf 41
(`.claude/plan/2026-10-05-0015_backlog-aufbereitungslauf-41.md`, **PR #823 —
offen als Draft, grün, `mergeable_state = clean`**)

Norm: **Agent-ready Arbeitspaket**. Auftrag: jedes offene Issue gegen die Norm
prüfen, Belegbares selbst entscheiden und mit Beleg ins Issue schreiben,
Urteilsfragen als Kommentar mit drei Optionen und Empfehlung zurückgeben,
danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

**Umgebungsgrenze:** die Who2Be-MCP-Lesewerkzeuge (`get_persona`,
`list_triggers`, `fetch_playbook`, `search_memory`) waren in dieser Session
**nicht** verfügbar — nur `propose_memory_change`. Persona und Playbook-Katalog
sind in den Systemprompt eingebettet und wurden daraus gelesen; das Playbook
„Projekt-Standup"/„Code-Task-Flow" konnte nicht nachgeladen werden. Der Lauf
ist deshalb aus dem eingebetteten Katalog gefahren worden, nicht aus dem
gefetchten.

## 1. Befund in drei Sätzen

1. ✅ **Zum ersten Mal seit Lauf 39 kann überhaupt etwas mergen: drei PRs sind
   grün und `mergeable_state = clean`** (#827, #825, #824), ein vierter (#823)
   ebenfalls und hängt **nur am Draft-Flag**. Das ist nicht das Ergebnis einer
   Tat, sondern von Dependabot: vier neue PRs am 2026-10-05 zwischen 04:18 und
   04:31 UTC, gegen einen Fragment-Bestand, der heute heil ist. **Die Weiche
   von Lauf 41 ist beantwortet, ohne beantwortet zu werden — ihre Prämisse ist
   weggefallen.**
2. 🔴 **Der zentrale Fund ist ein Zeiger-Paar, das in zwei Issues gekreuzt
   stand, während beide Bodies die richtige Zuordnung ein paar Absätze weiter
   trugen.** #535 labelte `core/config.py:159` als `rate_limit_write`, #540
   labelte `:83` als `ingest_max_bytes`. Gemessen: `:83` = `rate_limit_write`,
   `:159` = `ingest_max_bytes`. → **Regel 97**.
3. 🔴 **Lauf 41 hat einen fehlenden Hebel behauptet, den es gibt.** Aus einem
   `rerun_failed_jobs` → HTTP 403 schloss er, es gebe „keinen legitimen Hebel
   ausser einem inhaltlichen Push". Ein **Branch-Update** auf die drei
   144 Commits alten Redis-PRs löst einen frischen Lauf aus. → **Regel 96**.

## 2. Methode

Drei parallele Prüf-Sub-Agents (Sonnet — Struktur-Abgleich gegen eine feste
Rubrik plus Beleg-Verifikation im Repo, keine Design-Entscheidung; das
rechtfertigt das kleinere Modell), read-only, mit ausdrücklichem Verbot von
Testläufen im geteilten Baum (Regel 31/76):

| Agent | Auftrag |
|---|---|
| A | Zeiger und Norm-Stand in #632, #633, #435 |
| B | Zeiger und Norm-Stand in #428, #535, #540 |
| C | Queue-Zeiger: Caddy, Coverage-Gate, E2E-Zählung, i18n-Gate, Sonstiges |

**Kein Rücklauf ist ungeprüft übernommen worden.** Zwei Beispiele, beide
relevant:

- Agent A meldete „`apps/web/.nvmrc` existiert nicht". Nachgemessen:
  `.nvmrc` liegt im **Repo-Root** und fordert `22` — es ist die einzige im
  Repo. **Ein zu schmaler Suchraum sieht genauso aus wie echte Verrottung**
  (Regel 93). Der Zeiger ist präzisiert worden, nicht „korrigiert".
- Agent C meldete für `test_compose_hardening.py:216` nur „Assertion
  irgendwo zwischen `:214` und `:217`", Agent A nannte `:216` exakt.
  Selbst nachgelesen: `:216` ist `assert (major, minor) >= (2, 11)`. **Der
  Zeiger hält.**

Die Web-Messungen liefen **sequenziell**, ein Schreiber im Baum. Der Klon war
shallow (50 Commits) und ist einmal entpackt worden (**1439**) — fünfter Lauf
in Folge, Regel 90.

## 3. Messwerte

Node **v22.22.0**, `main` @ `6b8ef201`:

| Messung | Ergebnis | Lauf 41 |
|---|---|---|
| `npm run lint` | Exit 0, **91** problems, 0 errors, 59 Dateien, 8 Regeln, **9** `--fix`-bar | 91 |
| `npx tsc -b` | Exit 0 | Exit 0 |
| `npm run test:coverage` | Exit 0, **248** Dateien, **1944** Tests | 248/1944 |
| → Statements / Branches / Functions / Lines | **88,19 / 82,28 / 84,37 / 89,76** | identisch |
| `npm run i18n:check` | Exit 0, **159** Altwaisen (**eine geteilte Liste**) | 159 |
| `uv run pytest --collect-only -q` | **3022** Tests, Billing in der Collection | 2971 |
| `changelog_fragments.py check` (**ohne Pipe**) | Exit 0, **207** Fragmente | 204 |
| `docker info` | **Exit 1** | Exit 1 |
| E2E-Körper / davon über `createUser` | **35 / 26** — ohne `E2E_EDITION=cloud` **33 / 24** | 35/26 |

**Die vier Web-Zahlen sind identisch zu Lauf 41 — neu gemessen, nicht
übernommen.** Der Grund ist belegt: die drei Commits dieses Zeitraums (#802,
#828, #829) fassen `apps/mcp`, `apps/api`, `packages/models` und Docs an,
keinen Web-Pfad. **Eine unveränderte Zahl ist ein Messwert, kein ausgelassener
Lauf** (Regel 21).

## 4. PR-Zustandsmessung (Regel 95)

`all-green` namentlich aus `commits/<head>/check-runs`, `mergeable_state` per
`pull_request_read`, Datei-Scope über die ausdrücklich berechnete merge-base.

| PR | Inhalt | `all-green` | `mergeable_state` | Lauf | Klasse |
|---|---|---|---|---|---|
| #827 | nginx/seaweedfs/postgres, 4× compose | ✅ 13/13 | ✅ `clean` | 2026-10-05 | — |
| #825 | python-minor-patch, `uv.lock` | ✅ | ✅ `clean` | 2026-10-05 | — |
| #824 | web-minor-patch, `package.json` | ✅ 13/13 | ✅ `clean` | 2026-10-05 | — |
| #823 | Zeiger-Reparatur Lauf 41 | ✅ 17/17 | ✅ `clean`, **Draft** | 2026-10-05 | — |
| #686 / #683 / #682 | redis 7→8, je **eine** Zeile | 🔴 nur `changelog-guard` | 🔴 `blocked` | **2026-09-28** | **veraltet** |
| #826 | fastmcp 3.4.7 → **4.0.10** | 🔴 `python` | 🔴 blocked | 2026-10-05 | **eigen** |
| #674 | Vitest 4 → **5** | 🔴 `web` + 6 Folgejobs | 🔴 blocked | 2026-10-05 | **eigen** |

**Drei Dinge, die Lauf 41 nicht wusste:**

1. **Der „veraltet"-Befund ist jetzt von beiden Seiten belegt.** Lauf 41 leitete
   ihn aus Zeitstempeln her (#678 hat den Fragment-Bestand am 2026-09-28 um
   04:42 UTC repariert, die drei Läufe starteten 13–21 Minuten davor). **Die
   Gegenprobe steht: alle vier PRs vom 2026-10-05 haben `changelog-guard`
   grün.**
2. **#681 ist geschlossen, #826 ist sein Nachfolger — der fastmcp-Bruch ist
   damit zweimal unabhängig gemessen** (4.0.9 und 4.0.10, beide brechen
   `python`). Und **#674** ist am 2026-10-05 von Dependabot neu aufgesetzt
   worden und gegen die aktuelle Basis gelaufen. **Beide sind `eigen`, nicht
   `ungemessen`** — die von Lauf 41 offengelassene Diagnose ist nachgeholt,
   ohne dass ein Re-Run nötig war.
3. **Zwei PR-Paare kollidieren untereinander:** #825 ↔ #826 (`uv.lock`),
   #824 ↔ #674 (`apps/web/package.json` + Lock). In beiden Paaren ist der
   grüne der kleine und der rote der Major-Bump. **Den grünen zuerst mergen.**

## 5. Selbst erledigt (mit Beleg ins Issue geschrieben)

### 5.1 Das gekreuzte `config.py`-Zeiger-Paar — #535 und #540

```
$ grep -nE "rate_limit_write|ingest_max_bytes" apps/api/src/who2be_api/core/config.py
83:    rate_limit_write: str = "30/minute"
159:    ingest_max_bytes: int = Field(
```

- **#535** Statusblock: `:159` mit dem Label `rate_limit_write` → **falsch**.
  Der Abschnitt „Der teuerste Befund zuerst" desselben Bodys nennt `:159`
  korrekt als `WHO2BE_INGEST_MAX_BYTES`.
- **#540** Statusblock: `:83` mit dem Label `ingest_max_bytes` → **falsch**.
  Der Abschnitt „Ehrlich zur Schwere" desselben Bodys nennt `:83` korrekt für
  die 30/min.

`git log` für die Datei erklärt keine Verschiebung — es war **keine Wanderung,
sondern eine Transposition aus einer gemeinsamen Vorlage**, die beide Issues
gleichzeitig verrottet hat. **Warum sie so lange überlebt hat:** jede Prüfung,
die fragt „existiert Zeile 159 und sieht sie plausibel aus?", sagt ja. Nur
eine, die fragt „steht dort **das**, was der Zeiger behauptet?", sagt nein.
→ **Regel 97**. Beide Labels korrigiert.

### 5.2 #435 widerspricht sich zwölf Absätze lang selbst

Der Kopf von #435 meldete in Lauf 41 den `vite.config.ts`-Zeiger als korrigiert
(`:49-54` → `:81-85`) und schrieb: „Derselbe Zeiger stand in #632, #633 und
#442 — **Regel 58, in allen vier nachgezogen.**" Der **Verifikations-Abschnitt
desselben Issues** trug weiter:

| Behauptung | Ist-Stand |
|---|---|
| `vite.config.ts:49-54` | **`:82-85`** (`thresholds:` `:81`, `coverage` ab `:67`, Datei 89 Zeilen) |
| Coverage 87,86 / 82,10 / 83,90 / 89,32 | **88,19 / 82,28 / 84,37 / 89,76** |
| „3,1 Prozentpunkte" Abstand bei Branches | **3,28** |
| Lint **90** auf Basis `f38979bd` | **91** auf `6b8ef201` |
| „in den letzten **17** Commits" | 11 (Lauf 41) bzw. **3** (Lauf 42) |

**Regel 58 gilt also nicht nur zwischen Issues, sondern innerhalb eines
Bodies** — und ein Satz „überall nachgezogen" ist am gefährlichsten, wenn er
stimmt, bloß nicht für die eigene Datei. Alles korrigiert.

### 5.3 Der „17 Commits"-Baustein in drei Issues

`#435`, `#535` und `#633` trugen im Verweis-Block „die 17 Commits dieses
Laufs" — eine Zahl aus einem früheren Lauf, die mit der jeweiligen Kopfzeile
nie übereinstimmte. In allen drei durch die Sache statt die Zahl ersetzt.

### 5.4 Die i18n-Waisen-Baseline ist keine Liste je Locale

`apps/web/src/i18n/orphan-baseline.json` ist ein **flaches Array mit 159
Einträgen**, nicht 159 je Locale. **Dieselbe Liste filtert beide Locales**, und
die Gegenrichtung (`audit.test.ts:321`) läuft **nur gegen `de`**
(`findOrphanKeys(de as LocaleTree, repoUsage, 'de', …)`). Die Zahl war immer
richtig, **„je Locale" war es nie** — Regel 18 in der Variante, in der nicht
der Zähler, sondern seine **Einheit** falsch ist. In #632, #633, #435 und #442
korrigiert.

### 5.5 Die tragende E2E-Zahl von #633 hat eine unbenannte Bedingung

`billing.spec.ts:43` trägt ein datei-weites, **laufzeitbedingtes**
`test.skip(() => !isCloudRun, …)`. **35 Körper / 26 über `createUser`** gilt
für den Lauf *mit* `E2E_EDITION=cloud` (CI-Job `e2e-billing-cloud`,
`ci.yml:503`); ohne ihn — also im Job `e2e` (`:423`) und in dem
Verifikations-Kommando, das #633 selbst nennt — sind es **33 / 24**.

**Das ist nicht kosmetisch:** #633s „Grün heißt" verlangt, dass die Testzahl
„um genau diesen einen Fall gewachsen" ist. Wer gegen 35 vergleicht, wo das
Werkzeug 33 fährt, liest eine Abweichung von zwei als Schaden. In #633 als
Tabelle eingetragen, in #632, #435 und #442 als Nebenbedingung vermerkt.

### 5.6 Akzeptanzkriterium 5 von #428 ist entsperrt

**`ROADMAP.md` und `README.md` sind frei — #802 ist gemergt (`676fc7e0`).**
Lauf 41 schrieb, die Belegung sei „auf unbestimmte Zeit"; **sie hat einen Tag
gehalten.** Und die zweite Prognose desselben Blocks ist ebenfalls nicht
eingetreten: der Zeiger `ROADMAP.md:69` ist **nicht** gewandert
(`git diff --numstat 54e48ee6 676fc7e0 -- ROADMAP.md` → **1/1**, zeilenneutral;
`:69` trägt vor und nach dem Merge denselben Text).

**Zwei Prognosen, zwei Fehlschläge, in entgegengesetzte Richtungen.** Die Lehre
ist nicht „Regel 58 gilt nicht", sondern: **Zeiger- und Sammelpunkt-Zustände
werden gemessen, nicht prognostiziert.**

### 5.7 Kleinere Präzisierungen

- **#435:** `grep -rn "supabase/gotrue" --include="*.yml" .` liefert **vier**
  Zeilen, nicht drei — die vierte ist `.github/dependabot.yml:168`
  (`dependency-name`, kein Pin). Das Kriterium ist erfüllt, seine Zählung war
  es nicht (Regel 85).
- **#428:** `ci.yml:826` ist der Step-**Name** `npm audit`, nicht die
  `run`-Zeile; `:817` und `:871` sind `run`-Zeilen.
- **#540 / #535:** `deploy/hetzner/RUNBOOK.md` ist von **#823** belegt und ist
  damit die **erste echte Datei-Sperre, die #540 je hatte** (Akzeptanzkriterium
  5 schreibt diese Datei).
- **#442:** `changelog.d/` enthält **208** `.md`-Dateien, der Checker zählt
  **207** — die Differenz ist `README.md`. **Kein Defekt**, hier aufgelöst statt
  gemeldet.
- **`.nvmrc`:** liegt im Repo-Root, fordert `22`, ist die einzige im Repo. In
  #632 und #633 mit Pfad eingetragen; in #442 als Kommentar-Ergänzung, weil der
  Body-Satz unvollständig und nicht falsch ist (Begründung dort).

## 6. Norm-Stand aller zehn offenen Issues

**Zehn Issues offen — exakt dieselben zehn wie in Lauf 41. Null
Issue-Bewegung in 24 Stunden, bei drei Merges und vier neuen PRs.**

| Issue | (a) Outcome | (b) AK | (c) Verifikation | (d) Out of scope | Befund |
|---|---|---|---|---|---|
| **#632** | ✅ | 5, alle mit Schwelle | ✅ exakte Kommandos | ✅ | **norm-vollständig**, `agent-ready` zu Recht |
| **#633** | ✅ | 6 (Norm 2–5, im Body vermerkt) | ✅ inkl. E2E | ✅ | vollständig; Verifikations-Basis präzisiert (5.5) |
| **#435** | ✅ | 6, **zwei ohne Schwelle** | ✅ | ✅ | `size/M`, aber **kein ungeschnittener Rest** (W2 geschnitten) |
| **#540** | ✅ | 7, **Nr. 1 ohne Kommando, Nr. 2 ohne Frist** | ✅ mit „Grün heißt" | ✅ | vollständig, **dreifach blockiert** + neue Datei-Sperre |
| **#428** | ❌ **fehlt ganz** | 5, **nur 1/3/5 prüfbar** | ❌ **fehlt ganz** | ✅ | Tracking; AK 5 **entsperrt** |
| **#535** | ❌ **fehlt ganz** | 3, **nur Nr. 1 prüfbar** | ❌ **fehlt ganz** | ✅ | Tracking; **AK 2 seit sechs Läufen zur Hälfte unbelegt** (`BillingPanel`-Zahlen nie gegengeprüft) |
| **#442** | — | — | — | — | die Warteschlange selbst |
| **#454, #338, #542** | — | — | — | — | `human-only` — der Refinement-Lauf endet an diesem Label |

## 7. Reihenfolge und Wellen

Vollständig in #442. Kurzfassung:

**Reihenfolge:** 1. #632 (Kriterium 3) · 2. #633 (Kriterium 1, nach #632) ·
3. `audit`-Job trennen (Frist **27 Tage**) · 4. Caddy-Versions-Widerspruch ·
5. die 9 `--fix`-baren Lint-Warnungen · 6. #540 (dreifach blockiert).

**Wellen:** A (#632, Web-Stack allein) · B (#633, nach A, braucht Docker) ·
C (`audit`-Trennung, `ci.yml`) · D (Caddy, kollidiert mit C über `ci.yml`) ·
E (Lint-`--fix`, ein Vitest-Baum mit A/B) · F (Coverage-Boden) ·
**G (die vier mergebaren PRs — ein Klick, kein Agent)** ·
**H (die drei Redis-Einzeiler per Branch-Update)**.
**A ∥ C ist das einzige echte Parallel-Paar.** G und H sind zu allem disjunkt.

## 8. Neue Regel-Vorschläge

- **96 — Ein fehlender Hebel ist eine Behauptung über die eigene Werkzeugkiste
  und wird belegt wie eine Zahl.** Lauf 41 schloss aus einem HTTP 403 bei
  `rerun_failed_jobs` auf „keinen legitimen Hebel ausser einem inhaltlichen
  Push". Ein Branch-Update auf die drei 144 Commits alten Redis-PRs löst einen
  frischen Lauf aus, ohne Leer-Commit und ohne Close/Reopen; alle drei mergen
  konfliktfrei (`git merge-tree --write-tree`). **Nicht gezogen** — ein
  Schreibvorgang an einem fremden PR ist kein Teil eines Aufbereitungslaufs.
  Gegenmaßnahme: wer „ich kann X nicht" notiert, nennt **das Werkzeug** und
  **die Bedingung**, unter der ein anderes es könnte.
- **97 — Ein Zeiger kann in der Zeile stimmen und im Label falsch sein, und
  derselbe Body trägt die richtige Zuordnung oft ein paar Absätze weiter.**
  Siehe 5.1. Gegenmaßnahme: eine Zeiger-Prüfung **vergleicht den Zeileninhalt
  mit dem Label**, nicht nur die Existenz der Zeile.

Dazu zwei Regeln, die in diesem Lauf erneut eingetreten sind: **59** (`get_status`
meldete für den grünen PR #825 `pending` bei `total_count: 0` — die
Legacy-Commit-Status-API ist in diesem Repo leer, es laufen Check-Runs) und
**93** (zweimal: `.nvmrc` und `test_compose_hardening.py:216`).

## 9. Was dieser Lauf NICHT getan hat

- **Kein Code angefasst.** Die einzige Datei dieses PRs ist dieses Protokoll.
- **`.claude/context/STATE.md` nicht gepflegt** — sie ist von **PR #823**
  belegt (Draft, grün, `clean`), ebenso `.github/PROJECT.md` und
  `deploy/hetzner/RUNBOOK.md`. Ein zweiter Schreiber dort wäre ein Konflikt an
  einem mergebaren PR. **CLAUDE.md verlangt STATE.md pro Run; dieser Lauf hält
  die Pflicht bewusst zurück, bis #823 gemergt ist**, und vermerkt das hier
  statt es stillschweigend zu übergehen.
- **Kein Merge, kein Branch-Update, kein Re-Run an einem fremden PR.** Das ist
  die Weiche in #442, nicht die Tat dieses Laufs.
- **#823 nicht aus dem Draft geholt.** Es ist der PR dieses Routine-Stranges
  und grün — aber ein Schritt Richtung Merge ohne Freigabe. Stattdessen ein
  Kommentar am PR, der nennt, welche seiner Messwerte dieser Lauf überholt hat,
  damit ein Reviewer nicht auf alte Zahlen schaut (Regel 88).

## 10. Bedingungen dieses Laufs

Read-only am Arbeitsbaum außer dieser Plan-Datei auf
`claude/upbeat-mayer-bym28u`. Kein Docker (nicht vorhanden), keine E2E-Läufe.
Alle Web-Messungen sequenziell, ein Schreiber im Baum (Regel 31/76). Jeder
Exit-Code ohne Pipe gelesen (Regel 94). Jede merge-base ausdrücklich auf
nicht-leer geprüft, nach einmaligem `--unshallow` (Regel 90). Jeder CI-Zustand
über den Run zum HEAD-SHA, `status` und `conclusion` getrennt (Regel 91). Jeder
Sub-Agent-Rücklauf vor dem Schreiben selbst nachgemessen.
