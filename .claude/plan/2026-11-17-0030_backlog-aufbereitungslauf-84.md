# Backlog-Aufbereitungslauf 84

**Datum:** 2026-11-17
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `status --porcelain` leer)
**Fenster seit dem letzten Messpunkt:** **0 Commits — zum neunten Mal in Folge.**
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **11 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`) — **kommentiert, nicht vollgeschrieben**;
Begründung in §Der Verzicht.
**Status:** abgeschlossen (Owner-Entscheidungen offen)

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen, Issue bekommt `needs-decision`. Danach die Warteschlange
neu ordnen (harte Abhängigkeit, Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt,
bei Gleichstand das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — neunzehnter Lauf in Folge.**
Der Server verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann; ein
erneuter Verbindungsversuch über den Server-Namen wurde ausdrücklich abgelehnt. Nicht
verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die
Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage`, `submit_feedback`,
`search_memory`/`save_memory`. Persona und Playbook-Katalog lagen im System-Prompt vor. Der
Lauf fuhr nach #442 und `.github/PROJECT.md` §Constraints.
**Neunzehnter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB.**

**Kein Playbook-Trigger traf** („Backlog aufbereiten" steht in keiner Trigger-Liste; am
nächsten liegen Projekt-Standup, read-only, und Code-Task-Flow, zu groß).

