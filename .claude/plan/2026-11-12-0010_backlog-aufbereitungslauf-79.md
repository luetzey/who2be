# Backlog-Aufbereitungslauf 79

**Datum:** 2026-11-12
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`) — unverändert gegenüber Lauf 74–78
**Fenster seit dem letzten Messpunkt:** 🔴 **0 Commits, zum fünften Mal in Folge.** `main` steht
seit dem 2026-11-06T08:05:51+01:00 still — **sechs Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.
**PR-Bestand:** 🔴 **38 offene PRs** _(waren 37)_ — der Zuwachs ist **#1138**, das Protokoll von
Lauf 78.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit, Owner-Vorgabe,
Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen
gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — vierzehnter Lauf in Folge.** Der
Server verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann; `get_persona`,
`list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"),
`record_usage`, `submit_feedback` und `search_memory`/`save_memory` standen nicht zur Verfügung.
Persona und Playbook-Katalog lagen im System-Prompt vor, die Playbook-**Bodies** nicht. Der Lauf
fuhr nach dem Body von #442 (§Pflege-Regeln 1–62) und `.github/PROJECT.md` §Constraints.
**Vierzehnter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-12 auf `main` @ `f89acf87` erhoben, sequenziell (ein Schreiber je Baum,
Regel 13/164), **ohne vorherige Reparatur** (Regel 120), **Exit-Codes am unverketteten Befehl**
(Regel 36/94/172). `npm`-Gates in `apps/web/` mit `pwd`-Beleg. Node **v22.23.4**, npm **10.9.9**,
uv **0.11.32**. Klon war shallow (50) → **1676** Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis | gegen Lauf 78 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **405 Fragment(e)** — Eigenzahl des Skripts; `ls changelog.d/*.md` sagt **406**, die Nicht-Fragment-Datei ist `README.md` | gleich |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1** — **`oauthlib 4.0.0`, CVE-2026-49272, Fix 4.0.1**, bei **398** Requirements | 🔴 **unverändert rot, fünftes leeres Fenster** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, „Alle i18n-Pruefungen in Ordnung" | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **28 moderate** (`glob 9.0.0 - 14.0.1`, `minimatch 7.0.0 - 11.0.0`, dev-only) | gleich |
| `npx playwright test --list --project=chromium` | 🟢 **44 Tests in 9 Dateien**; je Datei: billing 5, consent-overlay 2, editor-profiles 6, journeys 6, navigation 3, public 4, review-gate 2, **scroll-guard 15**, status-actions-viewport 1 | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, `instructions` **1.834** Bytes | gleich — **14. identische Messung** |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | **Exit 0**, **64 passed** | neu gefahren |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 30/160) — Fenster **0 Commits**, `git diff --name-only f89acf87 origin/main -- apps/web/src` liefert **0** Zeilen | übernommen aus Lauf 74 |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet**, Beleg: `apps/web/src` unbewegt | — |
| 🔴 **`main`-CI am Kopf `f89acf87`** | 🔴 **Lauf `42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen (Regel 91) — **2 von 14 Jobs** rot (`audit`, `all-green`), heute an der Job-Liste selbst gezählt | 🔴 **unverändert rot, 6 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **55. Messung in Folge** |

🟢 **Zeichengleiche Baum-Gates sind an einem bitgleichen Baum die Erwartung, kein Befund**
(Regel 20/150): `rev-list --count f89acf87..origin/main` → **0**, Baum `c751ed64`,
`status --porcelain` leer — keine abweichende Baum-Zahl aufgetreten. 🔴 **Regel 160 gilt nicht für
advisory-gefütterte Gates** (Regel 45/181): `pip-audit` und `npm audit` sind trotz des leeren
Fensters gefahren.

## PR-Bestand

**38 offene PRs** _(waren 37)._ Scope je PR über `git merge-base` + `git diff --name-only` mit
Nicht-leer-Prüfung, Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über
`git rev-list --count`. **Alle 38 heute selbst gerechnet.**

- 🔴 **Die Differenz 37 → 38 ist vollständig erklärt und wieder selbstverschuldet: +#1138**, das
  Protokoll von Lauf 78. **Nichts gemergt, nichts geschlossen — sechster Tag.** Weiche 51 in
  reinster Form, **zum zweiten Mal in Folge**: der einzige Zuwachs im Fenster ist der Lauf selbst.
- 🟢 **Alle 38 mergen konfliktfrei** (rc 0), alle 38 merge-bases rechnen.
- **Rückstand auf `main`:** **0** → 18 PRs (#1138, #1137, #1136, #1135, #1134, #1133, #1132,
  #1131, #1130, #1129, #1128, #1127, #1126, #1125, #1124, #1123, #1120, #674) · **10** → #1122,
  #1121, #1119, #1118, #1117, #1113, #1112, #1106 · **15** → #1107, #1105, #1104, #1103 ·
  **19** → #1090, #1089 · **33** → #1078 · **48** → #1056 · **73** → #1025 · **89** → #1002 ·
  **114** → #990 · **237** → #831.
- **Die 38 PRs bewegen zusammen 42 Dateipfade** _(waren 41 bei 37 PRs; der Zuwachs ist #1138s
  Plan-Datei)._
- 🔴 **Protokoll-Rückstand: 23.** Auf `main` liegen Protokolle für Lauf **31** und **43–55**
  (14 numerierte Dateien plus das unnumerierte Erst-Protokoll vom 2026-09-06 = 15 Dateien, über
  `git ls-tree -r origin/main .claude/plan/` gezählt). **22** stecken in offenen Drafts
  (#831=42, #990=56, #1002=57, #1025=58, #1056=59, #1078=60, #1089=61, #1090=62, #1103=64,
  #1104=65, #1105=66, #1107=67, #1112=68, #1113=69, #1117=70, #1118=71, #1119=72, #1121=73,
  #1125=74, #1126=75, #1137=77, #1138=78). 🔴 **Zu Lauf 63 UND zu Lauf 76 existiert nirgends
  eines** — über `git ls-tree` **und** über die Dateilisten aller 38 offenen PRs gemessen
  (Regel 61 hält). Dieser Lauf legt das **vierundzwanzigste** dazu.

### Merge-fertig — **einer**, und er ist weiter der CVE-Fix

| PR | Titel | Rückstand | Checks | Scope | Lage |
|---|---|---:|---:|---|---|
| 🟢 **#1120** | `deps`: oauthlib 4.0.0 → 4.0.1 — **der CVE-Fix** | **0** | 🟢 **18 / 18 grün** (18 `success` + 0 rot + 0 `neutral` = 18, addiert nicht geschätzt — Regel 37/173) | `uv.lock` | 🟢 **mergebar, ein Klick** |

🟢 **Merge-Wirkung am Ergebnisbaum gemessen, nicht am Branch** (Regel 52/188):

```
$ T=$(git merge-tree --write-tree origin/main refs/pr/1120)
$ git diff --stat origin/main $(git commit-tree $T -p origin/main -m probe)
 uv.lock | 6 +++---
 1 file changed, 3 insertions(+), 3 deletions(-)
