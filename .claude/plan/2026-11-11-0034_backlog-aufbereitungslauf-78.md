# Backlog-Aufbereitungslauf 78

**Datum:** 2026-11-11
**Messpunkt:** `main` @ `f89acf87` (`deps(compose): bump caddy in /deploy/monitor (#1097)`), Baum `c751ed64`
**Fenster seit dem letzten Messpunkt:** 🔴 **0 Commits, zum vierten Mal in Folge** — der Baum ist
bitgleich mit dem von Lauf 75/76/77. `main` steht seit dem 2026-11-06T08:05:51+01:00 still,
**fünf Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit, Owner-Vorgabe,
Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen
gruppieren. Bericht in drei Blöcken.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — dreizehnter Lauf in Folge.**
Der Server verlangt eine Autorisierung, die diese Session nicht selbst anstoßen kann; `ToolSearch`
liefert keine seiner Werkzeuge. Persona und Playbook-Katalog lagen im System-Prompt vor;
`get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource` (darunter die Norm
„Agent-ready Arbeitspaket"), `record_usage`, `submit_feedback` und `search_memory`/`save_memory`
nicht. Der Lauf fährt nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints.
**Dreizehnter Lauf ohne Kurations-Rückmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-11-11 auf `main` @ `f89acf87` erhoben, sequenziell (ein Schreiber je Baum),
Node **v22.23.4**, npm **10.9.9**, uv **0.11.32**, **ohne vorherige Reparatur** (Regel 120),
**Exit-Codes ohne Pipe** (Regel 94/172), `npm`-Gates in `apps/web/` mit `pwd`-Beleg (Regel 146/164).
Der Klon war **shallow** (50 Commits); nach `git fetch --unshallow`: **1676** Commits (Regel 90).

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests |
| `scripts/changelog_fragments.py check` | **Exit 0**, **405 Fragment(e)** bei **406** Dateien (`README.md` ist keines) |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1** — `oauthlib 4.0.0` (`uv.lock:1843-1844`), **CVE-2026-49272**, Fix 4.0.1, bei **398** Requirements |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0** |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `npm audit` (voll) | ⚠️ **Exit 1**, **28 moderate** (`glob`/`minimatch`, dev-only) |
| `npx playwright test --list --project=chromium` | **44 Tests in 9 Dateien** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 160) — Fenster 0 Commits, `git diff --name-only f89acf87 origin/main -- apps/web/src` → **0** Zeilen |
| 🔴 `main`-CI am Kopf `f89acf87` | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen (Regel 91) |
| `docker info` | 🔴 **Exit 1**, kein `podman` — **54. Messung in Folge** |

**Playwright je Spec-Datei** (der Messweg, der diesen Lauf entschieden hat): billing 5,
consent-overlay 2, editor-profiles 6, journeys 6, navigation 3, public 4, review-gate 2,
**scroll-guard 15**, status-actions-viewport 1 → **44**.

**Weichen-Werte selbst nachgemessen:** `grep -c pip-audit CLAUDE.md` → **0** (W41) ·
`docs/licensing/plans.md:28/:29` „100 MB"/„10 GB" gegen `:37` `100 MiB`/`10 GiB`, Datei 271 Z (W9) ·
`osv-scanner.toml:18-20` nennt `minimatch@…/3.1.5` im `reason` (W15/46) · ADR-0061 führt W61-1,
W61-2 (`:219`), W61-3 (`:238`/`:368`) als offen (W30) · Caddy: Betriebs-Pin `caddy:2.11.7-alpine`
auf `deploy/hetzner/who2be/docker-compose.yml:480`, CI-Pins auf `ci.yml:373`/`:381`/`:382`/`:397`/
`:398`, `deploy/monitor/compose.yml:48` mit `@sha256:eb4d35b7…`, `Caddyfile` **208** Z, `rate` **0×**
(W7) · Node-Boden `>=22 <23` auf `apps/web/package.json:8`, `license-checker-rseidelsohn ^5.0.1`
auf `:74` (W47) · Thresholds `vite.config.ts:99-104` = 80/79/75/80 (W6).

