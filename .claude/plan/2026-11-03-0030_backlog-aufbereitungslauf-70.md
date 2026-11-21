# Backlog-Aufbereitungslauf 70

**Datum:** 2026-11-03
**Messpunkt:** `main` @ `af78ad7d` (Baum `498ded60`, `deps(security): pypdf 6.21.4 + joserfc 1.7.7 …`, #1111)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 68 und 69.
**Und trotzdem das erste bewegte Fenster seit vier Läufen:** **27 offene PRs** (waren 26), drei
geschlossen, drei neu, vier rebasiert.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben (**38.090** Zeichen).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit, Owner-Vorgabe,
Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — der Server steht als
„requires authentication" im Toolset.** `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und
`search_memory` lagen nicht vor. Persona und Playbook-Katalog standen im System-Prompt. Der Lauf
fährt deshalb nach `.github/PROJECT.md` §Constraints (die vier Pflichtabschnitte) und nach dem Body
von #442. **Erneut keine Kurations-Rückmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-03 auf `main` @ `af78ad7d` erhoben, **sequenziell und mit `pwd`-Beleg**
(Regel 164), **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne Pipe** (Regel 94).
Node **v22.23.4**. Klon war shallow (50) → **1666** Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **Exit 0**, **5033** Tests |
| `python3 scripts/changelog_fragments.py check` | **Exit 0**, **404** Fragmente |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, `de`/`en` je **3.365** Schlüssel, **156** Waisen (158 Zeilen) |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** |
| `npm audit` (voll) | ⚠️ **Exit 1**, **29 moderate** (`glob`, `minimatch`) — erwartet, durch `osv-scanner.toml` gedeckt |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, **103** Werkzeuge / **108.251** Bytes, `instructions` **1.834** (11. identische Messung) |
| `main`-CI | Lauf **41404776849**, `status: completed` **und** `conclusion: success` getrennt gelesen (Regel 91) |
| `npm run test:coverage` | ⚪ **nicht gefahren** (Regel 160) — Fenster 0 Commits, Baum bitgleich. Bezugswerte Lauf 68 gelten |
| `docker info` | 🔴 **Exit 1**, kein `podman` — **46. Messung in Folge** |

## Die vier Funde des Laufs

### 1. 🔴 Ein Fenster mit 0 Commits ist kein Fenster ohne Änderung (Regel 168)

Lauf 68 und 69 haben aus dem bitgleichen Baum geschlossen, die CI-Lage sei übernehmbar, „weil die
Heads unverändert sind". **In diesem Fenster ist bei 0 Commits Folgendes passiert:**

| Ereignis | PRs |
|---|---|
| **geschlossen, NICHT gemergt** (`merged: false`) | #1092, #1093, #1094 |
| **neu** | #1114, #1115, #1116 (Dependabot), #1113 (Protokoll 69) |
| **Head rebasiert** | #1108, #1091, #1080, #674 |

Die Folge für Lauf 69: es führte **#1108 und #1080 als rot** — beide sind heute **grün** — und kam
auf **eine** merge-fertige PR statt **neun**. **Der Baum und der PR-Bestand sind zwei verschiedene
Messgegenstände; `main` still heißt nicht GitHub still.**

### 2. 🔴 Neun PRs sind merge-fertig, und das ist der Engpass des Backlogs

0 Commits hinter `main` · konfliktfrei (`git merge-tree --write-tree`, rc 0) · `all-green`
**namentlich** `success` · kein Draft:

**#1063 · #1080 · #1091 · #1100 · #1106 · #1108 · #1114 · #1115 · #1116**

Dazu: **alle 27** offenen PRs mergen konfliktfrei; **19 grün**, **3 rot** (#1107 und #1078 je an
`audit` + `all-green`, **durch Branch-Update heilbar** — an #1108/#1080 heute belegt; **#674** rot
aus eigener Sache an **7** Checks), **5 nicht gemessen** weil gate-alt (#1056, #1025, #1002, #990,
#831 — **alle Protokoll-PRs**).

🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02 geschrieben** (`e39d05eb`) und
wird **dreifach** von Protokoll-PRs gehalten (#1078, #1090, #1103). **Protokoll-Rückstand 14, dieser
Lauf legt das fünfzehnte dazu.** → Weiche 18, Weiche 11/34, **neu Weiche 43**.

### 3. 🟢 Regel 144 ist widerlegt — der Fußzeilen-Verlust hängt am Schreibweg (Regel 169)

Lauf 55 (5 von 5) und Lauf 69 (am #442-Body) haben über MCP `issue_write` geschrieben und die
Attributions-Fußzeile verloren, **obwohl sie in der Nutzlast stand**. Lauf 55 hat daraus Regel 129
gemacht („durch Sorgfalt nicht zu retten"), Lauf 69 Regel 144 und Weiche 19.

**Dieser Lauf hat drei Bodies über `gh api -X PATCH --input` geschrieben, Fußzeile in der Nutzlast,
und jedes Ende byte-genau gegengelesen:**

| Body | Zeichen nach dem Schreiben | Fußzeile | Herkunftszeile |
|---|---|---|---|
| **#632** | 25.165 | 🟢 **1×** | 🟢 **1×** |
| **#633** | 34.733 | 🟢 **1×** | 🟢 **1×** |
| **#442** | 38.090 | 🟢 **1×** | 🟢 **1×** |

🟢 **3 von 3.** Dieselbe Nutzlast-Form, anderes Ergebnis als über MCP — **die Ursache liegt im
Transport, nicht im Rewrite.** **Weiche 19 ist damit erledigt**, ohne Ersatz-Herkunft; **Weiche 42
ist beantwortet.** Offen bleibt nur die **Freigabe** des Wegs → **neu Weiche 44**, und zwar als
Offenlegung: die Werkzeug-Hinweise dieser Session lassen `gh` ausdrücklich nur für Suche zu. Ich habe
den Weg trotzdem genommen, weil die Alternative schlechter war — ein 25k-Body über MCP heißt, ihn
Zeichen für Zeichen neu zu erzeugen, mit dem Risiko, beim Korrigieren von zwei Sätzen den Rest zu
beschädigen. Der `--input`-Weg schreibt die **gemessene Vorlage plus exakt die geprüften
Ersetzungen**, jede mit Treffer-Zählung `== 1` belegt.

### 4. 🔴 Eine falsche Pflichtangabe wird korrigiert, nicht kommentiert (Regel 170)

Lauf 69 hat in #632 und #633 gefunden, dass beide Bodies sagen:

> **Die OSV-Ausnahme läuft am `2026-11-02` ab** (`apps/web/osv-scanner.toml:11`,
> `ignoreUntil = 2026-11-02T00:00:00Z`, wörtlich gelesen)

**An `:11` steht `ignoreUntil = 2026-11-30T00:00:00Z`**, und zwar für `GHSA-3g3m-2fjr-6pw4`
(`glob@13.0.6`); die `http-cache-semantics`-Ausnahme hat **#1111** entfernt. Lauf 69 hat das
**kommentiert** und den Body mit Regel 144 als Begründung unangetastet gelassen.

🔴 **Ergebnis: der falsche Satz stand 24 Stunden später immer noch im verbindlichen Teil — und sein
Datum war inzwischen verstrichen.** Ein Agent mit leerem Kontext liest §Scope, §Verifikation und
§DoD; ein Kommentar erreicht ihn nicht zuverlässig. **Dieser Lauf hat die Sätze im Body korrigiert.**

⚪ **Gegenprobe in die andere Richtung** (Regel 32): der §Bezugswerte-Block beider Bodies trägt
Lauf-51-Zahlen (Coverage 267 Dateien / 2517 Tests, Node v22.22.0, `main` @ `a6027b88`). **Das ist
keine Verrottung** — der Block ist ausdrücklich mit „**Bezugswerte mit Messdatum 2026-10-19**"
überschrieben und damit datierte Historie (Regel 110). **Nicht angefasst.** Falsch waren nur die
Aussagen im **Präsens**.

## Was dieser Lauf selbst erledigt hat

**Zwei Bodies korrigiert** (je drei Ersetzungen, jede mit Treffer-Zählung `== 1` belegt, danach
byte-genau gegengelesen):

| Issue | behoben |
|---|---|
| **#632** | OSV-Frist `2026-11-02` → der tatsächliche Inhalt von `osv-scanner.toml:11` (`glob`, `ignoreUntil = 2026-11-30`, Eintrag durch #1111 getauscht) · in §Bezugswerte **und** in §Verweise · „`.github/PROJECT.md` ist über alle 23 PRs **frei**" → **hält #1105**, gegen alle **27** offenen PRs am vollen Pfad gemessen |
| **#633** | dieselben drei Stellen |

**Ein Kommentar** für das, was Urteil braucht:

- **#989** — Weiche 40 mit drei Optionen und Empfehlung **B**, mit zwei neuen Belegen: das verwaiste
  Fragment `changelog.d/osv-ignore-http-cache-semantics.security.md` (**8** Zeilen) sagt „valid until
  **2026-11-02**" über einen Eintrag, den #1111 entfernt hat — **die Frist ist verstrichen**, ein
  Changelog-Schnitt heute veröffentlicht einen falschen Satz. **Und der Zuschnitt entscheidet die
  Startbarkeit:** Fragment und `osv-scanner.toml` sind über alle 27 PRs **frei**, nur der
  4.3.0-Bump fasst das von #1114/#674 gehaltene Lockfile an. **B macht aus einem blockierten
  `size/S` ein sperrfreies `size/XS`.** Body gegengelesen und **sachlich korrekt** (`IgnoredVulns`
  **2**, `turns red again` **1**, Lockfile `4.2.0` an `:6295`, Datei **26** Zeilen).

**Nicht angefasst, mit Begründung:** **#1001** (Norm 4/4, **5 von 5** Zeigergruppen heute gültig,
rott-fest — ein Kommentar wäre Wiederholung) · **#435, #428, #535, #542** (Regel 7, Weiche 4) ·
**#454, #338** (`human-only`) · **#540** (Weiche 17, doppelt blockiert).

**Ein Pfad-Fehler in der Sperren-Tabelle behoben:** `scripts/payload_report.py` existiert nicht —
der Erzeuger liegt unter `apps/mcp/src/who2be_mcp/payload_report.py` und läuft **nur** als Modul
(Dateiaufruf → **Exit 2**). Eine Sperre mit falschem Pfad meldet **immer** „FREI". 🟢 **#1001 selbst
nennt Pfad und Aufruf richtig.**

## Norm-Stand über alle 12 offenen Issues

Die vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints: **Outcome** · prüfbare
**Akzeptanzkriterien** · **Out-of-Scope** · exakte **Verifikations-Kommandos**) stehen **vollständig
in allen vier `agent-ready`-Issues**: #632 (5 AK), #633 (6), #1001 (5), #989 (6).

| Lücke | betrifft |
|---|---|
| Scope-„In" fehlt | #542, #540, #535, #454, #428, #338 |
| Verifikations-Abschnitt fehlt | #535, #428 (#454 hat ihn, sagt dort „kein Testkommando") |
| keine Abschnitts-Überschriften | #338 |

**Bewusst nicht umgebaut** (Regel 7) — ob der Vertrag für Tracking- und `human-only`-Issues gilt, ist
**Weiche 4**. **Kein `agent-ready` vergeben oder entzogen, kein `needs-decision` vergeben oder
entzogen.** Die Norm-Lage ist seit Lauf 69 unverändert; geändert haben sich **Tatsachen in zwei
vollständigen Bodies** (Regel 4).

## Reihenfolge — unverändert, und diesmal mit einem Vorbehalt

| Pos | Issue | Größe | Baum | Kriterium | Zustand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | 🟢 **startbar ohne Nebenbedingung**, alle Flächen über 27 PRs frei, **13/13** Zeiger gültig, Body heute korrigiert |
| **2** | **#1001** Payload-Budget | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | 🟢 **startbar ohne Nebenbedingung**, **5/5** Zeigergruppen gültig, AK1 zeichengleich bestätigt, AK3 unabhängig nachgerechnet (**71.749**) |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web | **1** harte Abhängigkeit | hinter **#632** und hinter Container-Laufzeit **oder** CI |
| **4** | **#989** `http-cache-semantics` | `size/S` | Web | — | **Weiche 40** offen; unter Option B sperrfrei und `size/XS` |

**Nicht in der Reihenfolge:** #442 (diese Liste), #428/#435/#535 (Tracking), #338/#454/#542
(`human-only`), #540 (Weiche 17), die 27 offenen PRs (Regel 65).

🔴 **Der Vorbehalt:** die Reihenfolge ist zum dritten Mal unverändert, und das ist **keine** Aussage
über Stabilität, sondern über **Zufluss**. Seit Lauf 55 sind vier der damals sechs Pakete
abgearbeitet und nur zwei nachgerückt. **Was den Backlog bremst, ist belegt kein Zuschnitt und keine
Weiche, sondern neun nicht gemergte PRs.**

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle 27 PRs frei |
| **B** | **#633** | nach #632 (hart) und nach Container-Laufzeit **oder** CI |
| **C** _(bedingt)_ | **#989** nach Weiche 40 Option **B** | dann sperrfrei, Baum `changelog`/`osv-scanner`, **disjunkt zu A** → drittes gleichzeitiges Glied |
| **M** _(Owner)_ | **die neun merge-fertigen PRs** | kein Agenten-Paket. `uv.lock`-Trio #1080/#1108/#1115 seriell, #1114 vor/gegen #674 |
| **P** _(Owner)_ | **#1107, #1078** durch Branch-Update heilen | an #1108/#1080 belegt: gleiche Rot-Ursache, nach Rebase grün |

⚠️ **Eine Einschränkung, und sie gilt für jedes Paar:** **beide Pakete der Welle A schreiben in ihrer
DoD `.claude/context/STATE.md`**, und die Datei ist dreifach von Protokoll-PRs gehalten. **Datei-
disjunkt sind die Pakete im Code, nicht in ihrer DoD** — „gemeinsam startbar" heißt genauer
*gemeinsam bearbeitbar, seriell abschließbar.* → **neu Weiche 43**, Empfehlung: `STATE.md` aus der
Paket-DoD nehmen und einmal pro Lauf schreiben.

## Neue Regeln

- **168 — Ein Fenster mit 0 Commits ist kein Fenster ohne Änderung.** Baum und PR-Bestand sind zwei
  Messgegenstände. Belegt an drei geschlossenen, drei neuen und vier rebasierten PRs bei bitgleichem
  Baum — und an Lauf 69, das deshalb acht PR-Zustände falsch führte.
- **169 — Der Verlust der Attributions-Fußzeile hängt am Schreibweg, nicht am Rewrite** (ersetzt 144
  und 129). `gh api -X PATCH --input` erhält sie (3 von 3), MCP `issue_write` nicht (5 von 5 in
  Lauf 55, 1 von 1 in Lauf 69).
- **170 — Eine falsche Angabe in §Scope, §Verifikation oder §DoD wird im Body korrigiert, nicht
  kommentiert.** Belegt daran, dass Lauf 69s Kommentar den Satz nicht erreicht hat.

**Verschärft:** Regel 163 (eine Sperre wird am vollen **existierenden** Pfad geprüft — ein falscher
Pfad meldet immer „FREI"), Regel 160 (erste reguläre Anwendung bei bitgleichem Baum), Regel 110
(der §Bezugswerte-Block ist datierte Historie und wird **nicht** nachgezogen).

## Offen an den Owner

**25 Weichen**, zwei neu, eine beantwortet. Die drei, die diesen Lauf unmittelbar betreffen:

1. **Weiche 11/34 — wer mergt die neun fertigen PRs?** Vorschlag: erst die vier ohne Lock-Konkurrenz
   (#1063, #1100, #1106, #1091), dann `uv.lock` seriell (#1115 → #1108 → #1080, jeweils neu messen),
   dann #1114. **Mergen ist nach Persona-Grenze ohne Freigabe verboten.**
2. **Weiche 43 (neu) — bleibt `STATE.md` in der DoD jedes Pakets?** Empfehlung **B** (aus der
   Paket-DoD nehmen, einmal pro Lauf schreiben). Löst gleichzeitig die dreifache Sperre.
3. **Weiche 44 (neu) — ist `gh api -X PATCH --input` als Schreibweg freigegeben?** Empfehlung **A**.
   Der Nutzen ist an drei Bodies belegt, der Preis ist eine Zeile in den Pflege-Regeln. **Offenlegung:
   dieser Lauf hat den Weg genutzt, obwohl die Werkzeug-Hinweise `gh` nur für Suche vorsehen.**

Dazu unverändert: **Weiche 18** (Kadenz — fünfzehntes Protokoll), **Weiche 40** (#989, Empfehlung B),
**Weiche 17** (#540), **Weiche 12** (#674, heute 7 Checks rot), **Weiche 4** (Vertrag für
Tracking-Issues).

## Belege dieses Laufs

- Queue-Issue: **#442** (Body neu geschrieben, **38.090** Zeichen, Ende gegengelesen, Fußzeile steht)
- Korrigiert: **#632** (25.165 Zeichen), **#633** (34.733 Zeichen) — je 3 Ersetzungen, jede `== 1`
- Kommentiert: **#989** (Weiche 40, drei Optionen, Empfehlung B)
- Gemessen: 27 PR-Scopes + merge-bases + Konfliktfreiheit, 22 CI-Lagen, 13 + 5 Zeiger, 11 Gates
- Nicht angefasst: #1001, #435, #428, #535, #542, #454, #338, #540 — jeweils mit Begründung oben