```

🔴 **Gegenprobe am anderen `uv.lock`-PR:** **#1123** führt `oauthlib` weiter in **4.0.0**
(`refs/pr/1123:uv.lock:1750-1751`) — **wer #1123 statt #1120 mergt, hebt zehn Pakete und die CVE
bleibt.**

---

## Fund 1 — der `audit`-Job hat 9 Schritte, nicht 13; `pip-audit` ist der vierte, nicht der dritte

🔴 **#442 §Pflege-Regel 47 und Weiche 48c sagen seit Lauf 74: „Der `audit`-Job fährt `pip-audit`
als dritten und `OSV-Scan` als dreizehnten Schritt."** Dieselbe Formulierung steht in **#632**
§Startbedingung, **#633** §Startbedingung 5 und **#1001** §Startbedingung. **Beide Ordinalzahlen
sind in beiden möglichen Zählweisen falsch** — heute auf zwei unabhängigen Wegen gemessen
(Regel 10/24):

| Zählweg | `pip-audit` | `OSV-Scan` | Gesamt |
|---|---|---|---|
| **CI-Definition**, `yaml.safe_load(ci.yml)['jobs']['audit']['steps']` | **4.** (`ci.yml:974`) | **9. und letzter** (`ci.yml:1030`) | **9** Schritte |
| **Runner-Numerierung**, `main`s Lauf `42178623925` | **5.** | **10.** | **13** Einträge (inkl. `Set up job`, `Post …`, `Complete job`) |

🟢 **Die Aussage, auf die es ankommt, ist belegt und bleibt:** der Job bricht bei `pip-audit`
ab, und `OSV-Scan` läuft nicht — an `main`s Job-Liste wörtlich gelesen: Schritt
`pip-audit (Python)` → `conclusion: failure`, `OSV-Scan (Web-Lockfile, …)` → `skipped`, dazu
`npm audit`, `License check` und `Install web deps` ebenfalls `skipped`. **Richtig ist also der
Mechanismus, falsch sind nur die Ordinalzahlen** — und sie stehen an der Stelle, an der ein Agent
mit leerem Kontext nachzählen würde.

**Allokation (Regel 11 gegen Regel 33):** erste Sichtung → **Kommentar** an #632, #633 und #1001;
**korrigiert im Body von #442**, weil die Zahl **dort** entstanden ist (Regel 47 und Weiche 48c
sind die Quelle, die drei Paket-Bodies sind Kopien). Ein Vollschrieb von drei Bodies über MCP
(zusammen ~63.000 Zeichen) für zwei Ordinalzahlen trägt den Preis nicht, solange die operative
Anweisung („lies den `audit`-Job-**Log**, nicht die Conclusion") unberührt gilt — Weiche 45,
Option A „mit Maß". **Der Grund steht im Kommentar, nicht nur hier** (Regel 62). → **Regel 63.**

## Fund 2 — Weiche 2s Delta gilt für 15 der 20 gate-alten PRs, und bei #831 fehlt ein ganzer Job

🔴 **#442 Weiche 2 sagt: „Der Delta ist unverändert 3 Zeilen und dreimal derselbe Action-SHA
(`setup-uv` v10.3.0 → v10.3.3). **Kein Job, kein Schritt, keine Schwelle.** Die Kennzahl ist ein
Alarm ohne Inhalt."** Heute **zum ersten Mal pro Rückstandsgruppe** gemessen statt an einem
merge-base — und an der Methode, die Regel 26/158 vorschreibt (Blob-Vergleich von
`.github/workflows/ci.yml` an merge-base gegen `origin/main`), nicht am Commit-Abstand:

| Gruppe | PRs | `ci.yml`-Delta | Inhalt |
|---|---|---|---|
| 🟢 Rückstand **10–33** | #1106, #1112, #1113, #1117, #1118, #1119, #1121, #1122, #1103, #1104, #1105, #1107, #1089, #1090, #1078 (**15**) | **3+/3−** | 3× derselbe Action-SHA — **hier trifft Weiche 2 genau zu** |
| 🔴 Rückstand **48–89** | #1056, #1025, #1002 (**3**) | **25+/3−** | ein ganzer **Schritt** mehr: `Hilfe-Drift (Warnung, UI geändert ohne Hilfe)` mit `scripts/ci/help_drift.py` |
| 🔴 Rückstand **114** | #990 (**1**) | **66+/19−** | dazwischen |
| 🔴 Rückstand **237** | #831 (**1**) | **186+/19−** | 🔴 **merge-base hat 11 Jobs, `main` hat 12 — es fehlt `secrets`**, der Gitleaks-Scan |

🟢 **Die Kennzahl selbst ist bestätigt: 20 von 38 gate-alt**, und die Menge deckt sich exakt mit
„Rückstand > 0" — **kein PR mit Rückstand 0 ist gate-alt, keiner mit Rückstand > 0 ist
gate-aktuell.** 🔴 **Die Schlussfolgerung deckt sich nicht.** „Kein Job, kein Schritt" ist für
**5 der 20** falsch, und bei #831 im stärksten denkbaren Sinn: **sein grünes `all-green` ist gegen
eine CI-Definition ohne Secret-Scan gemessen.**

**Das ist Regel 60 an einer neuen Stelle:** eine Bilanz gilt nur für die Menge, die sie zählt. Die
Empfehlung zu Weiche 2 ist deshalb **nicht mehr flach B**, sondern gruppenweise — s. #442.
→ **Regel 64.**

## Fund 3 — #1001s Herkunftszeile nennt ein Protokoll, das nie geschrieben wurde

🔴 Die Fußzeile von **#1001** nennt als Protokoll
`.claude/plan/2026-11-09-0030_backlog-aufbereitungslauf-76.md`. **Diese Datei existiert nicht** —
nicht auf `main` (`git ls-tree -r origin/main .claude/plan/`) und in **keinem** der 38 offenen PRs
(über die Dateilisten aller 38 gemessen). **Zu Lauf 76 gibt es nirgends ein Protokoll** (Regel 61).
🔴 **#1001 ist damit der einzige der vier `agent-ready`-Bodies, dessen Herkunftszeile auf ein
Dokument zeigt, das nie entstanden ist.** Zum Vergleich: **#989** nennt `…-74.md` — die Datei
existiert, aber nur im offenen Draft **#1125**; **#632** und **#633** nennen seit Lauf 78 keinen
Pfad mehr, sondern den Protokoll-Stand.

## Norm-Prüfung „Agent-ready Arbeitspaket" — 4 von 4 vollständig, alle Zeiger gültig

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**. Jeder Zeiger je
Issue einzeln gegen den Baum gemessen, jeder Negativ-Befund von Hand gegengelesen (Regel 10).

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ `### Fertig heißt` | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **Tabelle 13/13 gültig** | 🟢 **vollständig; ein Ordinal-Fund kommentiert** |
| **#1001** | ✅ `## Fertig heißt` | ✅ 5 | ✅ `**Out of Scope:**` | ✅ | 🟢 **alle 5 Gruppen gültig** | 🟢 **vollständig; Ordinal + Herkunftszeile kommentiert** |
| **#633** | ✅ `### Fertig heißt` | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 **Tabelle 10/10 gültig** | 🟢 **vollständig; ein Ordinal-Fund kommentiert** |
| **#989** | ✅ `## Fertig heißt` | ✅ 6 | ✅ `**Out of Scope:**` | ✅ | 🟢 **alle gültig** | 🔴 **zwei Defekte in DRITTER Sichtung → Weiche 52** |

