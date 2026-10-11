# Backlog-Aufbereitungslauf 47 (2026-10-11)

Basis: `origin/main` @ `3b4a1783` · Vorgänger-Basis: `6858f707` (Lauf 46) ·
Warteschlange: #442 · Auftrag: jedes offene Issue gegen die Norm
**Agent-ready Arbeitspaket** prüfen, Belegbares selbst entscheiden und mit Beleg
ins Issue schreiben, Urteilsfragen als Kommentar mit drei Optionen zurückgeben,
danach die Warteschlange neu ordnen und in Wellen gruppieren.

> **Umgebungsgrenze, zweiter Lauf in Folge:** der MCP-Server der eigenen AgentDB
> (`Who2Be---Coder`) liefert über `ToolSearch` **keine** Werkzeuge. Persona und
> Playbook-Katalog lagen im System-Prompt vor, aber `fetch_playbook`,
> `search_memory`/`save_memory` und `record_usage`/`submit_feedback` waren nicht
> aufrufbar. **Der Lauf ist nach dem in #442 kodifizierten Verfahren gefahren,
> nicht nach dem geladenen Playbook.** Die Prüfnorm ist aus
> `.github/PROJECT.md` §Constraints rekonstruiert: `agent-ready` wird nur
> vergeben, wenn **Outcome**, **prüfbare Akzeptanzkriterien**, **Out-of-Scope**
> und **exakte Verifikations-Kommandos** tatsächlich im Issue stehen.

## Ausgangslage