**Lauf-Nummer nach Regel 70 bestimmt** (nicht aus der #442-Fußzeile): das jüngste Protokoll
ist `.claude/plan/2026-11-16-0000_backlog-aufbereitungslauf-83.md` in PR **#1145**, also ist
dies **84**.

## Messgrundlage

Alle Werte am 2026-11-17 selbst erhoben, sequenziell, **ohne vorherige Reparatur**,
Exit-Codes am unverketteten Befehl. Node **v22.23.4**, npm **10.9.9**, uv **0.11.32**,
Interpreter **CPython 3.11.18**. `npm`-Gates in `apps/web/`, Python-Gates im Repo-Root.
Klon war shallow (50) → **1676** Commits nach `--unshallow`.

| Gate | Ergebnis | gegen Lauf 83 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **405** Fragment(e); `ls changelog.d/*.md \| wc -l` = **406** | gleich |
| 🔴 `pip-audit` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **125** Requirements (398 Zeilen) | **gleich** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors** | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities | gleich |
| ⚠️ `npm audit` (voll) | ⚠️ **Exit 1**, 🔴 **27 moderate** | 🔴 **28 → 27** |
| `npx playwright test --list --project=chromium` | **44** Tests in **9** Dateien | gleich |
| `payload_report` | **Exit 0**, Builder **103 / 108.251**, `instructions` **1.834** B | 🟢 **19. identische Messung** |
| 🟢 `npm run test:coverage` | 🟢 **Exit 0**, **282** Dateien / **2849** Tests, **248,38 s** | 🟢 **gefahren statt übernommen** |
| 🟢 Coverage | 🟢 **89,89 / 83,95 / 86,81 / 91,75** | 🟢 **bestätigt** |
| 🔴 `main`-CI | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen | 🔴 **unverändert rot, 11 Tage** |
| `docker info` | 🔴 **Exit 1**; kein `podman`, kein `nerdctl` | **60. Messung in Folge** |

🟢 **Die Coverage ist nach neun Läufen Übernahme erstmals wieder selbst gefahren — und
zeichengleich bestätigt:** Statements 13163/14642, Branches 9179/10933, Functions 3793/4369,
Lines 12049/13132. **Die Übernahme der Läufe 75–83 war korrekt; das war bis heute begründet,
nicht gemessen.**

🔴 **Die einzige Zahl, die sich bewegt hat, gehört nicht dem Repo:** `npm audit` voll meldet
**27** statt 28 moderate, am bitgleichen Baum. `pip-audit` dagegen zeichengleich dieselben
7 CVEs wie in den Läufen 81–83. **Beides sind Messwerte, keine Nicht-Ereignisse** — und beide
nur bekannt, weil die Gates trotz leeren Fensters gefahren werden (Regel 181).

## Der Fund des Laufs: Welle-0-Schritt 4 macht das Gate grün, nicht die Abhängigkeit

Welle 0 in #442 führt als vierten Schritt `uv lock --upgrade-package soupsieve`. Vier Bodies
(#632, #633, #989, #1001) schreiben ihn in §Verifikation bzw. §DoD fort.

🔴 **Der Befehl hebt `soupsieve` nicht, er spaltet es.** In einem Worktree auf `origin/main`:

```
Updated soupsieve v2.9.2 -> v2.10, v4.1.1        # ZWEI Versionen
soupsieve==2.10  ; python_full_version < '3.11.5'
soupsieve==4.1.1 ; python_full_version >= '3.11.5'
```

`pip-audit` meldet darauf Exit 1 / 3 CVEs in 3 Paketen — `soupsieve` scheinbar erledigt.
🔴 **Das ist ein Artefakt des prüfenden Interpreters, kein Zustand des Locks:** `pip-audit`
wertet den Marker aus und überspringt die `2.10`-Zeile, weil der Interpreter dieses Laufs
`3.11.18` ist.

**Positiv-Kontrolle, derselbe Befehl, dieselbe Advisory-Datenbank, Marker entfernt:**

```
$ printf 'soupsieve==2.10\n' > /tmp/ctrl.txt
$ uv tool run pip-audit --disable-pip --no-deps -r /tmp/ctrl.txt
Found 3 known vulnerabilities in 1 package   # 126190 (Fix 4.0.0), 126193, 126191 (je 3.0.2)
```

🔴 **`soupsieve 2.10` trägt drei der vier CVEs**, und genau diese Version steht nach Schritt 4
für `python_full_version < '3.11.5'` im Lockfile — einen Bereich, den
`requires-python = ">=3.11"` als unterstützt deklariert. 🔴 **Der `audit`-Job pinnt dabei
keinen Interpreter:** kein `setup-python` in `ci.yml:959-975`, und `grep -c python-version`
→ **0** in allen drei Workflows. **Ob die verwundbare Zeile überhaupt geprüft wird, hängt an
einer Größe, die das Repo nicht festlegt.**

### Der Mechanismus, von `uv` selbst benannt

Der Versuch, `soupsieve>=4` direkt zu deklarieren, schlägt fehl:

```
╰─▶ Because the requested Python version (>=3.11) does not satisfy Python>=3.11.5
    and soupsieve>=4.0 depends on Python>=3.11.5 …
hint: Consider using a more restrictive `requires-python` value (like >=3.11.5).
```

🔴 **`soupsieve >= 4.0` verlangt Python >= 3.11.5.** Der Split ist kein Versehen, sondern die
einzige Lösung für die deklarierte Spanne.

### Warum Dependabot dafür keinen PR öffnet — gemessen, nicht vermutet

Für `dnspython`, `oauthlib` und `opentelemetry-api` gibt es PRs (#1141, #1120, #1142) —
**Transitivität allein erklärt die Lücke nicht**, und **kein** `pyproject.toml` deklariert
eines der vier Pakete direkt (einziger Treffer: `beautifulsoup4`, `apps/api/pyproject.toml:14`).
Der Unterschied ist die Fix-Version: **4.0.0 ist ein Major**, und das `uv`-Ökosystem in
`.github/dependabot.yml:18` hat **genau eine** Gruppe, `python-minor-patch` (`:31-35`,
`update-types: minor, patch`). 🔴 **Das eine Paket, dessen Fix ein Major ist, liegt außerhalb
der einzigen Gruppe, die es für `uv` gibt.** Der neue Gruppen-PR **#1148** belegt es: er hebt
**keines** der vier CVE-Pakete (am Inhalt gemessen).

🟢 **Gegenprobe, damit #1148 nicht fälschlich als Risiko gilt:** er dreht keinen der drei
Bumps zurück. Schrittweise gemessen (`git merge-tree --write-tree`, je rc 0): `main` + #1120
→ `oauthlib 4.0.1`, danach + #1148 → **weiter 4.0.1**; dasselbe für #1141 und #1142.
**Welle 0 bleibt reihenfolge-frei.**

### Die drei Optionen, alle drei gemessen

| | Option | Änderung | `soupsieve` im Lock | Export-Zeile | Reqs | `pip-audit` |
|---|---|---|---|---|---|---|
| **A** | `requires-python` → `">=3.11.5"` + Upgrade | 5 Dateien, je 1 Zeile | 🟢 **1×** `4.1.1` | **ohne** Marker | **123** | Exit 1, 3 CVEs / 3 Pakete |
| **B** | `environments` in `[tool.uv]` + Upgrade | 1 Datei, 1 Zeile | 🟢 **1×** `4.1.1` | **mit** Marker | **123** | Exit 1, 3 CVEs / 3 Pakete |
| **C** | nur Upgrade (heutiger Schritt 4) | 0 Dateien | 🔴 **2×** | zwei Zeilen | **126** | Exit 1, 3 CVEs — 🔴 nur dank Marker |

**Empfehlung A.** 🟢 **Ihr Preis ist an vier Stellen als 0 gemessen:** mypy
(`pyproject.toml:72` nimmt keine Patch-Ebene), `python-version` in den Workflows (0
Vorkommen), und beide Dockerfiles fahren `python:3.14-slim` (`apps/api/Dockerfile:14`/`:49`,
`apps/mcp/Dockerfile:9`/`:33`; **#1146** hebt auf 3.15). **Die Spanne 3.11.0–3.11.4, in der
allein das verwundbare `soupsieve` auflöst, benutzt kein ausgeliefertes Who2Be-Artefakt.**

🟢 **Verträglichkeit gemessen statt gehofft:** mit installierter 4.1.1 → `soupsieve 4.1.1` /
`bs4 4.15.0`, `pytest apps/api/tests/test_wa_ingest.py -q` → **Exit 0, 17 passed / 12
skipped**. `wa_ingest` ist der einzige `bs4`-Verbraucher im Repo.

## Was dieser Lauf selbst erledigt hat

### 🆕 #1150 angelegt — Weiche 54 hat einen Träger

Der Schritt lief seit Lauf 80 als „kein PR, kein Issue" mit (Regel 34a, „Fund ohne Issue").
**Dieser Lauf hat das Arbeitspaket angelegt:** **#1150**, **21.986** Zeichen, norm-vollständig
(Outcome · **5** prüfbare AK · Scope In/Out · exakte Verifikations-Kommandos), Labels
`enhancement`, `backend`, `size/S`, **`needs-decision`**.

**Bewusst kein `agent-ready`:** die Pflichtfelder stehen, aber die Startfreigabe hängt an der
Owner-Antwort A/B/C (`.github/PROJECT.md` §Constraints — „sonst `needs-decision`").

🟢 **Gegengelesen gegen die Entwurfsdatei** (Regel 73): alle **19** Überschriften in
Reihenfolge, alle Zahlen-Invarianten zeichengleich (7/4, 46, 125, 398, 123, 126, 405, 406,
5034, 659, 17 passed, 12 skipped, 4.1.1, 2.9.2, 2.10, 3.11.5, 3.11.18, 11 Tage, 27 moderate).
🟢 **`issue_write` hat keine Fußzeile angehängt — Regel 72 bestätigt.**

**AK4 ist eine Neuerung, die aus dem Fund folgt:** das Paket muss die **Positiv-Kontrolle**
fahren und im PR-Body belegen. Ohne sie ist „`pip-audit` nennt `soupsieve` nicht mehr" auch
dann erfüllt, wenn das Werkzeug die Zeile nur nicht liest.

### Fünf Kommentare mit je eigenem Befund

| Issue | Inhalt |
|---|---|
| **#442** | Lauf-84-Stand: Gates, PR-Delta, Reihenfolge, Wellen, der Fund, Weichen · **plus Selbstkorrektur** (s. §Eigene Fehler) |
| **#989** | Schritt-4-Korrektur · **28 → 27 moderate** (3 Stellen) · „398 Requirements" als falsche Größe · 43 → **46** PRs · 9 → **11** Tage · #1128 → **#1147** · AK6-Bezugswerte **gefahren und bestätigt** |
| **#1001** | Schritt-4-Korrektur · 🟢 **„ab 4.0.0" ist hier richtig** (anders als #989) · 398/125 · 26 → **46** PRs, 31 → **49** Pfade · `STATE.md` 38 → **46** Tage · alle fünf Zeigergruppen + 609 Zeilen bestätigt |
| **#632** | 🟢 **Zeiger-Tabelle 13/13 plus fünf Zeilen-Zeiger und die Baseline exakt** (14. Lauf) · Schritt-4-Korrektur · 39 → **46** PRs über **49** Pfade · Frist 17 → **13** Tage · `STATE.md` 42 → **46** · Coverage **gefahren** |
| **#633** | 🟢 **Norm selbst geprüft (6 AK nachgezählt), alle Zeiger exakt**, E2E-Verteilung 5/2/6/6/3/4/2/15/1 = **44** zahlengleich · Schritt-4-Korrektur **doppelt relevant** (CI-Ausweichweg) · `docker` 54. → **60.** Messung |

**Warum Kommentare und kein Body-Schrieb:** Lauf 83 hat die Übertragungs-Fehlerrate gemessen
(drei von sechs Vollschrieben trugen einen strukturellen Fehler). Kein Posten dieses Laufs
ändert eine Start-Entscheidung. 🟢 **Und der eine Punkt, der wirklich eine falsche Anweisung
war, steht ab heute maßgeblich im Body von #1150** — ein **neues** Dokument statt eines
Rewrites: dieselbe Wirkung, ohne Risiko am wichtigsten Body. **Das ist der Ausweg, den
Weiche 44 seit vier Läufen sucht.**

## 🔴 Eigene Fehler dieses Laufs — offengelegt, nicht berichtet

Drei, alle von der eigenen Gegenprobe gefangen, keiner stehen geblieben.

### 1. Zwei Vitest-Läufe auf demselben Coverage-Verzeichnis

Der erste `test:coverage`-Lauf endete **Exit 1** mit `Something removed the coverage
directory` — ein scheinbar abgebrochener Hintergrund-Lauf lebte doch und hat nachträglich in
dieselbe Logdatei angehängt (das Log trug am Ende **zwei** `EXIT=`-Zeilen, 1 und 0, was den
Fund auslöste). 🔴 **Mein Fehler, kein Repo-Befund.** Nach `pkill`, `rm -rf coverage` und
**einem** sauberen Lauf: Exit 0, 282/2849. **Die rote Messung ist verworfen.**
⚠️ **#632 und #633 warnen beide genau davor** („Wer misst, misst allein", Regel 31/76) — die
Warnung gilt auch für den Aufbereitungslauf.

### 2. Ein leerer Export ist ein grünes Gate, das nichts geprüft hat

Zwei meiner `uv lock`-Versuche scheiterten an einem TOML-Fehler (ein `[tool.uv]` existierte
schon in der Wurzel-`pyproject.toml`). Der daraus entstandene Export war **leer**, und
`pip-audit` meldete darauf **„Exit 0, No known vulnerabilities found"**. 🔴 **Beide Male nur
durch die Requirements-Zählung erkannt.** → als Leitplanke in #1150 §Zusätzliche Grenzen
hinterlegt. → **Regel 75.**

### 3. Die Sperren-Messung lief über 45 PRs, nicht über 46 — und eine Angabe war zu grob

🔴 Meine Zählliste hat **#1132** verschluckt. Aufgefallen durch die Gegenprobe „Zahl der
gemessenen PRs gegen Zahl der offenen PRs", **nachgeholt** (46/46, **49** Pfade).
🔴 Außerdem führte der erste #442-Kommentar `apps/mcp/**` als 🟢 FREI — **#1146 hält
`apps/mcp/Dockerfile`**. Beides in einem Folgekommentar an #442 korrigiert.
🟢 **Für die Reihenfolge ändert keiner der zwei etwas:** #1132 bewegt einen Compose-Pfad,
#1146 genau zwei Dockerfiles, und **alle drei Hebel von #1001 sind frei.**
→ **Regel 76:** eine Sperren-Messung braucht **zwei** Gegenproben — Existenz des Pfades
**und** Vollständigkeit der PR-Liste. Die erste war etabliert, die zweite nicht; sie hat hier
den Fehler gefunden.

## PR-Landschaft — 46 offen, Delta vollständig erklärt

🟢 **44 → 46 aus benannten Trägern, nicht fortgeschrieben** (Regel 69 hält, Weiche 51 gilt):

- **geschlossen, alle drei `merged: false`**, am 2026-11-16 als Dependabot-Ersetzung:
  **#1123** (05:19:52) · **#1128** (05:17:18) · **#1131** (05:27:49)
- **neu, fünf:** **#1145** (Protokoll Lauf 83) · **#1146** (Docker-Images) · **#1147**
  (`web-minor-patch`, 16) · **#1148** (`python-minor-patch`, 11) · **#1149**
  (`compose-images`, 5)
- 44 − 3 + 5 = **46** ✅

🔴 **Seit dem 2026-11-06 ist kein einziger PR gemergt.** Das ist die Ursache des neunten
leeren Fensters — ein stehender Rückstand, nicht eine Folge von Einzelfällen.

### Datei-Sperren — gegen alle 46 PRs, am vollen Pfad, Existenz zuerst belegt

| Datei | Existenz | Träger | Änderung |
|---|---|---|---|
| 🔴 `uv.lock` | belegt | **#1120, #1141, #1142, #1148** | #1123 → #1148 |
| 🔴 `apps/web/package.json` · `package-lock.json` | belegt | **#674, #1124, #1129, #1130, #1147** | #1128 → #1147 |
| 🔴 `apps/web/osv-scanner.toml` | belegt | **#1124** | unverändert |
| 🔴 `.claude/context/STATE.md` | belegt | **#1078, #1090, #1103** | unverändert |
| 🔴 `.github/PROJECT.md` | belegt | **#1105** | unverändert |
| 🔴 `apps/api/Dockerfile` · `apps/mcp/Dockerfile` | belegt | **#1146** | 🆕 **neue Sperre** |
| 🔴 Compose-/Deploy-Stacks | belegt | **#1132–#1136, #1149** | #1131 → #1149 |
| 🟢 `apps/web/src/**` · `apps/web/e2e/**` | belegt | 🟢 **KEIN** der 46 | unverändert |
| 🟢 `apps/api/src/**` · `docs/mcp-payload-budget.md` | belegt | 🟢 **FREI** | unverändert |
| 🟢 `payload_report.py` · `test_tool_payload_budget.py` | belegt | 🟢 **FREI** | unverändert |
| 🟢 `apps/web/vite.config.ts` · `.github/workflows/ci.yml` | belegt | 🟢 **FREI** | unverändert |
| 🟢 die fünf `pyproject.toml` · `.github/dependabot.yml` | belegt | 🟢 **FREI** | für #1150 gemessen |

## Norm-Prüfung — alle 13 offenen Issues

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | gelesen |
|---|---|---|---|---|---|
| **#632** | ✅ | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **selbst, ganz** |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **selbst, ganz** |
| **#633** | ✅ | ⚠️ 6 | ✅ `**Out:**` | ✅ | 🟢 **selbst, ganz** |
| **#989** | ✅ | ⚠️ 6 | ✅ | ✅ | 🟢 **selbst, ganz** |
| 🆕 **#1150** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **selbst geschrieben** |

⚠️ **Die „6 AK"-Markierung bleibt kein belegter Verstoß**, solange **Weiche 55** offen ist.
🟢 **Heute erneut gegengeprüft:** `grep -rn '2–5\|2-5\|bis 5' .github/PROJECT.md` → kein
Treffer. **Zwanzigster Lauf, in dem die einzige mögliche Quelle nicht lesbar ist.**

**Die sieben übrigen** (#428, #435, #535, #540, #454, #542, #338) **nicht neu an den Stellen
gelesen — mit Beleg statt als Abkürzung:** ihr `updated_at` liegt sämtlich **vor** dem
Lesezeitpunkt von Lauf 83 (#540 2026-10-27, #535/#435 2026-10-17, #428 2026-10-15,
#542/#454/#338 2026-10-12), ihre Bodies sind also byte-identisch zu dem, was Lauf 83 an den
Stellen gelesen hat. 🟢 **Stichprobe gefahren: #338** — `human-only`, kein `size`-Label,
**0 von 4** Feldern (der Body sagt es im Kopfblock selbst). **Deckt sich mit Lauf 83.**
→ **Regel 77:** eine Übernahme ist zulässig, wenn ihr Beleg (`updated_at` vor dem
Lesezeitpunkt) **gemessen** und eine Stichprobe gefahren ist; ohne beides ist sie eine
Abkürzung.

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` entzogen.** #1150 trägt
`needs-decision` von Anfang an.

## Reihenfolge — unverändert, und das ist das Ergebnis

Kriterien: **harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche → Inventar vor
Zuschnitt → bei Gleichstand das kleinere.**

**#632 → #1001 → #633 → #989.**

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen | `size/S` | Web/Vitest | **3** Fundament vor Fläche | ✅ **startbar**, Fläche frei, Zeiger 13/13 |
| **2** | **#1001** Payload-Budget, Rest ADR-0058 P4b | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar**, alle drei Hebel frei |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web/E2E | **1** harte Abhängigkeit | ⛔ **#632** + Container-Laufzeit (60.) |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **1** + Owner | ⛔ **Weiche 48** + fünf Schreiber |

**Im Fenster ist kein Issue geschlossen, keines der vier bewegt, keine Weiche beantwortet,
kein PR gemergt. Es gibt nichts, was eine Position verschieben könnte — zum neunten Mal.**

**Nicht in der Warteschlange:** #442 (ist die Liste) · #428/#435/#535 (Tracking-Epics) ·
#338/#454/#542 (`human-only`) · #540 (`needs-decision`, Weiche 17) · 🆕 **#1150**
(`needs-decision`, Welle-0-/Owner-Arbeit — rückt nach der Antwort A/B/C in die Liste) ·
die **46** offenen PRs (ein PR ist kein Issue).

## Wellen — was gemeinsam startbar ist

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + 🆕 #1150** | 🟢 **Schritt 4 hat ab heute einen Träger**, 🔴 aber eine offene Weiche (A/B/C). **Reihenfolge-frei**, #1148 dreht nichts zurück. **Vor allem anderen** |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle 46 frei. ⚠️ Gemeinsame DoD-Fläche `STATE.md` → zweiter rebasiert auf **#1103** |
| **B** | **#633** | nach #632 (hart) **und** Container-Laufzeit **oder** einzeln gelesenen E2E-Conclusions. Billig erst nach Welle 0 |
| **C** | **#989** | erst **Weiche 48**, dann die Fläche (fünf Schreiber, #1124 gegenläufig). **Ohne Antwort nicht starten** |
| **M** _(Owner)_ | Welle 0 → #1124 → #1148 → #1132–#1136/#1149 → #1146 → Domain-Doku | #1149 fasst 5 Compose-Pfade an und überschneidet #1133–#1136 — nacheinander. **#1106/#1122 nicht beide** (Weiche 49), **einer muss kommen** (Betreiber-Host) |
| **N** _(Owner)_ | **24 Protokoll-PRs** | #1145, #1144, #1143, #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — je eine Datei außer #1105. Danach **seriell** #1103 → #1090 → #1078 |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | #831: grünes `all-green` aus einer CI-Definition **ohne** `secrets`-Job. Erst nach Welle 0 neu messen |
| **Q** _(Owner)_ | **#674** | konfliktfrei, 0 hinter `main`, eigene Checks rot. **Empfehlung B (schließen)** |
| **R** _(Owner)_ | **#1129, #1130, #1147** | zwei Major plus Gruppen-PR, dieselbe Fläche wie #1124. **Nach #1124, einzeln** |

🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier agent-ready, zwei
blockiert. **Zum neunten Mal unverschoben.**

## Der Verzicht — #442 ist kommentiert, nicht vollgeschrieben

**71.604** Zeichen, überwiegend Entscheidungs- und Regeltext; `issue_write` ersetzt den Body
vollständig, einen Teil-Schreibweg gibt es nicht (Weiche 44 unbeantwortet).

🟢 **Die gemessene Fehlerrate aus Lauf 83 (3/6) spricht gegen einen Vollschrieb am Dokument,
das die einzige maßgebliche Reihenfolge-Quelle des Projekts ist** — und dieser Lauf hat drei
eigene Fehler offenzulegen, was die Schätzung nicht senkt. 🟢 **Was den Verzicht tragbar
macht, ist gemessen:** die Reihenfolge hat sich nicht bewegt, und der einzige Posten mit
Anweisungscharakter steht vollständig in **#1150**.

🔴 **Vierte Quittung für Weiche 44** — 🟢 **aber diesmal mit einem Ausweg, der funktioniert
hat:** eine falsche Anweisung in einem 71k-Body wird durch ein **eigenes, neues Issue**
ersetzt statt durch einen Rewrite. → **Regel 78.**

## Neue Regeln

- **75 — Ein leerer Export ist ein grünes Gate, das nichts geprüft hat.** `pip-audit` auf
  einer leeren Requirements-Datei meldet Exit 0. **Vor jeder Deutung die Requirements
  zählen.** Zweimal in diesem Lauf eingetreten.
- **76 — Eine Sperren-Messung braucht zwei Gegenproben:** Existenz des Pfades **und**
  Vollständigkeit der PR-Liste. Die zweite hat hier den Fehler gefunden (45 statt 46).
  **Und eine Sperre wird nie als Glob gemeldet** (`apps/mcp/**` war „frei", `apps/mcp/Dockerfile`
  nicht).
- **77 — Eine Übernahme ist zulässig, wenn ihr Beleg gemessen ist.** `updated_at` vor dem
  Lesezeitpunkt plus eine Stichprobe; ohne beides ist sie eine Abkürzung.
- **78 — Eine falsche Anweisung in einem sehr langen Body wird durch ein eigenes Issue
  ersetzt, nicht durch einen Rewrite.** Dieselbe Wirkung, kein Risiko am Hauptdokument.
- **79 — Ein Gate-Urteil, das an einem nicht gepinnten Interpreter hängt, ist kein Urteil.**
  Belegt an `soupsieve==2.10 ; python_full_version < '3.11.5'`.

**Ergänzt:** Regel 12 (an „398 Requirements" — die falsche Größe statt einer verrotteten
Zahl), Regel 21 (die Positiv-Kontrolle als eigenes Akzeptanzkriterium, AK4 in #1150),
Regel 69 (PR-Delta vollständig aus Trägern erklärt), Regel 72 (bestätigt: `issue_write` hängt
nichts an), Regel 73 (am #1150-Body eingelöst), Regel 163 (am eigenen Glob-Fehler),
Regel 176 (28 → 27 moderate am bitgleichen Baum), Regel 181 (beide Richtungen: npm bewegt,
pip nicht).

## Offen an den Owner — 36 Weichen, eine neu entschieden-vorgelegt

1. 🆕 **#1150 / Weiche 54, Options-Teil** — **A**, **B** oder **C**? **Empfehlung A.**
   🟢 Der Träger-Teil ist erledigt. Ohne die Antwort bleibt Welle 0 und damit ein grünes
   `audit` unerreichbar.
2. 🔴 **Weiche 11 / 2 — die Merge-Reihenfolge, und zwar jetzt.** Seit dem 2026-11-06 ist kein
   PR gemergt, **46** liegen offen, **24** davon sind Protokolle dieses Verfahrens,
   `main`-CI ist **11 Tage** rot. **Größter Hebel, und der einzige, den kein Agent allein
   bewegen kann.**
3. **Weiche 55** — Quelle der Norm-Spanne „2–5". Empfehlung **B** (in `.github/PROJECT.md`
   §Constraints nachtragen). **Zwanzigster Lauf ohne lesbare Quelle.**
4. **Weiche 46** — `glob`/`minimatch`-Frist 🔴 **13 Tage** (2026-11-30), Arbeit in #1124.
5. **Weiche 18** (Kadenz) **C** — das neunte leere Fenster hat den substanziellsten Fund seit
   Lauf 80 geliefert, **einen falschen Welle-0-Schritt**, der in einem bewegten Fenster nicht
   aufgefallen wäre.
6. 🆕 **Befund ohne Weiche:** `.github/dependabot.yml:31-35` hat für `uv` nur eine
   `minor`/`patch`-Gruppe. **Ein Paket, dessen Sicherheits-Fix ein Major ist, bekommt
   strukturell keinen Gruppen-Träger.** Als Fund in #1150 §Verweise festgehalten.

## Funde ohne Issue (Regel 34a)

- 🔴 **Ein realer Betreiber-Host liegt auf `main`** —
  `.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md:11`. `CLAUDE.md` §Security
  verbietet es, das Repo ist public, **und der Ein-Zeilen-Fix liegt in beiden Duplikat-PRs
  #1106/#1122.** → Weichen 39 und 49. **Es ist ein Merge, keine Arbeit.**
- ⚠️ **Zu Lauf 63 und 76 existiert nirgends ein Protokoll** — über `main` und alle PR-Heads
  gemessen. Dieser Lauf legt das **28.** Draft dazu.
- ⚠️ **Ein kosmetischer Rest in #1150:** „ausläßt" statt „auslässt" in §DoD. **Bewusst nicht
  korrigiert** — ein Vollschrieb von 22.000 Zeichen für einen Buchstaben ist bei gemessener
  Übertragungs-Fehlerrate das schlechtere Geschäft (Regel 74).

## Belege dieses Laufs

- **Angelegt:** **#1150** (21.986 Zeichen, gegen die Entwurfsdatei gegengelesen)
- **Kommentiert:** #442 (zweimal — Stand **und** Selbstkorrektur), #989, #1001, #632, #633
- **Kein Body geschrieben**, mit Begründung (§Der Verzicht)
- **Nicht angefasst:** #428, #435, #535, #540, #454, #542, #338 (Begründung + Stichprobe in
  §Norm-Prüfung)
- **Gates:** alle selbst gefahren, **inklusive** `test:coverage` (erstmals seit Lauf 74)