**Einzeln gegengemessen (Auswahl, je Datei `wc -l` plus `grep -n`/`sed -n` an der Stelle):**
`MfaSection.tsx` **297** / `.test.tsx` **284** / `.a11y.test.tsx` **45** · `SessionProvider.tsx`
**267**, `mfaStepUpPending` `:57`, Aufrufer `:134`/`:222` · `LoginPage.tsx` **399**,
`completeMfaChallenge` **`:39`**, Aufruf **`:172`** · `e2e/helpers/auth.ts` **199**, `createUser`
`:33`, `enrollTotpAal2`-Aufruf `:55`, Definition `:97` · `i18n/audit.test.ts` **371**, `it.each([`
`:297`, Testname `:301`, Baseline-Filter `:308`, blankes `it(` `:321` · `orphan-baseline.json`
**156** (flache Liste, per `json.load`) · `api/client.ts` **1849** · `api/types.ts` **2407** ·
`test/a11y.test.ts` **77**, Untergrenze `:74` · `vite.config.ts` **107**, `thresholds:` `:99`,
Werte `:100-103` (80/79/75/80), Glob `:20` gegen `:90` **unterschiedlich** (Regel 118 hält) ·
`package.json` **82**, `engines.node` `">=22 <23"` `:8`, `@supabase/supabase-js` **`^2.118.0`**
`:38` (Lockfile `:2990` → **2.118.0**), `@playwright/test` **`^1.64.1`** `:58`, `vitest`/
`coverage-v8` **`^4.1.12`** `:66`/`:79` · `ci.yml` **1259**, `test:a11y` `:325`,
`changelog-guard:` `:780`, Step-Name `:828`, `run` `:844`, E2E `:463`/`:544`, `license:check`
`:1029` · GoTrue **v2.197.0** an allen drei Stellen (`docker-compose.yml:63`,
`deploy/hetzner/supabase/…:92`, `deploy/dokploy/…:115`) · `osv-scanner.toml` **26** Zeilen,
`IgnoredVulns` **2**, `ignoreUntil = 2026-11-30` an `:11`/`:19`, „turns red again" **1×** an `:6` ·
`package-lock.json` `http-cache-semantics` **4.2.0** an `:6313-6315`, Elternrange `^4.1.1` `:7620`,
`npm ls` ein Pfad · `docs/mcp-payload-budget.md` **609** Zeilen, `104.777` an `:233`/`:292`/`:327`/
`:487`, `108.262` an `:234`/`:331`, `71.738` an `:236`/`:335`, Kopf `:254`, Tabelle `:260-265`
**zeichengleich** mit dem eigenen `payload_report`-Lauf, `instructions` **1.834** an `:267`/`:309` ·
`security.py` `require_aal2` `:202`, `verify_supabase_jwt` `:609`, `aal`-Claim `:649` ·
`Caddyfile` **208** Zeilen, `rate` **0×** · `docs/licensing/plans.md` **271** ·
`.github/PROJECT.md` **179** · `uv.lock` **3485**, `oauthlib 4.0.0` `:1843-1844`.

