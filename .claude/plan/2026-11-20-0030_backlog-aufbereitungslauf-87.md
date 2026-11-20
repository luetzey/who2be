# Backlog-Aufbereitungslauf 87

**Datum:** 2026-11-20
**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `deps(compose): bump caddy in /deploy/monitor`, #1097)
**Fenster seit dem letzten Messpunkt (Lauf 86):** 🔴 **0 Commits, zum zwölften Mal in Folge** —
`main` steht seit dem 2026-11-06T08:05:51+01:00 still, **14 Tage**.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf gepflegt.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung. Danach die Warteschlange neu ordnen (harte Abhängigkeit → Owner-Vorgabe →
Fundament vor Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere) und in Wellen
gruppieren. Bericht in drei Blöcken.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — die Sitzung hält die Anmeldung,
der Server weist sie ab.** `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket"), `record_usage`, `search_memory` und `save_memory`
sind diesen Lauf nicht verfügbar. Persona und Playbook-Katalog lagen im System-Prompt vor. Der
Lauf fährt deshalb nach dem Body von #442 (§Pflege-Regeln, 75 Regeln) und nach
`.github/PROJECT.md` §Constraints — dort stehen die vier Pflichtabschnitte der Norm.
**Kein Kurations-Feedback an die eigene AgentDB, erneut.**

## Messgrundlage

Alles am 2026-11-20 auf `main` @ `f89acf87` erhoben, **ohne vorherige Reparatur** (Regel 120),
Exit-Codes am **unverketteten** Befehl (Regel 36/94/172), `npm`-Gates in `apps/web/` mit
`pwd`-Beleg (Regel 13/164), sequenziell. Node **v22.23.5**, npm **10.9.9**, uv **0.11.32**,
CPython **3.11.18**. Klon war shallow (50) → **1676** Commits nach `--unshallow` (Regel 90).
`git status --porcelain` leer, `rev-list --count f89acf87..origin/main` → **0**.

| Gate | Ergebnis | gegen Lauf 86 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `changelog_fragments.py check` | **Exit 0**, **405 Fragment(e)** (Eigenzahl; `ls changelog.d/*.md \| wc -l` = **406**, Differenz `README.md`) | gleich |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** bei **125** Requirements / **124** Namen (`wc -l` = **398** Zeilen) | gleich |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **27 moderate, 0 high** — nur `glob` + `minimatch`; `--package-lock-only` **zeichengleich**, Exit **1**; `grep -c GHSA-fc5q-39xc-vjpf` → **0** | gleich |
| `npx playwright test --list --project=chromium` | **44 Tests in 9 Dateien** | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** Bytes | 🟢 **22. identische Messung** |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | **Exit 0**, **64 passed** | gleich |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 30/160) — Fenster **0 Commits**, `git rev-list --count f89acf87..origin/main -- apps/web/src` → **0**, `status --porcelain apps/web` leer | übernommen |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet**, Beleg: Baum bitgleich | — |
| 🔴 **`main`-CI am Kopf `f89acf87`** | 🔴 Lauf **`42178623925`**, `status: completed` **und** `conclusion: failure` getrennt gelesen; **14** Jobs, **2** rot (`audit`, `all-green`) — an der Job-Liste gezählt | 🔴 **unverändert rot, 14 Tage** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **63. Messung in Folge** |

🔴 **Der `audit`-Job, Schritt für Schritt wörtlich gelesen** (Regel 183): `pip-audit (Python)` →
`failure` (Runner-Eintrag **5.**), danach `Run actions/setup-node`, `Install web deps`,
`npm audit (Web, prod-only, high+)`, `License check (Web · Deny-Liste)` und
`OSV-Scan (Web-Lockfile …)` sämtlich **`skipped`** (Einträge 6.–10.). **Die Schritte nach
`pip-audit` sind seit dem 2026-11-06 unbeobachtet.**

🟢 **`compose-smoke` ist grün — und trägt den Schritt `fail2ban-Filter (Rate-Limit an der Kante,
#540)`** (`ci.yml:399`, `run` auf `:407`). Siehe Fund 1.

## PR-Bestand

🔴 **49 offene PRs** _(waren 48)_, zusammen **54** bewegte Dateipfade _(waren 53)_, **73**
Pfad-Vorkommen. Scope je PR über `git merge-base` + `git diff --name-only` mit Nicht-leer-Prüfung,
Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über `git rev-list --count` —
**alle 49 selbst gerechnet**.

- 🟢 **Die Differenz 48 → 49 ist vollständig erklärt: +#1153** (Protokoll Lauf 86, der Vorlauf).
  **Keine Abgänge** (Regel 74: `state` + `merged` + `closed_at` je PR gelesen).
- 🟢 **Alle 49 mergen konfliktfrei** (`rc 0`), **keiner bewegt 0 Dateien**.
- 🔴 **Seit dem 2026-11-06 ist kein PR gemergt — 14 Tage, zwölftes leeres Fenster.**
- **Rückstand auf `main`:** **0** → 29 PRs · **10** → #1106, #1112, #1113, #1117, #1118, #1119,
  #1121, #1122 (**8**) · **15** → #1103, #1104, #1105, #1107 (**4**) · **19** → #1089, #1090
  (**2**) · **33** → #1078 · **48** → #1056 · **73** → #1025 · **89** → #1002 · **114** → #990 ·
  **237** → #831. _(29+8+4+2+6 = 49, addiert.)_
- 🔴 **Protokoll-Lage: 30 in offenen PRs.** Vorhanden sind die Läufe 42, 56–62, 64–75, 77–86;
  🔴 **zu Lauf 63 UND 76 existiert nirgends eines** (Regel 61). Dieser Lauf legt das
  **einunddreißigste** dazu.
- 🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02 geschrieben**
  (`e39d05eb`) — **49 Tage**, dreifach gehalten (#1103 bei 15, #1090 bei 19, #1078 bei 33).
  **Basis für ein abschließendes Paket: #1103.**

---

## Die drei Funde des Laufs

### 1. 🔴 Die Warteschlange nennt für #540 einen Blocker, der seit einem Monat erledigt ist

#442 §„Nicht in der Warteschlange" sagt über **#540**: „`needs-decision`, **Weiche 17**
unbeantwortet. 🟢 `Caddyfile` und `ci.yml` frei; **es bleibt an der Mechanismus-Entscheidung**
und an der fehlenden Container-Laufzeit." Dieselbe Formel trägt die Weichen-Tabelle in Weiche 17
(„🔴 Mechanismus-Entscheidung und `docker info` → Exit 1").

🔴 **Die Mechanismus-Entscheidung ist nicht offen.** Am Repo gemessen:

| Messung | Ergebnis |
|---|---|
| `git log --oneline origin/main -- deploy/hetzner/fail2ban` | **`39407da6`** `feat(deploy): Rate-Limit an der Kante per fail2ban auf Caddys Access-Log (#540) (#980)` |
| Commit-Datum | **2026-10-20T07:06:53+02:00** — **31 Tage** vor diesem Lauf |
| Umfang (`git show --stat`) | **7** Dateien, **573** Insertions: `ci.yml` (+9), `Caddyfile` (+8), `RUNBOOK.md` (+175), `fail2ban/filter.d/who2be-caddy.conf` (**78**), `fail2ban/jail.d/who2be-caddy.conf` (**74**), `tests/test_fail2ban_filter.sh` (**211**), ein Changelog-Fragment (**18**) |
| CI | `compose-smoke` fährt `bash deploy/hetzner/tests/test_fail2ban_filter.sh` (`ci.yml:399`/`:407`) und war am `main`-Kopf **`success`** |

🔴 **Und der Body von #540 behauptet das Gegenteil seines eigenen Kopfblocks.** Der Kopfblock
(Lauf 57) sagt richtig „Die Mechanismus-Entscheidung ist gefallen und ausgeliefert: Option A".
§Owner-Entscheidung (`:109-119`) stellt die Frage „Welcher Mechanismus?" weiter als offen, und
§Eskalation (`:161`) begründet die Gewichtung mit: „**`fail2ban` existiert im Repo nicht**, A
hängt also an einem Host-Setup ausserhalb des Repos." **Gemessen existiert es in vier Dateien
plus RUNBOOK-Abschnitt plus CI-Schritt** (`grep -ril fail2ban` → 10 Treffer außerhalb von
`.git/`). **Lauf 55 hat diesen Selbstwiderspruch schon benannt** — er steht seit **32 Läufen**
unkorrigiert im Body, weil #540 nicht aufgreifbar ist (Regel 62).

**Warum das mehr ist als ein verrotteter Zeiger:** #540 trägt `needs-decision` und liegt damit
auf dem Antwort-Stapel des Owners. Wer den Body liest, um Weiche 17 zu beantworten, liest zuerst
eine Mechanismus-Frage, die vor einem Monat entschieden **und gebaut** wurde. **Die Warteschlange
hat diesen falschen Grund elf Läufe mitgetragen** → **Regel 76**, und die Korrektur gehört in
**diese Liste** (Pflege-Regel 63c: eine Aussage, die in dieser Liste entstanden ist, wird hier
korrigiert).

### 2. 🔴 Drei Paket-Bodies führen geschlossene PRs als lebende Datei-Sperren

Lauf 86 hat gemessen, dass **#1128** und **#1131** am 2026-11-16 geschlossen wurden
(`merged: false`), und daraus Regel 74 gezogen. 🔴 **Er hat danach nicht die Bodies gesucht, die
sie zitieren** (Regel 152/184 verlangt genau das). Heute selbst gelesen:

| Body | Stelle | Behauptung | heute gemessen |
|---|---|---|---|
| **#632** | §Startbedingung `:199-200` | `apps/web/package.json` halten **#1130, #1129, #1128, #1124, #674** — „fünf" | 🔴 **#1128 ist geschlossen**; Träger sind **#1147**, #1130, #1129, #1124, #674 — **wieder fünf, andere Menge** |
| **#632** | §Verweise `:377` | „**#1128/#1129/#1130** — drei npm-Bumps … Weiche 31" | 🔴 **#1128 geschlossen**, der Nachfolger **#1147** fehlt |
| **#633** | §Startbedingung `:210-212` | package.json **fünffach** mit #1128 · `uv.lock` (**#1120, #1123**) · Compose (**#1131**–#1136) | 🔴 **drei Fehler:** #1128 **und** #1123 geschlossen, #1131 geschlossen (Bereichsanfang); `uv.lock` ist **vierfach** (#1120, #1141, #1142, #1148), Compose ist **#1132–#1136** plus #1146/#1149 |
| **#989** | §Startbedingung `:400` | `package-lock.json`: #1124 · #674 · **#1128**, #1129, #1130 — „fünf Schreiber" | 🔴 **#1128 geschlossen**, **#1147** fehlt |

**Selbst gegengelesen, zwei Wege** (Regel 10): je PR `state` + `merged` + `closed_at`, und die
Verdrängung an der Uhrzeit — **#1128** (`closed_at` 2026-11-16T05:17:18Z, 2 Dateien,
„web-minor-patch … 14 updates") ↔ **#1147** (eröffnet 05:18:03, „… 16 updates");
**#1123** (05:19:52, „python-minor-patch … 10 updates") ↔ **#1148** (05:20:25, „… 11 updates");
**#1131** (05:27:49, „compose-images … 3 updates") ↔ **#1149** (05:27:53, „… 5 updates").
🟢 **Es waren drei Verdrängungen an diesem Tag, nicht zwei** — #1123 war in #1150 schon geführt,
in Lauf 86s Bilanz aber nicht.

🔴 **Eine falsche Sperr-Tabelle ist keine verrottete Zahl, sondern eine falsche Anweisung**
(Regel 63a): sie schickt einen aufgreifenden Agenten dazu, auf einen Merge zu warten, der nie
kommt, und verschweigt den Schreiber, der wirklich auf der Datei sitzt. **Korrektur im Body,
nicht im Kommentar** (Regel 33/170) — und alle vier betroffenen Bodies haben ihre
Attributions-Fußzeile bereits verloren (Lauf 86), der Vollschrieb kostet hier also nichts
(Weiche 19).

### 3. 🟢 #1124 verlässt die Advisory-Bereiche an **jeder** Deklaration — jetzt pro Knoten gemessen

Lauf 86 hat #1124 gegen beide Advisory-Bereiche gelesen und „glob 14.0.3 / minimatch 11.0.3"
notiert — **an je einer Stelle**. Regel 67 verlangt die Messung am **Deklarationsort**, und von
`minimatch` gibt es im Lockfile **neun**. Heute über `json.load` beider Lockfiles gezählt:

| Paket | Deklarationen | `main` @ `f89acf87` | `refs/pr/1124` | Advisory-Bereich | Urteil |
|---|---|---|---|---|---|
| `glob` | **1** (`node_modules/glob`) | **13.0.6** | **14.0.3** | `>=9.0.0 <=14.0.1` | 🟢 **außerhalb** |
| `minimatch` | **9** | **8×** betroffen: `10.2.5` ×7, `10.2.6` ×1 — plus `node_modules/minimatch` **3.1.5** | **8× 11.0.3**, die 9. unverändert **3.1.5** | `>=7.0.0 <11.0.1` | 🟢 **alle acht außerhalb; die neunte war nie drin** |
| `picomatch` | **1** | **4.0.7** (`package-lock.json:8502` — Zeiger gültig) | **4.0.7** | — (`GHSA-fc5q-39xc-vjpf` wird nicht mehr gemeldet) | — |

🟢 **Weiche 46 Option A ist damit nicht an einem Punkt, sondern an allen zehn betroffenen
Knoten belegt.** ⚠️ **Die neunte `minimatch`-Deklaration ist der Grund, warum der `reason`-String
der OSV-Ausnahme `3.1.5` falsch als betroffen nennt** (#989 §Out of Scope führt das korrekt als
#1124s Sache).

## Norm-Prüfung „Agent-ready Arbeitspaket" — alle 13 offenen Issues

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**. 🟢 **Jeder der 13
Bodies ist in diesem Lauf wörtlich gelesen**, keine Zeile als übernommen geführt (Regel 42/189).

| Issue | Labels | Outcome | AK | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|---|
| **#632** | `agent-ready` `size/S` | ✅ `### Fertig heißt` | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **4/4** |
| **#1001** | `agent-ready` `size/S` | ✅ `## Fertig heißt` | ✅ 5 | ✅ `**Out of Scope:**` | ✅ | 🟢 **4/4** |
| **#633** | `agent-ready` `size/S` | ✅ `### Fertig heißt` | ⚠️ 6 | ✅ `**Out:**` | ✅ | 🟢 **4/4** |
| **#989** | `agent-ready` `size/S` `needs-decision` | ✅ `## Fertig heißt` | ⚠️ 6 | ✅ `## Scope`/`Out of Scope` | ✅ | 🟢 **4/4** |
| **#1150** | `needs-decision` `size/S` | ✅ `## Fertig heißt` | ✅ 5 | ✅ `## Scope` mit `**In:**` | ✅ `## Verifikation (exakte Kommandos)` | 🟢 **4/4**, bewusst ohne `agent-ready` |
| **#540** | `needs-decision` `size/M` | ✅ `### Fertig heißt` | ⚠️ 7 | ✅ `### Out of scope` | ✅ | 🟢 **4/4 formal** — 🔴 **mit falscher Aussage in §Owner-Entscheidung/§Eskalation, s. Fund 1** |
| **#454** | `human-only` | ✅ `### Fertig heißt` | ✅ 5 | ✅ `### Out of Scope` | ⚠️ `### Verifikation` **ohne Befehl** | **3/4**, `human-only` |
| **#542** | `needs-decision` `human-only` `size/M` | ❌ | ✅ 5 | ✅ `### Out of scope` | ⚠️ nur für Option A/C | **3/4** |
| **#435** | `epic` `size/M` | ⚠️ nur inline `**Fertig heißt:**` | ⚠️ 6 | ✅ `**Out:**` | ✅ | **4/4 formal**, Tracking |
| **#535** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 3 | ✅ `### Out of scope` | ❌ | **2/4**, Tracking |
| **#428** | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 5 | ✅ `### Out of scope` | ❌ | **1/4**, Tracking |
| **#338** | `human-only` | ❌ | ❌ (Checkboxen O1–O4) | ❌ | ❌ | **0/4**, Checkliste |
| **#442** | `needs-decision` `backlog-queue` | — | — | — | — | diese Liste |

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines entzogen.**
🔴 **Ein `size/M`-Issue wird nie durch Nachtragen von Feldern startbar** (§Constraints) — #428,
#435, #535, #540, #542 brauchen Zuschnitt, kein Refinement.
⚠️ **Die „6/7 AK"-Markierungen bleiben kein belegter Verstoß:** `grep -rn '2–5\|2-5\|bis 5'
.github/PROJECT.md` → **kein Treffer**, **dreiundzwanzigster Lauf ohne lesbare Quelle für die
Obergrenze** (Weiche 55 offen; die Norm selbst liegt in der AgentDB und war diesen Lauf nicht
erreichbar).

### Zeiger — selbst nachgemessen, nicht übernommen

🟢 **#632: alle 14 Zeiger seiner Tabelle gültig, null verrottet** — `MfaSection.tsx` **297** ·
`MfaSection.test.tsx` **284** · `MfaSection.a11y.test.tsx` **45** · `SessionProvider.tsx` **267**
(`mfaStepUpPending` `:57`) · `i18n/audit.test.ts` **371** (Filter `:309` = `.filter((f) =>
!known.has(f.key))`) · `LoginPage.tsx` **399** · `package.json` **82** (`engines.node` `:8`) ·
`vite.config.ts` **107** (`thresholds:` `:99`, Werte `:100-103` = 80/79/75/80) ·
`e2e/helpers/auth.ts` **199** (`createUser` `:33`, Aufruf `:55`, Definition `:97`) ·
`api/client.ts` **1849** · `api/types.ts` **2407** · `ci.yml` **1259** · `test/a11y.test.ts`
**77** (`:74` `toBeGreaterThanOrEqual(20)`) · `orphan-baseline.json` **156** (flache Liste) ·
`osv-scanner.toml` **26** Zeilen, `ignoreUntil = 2026-11-30` auf `:11`, `IgnoredVulns` **2×**.

🟢 **#1001: alle fünf Zeigergruppen gültig** — Datei **609** Zeilen; `104.777` auf `:233`, `:292`,
`:327`, `:487`; `108.262` auf `:234`, `:331`; `71.738` auf `:236`, `:335`; Kopf `:254` („Stand
2026-10-27, 103 Werkzeuge" — Datum ohne Commit, genau der AK1-Rest); Referenzprofil `:260-265`
zeichengleich mit meinem `payload_report`-Lauf; `instructions` **1.834** auf `:267`/`:309`.

🟢 **#989: alle Zeiger gültig** — `http-cache-semantics` **4.2.0**, Eintrag `:6313`, `"version"`
`:6314`, `resolved` `:6315`, Elternrange `^4.1.1` `:7620`; `npm ls` nennt **einen** Pfad
(`license-checker-rseidelsohn → @npmcli/arborist → npm-registry-fetch → make-fetch-happen`);
`turns red again` **1×** auf `osv-scanner.toml:6`; `IgnoredVulns` **2**; das zu löschende
Fragment **8** Zeilen.

🟢 **#633: alle Zeiger gültig** — `ci.yml:463` (`npm run e2e -- --project=chromium`), `:544`
(`npx playwright test e2e/billing.spec.ts`), `LoginPage.tsx:39` (`completeMfaChallenge`), Aufruf
`:172`.

🟢 **#1150: Option A ist an fünf Dateien belegt** — `requires-python = ">=3.11"` steht in
`pyproject.toml`, `apps/api`, `apps/mcp`, `packages/models`, `packages/billing` (je `:5`);
`soupsieve` im Lock **1×** (`uv.lock:2805`), Version `2.9.2` (`:2806`).
🔴 **Die Zielversion in #1150s `# erwartet:`-Block (`4.1.1`) ist überholt.** Messweg benannt
(Regel 176): `https://pypi.org/pypi/soupsieve/json` am 2026-11-20 → `info.version` **4.1.2**,
jüngste Releases `… 4.0.1, 4.1, 4.1.1, 4.1.2`. **Lauf 86s Korrektur hält, zweite Quelle.**

🔴 **#540: acht Zeiger verrottet, heute selbst nachgemessen** — `Caddyfile` **208** Zeilen
(Body: `:125-155`, heute `api.{$DOMAIN}` auf **`:133`**, `import access_log` `:135`, `respond
@internal` `:145`, `@internal_alt` `:154`, `max_size 32MB` **`:160`**, `reverse_proxy api:8000`
**`:162`**, `mcp.{$DOMAIN}` **`:196`**, `flush_interval -1` **`:206`**); `grep -cE "\brate\b"` →
**0** (hält); `RUNBOOK.md` **3244** Zeilen (Body: `:830`; §Rate-Limit heute **`:1002`**,
§Entsperren **`:1124`**, TOC `:15` hält); Caddy-Pin **`:480`** bei **605** Zeilen (Body: `:452`
bei 573); `ci.yml:351/367` → heute **`:381`/`:398`** (`CADDY_IMAGE=caddy:2.8-alpine`);
`test_compose_hardening.py:216` ist heute
`def test_caddy_access_log_is_enabled_for_every_site()`, nicht der Versions-Guard.
🟢 **Unverändert gültig:** `core/config.py:83` (`rate_limit_write: str = "30/minute"`),
`core/rate_limit.py:47` (`return get_remote_address(request)`).

## Reihenfolge und Wellen

**Unverändert gegenüber Lauf 86 — und das ist gemessen, nicht übernommen:** das Fenster hat
**0 Commits**, kein PR ist gemergt, keine harte Abhängigkeit hat sich gelöst, kein Blocker ist
weggefallen, kein neues Issue ist eingegangen.

| Pos | Issue | Größe | Baum | Kriterium | Lage |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | ✅ **startbar** — 🟢 **keiner der 49 PRs fasst `apps/web/src/**` an** (Treffer 0) |
| **2** | **#1001** Payload-Budget (ADR-0058 P4b, Rest) | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar** — alle drei Hebel frei |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web/E2E | harte Abhängigkeit | 🔴 nach **#632** **und** Container-Laufzeit (`docker info` Exit 1, **63.**) **oder** ein CI-Lauf mit **einzeln** gelesenen E2E-Conclusions (`ci.yml:463`/`:544`) |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | Owner-Vorgabe fehlt | 🔴 erst **Weiche 48**, dann die Fläche (`package-lock.json` **fünffach**: #1147, #1130, #1129, #1124, #674) |

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + #1150** | Die vier Schritte zu `pip-audit` Exit 0, reihenfolge-frei. 🔴 **#1150 braucht zuerst A/B/C — Option C ist keine Lösung.** Zielversion heute an PyPI gemessen: **4.1.2** |
| 🟢 **A** | **#632 + #1001** | Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle **49** PRs frei. ⚠️ Gemeinsame DoD-Fläche `STATE.md` (dreifach gehalten) — wer zweiter fertig wird, rebasiert auf **#1103** |
| **B** | **#633** | nach #632 (hart) **und** Container-Laufzeit **oder** CI mit einzeln gelesenen E2E-Conclusions |
| **C** | **#989** | erst Weiche 48. 🟢 Entlastet: #1124 verlässt die Bereiche an allen Knoten (Fund 3) |
| **M** _(Owner)_ | Welle 0 → **#1124** → **#1148** → **#1132–#1136 / #1149** → **#1146** → Domain-Doku (#1106 **oder** #1122) | #1149 überschneidet #1134 und #1132 — nacheinander messen. **#1106/#1122 nicht beide** (Weiche 49), **und einer muss kommen** (Betreiber-Host) |
| **N** _(Owner)_ | **30 Protokoll-PRs** in beliebiger Reihenfolge | #1153, #1152, #1151, #1145, #1144, #1143, #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — **je genau eine Datei außer #1105** (zwei: Protokoll + `.github/PROJECT.md`) **und #1152** (drei: Protokoll + `CLAUDE.md` + `ARCHITECTURE.md`). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | Rückstand 15 / 33 / 237 |
| **Q** _(Owner, entscheidbar)_ | **#674** | 🟢 konfliktfrei, **0** hinter `main`. 🔴 eigene Checks rot. **Empfehlung B (schließen)** |
| **R** _(Owner)_ | **#1129, #1130, #1147** | zwei Major plus Gruppen-PR auf der Fläche von #1124. **Nach #1124, einzeln** |
| 🆕 **S** _(Owner, einzeln)_ | **#1127** | `ci: bump docker/login-action 4.7.0 → 4.8.0`. **Fläche: genau `.github/workflows/deploy.yml`** — berührt `ci.yml` **nicht** und damit kein Paket dieser Warteschlange. 🔴 **Stand heute in KEINER Welle geführt** (Fund siehe unten) |

🔴 **Lückenprüfung der Wellen, zum ersten Mal gerechnet:** Welle 0 (3) + M (11) + N (30) + Q (1)
+ R (3) = **48** von **49** offenen PRs. **Der Fehlende ist #1127** — er stand in Lauf 86s
Bestandszahl (48) und in **keiner** Welle, und in dessen Body kommt er **0×** vor. **Eine Summe
über eine Menge ist kein Beleg, dass die Menge zugeordnet ist** → **Regel 77**.

## Was geschrieben wurde

**In den Body** (Regel 33/170 — falsche Anweisung, Paket aufgreifbar): **#632**, **#633**,
**#989** (geschlossene PRs als Datei-Sperren, Fund 2; plus die strukturell verrotteten
Bestandszahlen auf die heutige Messung **49/54** und die Tagesabstände) und **#1001**
(Bestandszahlen **26/31 → 49/54**, „38 Tage" → **49**, „drei Tage" → **14**, „dreizehnte
identische Messung" → **22.**).

**In die Warteschlange** (#442, Pflege-Regel 63c): der falsche Blocker-Grund bei #540 (Fund 1),
die Wellen-Lücke #1127 (Welle S), die Pro-Knoten-Messung von #1124 (Fund 3), der PR-Bestand
49/54, die neuen Regeln **76** und **77**.

**Als Kommentar, mit benanntem Grund** (Regel 62 — nicht aufgreifbar, eine Body-Korrektur
erreicht keinen Agenten): **#540** (Fund 1 vollständig, mit den acht nachgemessenen Zeigern) und
**#1150** (Zielversion 4.1.2, zweite Quelle PyPI).

🔴 **Der Vollschrieb von #540 ist bewusst unterlassen** — #540 ist einer von nur noch **vier**
Bodies, die ihre Attributions-Fußzeile tragen (#540, #535, #435, #428), und ein MCP-Body-Write
zerstört sie nachweislich (Lauf 86, fünf Fälle). **Die zuständigen offenen Weichen sind 44**
(`gh api -X PATCH --input` als Teil-Schreibweg), **45** (darf ein langer Body komplett neu
geschrieben werden) **und 53** (Vollschrieb für eine einzelne falsche Stelle). Dieser Lauf
liefert ihnen erstmals einen Fall, in dem der Preis nicht eine verrottete Zahl, sondern eine
**falsche Aussage** ist. **Das macht die Frage dringender, aber nicht entscheidbar ohne den
Owner.**

🔴 **Eigene Korrektur, am Body von #442 gemessen: „Weiche 19" gibt es in der Liste nicht** (mehr).
Dieser Plan hat sie in seiner ersten Fassung als zuständige Weiche genannt — `grep -c 'Weiche 19'`
über den Body von #442 liefert **0**, und die Weichen-Tabelle trägt die Nummern 2, 4–10, 12, 15,
17, 18, 23, 30, 31, 36, 38–41, 43–49, 51–57. Die Fußzeilen-Mechanik steht dort als **Pflege-Regel
32** (Regel 169), nicht als Weiche. **Die Nummer stammt aus dem Protokoll von Lauf 55 und ist
seither nicht mehr geführt** — ein Zeiger in ein Dokument ist auch dann verrottet, wenn er auf
eine Weichen-Nummer zeigt (Regel 65).

⚠️ **Und eine Zusage der Weichen-Tabelle selbst trägt nicht** (Regel 57/60): ihr Kopf sagt
**„36 offene Weichen"**, die Tabelle hat **36 Inhaltszeilen** — darunter aber **#56 ausdrücklich
als GESCHLOSSEN**, **#52 als „eingelöst"**, eine Zeile mit **zwei** Nummern (**11 / 34**) und eine
**ganz ohne** Nummer (`#542`). **Je nach Zählweise sind es 33, 34 oder 36**; die Zahl steht ohne
ihre Zählweise da. **In dieser Liste korrigiert, nicht als Fund gegen das Repo geführt.**

### 🔴 Nachtrag zur Schreibphase: ein Vollschrieb über MCP ist ein Abtippen, kein Kopieren

Die vier Paket-Bodies sind von **je einem eigenen Sub-Agenten** geschrieben worden, der den
Originaltext als Datei vor sich hatte (`/tmp/claude-0/bodies/<nr>.md`), die Ersetzungen per
`str.replace` mit `assert count == 1` ausführte und das Ergebnis lokal ablegte. **Danach habe ich
alle vier geschriebenen Bodies zurückgelesen und maschinell gegen die lokalen Dateien
verglichen** — nicht per Sichtvergleich.

| Issue | lokal | auf GitHub | identisch |
|---|---|---|---|
| **#632** | 41.868 | 41.868 | 🟢 **ja** |
| **#989** | 32.416 | 32.416 | 🟢 **ja** |
| **#1001** | 25.377 | 25.377 | 🟢 **ja** |
| **#633** | 47.186 | **47.187** | 🔴 **nein — eine Abweichung** |

🔴 **Die Abweichung steht an Position 3123, im historischen Kopfblock („NICHT befolgen"):** das
Original und die lokale Datei sagen „an der beide **Vorläufe** gescheitert sind", auf GitHub steht
„beide **Vorläufer**". **Ein Zeichen in 47.187, inhaltlich im Vorzeichen falsch** (gemeint sind die
zwei vorangegangenen Läufe, nicht Vorgänger), **in einem Block, der ausdrücklich als Historie
markiert ist.**

🟢 **Der Sub-Agent hat drei von vier Bodies zeichengleich geschrieben und alle fünf Ersetzungen
korrekt gesetzt** — die Drift ist nicht in einer Ersetzung entstanden, sondern beim Abtippen des
unveränderten Teils. **Lauf 86 hat für diesen Weg notiert: „Das senkt die Fehlerrate" (Weiche 44).
Heute ist gemessen, dass es sie senkt und nicht beseitigt.**

🔴 **Bewusst NICHT nachgeschrieben.** Ein korrigierender Schrieb wäre ein zweites Abtippen
derselben 47.187 Zeichen mit derselben Drift-Wahrscheinlichkeit, für ein Wort in einem Block, den
der Body selbst als „nicht befolgen" kennzeichnet. **Der Nutzen trägt das Risiko nicht** →
**Regel 78**. Die Stelle ist hier protokolliert, damit der nächste Vollschrieb von #633 sie
mitnimmt.

⚠️ **Zwei Beobachtungen der Schreiber, die stehen bleiben, beide mit Grund:** in **#632** sagen
zwei Absätze in §Verifikation weiter „über alle **39** offenen PRs frei" — sie tragen
ausdrücklich das Messdatum **2026-11-13** und sind als datierte Historie richtig (Regel 19).
In **#1001** sagt §Wartestand weiter „aller **26** offenen PRs … am **2026-11-09**" — dieselbe
Lage. 🔴 **Ein Fehler in meiner eigenen Anweisung ist dagegen sofort nachgezogen worden:**
Ersetzung 5 in #1001 hob die Zahl auf 49, ließ im selben Klammerzusatz aber das Datum
**2026-11-09** stehen — eine Zahl von heute mit dem Datum von vorgestern. **Als elfte Ersetzung
auf 2026-11-20 korrigiert** (Regel 19: Messweg **und** Messdatum).

## Neue Regeln

**76.** 🆕 **Ein Blocker-Grund verrottet wie ein Zeiger — und schneller als er.** #442 hat elf
Läufe „es bleibt an der Mechanismus-Entscheidung" über #540 geführt, während die Entscheidung
seit dem 2026-10-16 gefallen und seit dem 2026-10-20 als PR #980 auf `main` lag. **Messweg: zu
jedem `needs-decision` einmal `git log` über die Fläche der Entscheidung fahren, nicht nur den
Weichen-Text fortschreiben.** Eine Weiche, deren Gegenstand gebaut ist, ist beantwortet, auch
wenn niemand sie abgehakt hat.

**77.** 🆕 **Eine Wellen-Tabelle wird gegen den Bestand abgeglichen, nicht gegen sich selbst.**
Zwölf Läufe haben 48 bzw. 49 offene PRs gezählt und in Wellen gruppiert, ohne die Differenz
Bestand − Zuordnung zu rechnen. **#1127 ist seit dem 2026-11-09 offen und in keiner Welle.**
Messweg: die Vereinigung aller Wellen-Mengen bilden und gegen die Liste der offenen PRs
differenzieren — Zugänge **und** nicht zugeordnete.

**78.** 🆕 **Ein Body-Vollschrieb über MCP ist ein Abtippen, kein Byte-Kopieren — und wird
maschinell gegengelesen, nicht per Sichtvergleich.** Von vier Bodies dieses Laufs sind drei
zeichengleich angekommen und einer mit **einem** unbeabsichtigt geänderten Wort (#633, Position
3123, 47.187 statt 47.186 Zeichen). **Ein Sichtvergleich findet das nie**; der Vergleich
`len(remote) == len(lokal)` **und** `remote == lokal` findet es in einem Befehl. **Folge:** wer
einen Body schreibt, legt das Ergebnis lokal ab und vergleicht danach zeichenweise; und
**ein Korrektur-Schrieb für eine harmlose Drift ist es nicht wert** — er ist ein zweites Abtippen
mit derselben Wahrscheinlichkeit.

---

_Protokoll zu Aufbereitungslauf 87, 2026-11-20, gegen `main` @ `f89acf87` (Baum `c751ed64`,
Fenster **0 Commits** zum zwölften Mal in Folge, **49** offene PRs über **54** Dateipfade).
**Der Kern in einem Satz: der oberste Posten des Backlogs ist unverändert Welle 0, aber der
teuerste Fund dieses Laufs ist, dass die Warteschlange dem Owner für #540 seit elf Läufen eine
Entscheidung abverlangt, die vor einem Monat gefallen und gebaut ist.** Dazu: drei Paket-Bodies
führten geschlossene PRs als lebende Datei-Sperren, und die Wellen-Tabelle hat einen offenen PR
(#1127) nie zugeordnet. Zwei neue Regeln (76, 77), eine neue Welle (S), keine neue Weiche —
Weiche 19 bekommt neues Gewicht._
