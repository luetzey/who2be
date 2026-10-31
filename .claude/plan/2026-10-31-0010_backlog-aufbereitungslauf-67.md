# Backlog-Aufbereitungslauf 67 — 2026-10-31

**Gemessen gegen `main` @ `1423488782c0bcb5f11e584b88cb7775f88225ee` (Baum `4622932e`).**
Fenster seit Lauf 66: **0 Commits** — vierter Lauf am bitgleichen Baum.
**0 PRs gemergt, 0 Pakete gestartet, 0 Issues geschlossen, 0 Weichen beantwortet.**
Neu: **2 PRs geoeffnet** (#1105 = Protokoll Lauf 66, **#1106** = zehn Minuten vor diesem Lauf).

Reihenfolge und Wellen stehen im Queue-Issue **#442** (Label `backlog-queue`); diese Datei
ist das Protokoll, nicht die Quelle.

## Umgebung

- Node **v22.22.0**, uv **0.11.32**. Klon shallow (50) → **1661** Commits nach `--unshallow`.
- `docker info` → **Exit 1**, kein `podman` — **43. Messung in Folge ohne Container-Laufzeit**.
- Die Who2Be-AgentDB (MCP-Server `Who2Be---Coder`) ist in dieser Session **nicht autorisiert**;
  `get_persona`, `fetch_playbook`, `search_memory`, `record_usage` und `save_memory` standen
  nicht zur Verfuegung. Gearbeitet wurde aus der eingebetteten Persona und den Norm-Dateien
  des Repos (`.github/PROJECT.md` §Constraints, `CLAUDE.md`).
- `gh auth status` meldet „token invalid", `gh api` funktioniert trotzdem (Regel 147).

## Gates

| Gate | Ergebnis |
|---|---|
| `main` Check-Runs @ `14234887` | **24** `success`, **1** `skipped` (`deploy`), **0** rot → Regel 80 greift nicht |
| `uv run ruff check .` | Exit 0, „All checks passed" |
| `uv run mypy .` | Exit 0, 0 Funde in **655** Dateien |
| `uv run pytest --collect-only -q` | **4971** Tests |
| `changelog_fragments.py check` | Exit 0 |
| `npm run lint` | Exit 0, **94** problems, **0 errors**, **7** `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe **0 Byte** |
| `npm run i18n:check` | Exit 0, `de.json`/`en.json` je **3.365** Schluessel, `orphan-baseline.json` **156** |
| `npm audit --omit=dev --audit-level=high` | Exit 0 |
| `npm audit` (voll) | Exit 0, **0 vulnerabilities** |
| `payload_report` | **103** Werkzeuge / **108.251** Bytes, `instructions` **1.732** — achte identische Messung |
| `npm run test:coverage` | **bewusst nicht gefahren** — siehe unten |

**Warum die Coverage-Suite nicht gelaufen ist.** Der Baum ist bitgleich mit Lauf 64, 65 und 66.
Lauf 66 hat Determinismus bei **n = 3** belegt, mit allen vier Coverage-Absolutpaaren identisch
und der Laufzeit als nachgewiesenem Rauschen (336,71 s gegen 282,28 s). Eine vierte identische
Messung an einem unveraenderten Baum kauft nichts und kostet ~340 s. Dieser Lauf aendert keinen
Code, die Frontend-DoD greift also nicht. Sobald sich `main` bewegt, wird die Suite wieder
gefahren. Das ist als **Regel-20-Umkehrung** in #442 festgehalten — mit Grund hingeschrieben,
nicht stillschweigend weggelassen.

## Funde

### 1. #1106 schreibt Betriebs-Hosts in eine oeffentliche Betreiber-Doku (Weiche 39)

Der einzige Fund dieses Laufs mit einer Frist.

| Messung | Wert |
|---|---|
| `docs/cloud-erstinbetriebnahme.md` auf `main` | **658** Zeilen, **0** Treffer auf die Betreiber-Domain |
| dieselbe Datei am Head von #1106 (`2a5a82f1`) | **1016** Zeilen, Treffer an **`:622`** und **`:623`** |
| `:622` | nennt Basis-Domain **und** vier abgeleitete Betriebs-Hosts als Betriebs-Hosts |
| die beiden Sub-Hosts `mcp.*`/`api.*` auf `main` | in **0** Dateien |
| `<DOMAIN>`-Platzhalter in den hinzugefuegten Zeilen desselben PR | **43×** |
| CI von #1106 | **17** Check-Runs, 0 rot, **0** Commits hinter `main`, konfliktfrei |

CLAUDE.md §Security verbietet reale Betreiber-Hosts in eingecheckten Dateien ausdruecklich,
Platzhalter ist `<DOMAIN>`, Grund: „das Repo geht oeffentlich, und die History vergisst nichts".
Das Repo ist seit dem 2026-08-20 public. Der PR ist **jetzt mergebar**, der Vorgang nach dem
Merge nicht ruecknehmbar.

**Gegenprobe (Regel 155), damit der Fund nicht zu breit wird:** die Basis-Domain steht auf `main`
bereits in **38** Dateien — als Fehler-Typ-URI (`apps/api/src/who2be_api/main.py`,
`apps/web/src/lib/promoteError.ts`), als Beispiel-Mailadresse (`docs/signup-and-invites.md`,
`docs/local-smoke.md`) und in alten Plan-Dateien. **Das sind genau die Kategorien, die die
Plan-Datei von #1106 selbst als „bleibt, kein Betriebs-Host" einordnet, und diese Einordnung ist
richtig.** Der Fund betrifft nur die zwei neuen Doku-Zeilen. Auch der Branch-Name traegt einen Host.

**Behandlung:** drei Optionen mit Empfehlung **A** (auf `<DOMAIN>` ziehen, wie der PR es 43× schon
tut — die einzige reversible Option) als Kommentar an #1106, plus Label `needs-decision`.
**Am PR selbst wurde nichts geaendert:** dieser Lauf hat ihn nicht geoeffnet, und ob die
Basis-Domain „laufende Installation" oder „oeffentliche Produkt-Domain" ist, ist eine
Owner-Entscheidung, keine Messung. **Die Hostnamen sind im Kommentar bewusst nicht wiederholt** —
er ist selbst oeffentlich.

### 2. Ein Grep-Treffer auf eine alte Formulierung ist noch kein Fund (Regel 157)

Dieser Lauf hat in #632/#633 die seit dem 2026-10-20 falsche axe-Anweisung wiedergefunden
(#632:41, #633:54) und war im Begriff, Lauf 66 eine unvollstaendige Korrektur vorzuwerfen —
Lauf 66 hatte in derselben Sitzung Regel 153 geschrieben („Zitatbloecke eingeschlossen") und
die Bodies als „jetzt gueltig" gemeldet.

**Beim Lesen loeste sich der Fund auf.** Beide Treffer stehen als ausdruecklich als falsch
markiertes Gegenbeispiel da:

```
> 🔴 DIESER SATZ STAND HIER UND IST SEIT DEM 2026-10-20 FALSCH: „Wer hier einen axe-Test
> anlegt, gibt ihm ein explizites Timeout oder die Namensform *.a11y.test.tsx." Wer ihm
> folgt, macht web rot. Richtig ist seit 56a3fc4f (PR #987, auf main am 2026-10-20): …
```

**Lauf 66 hat vollstaendig korrigiert, und sein Urteil war richtig.** Regel 153 verlangt das
Grepen, Regel 10 das Lesen — gezaehlt wird erst, was als Anweisung dasteht. Ein Verfahren, das
Vorkommen zaehlt statt Anweisungen, erzeugt Fehlalarme ueber genau die Reparatur, die
funktioniert hat. **Weiche 38 ist daraufhin von 🔴 auf ⚠️ herabgestuft:** der Kopfblock bleibt
lang (**31 %** von #632, **30 %** von #633) und steht ueber dem Vertrag — das ist Lesekosten,
nicht Fehlleitung.

### 3. „Gate-alt" ist an der falschen Variable gemessen worden (Regel 158)

Weiche 2 fragt nach dem PR, dessen gruenes `all-green` von **aelterer CI-Definition** stammt.
Neun Laeufe haben dafuer den Commit-Abstand genannt. Gemessen an der richtigen Variable —
`git diff --name-only <merge-base> main -- .github/workflows/ci.yml`:

| PR | Rueckstand | `ci.yml` bewegt? | gate-alt? |
|---|---:|---|---|
| #1100 | 1 | nein | nein |
| #1089–#1097, #1092, #1091, #674 | 4 | nein | nein |
| **#1080**, **#1078** | 18 | **nein** | **nein — trotz 18 Commits** |
| **#1056** | 33 | ja | **ja** |
| **#1025** | 58 | ja | **ja** |
| **#1002** | 74 | ja | **ja** |
| **#990** | 99 | ja | **ja** |
| **#831** | 222 | ja | **ja** |

**Fuenf statt einem.** Die Kante liegt zwischen 18 und 33 Commits, nicht bei „alt". Alle fuenf
sind Protokoll-PRs — das Gate-alt-Problem ist vollstaendig ein Problem des Protokoll-Rueckstands
und verschwindet mit Weiche 18.

### 4. Vier PRs sind gezaehlt und dann aus der Handlungsliste gefallen

Die Merge-Reihenfolge von Lauf 66 nennt in neun Schritten **20** von 24 gezaehlten PRs.
**#1056, #1025, #1002, #990** stehen nirgends darin, obwohl sie unter „Protokoll-Rueckstand: 10"
mitgezaehlt sind — und es sind genau vier der fuenf gate-alten. In #442 als Schritt 7 eingefuegt.

### 5. Eine negative Aussenmessung braucht eine Positiv-Kontrolle (Regel 156)

Lauf 66 belegte den Advisory-Rueckzug damit, dass der npm-Bulk-Endpunkt fuer
`http-cache-semantics@4.2.0` **`{}`** antwortet. **Ein `{}` ist von einem toten Endpunkt nicht
unterscheidbar.** Dieser Lauf hat am selben Endpunkt `lodash@4.17.11` mitgemessen → echte
Advisory (`GHSA-35jh-r3h4-6jhm`). Erst damit ist das `{}` ein Negativ-Befund.

**Nicht messbar aus dieser Session:** `advisories/GHSA-…` ist repo-scoped gesperrt (403),
`api.osv.dev` nicht erreichbar. Das `withdrawn_at` der Advisory selbst ist also **nicht**
gelesen; getragen wird der Befund von Registry-`dist-tags` und `npm audit`.

### 6. Die Begruendung des Ignores ist vollstaendig verfallen, nicht teilweise

`apps/web/osv-scanner.toml` (**15** Zeilen) begruendet den Ignore mit **zwei** Saetzen, und
**beide** sind gemessen falsch:

- `:5-7` „*when it expires the scan turns red again*" — ein abgelaufener Ignore hoert auf zu
  filtern, er erzeugt keinen Fund. **Von Lauf 66 gefunden.**
- `:11` „*http-cache-semantics@4.2.0 has no fixed release yet*" — **falsch seit dem 2026-10-04**:
  `4.3.0` ist `dist-tags.latest`, Registry-Zeitstempel `2026-10-04T02:56:05Z`. **27 Tage.** NEU.

In neun Laeufen fiel nur einer der beiden auf. Als Nachtrag in **AK2 von #989** geschrieben
(byte-exakt zurueckgelesen). `ignoreUntil` laeuft am **2026-11-02** ab — in zwei Tagen — und
bleibt ein Nicht-Ereignis.

### 7. Null verrottete Zeiger, zum ersten Mal seit Regel 151

Alle Zeiger der vier `agent-ready`-Bodies am 2026-10-31 gegen `main` nachgemessen:
`MfaSection.tsx` **297**, `LoginPage.tsx` **399**, `SessionProvider.tsx` **267**,
`e2e/helpers/auth.ts` **199**, `a11y.test.ts` **77**, `audit.test.ts` **371**,
`vite.config.ts` **107** (Schwellen `:100-103`, `thresholds:` `:99`), `ci.yml` **1259**
(`:463` `--project=chromium`, `:544` `billing.spec.ts` woertlich bestaetigt),
`orphan-baseline.json` **156**, `docs/mcp-payload-budget.md` **573**, `osv-scanner.toml` **15**,
Lockfile `:6296` = `4.2.0`, `Caddyfile` **208** (`rate` **0×**), `plans.md` **271**,
ADR-0061 **486** (W61-1 `:377`, W61-2 `:390`, W61-3 `:403`, §11 `:375`).

Lauf 65 fand zehn verrottete Zeiger, Lauf 66 elf, dieser **null**. Die Drift-Tabellen in
#632/#633 nennen heute exakt die Werte von `wc -l` (`client.ts` 1772→**1849**,
`types.ts` 2402→**2407**, `auth.ts` 180→**199**). **Das ist der Beleg, dass Regel 151 traegt**,
nicht dass sie ueberfluessig ist.

### 8. Zwei neue Datei-Sperren, und eine, die niemand erwartet hat

- `docs/cloud-erstinbetriebnahme.md` — neu **doppelt** (#1098 und #1106), **kein** Konflikt
  (`merge-tree` #1098↔#1106 rc 0, disjunkte Hunks).
- `uv.lock` — neu **dreifach** (#1106, #1093, #1080).
- **`.github/PROJECT.md` ist nicht mehr frei:** #1105 haelt es. **Das Protokoll des Vorlaufs
  sperrt die Datei, in der die Begruendung der Reihenfolge steht.**

### 9. Protokoll-Rueckstand: 11, und Lauf 63 fehlt weiter ganz

Offene Protokoll-PRs: #1105 (66), #1104 (65), #1103 (64), #1090 (62), #1089 (61), #1078 (60),
#1056 (59), #1025 (58), #1002 (57), #990 (56), #831 (42) = **11**; dieser Lauf legt das
zwoelfte dazu.

**Zu Lauf 63 existiert kein Protokoll** — unabhaengig nachgemessen (Regel 154): kein PR mit dem
Titel ueber offene **und** geschlossene PRs, kein Commit auf irgendeiner Ref
(`git log --all`, 1707 Commits ueber alle Refs). Vorhanden sind 56–62, 64–66 und 42; **63 fehlt**.
Weiche 38 haelt.

Letzter gemergter Protokoll-PR: **#983 (Lauf 55), 2026-10-20** — **elf Tage** ohne Protokoll auf
`main`. `.claude/context/STATE.md` ist auf `main` auf den **2026-10-02** datiert (**29 Tage**) und
wird von **drei** offenen PRs gehalten: #1103 (gruen, 0 hinter), #1090 (gruen, 4), #1078 (rot, 18).

## Reihenfolge und Wellen

Unveraendert gegenueber Lauf 66, beide Positionen neu gerechnet:

1. **#632** — Passkey registrieren/entfernen (`size/S`, Web). Kriterium 3, Fundament vor Flaeche.
   Alle drei Schreibflaechen ueber alle 26 PRs frei.
2. **#989** — `http-cache-semantics` → 4.3.0 (`size/S`, Web). Kriterium 5. Lockfile-Sperre
   #1092/#674 — **beide Heads tragen 4.2.0**, keiner bringt den Sprung mit.
3. **#633** — Step-up mit Passkey. Hart nach #632, zusaetzlich Container-Laufzeit.

Wartestand: **#1001** (Flaeche, Erzeuger und Nachweis von #1101 gehalten).
Nicht in der Warteschlange: #442, #428/#435/#535 (Tracking), #338/#454/#542 (`human-only`),
#540 (`needs-decision` + `ci.yml` gehalten + keine Container-Laufzeit), **#1106** (PR).

Wellen: **A** #632 · **B** #989 · **C** Merges (17 gruene PRs ≤ 4 Commits hinten) ·
**D** #633 · **E** #1001 nach dem Merge von #1101.
**Vierter Lauf in Folge ohne Parallel-Paar** — A, B und D liegen alle im Vitest-Baum, eine Kette.
**Welle E ist das Parallel-Paar, das ein einziger Merge (#1101) zurueckbringt.**

## Norm-Pruefung „Agent-ready Arbeitspaket"

**4 von 4 vollstaendig, und alle Zeiger gueltig** — #632, #633, #989, #1001.
`**Out:**` statt `**Out of Scope**` in #632/#633 bleibt eine Schreibvariante, keine Luecke
(zum sechsten Mal von Hand gegengelesen).

Norm-Stand der acht uebrigen Bodies unveraendert: Scope-„In" fehlt in #542/#540/#535/#454/#428/#338,
Verifikations-Abschnitt in #535/#428/#338, #454 sagt dort „Kein Testkommando", #338 traegt keine
Abschnitts-Ueberschriften. **Bewusst nicht umgebaut** (Regel 7, Weiche 4): `human-only` bzw.
`size/M`, und ein `size/M` wird laut Constraint nie durch Nachtragen von Feldern startbar.

**Kein neues `agent-ready` vergeben, keines entzogen.** Ein neues `needs-decision`: **#1106**.

## Geaendert in diesem Lauf

- **#442** — Body neu geschrieben (Reihenfolge, Wellen, Sperren, Gate-alt-Tabelle, Norm-Tabelle,
  24 Weichen, Regeln 156–158). Per `gh api --input`, byte-exakt zurueckgelesen.
- **#989** — AK2 um die zweite falsche Praemisse (`osv-scanner.toml:11`) und die Frist ergaenzt.
  Per `gh api --input`, byte-exakt zurueckgelesen.
- **#1106** — Kommentar mit Weiche 39 (drei Optionen, Empfehlung A) + Label `needs-decision`.
  **Am PR-Inhalt nichts geaendert.**
- **#632/#633** — **nicht angefasst.** Der geplante Eingriff ist nach dem Lesen entfallen (Fund 2).

## Neue Regeln

- **156** — Eine negative Aussenmessung braucht eine Positiv-Kontrolle am selben Endpunkt.
- **157** — Ein Grep-Treffer auf eine alte Formulierung ist noch kein Fund; zitierte
  Gegenbeispiele enthalten sie notwendigerweise. Gezaehlt wird, was als Anweisung dasteht.
- **158** — Gate-alt wird an der CI-Definition gemessen, nicht am Commit-Abstand.
- **Regel-20-Umkehrung** — Ist der Determinismus belegt und der Baum bitgleich, wird die teure
  Suite nicht erneut gefahren; das wird mit Grund hingeschrieben.