25 Commits seit `6858f707` (#895–#920), Spanne 20 h 53 min → **1,20
Commits/Stunde**, die dichteste der Messreihe. `main` ist **grün** (Lauf
`38088889802`, `completed`/`success`); der in Lauf 46 noch laufende Lauf
`38007771495` ist inzwischen `success`.

Offene Issues: **elf** zu Beginn, **zwölf** am Ende (#923 in diesem Lauf
geschnitten). Offene PRs: **fünfzehn** (Lauf 46: zwölf; neu #922, #921, #896).

## Der zentrale Fund: eine Weiche war nie eine Owner-Frage

Die Concurrency-Weiche („wie bekommt jeder `main`-Commit wieder einen
CI-Spruch?") stand seit **Lauf 44** offen und ist dreimal verschieden gedeutet
worden:

| Lauf | Deutung | Ergebnis |
|---|---|---|
| 44 | Vier fehlende Sprüche → hängender `e2e`-Job; **#849** geschnitten | Fund richtig |
| 45 | „Merge-Dichte allein genügt" → Option A für widerlegt erklärt, #849 eingeschränkt | falsch (→ Regel 105) |
| 46 | Widerlegung widerlegt, Weiche **neu gestellt**, Ursache „ungemessen" | richtig, aber offen |
| 47 | **`created_at` gegen `run_started_at` gelesen** | 🟢 **Weiche geschlossen** |

**Die Messung:** über **alle 40** `main`-Push-Läufe der aktuellen API-Seite
(2026-10-09 09:40 bis 2026-10-10 21:46 — die Zeiträume von Lauf 46 **und** 47)
gilt `created_at == run_started_at` bei **jedem einzelnen**. Dazu **40 ×
`success`**, **0 × `cancelled`**, alle `run_attempt: 1`.

**Kein `main`-Lauf hat jemals gewartet.** Damit entfällt die Grundlage der
Verdrängungs-Lesart: der Mechanismus „GitHub hält einen laufenden **und einen
wartenden** Lauf, ein neuer Push verdrängt den wartenden" braucht einen
wartenden Lauf. Außerhalb eines Hängers gibt es ihn nicht.

**Dazu der erste echte Überlapp als Beleg statt als Schluss:** `157e80fd` wurde
um **07:30:54** gepusht — **12 min 30 s** nach dem Start des Laufs zu
`39ec4d2e` (07:18:24), und dieser Lauf lief noch **bis 07:34:52**. Der neue Push
landete also rund **vier Minuten vor dem Ende** eines laufenden `main`-Laufs.
**Beide sind `success`, keiner wurde abgebrochen.** Dazu die beiden engeren
Paare aus Lauf 46, hier gegengeprüft: **1 min 30 s** (`fc10281b`→`5c7d3571`) und
**4 min 24 s** (`4dabd967`→`732620a8`) — alle sechs Läufe `success`.

**Folge:** Option B (`cancel-in-progress: true` auf `main`) ist nicht nur
unbelegt, sie wäre schädlich — sie bricht genau die laufenden Läufe ab, die
heute ausnahmslos durchlaufen (Regel 103). **Operativ: Concurrency nicht
anfassen, #849 bauen.** Der hängende Job bleibt der einzige belegte Mechanismus,
der auf `main` einen Spruch kostet.

**Rest-Unklarheit, eingegrenzt und ohne Folgen:** die Ursache des einen
`cancelled`-Laufs `37822973287` (2026-10-08) bleibt ungemessen — **Verdrängung
während des Wartens kann es nicht gewesen sein.** Das blockiert nichts.

→ **Regel 107** vorgeschlagen: *eine Weiche, die mehrere Läufe offen steht und
mehrfach verschieden gedeutet wird, ist oft an einem Rohfeld entscheidbar, das
niemand abgefragt hat — vor dem Neustellen wird nach diesem Feld gesucht.*

## Norm-Prüfung: alle zwölf Issues einzeln

Legende: **E** = im Repo belegt, selbst entschieden · **U** = braucht Urteil.

| Issue | Outcome | Akzeptanzkriterien | Out-of-Scope | Scope-„In" | Verifikation | Verdikt |
|---|---|---|---|---|---|---|
| #849 | ✅ | 6, alle mit Schwelle/Kommando | ✅ | ✅ | ✅ | **4 von 4** |
| #632 | ✅ | ✅ mit hartem CI-Gate | ✅ | ✅ | ✅ | **4 von 4** |
| #633 | ✅ | 6, alle mit Schwelle | ✅ | ✅ | ✅ | **4 von 4** |
| #923 🆕 | ✅ | 5, mit Kommando | ✅ | ✅ | ✅ | **4 von 4** |
| #435 | ✅ | 6, **5 ohne eigene Schwelle** | ✅ | ✅ | ✅ | 3 voll — **aber `size/M`** |
| #540 | ✅ | 7, **6 ohne Schwelle/Kommando** | ✅ | 🔴 **fehlt** | ✅ | 2 voll + partial |
| #454 | ✅ | 5, **4 ohne Schwelle** | ✅ | 🔴 **fehlt** | ⚠️ „kein Testkommando" | 2 voll + 2 partial |
| #542 | 🔴 **fehlt** | 5, **0 mit Schwelle** | ✅ | 🔴 **fehlt** | ✅ | 2 voll + partial |
| #535 | 🔴 **fehlt** | 3, 1 ohne Kommando | ✅ | 🔴 **fehlt** | 🔴 **fehlt** | **1 von 4** |
| #428 | 🔴 **fehlt** | 5, **0 mit Kommando** | ✅ | 🔴 **fehlt** | 🔴 **fehlt** | **1 von 4** |
| #338 | 🔴 **fehlt** | 🔴 kein Abschnitt (4 Punkte O1–O4) | 🔴 **fehlt** | 🔴 **fehlt** | 🔴 **fehlt** | **0 von 4** |
| #442 | — | das Queue-Issue selbst | — | — | — | — |

**Querschnitts-Befund:** ein expliziter **Scope-„In" fehlt in sechs von sieben**
nicht-`agent-ready`-Issues — nur #435 hat einen. **Alle Lückenhaften außer
#454/#338 sind `size/M`** → Pflege-Regel 7: der nächste Schritt ist ein
**Zuschnitt**, kein Nachtragen von Feldern. **Deshalb sind an ihren Bodies nur
Zeiger und Zahlen repariert worden, keine Felder ergänzt.**

## Elf verrottete Zeiger und Zahlen in fünf Issues — alle repariert

Die höchste Zahl der Messreihe. **Sie sitzt überwiegend dort, wo Lauf 46 nichts
geändert hat.**

### #435 — acht Messzahlen, und Lauf 46 hatte das Issue für sauber erklärt

Lauf 46 schrieb: „An #535, #435, #542 und #338 wurde bewusst nichts geändert:
alle Zeiger und alle Dateigrößen halten, **kein Satz in diesen Bodies ist falsch
geworden**." Für die **Zeilen**-Zeiger war das richtig — sie halten bis heute
ausnahmslos. **Für die Zahlen desselben Bodies war es falsch:**

| Behauptung (2026-10-07) | gemessen 2026-10-11 |
|---|---|
| Lint 91 problems, 59 Dateien, 9 `--fix`-bar | **90**, **61** von **654**, **7** |
| 248 Testdateien / 1944 Tests | **258** / **2209** |
| Coverage 88,19 / 82,28 / 84,37 / 89,76 | **88,88 / 82,82 / 85,4 / 90,62** |
| Branches-Abstand 3,28 | **3,82** |
| Waisen 159 | **160** |
| Collection 3042 | **3461** |
| Fragmente 215 | **289** |

→ **Regel 106** vorgeschlagen: *ein Zeiger-Check, der nur Zeilennummern prüft,
lässt die Zahlen durch, auf die sich derselbe Body beruft — und eine Datei, die
lange stillstand, verrottet ihre Zahl besonders leise.*

Dazu in #435 korrigiert: die Behauptung „`deploy/dokploy/**` kommt in `.github/`
und `scripts/` **nicht** vor" ist wörtlich falsch (drei Treffer in `.github/`:
`PROJECT.md:92`, `dependabot.yml:122`/`:137` — der letzte ein echter
Dependabot-Eintrag, **deshalb existieren #683/#686 überhaupt**). Die tragende
Aussage hält, genauer begründet: `dokploy` kommt in **keinem Workflow** vor
(0 Treffer), Dependabot hebt also Versionen, **kein CI-Job validiert den Stack**.

### #454 — vier von fünf Wegweisern zeigten auf fremden Inhalt

Für ein `human-only`-Paket, dessen einziger Wert die Wegweisung ist, die
teuerste Verrottung des Bestands.

| behauptet | tatsächlich |
|---|---|
| `deploy.yml:78-107` „Job und benötigte Namen" | liegt im **`debounce`**-Job; `deploy` beginnt `:205`, Namen `:228-248` |
| `deploy/hetzner/README.md:295-312` | Debounce-Fenster; Deploy-Bedingung `:322`/`:330`, Variablen `:377-378` |
| `RUNBOOK.md:167-213` „Erste Inbetriebnahme" | At-Rest-Verschlüsselung + SSH-Hardening; die Überschrift liegt auf **`:438`** |
| `RUNBOOK.md:704` „Protokoll …, noch leer" | Access-Log-Rotation. **Die Stelle existiert gar nicht** — `:1826` sagt, das Protokoll werde **betreiberseitig** geführt, **nicht im Repo** |
| `router.py:276-314` „Betreiber-Kennungen" | `CheckoutRequest`/`mollie_webhook`/`create_checkout`; Allowlist `:351`, Funktionen `:354`/`:364`, Endpunkt `:402` |

Der vierte ist der schwerste: er hat den Owner auf ein leeres Protokoll im Repo
verwiesen, das es nach Absicht des Runbooks nie geben soll. **Ein falscher Zeiger
kostet Suchzeit; ein Zeiger auf eine Sache, die es nicht gibt, kostet Vertrauen
in die ganze Liste.** Die beiden Zeiger, die Lauf 46 repariert hat (`:185`,
`:214`), halten.

### Die übrigen

- **#540 / #535:** der Caddy-Pin ist zum **vierten** Mal gewandert:
  `:342` → `:347` → `:352` → `:414` → **`:439`**;
  `deploy/hetzner/who2be/docker-compose.yml` ist **4×** auf `main` bewegt
  (#919, #917, #914, #910) und von **535 auf 560** Zeilen gewachsen.
  🟢 **Regel 98 hat hier funktioniert:** weil Lauf 46 die Gesamtzeilenzahl
  mitführte, fiel die Abweichung sofort auf.
- **#535 / #428:** Collection 3042 → **3461**, Fragmente 215 → **289**.
- **#632 / #633:** Waisen-Baseline **159 → 160** — und zwar **weil
  `orphan-baseline.json` nach acht unbewegten Läufen erstmals bewegt wurde**
  (`961cedc2`, #895). **Die Ruhe der Datei war der Grund, warum es niemand
  nachmaß.**
- **#338:** „alle 19 `uses:` SHA-gepinnt" ist als historische Aussage richtig,
  als Gegenwartszahl falsch (heute **33** gepinnte `uses:`, **keine** unpinnte).
  **Bewusst nicht geändert** — `human-only`, Formulierung historisch korrekt.

### Nebenfund: `.github/PROJECT.md` ist selbst dreifach verrottet

`:90-92` behauptet, alle drei Stacks pinnten **`supabase/gotrue:v2.196.0`** auf
`docker-compose.yml:63`, `deploy/hetzner/supabase/docker-compose.yml:63` und
`deploy/dokploy/docker-compose.yml:81`. Gemessen: die Version ist
**`v2.197.0`**, die beiden letzten Zeiger lauten **`:92`** und **`:82`**.

**Die Datei, die laut Pflege-Regel 4 „das Warum" trägt, ist an der Stelle falsch,
die die zwei obersten Pakete der Warteschlange beschreibt** — und sie wird seit
sechs Tagen von **PR #823** gehalten, einem Draft, der genau solche Zeiger
reparieren wollte und inzwischen 86 Commits zurückliegt. **Deshalb in diesem
Lauf nicht angefasst** (eine PR-Belegung ist eine Sperre) und als Argument in
die Weiche zu #823 geschrieben.

## Selbst entschieden (Beleg statt Rückfrage)

1. **Die Concurrency-Weiche geschlossen** — siehe oben. Eingetragen in #849
   (Reichweite ohne Vorbehalt), #633 (Hinweis) und #442 (Weiche als erledigt).
2. **#923 geschnitten** (Pflege-Regel 34): der `concurrency`-Kommentar
   (`ci.yml:8-11`) beschreibt eine „run_id-Gruppe"; `:13` liefert
   `ci-CI-refs/heads/main`, eine **Ref**-Gruppe. `grep -c run_id` → **1**.
   Der Kommentar hat drei Läufe lang die Fehldeutung getragen (Regel 35).
   Vier Pflichtfelder, `agent-ready`, `size/S`. **Empfehlung im Body: mit
   Welle D fahren**, weil `.github/**` nicht auf der Doku-Allowlist steht
   (`ci.yml:75`) und ein Kommentar-PR sonst den vollen Satz von zwölf Jobs für
   sich allein kostet.
3. **Elf Zeiger und Zahlen repariert** in #540, #535, #435, #428, #454 — plus
   die Basiswerte in #849, #632, #633.
4. **Den Lint-Rückgang vollständig zugeordnet:** 94 → **90**, ausschließlich
   `classnames-order` (22 → 18), alle vier entfallenen Meldungen in
   `features/playbooks/components/PlaybookListToolbar.tsx`, das **#895** auf
   `ListFilterBar` umgestellt hat. **Die `--fix`-baren fallen von 9 auf 7 und
   liegen jetzt in vier Dateien statt fünf** — Welle F wird von allein kleiner.
5. **Die E2E-Zahl 26/35 unabhängig neu hergeleitet** (Klammer-Matching je
   Testkörper, Schleifen expandiert, Direktiven ausgeschlossen) — **gegen eine
   `scroll-guard.spec.ts`, die zweimal auf `main` bewegt wurde** (#906, #904).
   Siebter Lauf, und der erste, in dem die Zahl etwas beweist statt
   stillzustehen. Ohne `E2E_EDITION=cloud`: **24 von 33**.

## Braucht eine Owner-Antwort — acht Weichen (eine weniger als in Lauf 46)

Alle stehen mit drei Optionen und Empfehlung in #442 und werden nicht erneut
gestellt (Pflege-Regel 9). Kurzfassung der Veränderungen:

1. ~~Concurrency~~ — **geschlossen, siehe oben.**
2. **Gate-alte grüne PRs mergen?** (Empf. B) — 🟢 **zweiter freier Durchgang:
   #922 ist gate-aktuell, 18/18 grün mit null `skipped`, 0 Commits hinter
   `main`.** Acht von fünfzehn PRs sind gate-alt.
3. **Gilt der Vertrag für Tracking-Issues?** (Empf. B) — unverändert; der
   Norm-Befund ist diesen Lauf gegen alle zwölf Issues gemessen, **neu inklusive
   Scope-„In"** (fehlt in sechs von sieben).
4. **`audit` im Required Check?** (Empf. A/C) — **Frist 22 Tage**
   (`osv-scanner.toml:11`). #831 bleibt der lebende Fall. **Neu: #923 fährt
   mit.**
5. **Coverage-Boden anheben?** (Empf. B) — 🟢 **zweiter Anstieg in allen vier
   Werten**, Abstand 3,82. Fehlermodus bleibt.
6. **Caddy-Versions-Widerspruch** (Empf. A, C als Folge) — startbar; Beleg-Zeiger
   zum vierten Mal nachgezogen (`:439`).
7. **ESLint-Warnungen** (Empf. B/C) — 🟢 Reihe **erstmals gefallen** (94 → 90),
   `--fix`-bar 9 → 7 in vier Dateien.
8. **MB/MiB in `plans.md:28-29`** — ein Ja/Nein. Unverändert belegt.
9. **#823 schließen und frisch reparieren?** (Empf. A) — 🔴 **deutlich stärkere
   Begründung:** 86 Commits zurück, `RUNBOOK.md` erneut 2× bewegt, der
   Compose-Zeiger seither zweimal weiter verrottet — **und `PROJECT.md` ist
   selbst dreifach verrottet.** Weiter die einzige Datei-Sperre, die aus einem
   Draft folgt.

Dazu unverändert: **#540** (Mechanismus + Verifizierbarkeit) und **#542**
(`human-only`, Rechnungsmodell/USt).

## Neue Reihenfolge

Kriterien unverändert: **1** harte Abhängigkeit → **2** Owner-Vorgabe →
**3** Fundament vor Fläche → **4** Inventar vor Zuschnitt → **5** bei
Gleichstand das kleinere.

1. **#849** — Timeouts in `ci.yml` _(Kriterium 3, bei Gleichstand 5)_. Dritter
   Lauf ohne Sperre, Datei frei **und** unbewegt, keine offene Frage — **und
   erstmals mit vollständig belegter Reichweite.**
2. **#632** — Passkey registrieren _(Kriterium 3)_. Öffnet #633. Zweiter Lauf
   ohne Vorbehalt.
3. **#633** — Step-up mit Passkey _(Kriterium 1)_. Nach #632 + Container-Laufzeit.
4. **`audit`-Trennung + #923** _(Kriterium 2 offen, dann 5)_. Beide schreiben
   nur `ci.yml`; **gemeinsam ein CI-Satz statt zwei.** Frist 22 Tage.
5. **Caddy-Widerspruch** _(Kriterium 2 offen)_. Drei Dateien gegen eine → hinter 4.
6. **Die 7 `--fix`-baren Lint-Warnungen** _(Kriterium 5)_. Kleinster
   schneidbarer Posten, jetzt noch kleiner.
7. **#540** _(Kriterium 1 offen, dreifach)_.

**Präferenz, nicht Kriterium:** **#922 mergen** — gate-aktuell, 18/18 grün,
**0 Commits hinter `main`**, ein Klick. Danach #825.

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | #632 | allein im Vitest-Baum; `locales` 9× bewegt, `orphan-baseline.json` 1× |
| **B** | #633 | nach A; braucht Docker; `e2e` 2× bewegt (beide an `scroll-guard.spec.ts`) |
| **C** | #849 | nur `ci.yml`; **A ∥ C ist das echte Parallel-Paar** (zwei Stacks) |
| **D** | `audit`-Trennung **+ #923** | `ci.yml`; nicht mit C; danach alle Zeiger neu messen |
| **E** | Caddy | `Caddyfile` + 2 `.sh` + `ci.yml`; nicht mit C oder D |
| **F** | 7 Lint-Fixes | vier Dateien, frei und unbewegt; nicht mit A/B |
| **G** | Coverage-Boden | nur `vite.config.ts:82-85`; selber Vitest-Baum wie A/B/F |
| **H** | Merges — **#922 zuerst**, dann #825, #921, Protokoll-PRs, #831, #824, #827 | parallel zu allem; #823 erst nach Weiche 9 |
| **I** | #682/#683/#686 | Branch-Update; 227 Commits zurück |
| **J** | MB/MiB | ein Satz; parallel zu allem |

**Keine Welle:** C/D/E gegeneinander (dieselbe `ci.yml` — **#923 gehört IN D**) ·
F/G gegen A/B (ein Vitest-Baum) · B vor A · #540 gegen alles ·
#674 gegen #824.

## Messwerte

Sequenziell erhoben, ein Schreiber je Baum (Regel 31/76); Web und Python sind
verschiedene Stacks und liefen nebeneinander. Node **v22.22.0**.

| Messung | Ergebnis | Lauf 46 |
|---|---|---|
| `npm run lint` | Exit 0, **90** problems, 0 errors, 61/654 Dateien, 8 Regeln, **7** `--fix`-bar | 94 / 62 / 9 |
| `npx tsc -b` | Exit 0, Ausgabe leer | Exit 0 |
| `npm run test:coverage` | Exit 0, **258 Dateien / 2209 Tests** | 253 / 2162 |
| → Statements | **88,88 %** (9977/11225) | 88,78 |
| → Branches | **82,82 %** (6825/8240) | 82,73 |
| → Functions | **85,4 %** (2914/3412) | 85,2 |
| → Lines | **90,62 %** (9249/10206) | 90,5 |
| `npm run i18n:check` | Exit 0, keine neue Waise, **160** bekannt | 159 |
| `uv run pytest --collect-only -q` | **3461** Tests, 135 Zeilen unter `packages/billing/` | 3362 |
| `uv run ruff check .` | Exit 0, 0 Funde | 0 |
| `uv run mypy .` | Exit 0, 0 Funde in **595** Dateien | 575 |
| `changelog_fragments.py check` | Exit 0 (ohne Pipe), **289** Fragmente | 265 |
| `docker info` | **Exit 1** — 23. Lauf in Folge | Exit 1 |
| `grep -c timeout-minutes ci.yml` | **0**, über `yaml.safe_load` für alle 12 Jobs | 0 |
| shallow? | `true`, nach `--unshallow` **1522** Commits | 1497 |

`ci.yml` **1212** Zeilen, letzte Änderung `11a243ff` (#839, 2026-10-06 17:25 UTC),
auf `main` seither **0** Commits.

**Alle fünfzehn PRs mergen konfliktfrei** (`git merge-tree --write-tree` → rc 0,
einzeln gemessen), alle fünfzehn merge-bases rechnen (nicht-leer geprüft,
Regel 90).

## Geschrieben

**#849**, **#632**, **#633** (Stand nachgezogen, Concurrency-Weiche als
beantwortet eingetragen) · **#540**, **#535**, **#435**, **#428**, **#454**
(Zeiger und Messzahlen repariert) · **#442** (Body neu geordnet + Kommentar zur
geschlossenen Weiche) · **#923** (neu angelegt).

**Bewusst nicht geändert:** **#542** (keine Zeilen-Zeiger, nichts Falsches) und
**#338** (`human-only`, die einzige schiefe Zahl ist historisch korrekt
formuliert). **Kein Code angefasst, kein Issue geschlossen, kein Label an einem
bestehenden Issue gewechselt.**

## Vorgeschlagene Regeln

- **106** — *Ein Zeiger-Check, der nur Zeilennummern prüft, lässt die Zahlen
  durch, auf die sich derselbe Body beruft — und eine Datei, die lange
  stillstand, verrottet ihre Zahl besonders leise.* (Gefangen an #435 und an
  `orphan-baseline.json`.)
- **107** — *Eine Weiche, die mehrere Läufe offen steht und mehrfach verschieden
  gedeutet wird, ist oft an einem Rohfeld entscheidbar, das niemand abgefragt
  hat — vor dem Neustellen wird nach diesem Feld gesucht.* (Gefangen an der
  Concurrency-Weiche, drei Läufe alt.)
