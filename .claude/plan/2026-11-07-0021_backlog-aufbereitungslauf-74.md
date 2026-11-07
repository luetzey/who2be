# Backlog-Aufbereitungslauf 74

**Datum:** 2026-11-07
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`), Kopf-Commit vom **2026-11-06T08:05:51+01:00**
**Fenster seit dem letzten Messpunkt:** 🟢 **10 Commits** — **das sechstägige Stillstands-Fenster ist zu Ende.**
**Warteschlange:** #442 (Label `backlog-queue`).
**Offene PRs:** **24** (waren 31 bei Lauf 73).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere)
und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — der Server verlangt eine
Autorisierung, die diese Session nicht selbst anstoßen kann.** Persona und Playbook-Katalog
lagen im System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket"), `record_usage` und `search_memory` nicht.
Der Lauf fährt deshalb nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints.
**Keine Kurations-Rückmeldung an die eigene AgentDB** — der Dauerzustand dieser Lauf-Reihe;
der Zugang muss in den Connector-Einstellungen freigegeben werden.

## Messgrundlage

Alle Werte am 2026-11-07 auf `main` @ `f89acf87` erhoben, **ohne vorherige Reparatur**
(Regel 120), Exit-Codes am unverketteten Befehl (Regel 94/172), `npm`-Gates in `apps/web/`,
Python-Gates im Repo-Root, sequenziell (Regel 164). Node **v22.23.4**, npm **10.9.9**,
uv **0.11.32**. Klon war shallow (50) → **1676** Commits nach `--unshallow` (Regel 90).
⚠️ `/usr/bin/time` existiert hier nicht (Regel 177) — **ohne Wrapper gemessen**.

| Gate | Ergebnis | gegen Lauf 73 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | 🟢 **+1** (#1063s Regressionstest) |
| `changelog_fragments.py check` | **Exit 0**, **406** Fragmente | **+3** |
| 🔴 `uv tool run pip-audit … -r <reqs>` | 🔴 **Exit 1** — **`oauthlib 4.0.0`, CVE-2026-49272, Fix 4.0.1**, bei **398** Requirements | 🔴 **unverändert rot — durch zehn Merges hindurch** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, „Alle i18n-Pruefungen in Ordnung" | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **28 moderate** — 1 `glob`-Knoten + **8** `minimatch`-Knoten | gleich |
| `npm run test:coverage` | 🟢 **Exit 0**, **282** Dateien / **2849** Tests, **291,29 s** | **selbst gefahren** |
| Coverage | **89,89 / 83,95 / 86,81 / 91,75** (Statements 13163/14642, Branches 9179/10933, Functions 3793/4369, Lines 12049/13132) | 🟢 **alle vier Absolutpaare zeichengleich** |
| 🔴 **`main`-CI am Kopf `f89acf87`** | 🔴 **Lauf `42178623925`, `conclusion: failure`** — **2 von 14 Jobs rot: `audit` und `all-green`** | 🔴 **Lauf 73 hat das vorhergesagt; jetzt ist es gemessen** |

🟢 **Die zeichengleiche Coverage ist kein Zufall und keine Übernahme, sondern erklärt.** Das
Fenster bewegt **17** Dateien, **null** davon unter `apps/web/src/**` (gemessen:
`git diff --name-only af78ad7d origin/main -- apps/web/src` → 0 Zeilen). Dieselbe Rechnung
erklärt die Collection: `apps/api/**` hat sich bewegt (#1063), und die Testzahl steigt um
genau **1**.

🟢 **`npx tsc -b`, `lint` und `i18n:check` sind trotz des `ci.yml`-Merges (#1091) unverändert** —
`ci.yml` ist weiter **1259** Zeilen lang; #1091 hat Action-SHAs getauscht, keine Zeilen.

## Die vier Funde des Laufs

### 1. 🔴 Zehn Merges — und der Drei-Zeilen-PR, der die CVE in `main` behebt, war nicht dabei

Lauf 73 hat #1120 zum **obersten Posten des ganzen Backlogs** erklärt: es behebt
CVE-2026-49272 in `main` und entsperrt damit das `audit`-Gate repo-weit. **Danach sind zehn
PRs gemergt worden — #1120 nicht.**

Gemergt im Fenster: #1108, #1080, #1063, #1100, #1114, #1091, #1116, #1095, #1096, #1097.
**Nicht gemergt: #1120.**

**Selbst gemessen am heutigen `main`-Stand, mit dem Befehl der CI-Definition
(`ci.yml:975`):**

```
$ uv export --format requirements-txt --no-emit-workspace --no-hashes --group billing > reqs.txt
$ uv tool run pip-audit --disable-pip --no-deps -r reqs.txt ; echo "EXIT=$?"
Found 1 known vulnerability in 1 package
Name     Version ID             Fix Versions
-------- ------- -------------- ------------
oauthlib 4.0.0   CVE-2026-49272 4.0.1
EXIT=1                                        # 398 Requirements
$ grep -A2 '^name = "oauthlib"' uv.lock        # version = "4.0.0"
```

🔴 **`main`s eigener CI-Lauf ist jetzt rot, nicht mehr nur veraltet.** Lauf
`42178623925` am Kopf `f89acf87` trägt `conclusion: failure`; von **14** Jobs sind genau
**zwei** rot, und `all-green` nennt den Grund wörtlich:

```
##[error]audit: 'failure', erwartet 'success'.
all-green: FEHLGESCHLAGEN.
```

Lauf 73 hatte geschrieben: „ein frischer Lauf auf `main` wäre heute rot." **Das ist jetzt
keine Prognose mehr.** _(Die acht Läufe unter dem Kopf tragen `cancelled` — Concurrency aus
der schnellen Merge-Folge, kein Befund; Regel 91.)_

🟢 **Der Fix ist drei Zeilen groß und bewirkt gemessen genau das, was er soll.** Der
**effektive** Diff von #1120 gegen den **heutigen** `main` (über `git merge-tree --write-tree`,
rc 0):

```
 uv.lock | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)
```

— nichts als `version`, `sdist` und `wheel` von `oauthlib`. 🟢 **Der von Lauf 73 gemeldete
Nebeneffekt „Revision 3 → 5" ist weg:** `main` trägt `revision = 5` inzwischen selbst
(`uv.lock:2`), der Posten hat sich durch das Fenster erledigt.

🟢 **Und die Wirkung ist belegt, nicht angenommen:** `pip-audit` auf dem Ergebnisbaum des
Merges (`be654b38`) → **Exit 0**, „No known vulnerabilities found", bei denselben **398**
Requirements, `oauthlib==4.0.1` im Export.

🔴 **#1120 ist der einzige offene PR, der den Fix trägt.** Gegenprobe an dem einzigen anderen
`uv.lock`-PR: **#1123** (`python-minor-patch`, 13 Versionssprünge) führt `oauthlib` weiter in
**4.0.0**. Wer #1123 statt #1120 mergt, hebt dreizehn Pakete und die CVE bleibt.

→ **Regel 182.**

### 2. 🔴 Das Gate verdeckt, ob der PR grün ist, der die nächste Frist abwendet

🆕 **#1124 ist neu und nimmt sich Weiche 46 vor** — den `glob`/`minimatch`-Ablauf am
2026-11-30. Es setzt `overrides` in `apps/web/package.json` und **entfernt beide
`[[IgnoredVulns]]`-Blöcke** aus `apps/web/osv-scanner.toml`.

**Sein Stand, selbst gemessen:** **0** Commits hinter `main`, konfliktfrei (rc 0), kein Draft,
**4** Dateien, **18** Check-Runs — **16 grün**, darunter `web`, `e2e`, `python`,
`compose-smoke`, `CodeQL` und alle drei `Analyze`. 🔴 **Rot sind genau zwei: `audit` und
`all-green`.**

🔴 **Und `audit` ist nicht an #1124s Inhalt gescheitert, sondern an `main`s CVE.** Der
Job-Log (`127774423452`, 2026-11-06T07:39:28) endet so:

```
oauthlib 4.0.0   CVE-2026-49272 4.0.1
##[error]Process completed with exit code 1.
```

**Der `audit`-Job fährt `pip-audit` als Schritt 3 und `OSV-Scan` erst als Schritt 13**
(`ci.yml`, Job `audit`: „Export non-workspace deps" → „pip-audit (Python)" → … →
„npm audit (Web, prod-only, high+)" → „License check" → „OSV-Scan"). **Der Abbruch im dritten
Schritt heißt: der OSV-Scan ist nie gelaufen.**

🔴 **Damit ist die eine Frage, die #1124 beantworten soll — „ist der Scan ohne die beiden
Ausnahmen grün?" — aus der CI nicht ablesbar.** Die Job-Conclusion sagt „rot", und sie sagt
nichts über den Schritt, um den es geht.

🟢 **Die tragende Behauptung von #1124 habe ich deshalb selbst geprüft, auf einem zweiten
Weg.** #1124s neuer Kopfkommentar begründet die Entfernung damit, `minimatch@3.1.5` liege
„*outside the corrected range of GHSA-g3hv-75wg-m249 (>=7.0.0 <11.0.1, OSV record modified
2026-11-04)*". ⚠️ Die OSV-API ist aus dieser Umgebung nicht erreichbar (`api.osv.dev` →
Proxy 403), **also über die Advisory-Daten von npm gegengeprüft**:

| Messung | Ergebnis |
|---|---|
| Range `GHSA-g3hv-75wg-m249` (`npm audit --json`) | `>=7.0.0 <11.0.1` — 🟢 **deckt 3.1.5 nicht** |
| Range `GHSA-3g3m-2fjr-6pw4` (`glob`) | `>=9.0.0 <=14.0.1` — 🟢 **deckt 14.0.3 nicht** |
| von npm gemeldete `minimatch`-Knoten | **8** — 🟢 **`eslint-plugin-jsx-a11y`s 3.1.5 ist NICHT darunter** |
| Bestand im Lockfile von `main` | `minimatch` 10.2.5 ×7, 10.2.6 ×1, **3.1.5 ×1**; `glob` 13.0.6 ×1 |
| Bestand im Lockfile von #1124 | `minimatch` **11.0.3 ×8**, 3.1.5 ×1; `glob` **14.0.3 ×1** |

🟢 **#1124 hat recht, und die Zahlen gehen auf:** 9 `minimatch`-Instanzen, 8 gemeldet, die
nicht gemeldete ist die 3.1.5. 🔴 **Nebenbefund:** der `reason`-String der heute noch
stehenden Ausnahme nennt „`minimatch@10.2.5/10.2.6/3.1.5`" als betroffen — **3.1.5 liegt
außerhalb des Ranges und war nie ein Fund.** Die Zahl stand so auch in #442 §Weiche 46.

→ **Regel 183.**

### 3. 🔴 #989 und #1124 verlangen von derselben Datei das Gegenteil

#989 §AK2, wörtlich: „🔴 **`grep -c "IgnoredVulns" apps/web/osv-scanner.toml` → bleibt `2`.**
… **Diese zwei Blöcke werden nicht angefasst.** Wer sie entfernt, macht `osv-scanner` rot."

**Gemessen an #1124s Baum:** `grep -c IgnoredVulns` → **0**. Beide Blöcke sind weg.

🔴 **Nach einem Merge von #1124 ist #989s AK2 nicht nur veraltet, sondern wieder schädlich —
diesmal in die andere Richtung.** Ein Agent mit leerem Kontext, der sie wörtlich erfüllt,
**trägt die beiden Ausnahmen wieder ein**, die #1124 gerade mit Beleg entfernt hat. Das ist
dieselbe Fehlerklasse, die Lauf 68 aus diesem Body entfernt hat (die alte AK2 forderte `0`,
als `2` richtig war) — nur mit getauschten Vorzeichen.

⚠️ **Und der erste Punkt von AK2 bleibt offen, auch nach #1124:** `grep -c "turns red again"`
ist in #1124s Fassung weiter **1**. Der Satz beschreibt den Mechanismus falsch — und nach
#1124 beschreibt er zusätzlich nichts mehr, weil es keine Ausnahme mehr gibt, die ablaufen
könnte. **#1124 nimmt #989 die Hälfte seiner AK2 weg und macht die andere Hälfte dringender.**

→ **Weiche 48**, neu, als Kommentar an #442 und an #989.

### 4. 🔴 Ein Zeiger ist an einem fremden Merge verrottet — und zwei PRs machen dieselbe Arbeit

**(a) #989s Lockfile-Zeiger.** AK1 nennt den Eintrag an **`:6295`** und die
`"version"`-Zeile an **`:6296`**. **Heute gemessen:** Eintrag **`:6313`**, `"version"`
**`:6314`**, `resolved` `:6315`. **Verschoben um 18 Zeilen durch den Merge von #1114** — das
Paket selbst hat sich nicht bewegt, die Version ist unverändert `4.2.0`. **Im Body
korrigiert.** → **Regel 184.**

**(b) #1106 und #1122 sind zwei offene PRs für dieselbe Arbeit.** Beide fassen **dieselben
vier** Dateien an (`.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md`,
`.claude/plan/2026-10-31-0056_domain-umzug.md`, `changelog.d/domain-move-checklist.added.md`,
`docs/cloud-erstinbetriebnahme.md`), beide **10** Commits hinter `main`, beide gegen `main`
einzeln konfliktfrei. **Ihre Ergebnisbäume unterscheiden sich um genau eine Datei:**

```
$ git diff --stat <tree1106> <tree1122>
 docs/cloud-erstinbetriebnahme.md | 14 ++++++++++----
 1 file changed, 10 insertions(+), 4 deletions(-)
```

**#1122 ist die erweiterte Fassung von #1106.** Wer beide mergt, mergt zweimal dasselbe und
kollidiert beim zweiten Mal. → **Weiche 49**, neu.

**(c) Eine eigene Korrektur.** #442 §Welle N führt **#1105** in der Gruppe „je genau eine
Datei, paarweise konfliktfrei, beliebige Reihenfolge". **Gemessen: #1105 fasst zwei Dateien
an** — sein Protokoll **und** `.github/PROJECT.md`. 🟢 **Die Folgerung hält trotzdem:**
`.github/PROJECT.md` wird von **keinem** anderen offenen PR gehalten, #1105 ist also weiter
paarweise konfliktfrei. **Richtiges Ergebnis, falscher Grund** — korrigiert.
→ **Regel 185.**

## Norm-Prüfung „Agent-ready Arbeitspaket" — 4 von 4 vollständig

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **13/13 gültig** | 🟢 vollständig, **ohne Fund — achter Lauf in Folge** |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **5/5 gültig** | 🟢 vollständig, **ohne Fund** |
| **#633** | ✅ | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 **E2E-Rechnung dreifach geschlossen** | 🟢 vollständig |
| **#989** | ✅ | ✅ 6 | ✅ | ✅ | 🔴 **1 verrottet (AK1), 1 Konflikt (AK2)** | 🟢 vollständig — 🔴 **Body korrigiert, Weiche 48 gestellt** |

**Einzeln nachgemessen am 2026-11-07:**
`MfaSection.tsx` **297** · `MfaSection.test.tsx` **284** · `MfaSection.a11y.test.tsx` **45** ·
`src/auth/SessionProvider.tsx` **267** · `LoginPage.tsx` **399** · `src/api/client.ts` **1849** ·
`src/api/types.ts` **2407** · `e2e/helpers/auth.ts` **199** (`createUser` an `:33`) ·
`vite.config.ts` **107** · `src/test/a11y.test.ts` **77** ·
`i18n/locales/{de,en}.json` je **4.661** Zeilen und je **3.365** flache Schlüssel
(Parität nachgerechnet) · `i18n/orphan-baseline.json` **156** Einträge ·
`createUser`: **39** Vorkommen / **31** Aufrufstellen / **7** von 9 Dateien
(Lauf 73s Korrektur hält) ·
`e2e/*.spec.ts` **9** Dateien, `^test(` → **42**, `^test.skip(` → **1**, zusammen **43** ·
`ci.yml` **1259** Zeilen, `:325` `test:a11y`, `:463` `npm run e2e -- --project=chromium`,
`:544` `npx playwright test e2e/billing.spec.ts`, `:780` `changelog-guard`,
`:1029` `license:check` — alle wörtlich bestätigt ·
`docs/mcp-payload-budget.md` **609** Zeilen, `104.777` an `:233`/`:292`/`:327`/`:487`,
`108.262` an `:234`/`:331`, `71.738` an `:236`/`:335`, Kopf `:254` „Stand 2026-10-27" ·
`osv-scanner.toml` **26** Zeilen, `IgnoredVulns` **2×**, `turns red again` an `:6` ·
`changelog.d/osv-ignore-http-cache-semantics.security.md` existiert, **8** Zeilen ·
`apps/web/package.json` **82** Zeilen (`engines.node` `">=22 <23"` an `:8`,
`license-checker-rseidelsohn` `"^5.0.1"` an `:74`, `license:check` an `:19`).

🔴 **Die Zeile „`main` ist gemessen grün" in #989 ist heute falsch und wird korrigiert, nicht
mehr stehen gelassen.** Lauf 73 hatte sie bewusst gehalten mit der Begründung, ein Merge von
#1120 mache sie „in Stunden" wieder richtig. **Sieben Tage später ist #1120 offen und `main`s
CI-Lauf rot.** Für die **Baum**-Gates stimmt die Aussage weiter (ruff, mypy, Collection, tsc,
lint, i18n, Coverage, Fragmente: alle Exit 0) — für `pip-audit` und für `all-green` auf `main`
nicht. **In #989 präzisiert; #632, #1001 und #633 tragen die Aussage nicht in dieser Form.**

**Norm-Stand der acht übrigen Bodies — unverändert, bewusst nicht umgebaut:** Outcome fehlt in
#542, #535, #428; Verifikations-Abschnitt fehlt in #535 und #428; #454 hat ihn mit „Kein
Testkommando — die Verifikation ist die Produktions-Smoke-Reise"; #338 trägt keine
Abschnitts-Überschriften; #540 trägt alle vier und bleibt `needs-decision`, weil die
Mechanismus-Entscheidung fehlt, nicht ein Feld; #435 trägt Outcome nur inline.
**Ein `size/M`-Issue wird nicht durch Nachtragen von Feldern startbar**
(`.github/PROJECT.md` §Constraints). Regel 7, Weiche 4.

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines
entzogen.** #989 trägt `needs-decision` seit Lauf 68 und behält es (Weichen 40/46/47/**48**).

## PR-Bestand

Scope je PR über `git merge-base` + `git diff --name-only` (Nicht-leer-Prüfung je PR),
Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über `git rev-list --count` —
**alle 24 heute selbst gerechnet.**

- 🔴 **Die Serie „alle mergen konfliktfrei" ist gerissen: #674 kollidiert jetzt** (rc 1).
  Ursache ist der Merge von **#1114** — beide fassen `apps/web/package*.json` an. Lauf 73 hat
  #674 noch als konfliktfrei gemessen. **23 von 24 sind konfliktfrei.**
- **Rückstand:** **0** → #1124 · **6** → #1123 · **10** → #1122, #1121, #1120, #1119, #1118,
  #1117, #1113, #1112, #1106, #674 · **15** → #1107, #1105, #1104, #1103 · **19** → #1090,
  #1089 · **33** → #1078 · **48** → #1056 · **73** → #1025 · **89** → #1002 · **114** → #990 ·
  **237** → #831.
- 🔴 **Protokoll-Rückstand: 18.** Auf `main` liegen Protokolle für Lauf **31** und **43–55**;
  für **56–73** keines. Siebzehn stecken in offenen Drafts (#990=56, #1002=57, #1025=58,
  #1056=59, #1078=60, #1089=61, #1090=62, #1103=64, #1104=65, #1105=66, #1107=67, #1112=68,
  #1113=69, #1117=70, #1118=71, #1119=72, #1121=73), dazu #831=42. **Zu Lauf 63 existiert
  nirgends ein Protokoll** — Weiche 38 hält. Dieser Lauf legt das **neunzehnte** dazu.
- **Dateizahl je Protokoll-PR, gemessen:** **14** fassen genau eine Datei an (#1121, #1119,
  #1118, #1117, #1113, #1112, #1107, #1104, #1089, #1056, #1025, #1002, #990, #831), **vier**
  fassen zwei an — **#1105** (`.github/PROJECT.md`) und **#1103/#1090/#1078**
  (`.claude/context/STATE.md`). 🟢 **Paarweise konfliktfrei sind trotzdem 15**, weil
  `.github/PROJECT.md` nur von #1105 gehalten wird; seriell nötig sind nur die drei
  `STATE.md`-Träger.
- 🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02 geschrieben** —
  **36 Tage** alt, **dreifach gehalten** (#1103 bei 15, #1090 bei 19, #1078 bei 33).
  **Wer ein Paket abschließt, nimmt #1103 als Basis.**

### Datei-Sperren — gegen alle 24 PRs, am vollen Pfad, Existenz zuerst belegt (Regel 163)

Die 24 PRs bewegen zusammen **29** Dateipfade _(waren 48 bei 31 PRs)_.

| Datei | Träger |
|---|---|
| 🔴 `.claude/context/STATE.md` | **#1103**, **#1090**, **#1078** — dreifach, alle drei Protokolle |
| 🔴 `uv.lock` | **#1120**, **#1123** — **zweifach, waren vier** |
| 🔴 `apps/web/package.json` · `apps/web/package-lock.json` | **#1124** (grün außer `audit`) und **#674** (rot **und jetzt kollidierend**) |
| 🆕 🔴 `apps/web/osv-scanner.toml` | **#1124** — **war bei Lauf 73 noch FREI** |
| 🆕 `changelog.d/web-glob14-minimatch11-overrides.security.md` | #1124 |
| 🔴 `.github/PROJECT.md` | **#1105** |
| ⚠️ 4 Pfade der Domain-Umzug-Doku | **#1106 und #1122 — dieselben vier, s. Fund 4b** |
| 🟢 **`apps/web/src/**` (der ganze Vitest-Baum)** | 🟢 **KEIN EINZIGER der 24 PRs** |
| 🟢 `docs/mcp-payload-budget.md` (609 Z) · `apps/mcp/**` | 🟢 **FREI** |
| 🟢 `changelog.d/osv-ignore-http-cache-semantics.security.md` (8 Z) | 🟢 **FREI** |
| 🟢 `.github/workflows/ci.yml` (1259 Z) · `deploy.yml` | 🟢 **FREI** — #1091 ist gemergt |
| 🟢 `deploy/hetzner/Caddyfile` · `deploy/monitor/compose.yml` | 🟢 **FREI** — #1097/#1116 sind gemergt |

**Jede als FREI gemeldete Datei ist vor der Prüfung auf Existenz belegt** (Regel 163).

🟢 **Zwei Sperren haben sich durch das Fenster gelöst:** `ci.yml` (war #1091) und der
Caddy-Pfad (war #1097/#1116). **Das macht #540 mechanisch freier** — es bleibt aber an
Weiche 17 und an der fehlenden Container-Laufzeit blockiert.

## Reihenfolge und Wellen

Kriterien: **1** harte Abhängigkeit · **2** Owner-Vorgabe · **3** Fundament vor Fläche ·
**4** Inventar vor Zuschnitt · **5** bei Gleichstand das kleinere.

⚠️ **Eine Nebenbedingung gilt für JEDES Paket, bis #1120 gemergt ist:** das `audit`-Gate ist
wegen der CVE in `main` rot, also wird **jeder** neue PR rot an `audit` + `all-green`, ohne
dass es am Paket liegt — **belegt an #1124 und an `main` selbst.** Das ist kein Grund, nicht
zu starten; wer startet, nennt den Grund im PR.

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren (#435 W2a) | `size/S` | Web/Vitest | **3** (öffnet #633) | 🟢 **startbar ohne Nebenbedingung.** 13/13 Zeiger gültig, `apps/web/src/**` über alle 24 PRs frei |
| **2** | **#1001** Payload-Budget (ADR-0058 P4b) | `size/S` | Python/pytest | **4** | 🟢 **startbar ohne Nebenbedingung.** 5/5 Zeiger gültig, alle drei Schreibflächen frei |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web | **1** (nach #632) | 🔴 zwei Blocker: #632 (hart) + Container-Laufzeit **oder** CI |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web/Lockfile | **1** | 🔴 **zurückgefallen.** Sperre gewechselt: #1114 ist gemergt, jetzt halten **#1124 und #674** die Fläche — **und #1124 widerspricht AK2 inhaltlich** (Weiche 48) |

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120** | **Der CVE-Fix.** Drei Zeilen gegen den heutigen `main`, konfliktfrei, `audit` grün, **Wirkung gemessen** (`pip-audit` Exit 0 auf dem Ergebnisbaum). **Vor allem anderen** — er entsperrt das Gate für jeden PR und für `main` |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle 24 PRs frei. ⚠️ Gemeinsame DoD-Fläche `STATE.md` → wer zweiter fertig wird, rebasiert (Basis **#1103**) |
| **B** | **#633** | nach #632 (hart) und nach Container-Laufzeit **oder** CI |
| **C** | **#989** | 🔴 **nicht mehr nur mechanisch blockiert.** Erst **Weiche 48** (Reihenfolge gegen #1124), dann die Fläche. Ohne Antwort nicht starten |
| **M** _(Owner)_ | **#1120** → **#1124** → #1123 → die Domain-Doku | 🔴 **#1120 zuerst** (CVE). Dann **#1124**, dessen OSV-Nachweis erst danach lesbar ist. Dann **#1123** (`uv.lock` neu messen). **#1106/#1122 nicht beide** — s. Weiche 49 |
| **N** _(Owner)_ | **15 Protokoll-PRs in beliebiger Reihenfolge** | #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — paarweise konfliktfrei (#1105 fasst zwei Dateien an, hält `.github/PROJECT.md` aber allein). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | #1107, #1078, #831 durch Branch-Update heilen | alle drei rot aus **echtem Rückstand** (#1107s Log: `joserfc 1.7.2`, `pypdf 6.21.2` — von #1111 behoben). ⚠️ **Nach dem Merge von #1120 neu messen** — vorher ist jedes Rot doppelt verursacht |
| **Q** _(Owner)_ | **#674** | 🔴 **neu kollidierend** seit dem Merge von #1114. Weiche 12 unverändert |

🔴 **Mehr als drei gleichzeitige Pakete gibt der Backlog nicht her** — vier Arbeitspakete
offen, zwei blockiert. **Der Engpass bleibt der Abfluss, aber er hat sich verschoben:** das
Fenster hat zehn PRs abgeräumt und **die beiden wichtigsten liegen gelassen** — den CVE-Fix
(#1120) und, als Folge, den Nachweis von #1124.

## Offene Weichen

**28 bestehende werden nicht erneut gestellt** (Regel 9). Dieser Lauf legt **zwei** dazu und
ändert **sechs**:

- 🆕 🔴 **48 NEU: In welcher Reihenfolge gehen #1120, #1124 und #989 — und wie wird #989s AK2
  formuliert, die #1124 widerspricht?** Drei Optionen + Empfehlung als Kommentar an #442 und
  #989. Empfehlung **A** (#1120, dann #1124, dann #989 mit auf `0` umgeschriebener AK2).
- 🆕 ⚠️ **49 NEU: #1106 und #1122 sind zwei offene PRs für dieselbe Arbeit.** Empfehlung **B**
  (#1122 behalten — es ist die erweiterte Fassung —, #1106 schließen).
- 🔄 🔴 **41 (`pip-audit` in die Befehlsliste): Empfehlung C, jetzt mit Beleg aus zwei
  Läufen.** Lauf 73 hat die Weiche als „übernommen" abgehakt und damit die CVE verdeckt;
  dieser Lauf hat `pip-audit` gefahren und **denselben Fund sieben Tage später unverändert
  vorgefunden**. `grep -c pip-audit CLAUDE.md` → **0**.
- 🔄 🔴 **36 (Rot aus Rückstand): Empfehlung A, aber die Messung ist bis #1120 nicht
  trennscharf.** Solange `main` die CVE trägt, ist jedes `audit`-Rot doppelt verursacht —
  #1124 ist der heutige Beleg. **Nach dem Merge von #1120 neu messen.**
- 🔄 🔴 **5 (`audit` im Required Check): Einsatz erneut gestiegen.** `ci.yml` ist jetzt
  **frei** (#1091 gemergt), die Weiche also mechanisch umsetzbar. 🔴 **Und der Schaden ist
  heute nicht mehr hypothetisch:** ein Required Check an einer fremden Datenbank hat `main`
  rot gemacht **und** verdeckt den Nachweis eines zweiten PRs (Fund 2).
- 🔄 🔴 **46 (`glob`/`minimatch`-Frist): es gibt jetzt einen PR, aber kein Issue.** **#1124**
  macht die Arbeit, seine tragende Behauptung ist heute unabhängig geprüft (Fund 2), und seine
  **23 Tage** Frist läuft weiter. **Empfehlung wechselt B → A** (mergen statt Frist
  verlängern) — mit der Auflage aus Weiche 48.
- 🔄 🔴 **40 (behält #989 einen Platz?): Empfehlung A bleibt, aber der Zuschnitt ändert sich.**
  Nach #1124 ist AK2 zur Hälfte gegenstandslos und zur Hälfte dringlicher; der 4.3.0-Bump
  selbst bleibt ein Ein-Zeilen-Weg.
- 🔄 🟢 **18 (Kadenz): Empfehlung C.** Das Fenster war **nicht** leer, und der Lauf hat
  trotzdem vier Funde gebracht, **darunter zwei, die nur ein bewegtes Fenster erzeugt** —
  der verrottete Lockfile-Zeiger und die neue Kollision von #674. **Das ist das erste
  Fenster, das das Argument aus der anderen Richtung stützt.**

## Doku-Nachzug

Keiner nötig: dieser Lauf ändert kein öffentliches Verhalten (keine API-Signatur, kein
CLI-Flag, keine Konfig, kein Setup). Die Änderungen liegen in Issue-Bodies auf GitHub und in
diesem Protokoll. **Kein CHANGELOG-Fragment** — der Bestand bleibt bei **406**.

🟢 **Dieser PR fasst nur die eigene Plan-Datei an** — nicht `STATE.md` und nicht
`.github/PROJECT.md` —, damit er in Welle N in beliebiger Reihenfolge mergebar bleibt
(Regel 185: und das ist hier gemessen, nicht behauptet).

## Neue Pflege-Regeln

- **182. Ein bewegtes Fenster ist kein Beleg, dass das Dringende gemergt wurde.** Zehn Merges,
  und der Drei-Zeilen-PR, den der Vorlauf zum obersten Posten des Backlogs erklärt hat, lag
  danach unverändert offen. **Was „oberster Posten" heißt, wird nach jedem Fenster neu
  gemessen, nicht abgehakt** — und am besten mit der Wirkung belegt, nicht mit der Absicht
  (`pip-audit` auf dem Ergebnisbaum des Merges, nicht auf dem Branch).
- **183. Ein Gate, das vor dem interessanten Schritt abbricht, macht ihn unbeobachtbar.** Der
  `audit`-Job fährt `pip-audit` als dritten und `OSV-Scan` als dreizehnten Schritt; ein Fund
  im dritten sagt nichts über den dreizehnten. **Wer eine Aussage über einen späteren Schritt
  braucht, liest den Job-Log oder misst selbst — die Job-Conclusion genügt nicht.**
- **184. Ein Zeiger verrottet an fremden Merges, nicht nur an eigenen.** #989s Lockfile-Zeile
  wanderte von `:6295` auf `:6313`, weil #1114 gemergt wurde; das Paket selbst hat sich nicht
  bewegt. **Zeiger in eine generierte Datei werden nach jedem nicht-leeren Fenster neu
  gemessen**, auch wenn der Gegenstand unverändert ist.
- **185. „Je genau eine Datei" ist eine Messung, keine Eigenschaft einer PR-Sorte.** #1105
  stand in der Ein-Datei-Welle und fasst zwei an. Die Folgerung hielt, der Grund nicht.
  **Ein richtiges Ergebnis aus falschem Grund wird korrigiert, nicht übernommen** — sonst
  trägt die nächste Welle die Annahme weiter, bis sie einmal nicht mehr stimmt.

## Belege dieses Laufs

- Queue-Issue: **#442** (Body neu geschrieben, §Pflege-Regeln unverändert übernommen)
- Body korrigiert: **#989** (AK1-Zeiger `:6295/:6296` → `:6313/:6314`, §Startbedingung auf
  #1124/#674, AK2-Konflikt benannt, „`main` gemessen grün" präzisiert)
- Kommentiert: **#442** (Weichen 48 + 49), **#989** (Weiche 48, issue-seitig)
- Nicht angefasst, mit Begründung: **#632**, **#1001**, **#633** (Zeiger alle gültig, kein
  Fund — Regel 38/129: ein Rewrite ohne Fund kostet mehr, als er nützt) · **#435**, **#428**,
  **#535**, **#542**, **#454**, **#338**, **#540** (Regel 7, Weiche 4)
- Gates: 13 selbst gefahren, darunter `pip-audit` **zweimal** (`main` und der Ergebnisbaum von
  #1120) und die Coverage-Suite
- PR-Bestand: 24 PRs, je Rückstand/Scope/Konfliktfreiheit selbst gerechnet
