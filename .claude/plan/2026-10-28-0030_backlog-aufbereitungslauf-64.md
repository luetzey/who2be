# Backlog-Aufbereitungslauf 64

**Datum:** 2026-10-28
**Messpunkt:** `main` @ `14234887` (`deps(security): authlib 1.9.1 + dnspython 2.9.0 in uv.lock (8 advisories)`, #1099)
**Fenster seit dem letzten Messpunkt (`3d55f09c`, Lauf 63):** **4 Commits** — das erste nicht-leere Fenster seit Lauf 61.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen und das Issue mit `needs-decision` versehen. Danach die Warteschlange neu
ordnen (harte Abhängigkeit, Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei
Gleichstand das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — der Server verlangt eine
Autorisierung, die aus dieser Session nicht gestartet werden kann.** Persona und Playbook-Katalog
lagen im System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket"), `record_usage` und `search_memory` nicht. Der Lauf
fährt deshalb nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints. **Keine
Kurations-Rückmeldung an die eigene AgentDB.** Trigger-Abgleich gegen den eingebetteten Katalog:
kein Playbook deckt die Backlog-Aufbereitung ab.

## Messgrundlage

Alle Werte am 2026-10-28 auf `main` @ `14234887` erhoben, **ohne vorherige Reparatur** (Regel 120),
**Exit-Codes ohne Pipe** (Regel 94), `npm`-Gates in `apps/web/` (Regel 146). Node **v22.22.0**.
Klon war shallow (50) → **1661** Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis |
|---|---|
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2849** Tests, **304,38 s** |
| Coverage | **89,89 / 83,95 / 86,81 / 91,75** — Statements 13163/14642, Branches **9179/10933**, Functions 3793/4369, Lines 12049/13132 |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen _(waren 160)_; Locales je **3.365** Schlüssel _(waren 3.364)_ |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `npm audit` (voll) | 🔴 **rc 1**, 1 high — `http-cache-semantics <=4.2.0`, „fix available via `npm audit fix`" |
| `uv run ruff check .` | **Exit 0** |
| `uv run mypy .` | **Exit 0**, **655** Dateien _(608 in Lauf 55)_ |
| `uv run pytest --collect-only -q` | **4971** Tests, **312** unter `packages/billing/` |
| `changelog_fragments.py check` | **Exit 0**, **397** Fragmente (Eigenzahl, Regel 143) |
| `pytest packages/billing/tests -q` | **Exit 0**, **301 passed / 11 skipped** |
| `docker info` | 🔴 **Exit 1**, kein `podman` — **40. Messung in Folge** |
| `main`-CI | **24** success, **1** skipped (`deploy`), **0** rot; `all-green` success (Status und Conclusion getrennt gelesen) |

## PR-Bestand

**22 offene PRs.** Scope je PR über `git merge-base` + `git diff --name-only` mit
Nicht-leer-Prüfung, Konfliktfreiheit über `git merge-tree --write-tree`, CI über die Check-Runs am
Head mit positivem Filter auf `failure`/`timed_out`.

- 🟢 **Alle 22 mergen konfliktfrei** (rc 0).
- 🟢 **Elf grün bei höchstens 4 Commits Rückstand**; #1102, #1101, #1098, #1085 bei **0**.
- 🔴 **Drei rot:** #674 (8 Checks), #1080 (`audit`, `all-green`), #1100 (`audit`, `all-green`).
- 🟢 **#1085 ist grün und entstapelt** — `base` jetzt `main`, 18 Check-Runs, 0 rot.
- 🔴 **Protokoll-Rückstand 8** (#1090, #1089, #1078, #1056, #1025, #1002, #990, #831); dieses ist das neunte.

## Die vier Funde des Laufs

### 1. #1077 ist erledigt — und dieser Lauf hat es selbst geschlossen

Träger war **#1087**, gemergt als `7ef15b8a`. Geprüft wurde **der gemergte Baum, nicht der
PR-Diff**: `keine eigenen Rechnungen aus` **2 → 0**, `nicht.*in der App abgebildet` **1 → 0**,
`Bis zur Umsetzung in Paket R2` **1 → 0**; `billing_invoice` **4**, `payment_id` **2**,
`invoice-retry` **2**, `invoices/` **2** (einzeln, nicht als Summe); `<PLATZHALTER` **6 → 10**
(gestiegen, wie AK3 verlangt); §7 mit **dritter** Zeile; `changelog_fragments.py check` Exit 0
(397 Fragmente) und `pytest packages/billing/tests -q` Exit 0 (301 passed / 11 skipped). Datei
**144 → 231** Zeilen.

**Begründung des Schließens:** ein offenes Issue über einer gemergten Umsetzung ist für einen
Agenten mit leerem Kontext eine Falle — er schreibt die Datei um, die schon richtig ist. **Ein
Schließen ist mit einem Klick umkehrbar, ein doppelt geschriebenes Dokument nicht.** Damit ist
**Weiche 24 durch Handlung beantwortet** und zum Schließen vorgeschlagen.

### 2. #1001 ist kein Paket mehr, sondern ein Wartestand — und sein Zuschnitt schrumpft

**#1101** fasst **alle drei Hebel** von #1001 an: die Zieldatei `docs/mcp-payload-budget.md`, den
**Erzeuger** der geforderten Zahl (`payload_report.py`) **und** den **Nachweis** aus AK5
(`test_tool_payload_budget.py`). Am Head von #1101 gelesen, nicht aus dem PR-Body:

| AK | am Head von #1101 | Rest |
|---|---|---|
| 1 Referenzprofil-Tabelle | 🟢 erledigt, zeichengleich mit der fünften unabhängigen Messung (`103 / 108.251`) | — |
| 2 ein gültiger Stand | ⚠️ überwiegend — `:262`/`:264` weg, **`:327` und `:487`** bleiben | 2 Zeilen |
| 3 `71.738` → 0 | 🔴 unberührt, weiter 2× (`:236`, `:335`); richtig **71.749** | ganz |
| 4 Historien-Zeile | 🔴 unberührt, endet mit `2026-10-23 … 103 … 108.262` | ganz |

🔴 **#1101 schreibt den Widerspruch fest:** eigene Referenztabelle **108.251**, eigene
Historientabelle `:234` **108.262**. Darin liegt der verbleibende Wert des Pakets.

**Folge für die Reihenfolge:** der **Python-Baum hat kein startbares Paket mehr**, und damit
verliert der Lauf sein einziges Parallel-Paar (#989 ‖ #1001 in Läufen 62/63). A → B → D ist eine
Kette, keine Welle. → **Weiche 35 (neu)**, Kommentar mit drei Optionen in #1001, Empfehlung **B**;
Label von `agent-ready` auf `needs-decision`.

**Zweiter Fall des Musters `Issue ⊃ offener PR`** nach #1077 ⊃ #1087, gefunden durch die
Gegenmaßnahme aus Weiche 31 B (jede Fläche gegen **alle** offenen PRs prüfen).

### 3. Zwei rote PRs sind rot aus Rückstand, nicht aus ihrem Diff — hart belegt

**#1100** ist docs-only (`CONTRIBUTING.md`, ein Fragment, `docs/adr/0033-*`) und fasst `uv.lock`
**nicht** an; trotzdem ist es an `audit` und `all-green` rot. Der Nachweis:

```
git show pr/1100:uv.lock | grep -A1 'name = "authlib"'   -> version = "1.7.2"
git show origin/main:uv.lock | grep -A1 'name = "authlib"' -> version = "1.9.1"
cmp pr/1100:uv.lock 7ef15b8a:uv.lock                      -> identisch
```

Der Baum von #1100 ist **bitgleich mit dem von #1087**, also **vor #1099** („8 advisories"). Der
Job `audit` lässt `pip-audit` auf den exportierten `uv.lock`-Deps laufen (`ci.yml:974`) — dasselbe
gilt für **#1080** (18 dahinter). **Ein Branch-Update behebt beide.**

🔴 **Verschärfend (Regel 140):** `pip-audit` läuft **vor** `npm audit` (`:984`) und der Job bricht
beim ersten Fund ab. **An beiden PRs ist damit unsichtbar, ob die npm-Hälfte — die Frist aus
Weiche 32 — auch rot wäre.** Der Rückstand erzeugt nicht nur ein falsches Rot, er **löscht die
Auskunft mit dem Datum.** → **Weiche 36 (neu)**, Empfehlung **A sofort** (zwei Branch-Updates),
**B** als kleines Paket nach dem Merge von #1091.

**Strukturelle Gegenprobe:** **#674** war in Lauf 63 bei **0** Commits Rückstand an **8** Checks
rot und ist heute bei **4** Rückstand an **denselben 8** rot. **Dort behebt ein Branch-Update
nichts.** Die beiden Fälle sehen im UI gleich aus und sind das Gegenteil voneinander.

### 4. Die Zähl-Falle hinter der 43 — Lauf 63 hatte recht, der naive Weg liegt um 1 daneben

Dieser Lauf hat erst **44** E2E-Testkörper gezählt, in einem Fenster, in dem **keine** Datei unter
`apps/web/e2e/` bewegt wurde — also eine scheinbare Veränderung ohne Ursache. Die Differenz ist
genau eine Stelle: `expectedName.test(probe.name ?? '')` in `scroll-guard.spec.ts:666`, ein
**RegExp**-Aufruf.

| Zählweg | Ergebnis |
|---|---|
| `grep -c "test("` | **44** |
| `grep -cE "^[[:space:]]*test\("` | **43** ✅ |

**Lauf 63s 43 ist bestätigt.** → **Regel 149.** Der naive Weg ist um exakt 1 falsch — klein genug,
um als Veränderung durchzugehen, und genau deshalb gefährlich.

## Was dieser Lauf selbst erledigt hat

| Artefakt | Handlung |
|---|---|
| **#1077** | **Geschlossen** (`completed`), mit allen fünf AK einzeln auf dem gemergten Baum belegt als Kommentar |
| **#1001** | **Body ergänzt** um §Startbedingung (Datei-Sperre, AK-für-AK-Abgleich gegen #1101); **drei falsche Angaben korrigiert** (Regel 145): „Keine Datei-Sperre … 18 offene PRs" → Sperre durch #1101 über alle 22; „`main` ist rot (CI-Lauf 2284)" → grün; „in den letzten 48 Stunden viermal bewegt" → seit 2026-10-22 still, fünfte gleiche Messung. **Kommentar mit drei Optionen (Weiche 35)**, Label `agent-ready` → `needs-decision` |
| **#633** | **Body korrigiert** (Regel 145): der E2E-Nenner stand auf „26 der 35 Testkörper" — gemessen **neun** Dateien / **43** Körper, davon höchstens **37** über `createUser` (Datei-Ebene, obere Grenze); ohne `E2E_EDITION=cloud` **38** / höchstens **32**. Die Zähl-Falle aus Fund 4 ist im Body benannt |
| **#442** | **Komplett neu geschrieben**: Reihenfolge, Wartestand, Wellen, Datei-Sperren, 21 Weichen, Funde ohne Issue, Pflege-Regeln 1–16 |

**Alle vier Schreibvorgänge an Bodies per `gh api --input`** (Regel 144) und **byte-exakt
zurückgelesen**: #1001 14.300 → 14.301 (abschließendes Newline), #633 28.739 = 28.739, #442 32.680
= 32.680 und nach dem Label-Nachtrag 33.243 = 33.243. **Fußzeile in allen vier je genau 1×.**

**Nicht angefasst, mit Begründung:** #989 (Body steht, Zahlen datiert und belegt — die „6 Tage" aus
Lauf 63 sind datiert, also Historie, keine Verrottung), #632 (alle Zeiger nachgeprüft und
unverändert), #435/#428/#535/#542 (Regel 7, Weiche 4), #454/#338 (`human-only`), #540
(entscheidungs- und umgebungsblockiert).

## Reihenfolge — eine Position gefallen, der Rest zieht nach

| Pos | Issue | Kriterium | Zustand |
|---|---|---|---|
| 1 | **#989** `http-cache-semantics` → 4.3.0 | 2 (Owner-Vorgabe: Frist) | startbar; **5 Tage**; Lockfile von #1092/#674 gehalten; **allein, kein Partner** |
| 2 | **#632** Passkey registrieren | 3 (Fundament vor Fläche) | **startbar ohne Nebenbedingung** — Locale-Sperre mit #1084 gefallen |
| 3 | **#633** Step-up mit Passkey | 1 (harte Abhängigkeit) | nach #632 **und** Container-Laufzeit |
| — | **#1001** Payload-Budget | — | **Wartestand** (war Position 2) |

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | #989 | allein im Web-Baum |
| **B** | #632 | nach A (derselbe Vitest-Baum) |
| **C** | Merges — elf grüne PRs bei ≤ 4 Rückstand | Klicks, kein Agent; **#1101 zuerst** (höchste Hebelwirkung) |
| **D** | #633 | nach #632, braucht Container-Laufzeit oder CI |
| **E** | #1001, neu zugeschnitten | **nach dem Merge von #1101** |

🔴 **Kein Parallel-Paar in diesem Lauf.** Der Python-Baum ist leer, solange #1001 im Wartestand
steht. **Das ist der messbare Preis der neuen Datei-Sperre**, und er endet mit dem Merge von
#1101 — Welle E ist das Parallel-Paar von morgen.

## Neue Regeln

- **148 — Absolutzahlen gehören neben jede Prozentzahl.** Die Coverage-Prozente sind zeichengleich
  mit Lauf 63 (89,89 / 83,95 / 86,81 / 91,75) — bei einem **veränderten** Baum und einem Test mehr.
  Lauf 63 hat seine Zähler/Nenner nicht festgehalten, also ist nicht entscheidbar, ob dasselbe
  gemessen wurde. **Ein Zufall auf zwei Dezimalen ist keine Bestätigung.**
- **149 — Ein Testkörper wird am Zeilenanfang gezählt.** `grep -c "test("` zählt RegExp-`.test(`
  mit und liegt um genau so viele Stellen daneben, wie es davon gibt. Belegt an
  `scroll-guard.spec.ts:666`.

**Ergänzt:** Regel 7 (die Fläche eines Pakets umfasst auch den **Erzeuger** der geforderten Zahl
und den **Nachweis**, nicht nur die Zieldatei — belegt an #1001/#1101), Regel 10 (hat die
44/43-Fehlmeldung abgefangen), Regel 14 (Weiche 32 behält ihre Empfehlung, aber ihr Preis ist
gestiegen — das gehört dazugeschrieben).

## Offen an den Owner

**21 Weichen**, zwei neu, zwei zum Schließen vorgeschlagen. Vollständig in #442; die fünf, die
diesen Lauf unmittelbar betreffen:

1. **Weiche 32** — die Frist, jetzt **5 Tage**. Empfehlung bleibt **A** (#1092 mergen, dann #989),
   aber #1092 steht nicht mehr bei 0, sondern **4** Commits hinter `main`. **B** ab 2026-10-31,
   **C** nur ab 2026-11-01.
2. **Weiche 35 (neu)** — was mit #1001 passiert. Empfehlung **B** (vier Restzeilen als Review an
   #1101, dann schließen), **A** als Rückfallebene.
3. **Weiche 36 (neu)** — wer einen PR aktualisiert, dessen Rot nur Rückstand ist. Empfehlung
   **A sofort** (zwei Branch-Updates), **B** nach dem Merge von #1091. **C nicht.**
4. **Weiche 24 und 33** — beide **beantwortet**, 24 durch Handlung dieses Laufs, 33 durch den Merge
   von #1054. **Zum Schließen vorgeschlagen.**
5. **Weiche 28** — die PM-Frage in #1085. **Jetzt fällig:** der Stapel ist weg, #1085 ist grün und
   0 dahinter, es hält nichts mehr auf außer dieser Antwort.

## Belege dieses Laufs

- Queue-Issue: **#442** (Body neu geschrieben, **33.243** Zeichen, zweifach gegengelesen)
- Geschlossen: **#1077** (`completed`, mit Beleg-Kommentar)
- Body korrigiert: **#1001**, **#633**
- Kommentiert: **#1077** (Erledigungs-Beleg), **#1001** (Weiche 35, drei Optionen)
- Label geändert: **#1001** (`agent-ready` → `needs-decision`)