## PR-Bestand

**37 offene PRs** (waren 36). Scope je PR über `git merge-base` + `git diff --name-only` mit
Nicht-leer-Prüfung, Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über
`git rev-list --count`. **Alle 37 heute selbst gerechnet.**

- 🔴 **Die Differenz 36 → 37 ist vollständig erklärt und selbstverschuldet: +#1137**, das Protokoll
  von Lauf 77. **Weiche 51 in reinster Form** — der einzige Zuwachs im Fenster ist der Lauf selbst.
- 🟢 **Alle 37 mergen konfliktfrei** (rc 0).
- 🟢 **Merge-fertig: einer — #1120**, der CVE-Fix: **18 von 18** Check-Runs `success`
  (`all-green`, `audit` und CodeQL darunter), Rückstand **0**, konfliktfrei, kein Draft.
  Merge-Wirkung am Ergebnisbaum **3 Zeilen in `uv.lock`** (Regel 188).
- 🔴 **#1124**: 18 Checks, 16 grün, rot nur `audit` + `all-green` (aus `main` geerbt).
- 🔴 **#674**: 15 Checks, **9 rot** (Lauf 77 zählte 8 — `all-green` fehlte), davon **7 eigene**
  (`web`, `e2e`, `compose-smoke`, `e2e-billing-cloud`, 3× `e2e-mobile`); 5 grün, CodeQL `neutral`.
  5 + 9 + 1 = 15 (Regel 173).
- 🔴 **Protokoll-Rückstand: 22.** Auf `main`: Lauf 31 und 43–55 (14 Dateien). In offenen Drafts:
  42, 56–62, 64–75, 77 (21 PRs). 🔴 **Zu Lauf 63 UND 76 existiert nirgends eines.**