**E2E-Rechnung je Körper nachgezählt** (Regel 16/29): `playwright --list` **44** in 9 Dateien;
`grep -c '^test('` über alle Specs **42**, dazu die eingerückte Schleifenzeile
`scroll-guard.spec.ts:237` (`for (const mode of ['native','fallback'])` auf `:236`) mit **2**
Körpern → **42 + 2 = 44** ✓; `expectedName.test(` auf `:666` ist ein RegExp-Aufruf, kein Körper ✓;
**genau ein** `test.skip(` im ganzen E2E-Baum (`billing.spec.ts:43`, `isCloudRun` `:41`) ✓;
`createUser`-Obergrenze 5+6+6+3+2+15+1 = **38** ✓; ohne `E2E_EDITION=cloud` 44 − 5 = **39** ✓.
🟢 **Alle fünf Korrekturen, die Lauf 78 in #633 geschrieben hat, halten.**

**Norm-Stand der acht übrigen Bodies — als übernommen gekennzeichnet**, Beleg der Übernehmbarkeit
ist `updated_at` (Regel 42/189; alle acht unverändert seit Lauf 78): Outcome fehlt in **#542**,
**#535**, **#428**; Verifikations-Abschnitt fehlt in **#535** und **#428**; **#454** hat ihn mit
„Kein Testkommando"; **#338** trägt keine Abschnitts-Überschriften (0 von 4); Scope-„In" fehlt in
#542, #540, #535, #454, #338. **#540** trägt alle vier und bleibt `needs-decision` — es fehlt die
Mechanismus-Entscheidung, nicht ein Feld. **Bewusst nicht umgebaut** (Regel 7, Weiche 4). **Ein
`size/M`-Issue wird nie durch Nachtragen von Feldern startbar** (§Constraints).

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines entzogen.**
Begründung: die drei Funde sind Ordinal-, Herkunfts- und Bezugszahl-Fehler in Bodies mit
vollständigen Pflichtfeldern; #989 trägt sein `needs-decision` aus Weiche 48 bereits.

