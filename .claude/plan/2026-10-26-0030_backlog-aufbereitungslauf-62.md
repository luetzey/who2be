# Backlog-Aufbereitungslauf 62

**Datum:** 2026-10-26
**Messpunkt:** `main` @ `3d55f09c` (`feat(billing,web): Rechnungen im Web, Liste und PDF-Download (Rechnung R3)`, #1088)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 61.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — siebzehnter Lauf in Folge.**
Die Sitzung meldet den Server ausdrücklich als autorisierungspflichtig; `ToolSearch` liefert
keines seiner Werkzeuge. Persona und Playbook-Katalog lagen im System-Prompt vor;
`get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm
„Agent-ready Arbeitspaket", `73a86231`), `record_usage`, `submit_feedback` und
`search_memory`/`save_memory` nicht. Der Lauf fährt deshalb nach dem reduzierten Kern des
Bootstrap-Skills, nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints.
**Siebzehnter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB** — und ohne die
Möglichkeit, die Funde dieses Laufs als Gedächtnis-Vorschlag abzulegen.

## Messgrundlage

Alle Werte am 2026-10-26 auf `main` @ `3d55f09c` erhoben, sequenziell (ein Schreiber je Baum),
Node **v22.22.0**, **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne Pipe** (Regel 94).
Der Klon war **shallow** (50 Commits, Voreinstellung dieser Umgebung); nach `git fetch
--unshallow`: **1657** Commits (Regel 90).

| Gate | Ergebnis | Lauf 61 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, 0 Funde | = |
| `uv run mypy .` | **Exit 0**, **652** Dateien | = |
| `uv run pytest --collect-only -q` | **Exit 0**, **4957** Tests, davon **312** unter `packages/billing/` | = |
| `scripts/changelog_fragments.py check` | **Exit 0**, **393** Fragmente | 🔴 dort **394** — s. Fund 2 |
| `npm run lint` | **Exit 0**, **0 errors / 94 warnings**, **7** `--fix`-bar | = |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | = |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | = |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** | = |
| 🔴 `npm audit` (mit dev) | **rc 1**, **1** Advisory (`http-cache-semantics@4.2.0`) | = |
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2848** Tests, **490,80 s** | 282 / 2848 / 359,79 s |
| Coverage Web | **89,89 / 83,95 / 86,81 / 91,75** | = |
| `main`-CI | Lauf **2324**, `status: completed` **und** `conclusion: success` getrennt (Regel 91) | = |

Dass bei **0 Commits** alle Zahlen außer der Laufzeit gleich bleiben, ist die erwartete
Gegenprobe und kein Befund. **Die Laufzeit ist +131 s — Umgebungsstreuung, keine Regression**
(gleiche Suite, gleiche Datei- und Testzahl).

Umgebung: `docker info` → **Exit 1**, kein `podman` (**38. Messung in Folge**).

**Fundstellen, einzeln gelesen:** `MfaSection.tsx` **297**; `LoginPage.tsx` **399**
(🔴 **nicht 394**, s. Fund 4); `e2e/helpers/auth.ts` **199**; `docs/mcp-payload-budget.md`
**573**; `deploy/hetzner/Caddyfile` **208**, `grep -cE "\brate\b"` → **0**;
`.github/workflows/ci.yml` **1.259**; `de.json`/`en.json` **3.364 / 3.364** Schlüssel;
`osv-scanner.toml:11` `ignoreUntil = 2026-11-02T00:00:00Z`.

## PR-Bestand

**14 offene PRs** (waren 13; neu nur **#1089**, das Protokoll von Lauf 61). Scope je PR über
`git merge-base` + `git diff --name-only` mit ausdrücklicher Nicht-leer-Prüfung (Regel 90),
Konfliktfreiheit über `git merge-tree --write-tree`.

- 🟢 **Alle 14 mergen konfliktfrei** (rc 0), alle 14 merge-bases rechnen.
- 🔴 **Protokoll-Rückstand: 7** (#831, #990, #1002, #1025, #1056, #1078, #1089) **plus diesem
  Lauf = 8.** Neuer Höchststand; **die Hälfte aller offenen PRs sind Protokolle.**
- 🔴 **Von den 7 offenen Code-PRs trägt weiter kein einziger ein Issue** (Weiche 23).
- 🟢 **Nichts gemergt, nichts gestartet, 24 Stunden.** Die von Lauf 61 empfohlene
  Merge-Reihenfolge ist zu **0 %** ausgeführt — daher 0 Commits.

| PR | Draft | hinter `main` | Fläche | Stand |
|---|---|---|---|---|
| 🆕 **#1089** Protokoll Lauf 61 | ja | **0** | 1 Plan-Datei | 🟢 `clean` |
| **#1087** `feat(deploy)` R2d Schalter + Doku | nein | **1** | 10 (3 Cloud-Overlays, `.env.example`, **GoBD-Doku**, `vvt.md`, Löschkonzept, Erstinbetriebnahme, Fragment, Plan) | 🟢 `clean`. 🔴 **Erledigt #1077 vollständig** (eigenständig nachgeprüft). ⚠️ Wartet auf **Owner-Go** |
| **#1085** `feat(api)` Werkzeug-Profile Q2b | nein | **2** | 20 | ⚠️ **Gestapelt auf dem Branch von #1054**, `mergeable_state: unstable`. Reihenfolge erzwungen: **#1054 → #1085** |
| **#1084** `feat` Viewer per Connector | nein | **2** | 10, darunter **`de.json` + `en.json`** | 🟢 `clean`, **einziger Locale-Träger** |
| **#1080** `deps` filelock 3.32.0 → **4.2.1** | nein | **14** | `uv.lock` (1) | ⚠️ Major-Sprung, `blocked` — gewöhnliche Triage |
| **#1078** Protokoll Lauf 60 | ja | **14** | 2 | `blocked` |
| **#1054** `feat(db)` Werkzeug-Profile Q2a | nein | **2** | 12 | 🟢 `clean`. 🔴 Enthält eine eigene PM-Frage (Weiche 28). **Muss vor #1085** |
| **#1056** Protokoll Lauf 59 | ja | **29** | 1 | 🟢 `clean` |
| **#1025** Protokoll Lauf 58 | ja | **54** | 1 | 🟢 `clean` |
| **#1017** `deps(web)` web-minor-patch | nein | **54** | `package.json`, `package-lock.json` | 🟢 `clean`, braucht Branch-Update. Behebt `http-cache-semantics` **nicht** |
| **#1002** Protokoll Lauf 57 | ja | **70** | 1 | 🟢 `clean` |
| **#990** Protokoll Lauf 56 | ja | **95** | 1 | 🟢 `clean` |
| **#674** `deps(web)` Vitest 4 → 5 | nein | **55** | `package.json`, `package-lock.json` | 🔴 `blocked`, 8 Checks rot. **Weiche 12, 14 Tage** |
| **#831** Protokoll Lauf 42 | ja | **218** | 1 | `blocked`; wird durch ein **Branch-Update** grün, nicht durch ein Paket |

### Datei-Sperren

| Datei | Träger |
|---|---|
| `apps/web/package-lock.json` | 🔴 **#1017 (54 hinter), #674 (55 hinter)** |
| `apps/web/src/i18n/locales/de.json` | 🟢 **nur #1084** (mit `en.json` zusammen) |
| `apps/web/osv-scanner.toml` | 🟢 **FREI** über alle 14 PRs |
| `docs/mcp-payload-budget.md` | 🟢 **FREI** |
| `MfaSection.tsx`, `LoginPage.tsx`, `e2e/helpers/auth.ts` | 🟢 **FREI** |
| `.github/workflows/ci.yml`, `deploy/hetzner/Caddyfile` | 🟢 **FREI** |
| `docs/compliance/gobd-verfahrensdokumentation.md` | 🔴 **#1087** |

## Norm-Prüfung — alle 13 offenen Issues

Maschinell gegen die Pflichtfelder geprüft (`**In:**` / Out-Abschnitt / §Verifikation /
Shell-Block / §Vorentschieden / §Eskalation), danach **jeder Negativ-Befund von Hand
gegengelesen** — und das war nötig, s. Fund 3.

| Issue | Labels | Norm | Befund |
|---|---|---|---|
| **#1077** | `agent-ready`, `size/S` | 🟢 vollständig | **aus der Warteschlange genommen** — Arbeit liegt in #1087 (Regel 142) |
| **#1001** | `agent-ready`, `size/S` | 🟢 vollständig | startbar, Befund dritte Messung bestätigt |
| **#989** | `agent-ready`, `size/S` | 🟢 vollständig | startbar; §Startbedingung im Body **überholt** (Fund 1) |
| **#633** | `agent-ready`, `size/S` | 🟢 vollständig | nach #632; Zeilenzahl im Body veraltet (Fund 4) |
| **#632** | `agent-ready`, `size/S` | 🟢 vollständig | startbar |
| **#435** | `epic` | 🟢 vollständig | Tracking, trägt keine eigene Arbeit |
| **#542**, **#540**, **#535**, **#454**, **#428**, **#338** | `human-only` / `epic` / `needs-decision` | 🔴 Lücken unverändert | **bewusst nicht umgebaut** (Regel 7, Weiche 4) |
| **#442** | `backlog-queue` | — | die Liste selbst, kein Arbeitspaket |

🟢 **Alle fünf `agent-ready`-Issues tragen die Pflichtfelder vollständig. Keine Nachbesserung
am Zuschnitt nötig** — die beiden Funde sind veraltete *Zahlen*, keine fehlenden Felder.

Der Norm-Stand der sieben nicht-`agent-ready`-Bodies ist gegenüber Lauf 61 **unverändert**, und
das ist belegt statt behauptet: kein einziger dieser Bodies ist seit dem Messpunkt von Lauf 61
angefasst worden (`updated_at` aller sieben liegt **vor** dem 2026-10-25).

## Die Funde des Laufs

### 1. Die Frist steht auf 7 Tagen, und §Startbedingung von #989 verbietet den Start

`apps/web/osv-scanner.toml:11` trägt `ignoreUntil = 2026-11-02T00:00:00Z` — am 2026-10-26 sind
das **7 Tage**. Danach wird der `audit`-Job auf `main` rot, **ohne dass jemand eine Zeile
anfasst**. Der Fix ist da (`npm view http-cache-semantics@latest version` → **4.3.0**), das
Lockfile steht auf **4.2.0**.

🔴 **Der Body von #989 verlangt aber: „Das Paket startet, wenn BEIDE Träger weg sind."** Die
beiden Träger von `apps/web/package-lock.json` sind **#1017 (54 Commits hinter `main`)** und
**#674 (55 hinter, 8 Checks rot, Weiche 12 seit 14 Tagen unbeantwortet)**. **Diese Bedingung
ist in 7 Tagen nicht erfüllbar.**

**Lauf 61 hat das erkannt und per Kommentar korrigiert. Dieser Lauf musste es erneut per
Kommentar korrigieren** — der Body ist unverändert. **Zwei Läufe in Folge patchen dieselbe
Stelle im Kommentar, statt sie im Body zu heilen**, weil Weiche 19 einen Body-Rewrite als
riskant markiert hat. **Fund 3 nimmt dieser Vorsicht die Grundlage.**

### 2. Die Fragmentzahl von Lauf 61 war ein Zählfehler (Regel 139)

Lauf 61 nennt **394** Fragmente, dieser Lauf misst **393** — bei **0 Commits** und bitgleichem
Baum. Eine der beiden Zahlen muss falsch sein, und es ist die ältere:

```
$ ls -1 changelog.d/ | wc -l            # 394
$ ls -1 changelog.d/*.md | wc -l        # 394
$ python scripts/changelog_fragments.py check
393 Fragment(e) in /home/user/who2be/changelog.d/ in Ordnung
```

Die Differenz ist **genau `README.md`**, und das ist **kein Defekt**, sondern die dokumentierte
Absicht: `scripts/changelog_fragments.py:84` führt
`IGNORED_NAMES = frozenset({"README.md", ".gitkeep", ".gitignore"})`, und `:297` erklärt es.

**Lehre: Lauf 61 hat Dateien gezählt, wo das Werkzeug Fragmente zählt.** Die zu zitierende Zahl
ist die **Eigenzahl des Werkzeugs** (393), nicht `ls | wc -l`. → **Regel 143.**

### 3. 🟢 Weiche 19 ist gelöst — die Ursache ist der Schreibweg (Regel 144)

Weiche 19 („Die Attributions-Fußzeile ist auf einem Issue-Body nicht zu halten") steht seit
Lauf 55 und hat seither **jeden** Body-Rewrite mit einem Risiko belastet. Lauf 55 schloss aus
fünf Bodies, die die Fußzeile nach seinem Rewrite verloren hatten, auf einen
Plattform-Mechanismus.

**Der erste Befund dieses Laufs war der umgekehrte Schluss — und er war falsch.** Gemessen am
2026-10-26 trugen genau die drei Bodies, die Lauf 55 als Verlustfälle führt (#632, #633, #989),
die Fußzeile, und ihre Pflege-Zeile nennt **Lauf 57**. Daraus schien zu folgen: die Plattform
entfernt nichts, es fehlt nur, wo keiner eine geschrieben hat. **Diese Hypothese erklärte jeden
bekannten Fall — und war dennoch unbelegt.**

🔴 **Die kontrollierte Gegenprobe hat sie widerlegt.** Der Body von #442 ist in diesem Lauf per
**MCP `issue_write`** mit Fußzeile in der Nutzlast geschrieben und danach byte-exakt per
`gh api` zurückgelesen: **0×**, bei **24.975** Bytes, und der Body ist **nicht** abgeschnitten
(er endet regulär mit seiner Pflege-Zeile).

**Danach drei Wege getrennt gemessen, jeder mit byte-exaktem Rücklesen:**

| Schreibweg | Nutzlast trug Fußzeile | zurückgelesen |
|---|---|---|
| **MCP `issue_write`** (Issue-Body, #442) | ja | 🔴 **0×** |
| **`gh api PATCH --input`** (Issue-Body, #1001) | ja | 🟢 **1×** |
| **`gh api PATCH --input`** (Issue-Body, #1077) | ja | 🟢 **1×** |
| **MCP `add_issue_comment`** (#989, #1001) | ja | 🟢 **1×** |

→ **Nicht die Plattform entfernt die Fußzeile, sondern der MCP-Body-Write.** Kommentare sind
unbetroffen, `gh api` ist es ebenfalls. Das Muster erklärt jeden Fall rückwirkend: #632/#633/#989
schrieb Lauf 57 auf einem erhaltenden Weg; #1001/#1077 schrieb Lauf 60 per MCP.

🟢 **Weiche 19 braucht damit keinen Owner-Beschluss, sondern einen Verfahrensschritt:
Issue-Bodies per `gh api --input` schreiben.** → **Regel 144.** In diesem Lauf angewandt: die
Korrektur von #442 ist auf diesem Weg geschrieben und trägt die Fußzeile (**1×**, 25.766 Bytes);
#1001 und #1077 sind **nachgetragen**.

🔴 **Die Methoden-Lehre ist der eigentliche Ertrag, und sie ist teuer bezahlt:** der erste
Schluss dieses Laufs stand schon im Body von #442, als die Gegenprobe ihn umwarf. **Eine
Hypothese, die alle bekannten Fälle erklärt, ist kein Beleg — erst der Versuch, sie zu brechen,
ist einer.** Das ist dieselbe Lehre wie Regel 130 („eine in sich aufgehende Partition ist kein
Beleg"), diesmal an der eigenen Schlussfolgerung statt an einer fremden Zahl.

### 4. Zwei Zahlen in Issue-Bodies sind gewandert (Regel 98)

- **#633** nennt `LoginPage.tsx` mit **394** Zeilen; die Datei hat **399**. Der Wert stammt aus
  Lauf 57; dazwischen liegen Commits, die die Datei angefasst haben.
- **#989** nennt als Bezugswert für AK5 **267 Dateien / 2517 Tests** (Stand 2026-10-20); heute
  sind es **282 / 2848** — **+15 Dateien, +331 Tests**. Der Body sagt selbst, dass der
  Startwert neu zu messen ist (Regel 128); der Kommentar dieses Laufs beziffert die Abweichung.

Beides **in Kommentaren richtiggestellt, nicht im Body** — s. Weiche 32 Option A.

### 5. Nichts ist gemergt, nichts gestartet — 24 Stunden, 0 Commits

Lauf 61 hat eine Merge-Reihenfolge empfohlen (**#1084 → #1054 → #1085 → #1087 → #989 → #1017 →
#1080 → #674**). **Keiner dieser Schritte ist ausgeführt.** Alle 14 PRs mergen konfliktfrei,
vier stehen höchstens 2 Commits hinter `main`. Gleichzeitig läuft die einzige datierte Frist
des Backlogs auf **7 Tage** zu.

🔴 **Der Engpass ist nicht mehr die Arbeitsversorgung, sondern der Merge-Durchsatz.** Drei
startbare Pakete liegen bereit, zwei davon echt parallel; es fehlt nicht an Paketen, sondern
an Vorgängen. → **Weiche 32.**

## Verifikation

- **Alle Zahlen** am 2026-10-26 gegen `main` @ `3d55f09c` erhoben, Exit-Codes ohne Pipe.
- **Beide Bäume grün**, Coverage-Gate Exit 0 bei 282 Dateien / 2848 Tests.
- **PR-Scope je PR** über `git merge-base` + `git diff --name-only`, Nicht-leer geprüft;
  **14/14 konfliktfrei** über `git merge-tree --write-tree`.
- **#1087 ⊃ #1077 eigenständig nachgeprüft**: GoBD-Doku **144 → 231** Zeilen, der Satz
  „stellt keine eigenen Rechnungen" **1 → 0**, `billing_invoice` **0 → 4**, `payment_id`
  **0 → 2**, `invoice-retry` **0 → 2**, `invoices/` **0 → 2**.
- **Norm-Prüfung** maschinell über alle 13 Bodies, **jeder Negativ-Befund von Hand
  gegengelesen** — zwei Fehlalarme dadurch gefangen (s. Fund 3 zur Fußzeile; #632/#633
  schreiben `**Out:**`, nicht `**Out of Scope**`, und sind norm-vollständig).
- **Fußzeilen-Gegenprobe:** #442-Body mit Fußzeile geschrieben, danach per `gh api`
  byte-exakt zurückgelesen.

## Ergebnis

**Selbst erledigt** (Repo belegt es): Frist-Neuberechnung und Startbedingungs-Korrektur in
#989 · dritte Bestätigung des #1001-Befundes mit gewanderten Zeilen-Zeigern · Zählfehler der
Fragmentzahl aufgeklärt (Regel 143) · **Weiche 19 gelöst und die Ursache isoliert (Regel 144)**,
Fußzeile in #1001 und #1077 nachgetragen · zwei gewanderte Zahlen richtiggestellt · #442 neu
geschrieben und danach korrigiert.

**Braucht eine Owner-Antwort:** **Weiche 32** (wie wird die Frist am 2026-11-02 bedient) —
neu, datiert, mit drei Optionen und Empfehlung **A**. Die 19 bestehenden Weichen werden nicht
erneut gestellt (Regel 9); ihr Stand steht in #442.

**Reihenfolge unverändert** gegenüber Lauf 61 — nicht aus Trägheit, sondern weil bei 0 Commits
kein Kriterium sich bewegt hat: **#989 → #1001 → #632 → #633**, Wellen **A (#989 ‖ #1001)**,
**B (#632)**, **C (Merges, kein Agent)**, **D (#633)**.