- **41 Dateipfade** bewegt (waren 40; +1 = #1137s Plan-Datei). Mehrfach gehalten:
  `apps/web/package.json`/`package-lock.json` **fünffach** (#1130, #1129, #1128, #1124, #674),
  `.claude/context/STATE.md` dreifach (#1103, #1090, #1078), `uv.lock` zweifach (#1120, #1123),
  `deploy/dokploy/docker-compose.yml` zweifach (#1134, #1131), die vier Pfade von #1106/#1122.
  🟢 **FREI und auf Existenz belegt:** `apps/web/src/**`, `apps/web/e2e/**`, `apps/mcp/**`,
  `docs/mcp-payload-budget.md` (609 Z), `vite.config.ts` (107 Z), `ci.yml` (1259 Z),
  `Caddyfile` (208 Z), `docs/licensing/plans.md` (271 Z).

## Die drei Funde des Laufs

### 1. Die Widerlegung von gestern trägt nicht (Regel 60)

Lauf 76 schrieb über #632 „**13 von 13** Zeigern nachgemessen, null verrottet". Lauf 77 erklärte
das für widerlegt („gemessen sind **12 von 13**") und stützte darauf **Regel 57**.

**Heute beide Mengen nachgezählt:** die Zeiger-Tabelle in #632 §Startbedingung hat **13 Zeilen**,
und alle 13 Werte sind gültig — `MfaSection.tsx` 297 / `.test.tsx` 284 / `.a11y.test.tsx` 45,
`SessionProvider.tsx` 267, `audit.test.ts` 371, `LoginPage.tsx` 399, `package.json` 82,
`vite.config.ts` 107, `e2e/helpers/auth.ts` 199, `client.ts`/`types.ts` 1849/2407, `ci.yml` 1259,
`orphan-baseline.json` 156, `a11y.test.ts` 77.

**Der falsche Wert stand in §Vorentschieden 3 — außerhalb der Tabelle:**
`@supabase/auth-js 2.117.3`, deklariert als `^2.117.3` auf `apps/web/package.json:37`. Gemessen:
**`^2.118.0`** auf **`:38`**, installiert **2.118.0** (`package-lock.json:2990`).

🔴 **Also: Lauf 76s Zahl war richtig, Lauf 77s Zahl war falsch, und der Fund war in beiden Fällen
echt.** Eine Bilanz gilt nur für die Menge, die sie zählt. Wer einen Fund außerhalb dieser Menge
gegen sie rechnet, belegt einen echten Fund mit einer falschen Zahl und erbt beides.
🟢 **Gegenmaßnahme:** beide korrigierten Bodies sagen jetzt an ihrer Tabelle ausdrücklich, dass
die Bilanz nur über die Tabelle spricht.

### 2. Zu Lauf 76 existiert nirgends ein Protokoll (Regel 61)

Gemessen über `git ls-tree -r origin/main .claude/plan/` **und** über die Dateilisten aller 37
offenen PRs: Protokolle liegen für Lauf 31, 43–55 (auf `main`) und 42, 56–62, 64–75, 77 (in
Drafts). **Für 63 und 76 gibt es keines.**

🔴 **Das trifft genau den Lauf, dessen Mess-Behauptung gestern bestritten wurde.** Ob Lauf 76 die
13 Zeiger wirklich gemessen hat, ist nicht nachprüfbar — sein Protokoll fehlt. Ein Protokoll ist
nicht Dokumentation, sondern die Prüfbarkeit des Laufs; fehlt es, ist Neumessen der einzige Weg.
**Wer ein Protokoll schreibt, prüft am Ende des Laufs, dass es als PR existiert.**

### 3. Neun Defekte, die als Kommentar zwei Läufe überlebt haben (Regel 62)

Regel 170 verlangt die Body-Korrektur, weil ein Kommentar einen Agenten mit leerem Kontext nicht
erreicht. **Dieser Lauf hat die Regel nach ihrem Zweck angewandt statt nach ihrem Wortlaut:**

| Issue | Lage | Entscheidung |
|---|---|---|
| **#632** | Position 1, **heute startbar** | **Body** — vier Korrekturen |
| **#633** | Position 3, Blocker fällt mit #632 | **Body** — fünf Korrekturen |
| **#989** | `needs-decision`, Weiche 48 unbeantwortet, Scope-Dateien von #1124 gehalten | **Kommentar**, Grund benannt |
| **#1001** | defektfrei | **Kommentar** (Messbestätigung + Herkunftszeile) |

**#632, im Body korrigiert:** (1) `@supabase/auth-js` **2.118.0** / `^2.118.0` / `:38` /
`package-lock.json:2990` statt 2.117.3 / `^2.117.3` / `:37` — zweite Sichtung. (2) Die
`createUser`-Rechnung: statt „42 + 1 = 43, davon 37" jetzt **44** Körper laut `playwright --list`
und **38** in den sieben Dateien, die `createUser` nutzen. (3) `.claude/context/STATE.md` steht
jetzt in §Scope (sie stand nur in der DoD — Regel 191), §Verifikation nennt den erwarteten Diff
und den Ausweg. (4) #674 nicht mehr als „rot und kollidierend" (konfliktfrei, 0 hinter `main`,
aber 9 von 15 rot — Regel 58), #1120 mit **18 von 18** statt 15 Checks, `package.json` mit
**fünf** Trägern statt zwei.

**#633, im Body korrigiert:** (1) `completeMfaChallenge` **`:39`** / Aufruf **`:172`** (war
`:38`/`:171` — dritte Sichtung). (2) `scroll-guard` **15** Körper statt 14. (3)
`createUser`-Obergrenze **38** statt 37 — der Body trug 37 in Kriterium 5 und §Startbedingung 7
und `≤ 38` in §Verifikation, also zwei Werte für dieselbe Größe (Regel 153). (4) Die Herleitung
der 44: **`42 + 2 = 44`**, weil `scroll-guard.spec.ts:237` eingerückt ist (Schleife über zwei Modi
auf `:236`) und `test.skip(() => !isCloudRun, …)` auf `billing.spec.ts:43` eine Datei-Direktive
ohne Körper ist. (5) `@playwright/test` **`^1.64.1`** (`package.json:58`), installiert **1.64.1**,
nicht 1.64.0. Dazu `STATE.md` in §Scope.

**#989, kommentiert:** AK3, §Verifikation und §Startbedingung nennen **406** Fragmente — die
Eigenzahl des Werkzeugs ist **405** (Regel 143). Dazu der unveränderte DoD-gegen-AK5-Widerspruch
(`STATE.md`) mit der exakten Ersetzung nach dem Muster aus #1001, und die überholte PR-Summe (24).

**#1001, kommentiert:** defektfrei, sechster Lauf ohne Zeiger-Fund; alle Zahlen heute gemessen
(609 Z, `payload_report` 103/108.251, Registry 103, `test_tool_payload_budget.py` 64 passed).
Offen nur die Herkunftszeile — ein Klassenfehler aus dem Protokoll-Rückstand.

**Beide Vollschriebe sind nach dem Schreiben gegengelesen** (Pflege-Regel 9): Abschnitts-Liste
vollständig, Code-Blöcke geschlossen, Body-Ende wörtlich geprüft, Altwerte nur noch als markierte
Zitate. **Kein Abschnitt verloren.** Die Attributions-Fußzeile fehlt in beiden weiter — sie fehlte
vorher auch; die Pflegezeile `_Zuletzt gepflegt: …_` hat überlebt (Weiche 19 Option B).

## Norm-Prüfung „Agent-ready Arbeitspaket"

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): Outcome · prüfbare Akzeptanzkriterien ·
Out-of-Scope · exakte Verifikations-Kommandos. **Alle vier `agent-ready`-Bodies: 4 von 4.**

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| #632 | ✅ | ✅ 5 | ✅ | ✅ | Tabelle **13/13**, 3 Werte außerhalb falsch | **im Body korrigiert** |
| #1001 | ✅ | ✅ 5 | ✅ | ✅ | **alle gültig** | **defektfrei** |
| #633 | ✅ | ✅ 6 | ✅ | ✅ | Tabelle **10/10**, 2 Zeiger außerhalb falsch | **im Body korrigiert** |
| #989 | ✅ | ✅ 6 | ✅ | ✅ | alle gültig | **kommentiert** |

**Kein `agent-ready` vergeben oder entzogen, kein `needs-decision` vergeben oder entzogen.**
Norm-Stand der acht übrigen Bodies als **übernommen** gekennzeichnet (Beleg: `updated_at` aller
acht unverändert).

## Reihenfolge und Wellen

**Unabhängig gegen die fünf Kriterien neu hergeleitet — unverändert:**

**#632 → #1001 → #633 → #989**

1. **#632** — Fundament vor Fläche (öffnet #633), startbar, Flächen frei.
2. **#1001** — Inventar vor Zuschnitt, anderer Verifikations-Baum, Flächen frei.
3. **#633** — harte Abhängigkeit nach #632, dazu Container-Laufzeit.
4. **#989** — `needs-decision` (Weiche 48) und fünffache Datei-Sperre.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** (Owner) | **#1120** | Der CVE-Fix. 18/18 grün, Rückstand 0 — ein Klick. Vor allem anderen |
| 🟢 **A** | **#632 + #1001** | Web/Vitest gegen Python/pytest, code-disjunkt; gemeinsame DoD-Fläche `STATE.md` → wer zweiter fertig wird, rebasiert (Basis #1103) |
| **B** | **#633** | nach #632 und nach Container-Laufzeit oder einzeln gelesenen E2E-Job-Conclusions |
| **C** | **#989** | erst Weiche 48, dann die Fläche |
| **M** (Owner) | #1120 → #1124 → #1123 → #1131–#1136 → Domain-Doku | #1106/#1122 nicht beide (W49) |
| **N** (Owner) | 19 Protokoll-PRs in beliebiger Reihenfolge, dann seriell #1103 → #1090 → #1078 | löst die Herkunftszeilen-Klasse |
| **P** (Owner) | #1107, #1078, #831 durch Branch-Update heilen | erst nach #1120 neu messen |
| **Q** (Owner) | **#674** | entscheidbar; Empfehlung **B** (schließen) — 9 von 15 rot, 7 eigene |
| **R** (Owner) | #1128, #1129, #1130 | nach #1124, einzeln, jeder mit eigener Check-Lesung |

## Weichen

**32 offene Weichen, keine neue in diesem Lauf.** Jede Empfehlung neu gerechnet (Regel 14).
Hervorzuheben:

- **41** (`pip-audit` in `CLAUDE.md`): `grep -c` → **0**, sechstes Mal mit Beleg. **Der Grund,
  warum eine CVE sechs Tage in `main` steht.** Empfehlung **C**.
- **11/34** (wer mergt): Reihenfolge **#1120 → #1124 → #1123**. Gegen #1120 steht kein
  mechanischer Einwand mehr. **Mergen ist nach Persona-Grenze ohne Freigabe verboten.**
- **12** (#674): Empfehlung bleibt **B** (schließen), heute präzisiert auf 9 von 15 rot.
- **51** (PR-Summen in Bodies): vierte Bestätigung, heute in #632/#633 teilweise umgesetzt
  (Summe nur mit Messdatum, Träger-Spalte verbindlich).
- **44/45** (Schreibweg): der Preis ist heute bezifferbar — zwei Body-Korrekturen = zwei
  Vollschriebe über MCP (18.800 und 25.600 Zeichen), weil `gh api -X PATCH --input` versperrt ist.
- **5** (`audit` als Required Check): Schaden vierfach belegt, `ci.yml` frei — mechanisch umsetzbar.
- **46** (`glob`/`minimatch`-Frist): **19 Tage**. Empfehlung **A** (mergen statt verlängern).

## Neue Pflege-Regeln

- **Regel 60** — Eine Bilanz gilt nur für die Menge, die sie zählt.
- **Regel 61** — Ein Lauf ohne Protokoll ist ein Lauf, dessen Behauptungen man nur glauben oder
  neu messen kann.
- **Regel 62** — Eine Korrektur gehört in den Body, wenn ein Agent das Paket aufgreifen kann —
  sonst in einen Kommentar, mit benanntem Grund.

## Was dieser Lauf geschrieben hat

| Ziel | Art |
|---|---|
| **#632** | Body neu geschrieben (vier Korrekturen), gegengelesen |
| **#633** | Body neu geschrieben (fünf Korrekturen), gegengelesen |
| **#989** | Kommentar (Fragment-Zahl, DoD-Widerspruch, PR-Summe, Grund für den Kommentar) |
| **#1001** | Kommentar (Messbestätigung, Herkunftszeile, Protokoll-Rückstand) |
| **#442** | Body neu geschrieben (Reihenfolge, Wellen, Weichen, Regeln 60–62) |
| dieses Protokoll | `.claude/plan/2026-11-11-0034_backlog-aufbereitungslauf-78.md` |

**Dieser PR fasst nur die eigene Plan-Datei an** — gemessen, nicht behauptet (Regel 185).
`.claude/context/STATE.md` bleibt unberührt (sie ist dreifach von Protokoll-PRs gehalten,
Weiche 43).

## Sub-Agents

Fünf, alle lesend, Modell nach Aufwand gewählt (right-sizing):

| Paket | Modell | Begründung |
|---|---|---|
| Zeiger-Messung #632, #1001, #633, #989 (4×) | Sonnet | mechanische `grep`/`sed`/Runner-Messung gegen einen festen Baum, kein Urteil |
| Gegenlesen der zwei Vollschriebe (2×) | Haiku | reine Anwesenheits- und Zitatprüfung |

**Jeder Negativ-Befund eines Sub-Agents ist von Hand gegengelesen, bevor er ein Fund wurde**
(Regel 10): die drei Werte in #632 §Vorentschieden 3 per `sed -n`/`grep -n` und am Lockfile, die
Körper-Zahlen per `playwright --list` **und** per `^test`-Split, `:39`/`:172` per `grep -n`,
`billing.spec.ts:41`/`:43` und `scroll-guard.spec.ts:236`/`:237` wörtlich, die 405 an der
Skript-Ausgabe, die Protokoll-Löcher über `git ls-tree` und alle 37 PR-Dateilisten.