## Was dieser Lauf selbst erledigt hat

1. **#442 vollständig neu geschrieben** — Gates, PR-Lagen (38), Dateisperren (42 Pfade),
   Reihenfolge, Wellen, Weichen, Pflege-Regeln 1–64. **Regel 47 und Weiche 48c tragen jetzt die
   gemessenen Ordinalzahlen** (4 von 9 bzw. 9 von 9 in der Definition; 5 bzw. 10 beim Runner)
   statt „dritter/dreizehnter".
2. **Weiche 2: Empfehlung neu gerechnet und aufgeteilt** (Regel 14) — **B für die 15 jüngsten**
   gate-alten PRs, **A für #990, #1002, #1025, #1056 und #831**, mit dem fehlenden `secrets`-Job
   als benanntem Grund.
3. **Drei Kommentare** für die Ordinal-Korrektur (#632, #633, #1001), jeder mit dem Grund, warum
   Kommentar und nicht Body (Regel 62).
4. **Weiche 52 neu gestellt** — #989s zwei Defekte sind in **dritter** Sichtung, und die
   Regel-62-Ausnahme trägt sie seit drei Läufen.
5. **Drei neue Pflege-Regeln: 63** (Regel 11 gegen Regel 33 bei erster Sichtung in einem
   Pflichtabschnitt), **64** (eine Kennzahl über eine Menge wird pro Teilmenge belegt, bevor eine
   Empfehlung auf ihr ruht) und **65** (ein Ordinal ist ein Zeiger und braucht die Zählweise dazu).

## Reihenfolge — unverändert, und das ist das Ergebnis

Im Fenster ist kein Issue geschlossen, keines neu, keine Weiche beantwortet, keine Datei-Sperre
verschoben. **Es gibt nichts, was eine Position verschieben könnte** (Regel 46/182: neu gemessen,
nicht abgehakt).

| Pos | Issue | Größe | Baum | Kriterium | Zustand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren (#435 W2a) | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | ✅ **startbar, Fläche frei** — kein PR fasst `apps/web/src/**` an |
| **2** | **#1001** Payload-Budget (ADR-0058 P4b, Rest) | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar**, alle Zeiger gültig, `payload_report` 14. identische Messung |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web/E2E | **1** harte Abhängigkeit | ⏸ **nach #632** + Container-Laufzeit **oder** einzelne E2E-Job-Conclusions |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **1**, und inhaltlich | 🔴 **erst Weiche 48** — Fläche hält #1124 (+4 weitere) |

**Nicht in der Reihenfolge:** #442 (die Liste), #428/#435/#535 (Tracking), #338/#454/#542
(`human-only`), #540 (`needs-decision`, Weiche 17), die 38 offenen PRs (Regel 65 — kein Issue).

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120** | Der CVE-Fix. **18/18 grün, Rückstand 0, konfliktfrei, kein Draft.** Wirkung am Ergebnisbaum 3 Zeilen, `pip-audit` danach Exit 0. **Vor allem anderen** |
| 🟢 **A** | **#632 + #1001** | Web/Vitest gegen Python/pytest, **code-disjunkt**, beide Flächen über alle 38 PRs frei. ⚠️ **Gemeinsame DoD-Fläche `STATE.md`** (dreifach PR-gehalten) — wer zweiter fertig wird, rebasiert auf **#1103** |
| **B** | **#633** | nach **#632** (hart) **und** Container-Laufzeit oder einzelnen E2E-Job-Conclusions |
| **C** | **#989** | 🔴 **erst Weiche 48**, dann die Fläche (5 Schreiber auf `package.json`/`package-lock.json`, #1124 auf `osv-scanner.toml`) |
| **M** _(Owner)_ | **#1120 → #1124 → #1123 → Compose-Bumps → Domain-Doku** | #1131 fasst alle vier Compose-Stacks an und überschneidet sich mit #1134 — nacheinander messen. **#1106/#1122 nicht beide** → Weiche 49 |
| **N** _(Owner)_ | **20 Protokoll-PRs in beliebiger Reihenfolge** | #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — paarweise konfliktfrei, je genau eine Datei außer #1105 (zwei). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | 🔴 **#831 jetzt mit benanntem Grund:** sein grünes `all-green` stammt aus einer CI-Definition **ohne** `secrets`-Job (Fund 2) |
| **Q** _(Owner)_ | **#674** | konfliktfrei, 0 hinter `main`, **9 von 15 Checks rot, 7 davon eigene**. Empfehlung **B** (schließen) |
| **R** _(Owner)_ | **#1128, #1129, #1130** | drei npm-Bumps, zwei davon Major, auf #1124s Fläche. **Nach #1124, einzeln** |

🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier Arbeitspakete offen,
zwei blockiert. 🔴 **Der Engpass hat sich zum fünften Mal nicht verschoben.**

## Verifikation dieses Laufs

- **Keine Repo-Änderung außer dieser Plan-Datei** — `git diff --name-only origin/main...HEAD`
  nennt genau `.claude/plan/2026-11-12-0010_backlog-aufbereitungslauf-79.md` (Regel 49/185:
  gemessen, nicht behauptet). `.claude/context/STATE.md` ist bewusst **nicht** angefasst, weil sie
  dreifach von Protokoll-PRs gehalten wird (#1103, #1090, #1078) und dieser Lauf kein Paket
  abschließt.
- **Alle Schreibvorgänge auf GitHub über MCP** — `gh` ist in dieser Session nur für Suche
  zugelassen (Weiche 44 unverändert versperrt).
- **Eigene Bilanzen gegen die Einzelwerte abgehakt** (Regel 56/57): „13/13" und „10/10" beziehen
  sich ausdrücklich auf die Zeiger-**Tabellen** in #632 §Startbedingung bzw. #633
  §Startbedingung 4 — jede Zeile einzeln gemessen; die Funde dieses Laufs liegen **außerhalb**
  dieser Tabellen und sind dort benannt (Regel 60).
- **Protokoll-Existenz am Ende geprüft** (Regel 61): diese Datei liegt als PR vor; die Nummer
  steht im Bericht.
