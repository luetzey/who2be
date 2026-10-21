# Backlog-Aufbereitungslauf 43 — 2026-10-07

**Basis:** `main` @ `4a9918ae` (8 Commits seit der Lauf-42-Basis `6b8ef201`).
Alle Zahlen in diesem Lauf sind gegen `origin/main`-Refs gemessen, nicht
fortgeschrieben. Auftrag: jedes offene Issue gegen die Norm
**Agent-ready Arbeitspaket** prüfen, Belegbares selbst entscheiden und mit
Beleg ins Issue schreiben, Urteilsfragen als Kommentar mit drei Optionen und
Empfehlung zurückgeben, danach die Warteschlange (#442) neu ordnen und in
Wellen gruppieren.

## Ausgangslage

Lauf 42 (2026-10-06) fand zehn offene Issues, eines startbar, und meldete als
zentralen Fund ein in #535 und #540 gekreuztes Zeiger-Paar in `core/config.py`
(Regel 97). Er hat am Ende ein neues Issue angelegt: **#832**, weil
`GHSA-68fv-2mgg-jv7q` (`source-map-js@1.2.1`) den `audit`-Job und damit das
einzige Merge-Gate des Repos geschlossen hatte.

Seither sind **8 Commits** gelandet:

| Commit | Inhalt |
|---|---|
| `0dea7fb7` (#833) | `source-map-js` 1.2.1 → 1.2.2 — **erledigt #832** |
| `f1222b21` (#830) | ADR-0056 Paket 3: Markdown-Default für vier lesende MCP-Werkzeuge |
| `91bcb165` (#834) | ADR-0056 Paket 4: acht weitere Werkzeuge |
| `36faad8b` (#835) | ADR-0056 Paket 5: Doku und Werkzeugübersicht |
| `40045b75` (#836) | fastmcp 3.4.7 → **4.0.11** — ersetzt #826 |
| `60902c0b` (#837) | Payload-Budget misst die Draht-Form von `tools/list` |
| `11a243ff` (#839) | **Gitleaks als Pflichtprüfung (Job `secrets` in `all-green`)** |
| `4a9918ae` (#838) | ADR-0054 Nachtrag, Weichen S1–S14 |

## Die drei Befunde dieses Laufs

### 1. 🔴 Ein Zeiger kann seine Zeile behalten und seinen Job verlieren

**Der zentrale Fund.** PR #839 hat `ci.yml` um den Job `secrets` erweitert.
Der Diff ist **rein additiv** — 120 Einfügungen, 0 Löschungen, vier Hunks —
und der große Block sitzt genau bei `:802`:

```
$ git diff --unified=0 6b8ef201..origin/main -- .github/workflows/ci.yml | grep '^@@'
@@ -801,0 +802,112 @@    <- der ganze Job `secrets`
@@ -988,0 +1101 @@       <- sein Eintrag in all-green.needs
@@ -1003,0 +1117 @@      <- SECRETS_RESULT im Auswertungs-Step
@@ -1086,0 +1201,6 @@     <- expect secrets … success
```

Damit verschiebt sich **alles ab der alten Zeile 802 um +112**:

| Zeiger | vorher | heute | Prüfung |
|---|---|---|---|
| `ci.yml` Zeilen | 1092 | **1212** | `wc -l` |
| `audit:` | `:802` | **`:914`** | 🔴 **`:802` trägt heute wörtlich `  secrets:`** |
| `all-green:` | `:955` | **`:1067`** | Job-Kopf |
| `needs:` | `:978` | **`:1090`** | |
| needs-Einträge | `:979-988`, zehn | **`:1091-1101`, elf** | `:1101` = `secrets` |
| Jobs im `jobs:`-Block | 11 | **12** | YAML-Parser, nicht Zeilenmuster |
| `pip-audit` | `:817` | **`:929`** | `run`-Zeile |
| `npm audit` (Step-**Name**) | `:826` | **`:938`** | |
| `license:check` | `:871` | **`:983`** | `run`-Zeile |

**Nicht gewandert, weil vor dem Einfügepunkt:** `:194` (`--cov-fail-under=85`),
`:296` (`test:a11y`), `:302` (i18n-Kommentar), `:351`/`:352`/`:367`/`:368`
(Caddy), `:383`/`:423` (`e2e`), `:438`/`:503` (`e2e-billing-cloud`), `:522`
(`e2e-mobile`), `:617` (`backup-alarm`), `:737`/`:784`/`:800`
(`changelog-guard`).

**Warum das der teuerste Zeiger-Fehlertyp bisher ist:** `:802` ist nicht leer
geworden. Es existiert, sieht weiter wie eine Job-Definition aus und gehört
jemand anderem. Jede Prüfung, die fragt „existiert die Zeile und ist sie
plausibel?", sagt **ja** und liefert den falschen Job. Regel 97 (Zeile **und**
Label prüfen) hätte es gefangen — aber nur, wenn man überhaupt nachsieht, und
bei einem rein additiven Diff sieht man keinen Grund dazu, weil sich an der
eigenen Stelle „nichts geändert hat".

→ **Regel 98**. Gegenmaßnahme: wer einen Zeiger in eine Datei setzt, die
wachsen kann, notiert **die Zeilenzahl der Datei mit**; weicht sie ab, sind
alle Zeiger dieser Datei neu zu messen. Und ein Diff mit `0` Löschungen ist
kein harmloser Diff — `--numstat` sagt nichts darüber, wie viele Adressen er
verschoben hat, `--unified=0 | grep '^@@'` sagt es.

**Korrigiert in:** #428 (neun Zeiger), #632 (einer), #435 (einer, an **zwei**
Stellen desselben Bodies — Regel 58 präventiv angewandt). #832 trug zwei
davon; dort als Abschluss-Kommentar notiert statt im Body korrigiert, weil
das Issue geschlossen wird.

### 2. 🔴 Ein grüner Required Check kann älter sein als das Gate, für das er bürgt

`secrets` hängt **ohne `needs: changes` und ohne `if:`** in `all-green`
(`expect secrets "$SECRETS_RESULT" success`, `:1205`; die Wahrheitstabelle
`scripts/ci/test_all_green_matrix.py:198-200` kennt den Fall) — bewusst, weil
ein Geheimnis in einer Doku-Datei genauso öffentlich ist wie eines im Code.

**#839 ist am 2026-10-06 17:25 UTC gemergt. Die grünen Läufe der drei
mergebaren Dependabot-PRs sind von 04:18–05:51** und tragen je **14
Check-Runs ohne `secrets`**:

| PR | `all-green` | Lauf vom | Check-Runs | `secrets` dabei? |
|---|---|---|---|---|
| #827 | ✅ | 2026-10-05 04:31 | 14 | 🔴 nein |
| #825 | ✅ | 2026-10-06 05:51 | 14 | 🔴 nein |
| #824 | ✅ | 2026-10-05 04:19 | 14 | 🔴 nein |
| #823 | ✅ 17/17 | 2026-10-05 00:55 | 17 | 🔴 nein |

GitHub betrachtet den Required Check als erfüllt — der Haken bürgt für zehn
Jobs, verlangt werden elf.

**Dazu eine zweite, unabhängige Veraltung, und die ist schärfer.** Gemessen:

```
source-map-js auf pr824            -> 1.2.1   (GHSA-68fv-2mgg-jv7q, High, CVSS 8.7)
source-map-js auf main             -> 1.2.2
source-map-js im Merge-Ergebnis    -> 1.2.2   (git merge-tree --write-tree)
"libc"-Felder im Merge-Ergebnis    -> 6       (unverändert)
```

Daraus folgen **zwei wahre Sätze, die in verschiedene Richtungen zeigen**:
#824 jetzt zu mergen ist **sicher**, weil der Text-Merge `main`s `1.2.2`
behält — und sein grüner Haken sagt das **nicht**, weil er gegen einen Baum
mit `1.2.1` erzeugt wurde. **Die Sicherheit kommt aus git, nicht aus dem
Check.**

→ **Regel 99**. Als Weiche mit drei Optionen an #442 gestellt, Empfehlung
**B** (vorher Branch-Update, dann mergen). **Nicht gezogen** — ein
Schreibvorgang an einem fremden PR ist kein Teil eines Aufbereitungslaufs,
und ein Merge ist eine Owner-Entscheidung.

### 3. 🔴 Eine Fläche kann frei von offenen PRs und trotzdem bewegt sein

`apps/web/e2e/review-gate.spec.ts` — die Fläche von #633 — ist über alle neun
offenen PRs frei **und** seit Lauf 42 von `main` aus geändert (#830: ADR-0056
hat den Antwort-Default der lesenden MCP-Werkzeuge auf Markdown umgestellt,
der Spec parste ihn als JSON). Dasselbe gilt für `apps/mcp/**` und
`packages/models/**`, die #830/#834/#835/#836/#837 stark bewegt haben.

**„Frei" hieß in der Warteschlange bisher „kein offener PR hält es" — das ist
eine Aussage über Sperren, nicht über Ruhe.**

→ **Regel 100**. Gegenmaßnahme: zur Kollisionsprüfung über offene PRs gehört
`git log --oneline <Basis>..origin/main -- <Fläche>`. Eine Belegung durch
einen PR ist eine **Sperre**; eine Bewegung auf `main` ist **keine Sperre**,
macht aber jede Zeilenangabe von gestern zu einer Vermutung.

## Arbeitspakete dieses Laufs

### A — selbst entschieden (das Repo belegt es)

1. **#832 geschlossen** (`completed`). Es wurde nie gezogen und ist trotzdem
   fertig: **#833 (`0dea7fb7`) hat es 33 Minuten nach seiner Anlage erledigt.**
   Alle fünf Akzeptanzkriterien einzeln gegengeprüft — `1.2.2` aufgelöst (genau
   ein Eintrag), **sechs `libc`-Felder vor und nach dem Commit**, `--numstat`
   **3/3**, `audit` grün mit OSV-Step `success`, vier Web-Gates bei
   Basiswerten. Der Weg war der im Issue empfohlene: kein `overrides`-Block,
   `package.json` unberührt.
2. **#535 Akzeptanzkriterium 2 belegt — nach sieben Läufen.** Lauf 42 schrieb,
   die `BillingPanel`-Zahlen seien „seit sechs Läufen nie gegengeprüft".
   Dieser Lauf hat sie gegengeprüft: **zehn Größen** zwischen `plans.py`,
   `entitlement.py`, `plans.md:28-29` und `BillingPanel.tsx:40-41`, alle
   deckungsgleich (Tabelle im Issue). Das Kriterium ist abgehakt.
3. **#428, #632, #435 Zeiger korrigiert** (elf Stellen, siehe Befund 1).
4. **#540, #535 Statusblöcke fortgeschrieben** — Zeiger einzeln bestätigt,
   Fristen und Alter nachgezogen, die Zeiger-Korrektur aus Lauf 42
   (`config.py:83`/`:159`) als haltend bestätigt.
5. **#442 neu geordnet** — Reihenfolge, Wellen, Kollisionen, Sammelpunkte
   gegen den neuen Stand; Regeln 98/99/100 ergänzt.

### B — braucht eine Owner-Antwort

| Frage | Alter | Ort |
|---|---|---|
| 🔴 **NEU** — Darf ein PR mergen, dessen grünes `all-green` von einer älteren CI-Definition und CVE-Datenbank stammt? (Empf. **B**) | 0 Tage | #442 |
| Gilt der Arbeitspaket-Vertrag auch für Tracking-Issues? (Empf. **B**) | 6 Tage | #442 |
| Bleibt `audit` im Required Check? (Empf. **A**, **C** als Paket) | seit Lauf 36 | #442 |
| Wird der Coverage-Boden angehoben? (Empf. **B**) | 3 Tage | #442 |
| Caddy-Versions-Widerspruch (Empf. **A**) | seit Lauf 35 | #442 |
| Die 91 ESLint-Warnungen (Empf. **B**) | seit Lauf 36 | #442 |
| 🔴 **NEU** — Sind Zehnerpotenzen in `plans.md:28-29` Absicht? (Ja/Nein) | 0 Tage | #442, #535 |
| #540 — Mechanismus **und** Prüfbarkeit | 18 Tage | #540 |

### C — als Ein-Zeilen-Posten notiert, ohne eigenes Issue (Regel 34)

**Eine Verkaufszahl steht in der falschen Einheit — in derselben Datei, die
sie ein paar Zeilen weiter exakt nennt.** `docs/licensing/plans.md:28`/`:29`
schreibt **100 MB** und **10 GB**; der Code rechnet `100 * 1024 * 1024` und
`10 * 1024 * 1024 * 1024`, also **100 MiB (104,86 MB)** und **10 GiB
(10,74 GB)**. Die Quellen-Fußnote derselben Datei (`:37`) schreibt es korrekt
als MiB/GiB.

**Die Richtung ist zugunsten des Kunden** — es wird weniger versprochen als
gegeben —, deshalb kein falsches Versprechen und kein Blocker. **Nicht
eigenmächtig geändert:** Zehnerpotenzen in einer Sales-Tabelle können Absicht
sein. Braucht ein Ja/Nein, dann ist es ein Satz.

## Neue Reihenfolge

Kriterien unverändert: harte Abhängigkeit → Owner-Vorgabe → Fundament vor
Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.

1. **#632** _(Kriterium 3)_ — Fundament vor Fläche, öffnet #633. Das einzige
   heute startbare Paket, **siebter Lauf in Folge ohne Vorbehalt**.
2. **#633** _(Kriterium 1)_ — nach #632, plus Container-Laufzeit. Zusätzlich:
   die eigene Fläche gegen `main` nachschlagen (Regel 100).
3. **Die Trennung des `audit`-Jobs** _(Kriterium 2 offen, dann 5)_ — schreibt
   nur `ci.yml`, frei. **Frist 26 Tage, zweiter Vorfall eingetreten.**
4. **Der Caddy-Versions-Widerspruch** _(Kriterium 2 offen)_ — drei Dateien
   plus `ci.yml`, deshalb hinter Position 3.
5. **Die 9 `--fix`-baren Lint-Warnungen** _(Kriterium 5)_ — kleinster
   schneidbarer Posten, fünf freie Dateien.
6. **#540** _(Kriterium 1 offen, dreifach)_.

**Nicht in der Reihenfolge, obwohl klein:** der Coverage-Boden (vier Zeilen,
hängt an Weiche 4) und die MB/MiB-Zeile (ein Satz, hängt an einem Ja/Nein) —
Regel 8/9.

## Wellen

| Welle | Inhalt | Warum eigenständig |
|---|---|---|
| **A** | #632 | Web-Stack allein; `features/settings/**` auch gegen `main` unbewegt |
| **B** | #633 | nach A; `e2e/**` inkl. `helpers/auth.ts`; braucht Docker |
| **C** | `audit`-Trennung | nur `ci.yml`, anderer Stack — **A + C ist das einzige echte Parallel-Paar** |
| **D** | Caddy-Widerspruch | Caddyfile + 2 `.sh` + `ci.yml` — nicht mit C |
| **E** | 9 Lint-Warnungen | fünf freie Dateien — nicht mit A oder B (ein Vitest-Baum) |
| **F** | Coverage-Boden | nur `vite.config.ts:82-85` — selber Vitest-Baum wie A/B/E |
| **G** | fünf Branch-Updates + Merges | kein Repo-Paket, Klicks; **#823 zuerst**, **#824 vor jedem #674-Rebase** |
| **H** | drei Redis-Einzeiler | Branch-Update; 152 Commits hinter `main` |
| **I** | MB/MiB-Zeile | nur `plans.md:28-29`, in keinem Stack — parallel zu allem |

**Sechs Dimensionen** (die sechste ist neu): Dateien · Bäume ·
Messgrundlagen · Werkzeug-Zwischenstände · mergebarkeit der Träger-PRs ·
**und ob die Fläche von `main` aus bewegt wurde, obwohl kein PR sie hält**.

## Messwerte

Einzeln und sequenziell erhoben (ein Schreiber im Baum, Regel 31/76), Node
**v22.22.0**:

| Messung | Ergebnis | vorher |
|---|---|---|
| `npm run lint` | Exit 0, **91 problems, 0 errors** (59 Dateien, 8 Regeln, 9 `--fix`-bar) | 91 — **zweiter Stillstand** |
| `npx tsc -b` | Exit 0 | — |
| `npm run test:coverage` | Exit 0, **248 Dateien, 1944 Tests**; 88,19 / 82,28 / 84,37 / 89,76 | identisch |
| `npm run i18n:check` | Exit 0, 159 bekannte Waisen (geteilte Liste, für **beide** Locales gemeldet) | identisch |
| `uv run pytest --collect-only -q` | **3042** Tests, Billing in der Collection | 3022 |
| `changelog_fragments.py check` | Exit 0, **215** Fragmente (ohne Pipe, Regel 94) | 207 |
| `docker info` | **Exit 1** | Exit 1 |
| `git rev-parse --is-shallow-repository` | `true`, 50 Commits; nach `--unshallow` **1447** | **sechster Lauf** |

🔴 **Die vier Web-Zahlen sind identisch zu Lauf 42 — und die Begründung von
Lauf 42 wäre hier falsch gewesen.** Lauf 42 schrieb „die Commits fassen keinen
Web-Pfad an". Dieser Zeitraum fasst **zwei** an
(`apps/web/e2e/review-gate.spec.ts`, `apps/web/package-lock.json`), der
CI-Job `web` lief scharf. **Die Zahl steht still, weil keiner dieser Pfade im
`include` der Unit-Coverage liegt** — „kein Web-Pfad" ist die bequeme
Erklärung, „kein Pfad, den die Unit-Suite einsammelt" die richtige. Regel 12
gilt auch für die Begründung einer Zahl, nicht nur für die Zahl.

### Unabhängig neu hergeleitet statt übernommen

**Die E2E-Zahl von #633: 26 von 35 Testkörpern.** Gemessen über alle acht
Specs: **34 `test(`-Zeilen, davon 25 mit `createUser`**; die Schleife auf
`scroll-guard.spec.ts:236` expandiert `:237` zu **zwei** Körpern, und dieser
Körper nutzt `createUser` (`:257`) → **35 Körper, 26 über `createUser`**. Im
ganzen `e2e/`-Baum: kein `.each`, kein `test.describe.skip`, kein `.fixme`,
kein `.only`; die einzige Direktive ist `billing.spec.ts:43`. **Ohne
`E2E_EDITION=cloud`: 33 / 24.** Dritter Stillstand, erstmals von Grund auf
nachgerechnet statt fortgeschrieben.

## Der Lauf hat auch eine Lesefalle gefunden

**Ein roter Lauf ist keine Aussage über den Job, den man wissen will.** Der
`main`-Lauf zu `0dea7fb7` — dem `source-map-js`-Fix selbst — hat
`conclusion: failure`, und **`audit` war darin grün** (OSV-Step `success`).
Rot waren `e2e-mobile (mobile-iphone-13)` und `e2e-mobile (mobile-320)`, beide
im Step 5 „Compose up (build + wait healthy)" nach **9 Sekunden**;
`e2e-mobile (tablet-ipad-gen-7)` im selben Run **grün**. Die vier folgenden
`main`-Läufe sind vollständig grün — der Docker-Hub-Transferfehler ist erneut
als transient belegt, **diesmal auf `main` selbst**.

Wer den Lauf liest statt den Job, hält einen Fix für gescheitert, der
gegriffen hat. → Regel 81 von der anderen Seite.

## Eine doppelte Belegung hat sich in die gute Richtung aufgelöst

Lauf 42 meldete `uv.lock` erstmals von **zwei** PRs gehalten (#825 grün, #826
rot auf `python`) und empfahl, #826 zu schließen und als Issue zu schneiden.
**Stattdessen ist der Sprung als eigener PR #836 (`40045b75`, fastmcp 3.4.7 →
4.0.11) gelandet** — ein frischer Stand gegen `main` nach ADR-0056 statt eines
Nachziehens, mit sechs Modulen, die den Antworttyp jetzt unter
`TYPE_CHECKING` aus derselben Quelle wie der TestClient importieren.
`uv.lock` trägt wieder nur #825.

**Lehre:** eine doppelt belegte Stelle kann sich auflösen, indem die Sache
anders gelöst wird als der Vorschlag es wollte. Regel 84 und 95 sind auch
hier einseitig — der Zustand eines Sammelpunkts wird gemessen, nicht
prognostiziert, in keine Richtung.

## Was der Lauf nicht tut

Kein Code an den Issues, kein Branch für sie, kein Issue-Claim, **keine neuen
Issues** (das wäre „GitHub-Artefakt anlegen & pflegen"). **Kein
Branch-Update, kein Merge, kein umgelegtes Draft-Flag** — ein Schreibvorgang
an einem fremden PR ist kein Teil eines Aufbereitungslaufs. Belegt ist
trotzdem beides: dass es geht (alle neun mergen konfliktfrei,
`git merge-tree --write-tree` → rc 0) und was dabei herauskäme (die
Lockfile-Messung in Befund 2).

**#454, #338 und #542 tragen `human-only`** — der Lauf endet dort nach
Schritt 1 des Playbooks.

**`.claude/context/STATE.md` und `.github/PROJECT.md` sind bewusst NICHT
gepflegt.** Beide sind von **PR #823** belegt (grün, `all-green` 17/17,
Draft), ebenso `deploy/hetzner/RUNBOOK.md`. Ein zweiter Schreiber dort wäre
ein Konflikt an einem mergebaren PR. CLAUDE.md verlangt STATE.md pro Run;
dieser Lauf hält die Pflicht zurück, bis #823 gemergt ist, und vermerkt das
hier statt es stillschweigend zu übergehen. `DECISIONS.md` ist nicht
betroffen — dieser Lauf hat keine Entscheidung getroffen, sondern zwei
Weichen gestellt und eine Messung nachgeholt.

## Ergebnis

Ausgeführt am 2026-10-07.

| Issue | Vorher | Nachher |
|---|---|---|
| **#832** | `agent-ready`, `size/S`, offen | ✅ **geschlossen** (`completed`), fünf Kriterien einzeln belegt |
| **#428** | neun verrottete `ci.yml`-Zeiger | korrigiert, Python-Collection und OSV-Frist nachgezogen |
| **#632** | `license:check` auf `:871` | **`:983`**; Statusblock neu, E2E-Zahl neu hergeleitet |
| **#633** | Statusblock Lauf 42 | neu; Regel-100-Warnung zur eigenen Fläche ergänzt |
| **#435** | `license:check` auf `:871` (zwei Stellen) | **`:983`** an beiden |
| **#535** | AK 2 zur Hälfte unbelegt | ✅ **AK 2 abgehakt**, zehn Größen gegengeprüft; MB/MiB-Posten notiert |
| **#540** | Statusblock Lauf 42 | neu; alle Zeiger fünften Lauf bestätigt |
| **#442** | Queue von Lauf 42 | neu geordnet, 6 Positionen + 9 Wellen, Regeln 98/99/100 |

**Zehn Issues offen** (Lauf 42: zehn; dazwischen #832 angelegt und
geschlossen). **Erste Issue-Bewegung seit Lauf 39 — und sie ging in beide
Richtungen am selben Tag.**
