# Backlog-Aufbereitungslauf 90 (2026-11-23)

Basis: `origin/main` @ `78352c7` (Kopf vom 2026-11-22T20:19:59+01:00) ·
Vorgänger-Basis: `f89acf87` (Lauf 89) · Warteschlange: #442 · Auftrag: jedes
offene Issue gegen die Norm **Agent-ready Arbeitspaket** prüfen, Belegbares
selbst entscheiden und mit Beleg ins Issue schreiben, Urteilsfragen als
Kommentar mit drei Optionen zurückgeben, danach die Warteschlange neu ordnen und
in Wellen gruppieren.

> **Umgebungsgrenze, 23. Lauf in Folge:** der MCP-Server der eigenen AgentDB
> (`Who2Be---Coder`) verlangt eine Autorisierung, die diese Session nicht selbst
> anstoßen kann. `get_persona`, `list_triggers`, `fetch_playbook`,
> `fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"),
> `record_usage`, `submit_feedback` und `search_memory`/`save_memory` standen
> nicht zur Verfügung. **Persona und Playbook-Katalog lagen im System-Prompt
> vor; gefahren ist der Lauf nach dem in #442 kodifizierten Verfahren und
> `.github/PROJECT.md` §Constraints, nicht nach einem geladenen Playbook.**
> Keine Kurations-Rückmeldung an die AgentDB.

## Der Kern in einem Satz

🟢 **Welle 0 ist durch und `main` ist nach 16 Tagen grün** — aber der Fix für
`soupsieve` ist als **Option C** gelandet, und `uv.lock` trägt für CPython
3.11.0–3.11.4 weiter eine Version mit **drei CVEs**, die das Gate wegen eines
Markers nicht sieht.

## Ausgangslage — das erste bewegte Fenster seit fünfzehn Läufen

**2 Commits** seit `f89acf87`: `8c022370` (#1120, oauthlib 4.0.1) und
`78352c79` (#1159, dnspython 2.9.2 / opentelemetry-api 1.45.2 / soupsieve
4.1.3). Der Stillstand seit dem 2026-11-06 ist beendet.

**Offene Issues: 13** (unverändert). **Offene PRs: 19** — waren **51**.

Am **2026-11-22** hat der Owner gehandelt, je PR `state` + `merged` +
`closed_at` gelesen (Regel 74):

| Vorgang | Zahl | Darunter |
|---|---|---|
| gemergt | **2** | #1120, #1159 |
| ohne Merge geschlossen | **35** | **alle 29 Protokoll-PRs** · #674 · #1106 · #1141 · #1142 · #1146 |

🟢 **Vier Weichen sind damit durch Handlung beantwortet, drei davon genau nach
der Empfehlung dieser Liste:** Weiche **12** (#674 schließen), Weiche **49**
(#1122 behalten, #1106 schließen), Weiche **11/34** (Welle 0 mergen), Weiche
**54** (soupsieve heben — aber als Option C).

## Fund 1 — Welle 0 ist durch, und der blinde Fleck ist zu

| Messung | Ergebnis |
|---|---|
| `main`-CI am Kopf `78352c7` | Lauf **`45060144554`**, **14 Jobs, 14× `success`**, addiert (Regel 37/173) |
| `pip-audit` (Befehl der CI-Definition, selbst gefahren) | 🟢 **Exit 0**, „No known vulnerabilities found", **126** Requirements bei **400** Zeilen |

🟢 **Der `audit`-Job bricht nicht mehr bei `pip-audit` ab.** Die Schritte **6–10**
sind erstmals seit dem **2026-11-06** gelaufen statt `skipped`: `npm audit`
✅, `License check` ✅, **`OSV-Scan`** ✅. Damit ist nach 16 Tagen wieder
messbar, was hinter dem Abbruch lag (Regel 72/81/183) — **und genau dort liegt
der Nachweis von #1124.**

## Fund 2 — das Gate ist grün, weil ein Marker die Zeile versteckt

**#1159 hat genau die Option umgesetzt, die #1150 selbst als „keine Lösung"
führt.**

| Messung | Ergebnis |
|---|---|
| `grep -c '^name = "soupsieve"' uv.lock` | 🔴 **2** — `:2812` = **2.10**, `:2825` = **4.1.3** |
| Export | `318:soupsieve==2.10 ; python_full_version < '3.11.5'` · `320:soupsieve==4.1.3 ; python_full_version >= '3.11.5'` |
| `pip-audit` am vollen Export | 🟢 Exit 0 (prüfender Interpreter: CPython **3.11.18**) |
| 🔴 **Positiv-Kontrolle** (`2.10` ohne Marker, Regel 10/156) | 🔴 **Exit 1 — 3 CVEs**: `CVE-2026-126190` (Fix 4.0.0), `CVE-2026-126193` (Fix 3.0.2), `CVE-2026-126191` (Fix 3.0.2) |
| Betroffener Bereich | **CPython 3.11.0 – 3.11.4** |
| `requires-python` | **`">=3.11"`** in allen fünf `pyproject.toml` (je `:5`) **und** `uv.lock:3` |
| Ausschluss im Repo? | 🔴 **keiner** — keine `.python-version`, keine `uv.toml`, kein `[tool.uv] environments`, `grep -rn 'python-version\|setup-python' .github/workflows/*.yml` → **0**. Dockerfiles `python:3.14-slim` schützen die Auslieferung, nicht ein `uv sync` |

**Das Repo sagt eine Unterstützung zu, die es nicht einhält**, und das Gate kann
es nicht melden. Das Changelog-Fragment von #1159 benennt es selbst: „Für Python
< 3.11.5, das soupsieve 4 nicht unterstützt, löst der Lockfile soupsieve 2.10
auf." → **Weiche 67**, **Regel 84**.

## Fund 3 — das Rot von #1124 ist geerbt, sein Nachweis erst seit gestern möglich

#1124 trägt die Arbeit für **Weiche 46**, Frist **2026-11-30** — **7 Tage**.
Heute an der Check-Liste addiert: **18 Check-Runs, 16 `success`, 2 `failure`**
(`audit`, `all-green`). 🔴 **Der Lauf ist `42182282519` vom 2026-11-06, also von
vor Welle 0** — das Rot ist dasselbe geerbte Rot, das `main` damals trug
(Regel 79/159). Und sein eigener Nachweis, der `OSV-Scan`, ist in **keinem**
Lauf dieses PRs ausgeführt worden, weil `audit` davor abbrach (Regel 81).

🟢 **Ein Branch-Update (2 Commits, `merge-tree` rc 0) macht sein Rot zum ersten
Mal zu einer Messung.** Das ist der billigste Weg zu Weiche 46/48.

⚠️ Der `OSV-Scan` auf `main` war grün **mit** den beiden Ausnahmen
(`osv-scanner.toml` 26 Z., 2 `[[IgnoredVulns]]`, `ignoreUntil 2026-11-30` auf
`:11`/`:19`). Wie er **ohne** sie ausgeht, bleibt die Messung aus #989 AK2.

## Fund 4 — drei Paket-Bodies hielten eine Erlaubnis, die zur Falle geworden war

Vier startbare Bodies (#632, #633, #989, #1001) trugen den Satz, `all-green` sei
**ausgesetzt** und ein rotes `audit` sei „nicht deins". Am 2026-11-20 richtig, am
2026-11-23 **eine falsche Anweisung**: sie hätte einen Agenten dazu gebracht, ein
echtes `audit`-Rot als Erbe abzutun. **In allen vier korrigiert** (Regel 33/170).

🔴 **Eigener Fehler, offengelegt:** zwei der vier Bodies (**#632**, **#633**)
sind von delegierten Schreibern über **`gh api -X PATCH`** geschrieben worden —
den Weg, den **Weiche 44** offen lässt und den Pflege-Regel 9 als „in dieser
Session nicht ausführbar" führt. Ursache war eine **Nebenvorgabe** im Auftrag
(„den Body nicht abtippen"), die mit der Grenze kollidierte; der Auftrag nannte
MCP, sagte aber nicht, was bei Kollision weicht. Nach dem ersten Fund ist die
Korrektur an alle laufenden Schreiber gegangen; **#989 und #1001 sind über MCP
geschrieben.** → **Regel 86**.

🟢 **Messbarer Nebenbefund für Weiche 44/53:** der `gh`-Weg ist byte-genau und
**hängt die Attributions-Fußzeile an** (+58 Zeichen), statt sie zu zerstören —
zweimal unabhängig gemessen. Davor war der Body je **zeichengleich** zum
erwarteten Text. Das korrigiert die Annahme hinter Regel 169.

## Fund 5 — der Vitest-Baum ist nicht mehr frei, und es traf die geteilte Fläche

Zwölf Läufe lang galt „KEIN EINZIGER der offenen PRs fasst `apps/web/src/**`
an". 🔴 **Vorbei.** **#1158** schreibt dort u. a. **`i18n/locales/de.json`** und
**`en.json`** — **genau die Dateien, die #632 und #633 teilen** — dazu
`ConnectGuide.tsx`, `WelcomeDialog.tsx` (+Test), `lib/installLinks.ts`,
`AgentConnectorSection.test.tsx`, `i18n/umlauts.test.ts`.

🟢 **Die eigentlichen Flächen bleiben frei:** `features/settings/**` (#632),
`apps/web/e2e/**`, `LoginPage.tsx`, `SessionProvider.tsx`, `api/**`,
`vite.config.ts`. **Hier war nicht der Zeiger falsch, sondern die Erlaubnis**
(Regel 63a).

🔴 **Dazu drei neue Code-PRs, die es seit zwölf Läufen nicht gab:** #1157
(Werkzeug-Profile, ADR-0059 Q5-0), #1158, #1160 (PUT bei offenem Review → 409).
Untereinander **datei-disjunkt**, je 1 hinter `main`, konfliktfrei.
⚠️ **Ungemessen, aber vorhersehbar:** #1160 ändert Antwort-Verhalten in
`apps/api`, #1157 trägt `openapi_surface.json` + `docs/reference/openapi.json` —
zwei Pakete auf einer Vertragsfläche ohne gemeinsame Datei (Regel 186). Die
Check-Runs dieser drei PRs sind in diesem Lauf **nicht** gelesen.

## Norm-Prüfung — alle 13 offenen Issues, jeder Body gelesen

| Issue | Labels | Outcome | AK | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|---|
| #632 | `agent-ready` `size/S` `needs-decision` | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **4/4** |
| #1001 | `agent-ready` `size/S` | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **4/4** |
| #633 | `agent-ready` `size/S` | ✅ | ⚠️ 6 | ✅ | ✅ | 🟢 **4/4** |
| #989 | `agent-ready` `size/S` `needs-decision` | ✅ | ⚠️ 6 | ✅ | ✅ | 🟢 **4/4** |
| #1150 | `needs-decision` `size/S` | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **4/4** — 🔴 AK1/AK2 nicht erfüllt |
| #540 | `needs-decision` `size/M` | ✅ | ⚠️ 7 | ✅ | ✅ | 🟢 **4/4 formal** — 🔴 drei widerlegte Aussagen |
| #454 | `human-only` | ✅ | ✅ 5 | ✅ | ⚠️ ohne Befehl | **3/4 + 1 ohne Befehl** |
| #542 | `needs-decision` `human-only` `size/M` | ❌ | ⚠️ 5, keines mit Befehl | ✅ | ✅ | **3/4** — 🔴 Frage entschieden |
| #435 | `epic` `web` `size/M` | ⚠️ inline | ⚠️ 6, 1 mit Befehl | ✅ | ✅ | **4/4 formal** |
| #535 | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 3 | ✅ | ❌ | **2/4** |
| #428 | `epic` `needs-decision` `size/M` | ❌ | ⚠️ 5, keines mit Befehl | ✅ | ❌ | **2/4** |
| #338 | `human-only` | ❌ | ❌ | ❌ | ❌ | **0/4** |
| #442 | `needs-decision` `backlog-queue` | — | — | — | — | diese Liste |

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben,
keines entzogen.**

## Reihenfolge — unverändert

Kriterien: **1** harte Abhängigkeit → **2** Owner-Vorgabe → **3** Fundament vor
Fläche → **4** Inventar vor Zuschnitt → **5** bei Gleichstand das kleinere.

1. **#1001** — Payload-Budget _(Kriterium 4)_. **Das einzige Paket, das heute
   ohne Owner-Antwort startet.** 🟢 Die DoD-Ausnahme ist entfallen: `STATE.md`
   ist frei, Weiche 43/66 sind dafür gegenstandslos.
2. **#632** — Passkey registrieren. 🔴 **Weiche 59**, heute am Baum erneut belegt.
3. **#633** — Step-up mit Passkey. Nach #632 (Code-Abhängigkeit belegt).
   🟢 **Umgebungssperre gefallen:** der CI-Weg ist offen.
4. **#989** — `http-cache-semantics`. Weiche 48, dann #1124.

## Wellen

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | #1001 allein | alle drei Hebel über 19 PRs frei; `STATE.md` frei |
| **A2** | #632 | nach Weiche 59; vor dem Start #1158 lesen (`locales/{de,en}.json`) |
| **B** | #633 | nach #632; E2E über eigenen CI-Lauf, keine Container-Laufzeit nötig |
| **C** | #989 | Weiche 48 → #1124 → Fläche |
| 🔴 **M** _(Owner, 7 Tage)_ | **#1124**, dann #1147 → #1129 → #1130 | erst Branch-Update von #1124 |
| **M2** | **#1122** | alleiniger Träger des Betreiber-Host-Fixes (Weiche 39) |
| **M3** | #1148 · #1127 | je allein auf ihrer Fläche |
| **M4** | #1149 ∥ #1134/#1132 seriell; #1136, #1135, #1133 unabhängig | |
| **R** | #1157, #1158, #1160 | datei-disjunkt; nach #1160 das OpenAPI-Drift-Gate neu lesen |
| **N** | #1156, #1152, #1105 | die drei letzten Protokoll-PRs → Weiche 68 |
| **W67** | #1150 nach der Antwort | 5 Zeilen + `uv lock`, Fläche frei |

🟢 **Lückenprüfung (Regel 77):** M (4) + M2 (1) + M3 (2) + M4 (6) + R (3) +
N (3) = **19** von **19**.

## Messwerte

Node **v22.23.5**, npm **10.9.9**, uv **0.11.32**, CPython **3.11.18**. Klon war
shallow (50) → **1678** Commits nach `--unshallow` (Regel 90).

| Gate | Ergebnis | gegen Lauf 89 |
|---|---|---|
| `uv run ruff check .` | Exit 0 | gleich |
| `uv run mypy .` | Exit 0, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **5034** Tests | gleich |
| `changelog_fragments.py check` | Exit 0, **406** Fragment(e); `ls` = **407** | 🟢 405 → 406 |
| `pip-audit` | 🟢 **Exit 0**, 126 Requirements / 400 Zeilen | 🟢 Exit 1 → 0 |
| `npm run lint` | Exit 0, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | Exit 0, 0 Byte | gleich |
| `npm run i18n:check` | Exit 0, **156** Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | Exit 0 | gleich |
| `npm audit` (voll) | Exit 1, **27 moderate, 0 high** | gleich |
| `npx playwright test --list` | **44** Tests in **9** Dateien | gleich |
| `payload_report` | Builder **103 / 108.251**, Guard dito, `instructions` **1.834** | 🟢 24. identische Messung |
| `test_tool_payload_budget.py` | Exit 0, **64 passed** | gleich |
| `npm run test:coverage` | ⚪ nicht gefahren, mit Grund — `git rev-list --count f89acf87..origin/main -- apps/web` → **0**; 🟢 **der `web`-Job inkl. Coverage-Ratchet ist am 2026-11-22 an genau diesem Kopf grün gelaufen** (Messung am Zielbaum, Regel 178) | 🟢 Beleg verbessert |
| `main`-CI | 🟢 Lauf `45060144554`, **14/14 success** | 🟢 rot → grün |
| `docker info` | 🔴 Exit 1, kein `podman` | **64. Messung** |

`.claude/context/STATE.md` steht auf `main` zuletzt am **2026-10-02**
(`e39d05eb`) — **52 Tage**. ⚠️ **Eine Messung am flachen Klon liefert fälschlich
2026-10-23**; sie ist nicht übernommen (Regel 90). Dasselbe Muster bei
`39407da6`: am flachen Klon „kein Vorfahre von `main`", am vollen Klon
`git merge-base --is-ancestor` → **Exit 0**.

**Alle 19 PRs mergen konfliktfrei** (`git merge-tree --write-tree` → rc 0),
keiner bewegt 0 Dateien.

## Geschrieben

**Body korrigiert** (Regel 33/170 — falsche Anweisung in einem aufgreifbaren
Paket; je Body ein eigener Schreiber mit dem Originaltext vor sich):

| Issue | Weg | Zeichen vorher → nachher | Gegenlese |
|---|---|---|---|
| **#1001** | 🟢 MCP | 25.377 → **21.724** | 🟢 zeichengleich |
| **#989** | 🟢 MCP | 32.416 → **28.550** | 🟢 zeichengleich |
| **#632** | 🔴 `gh api` | 41.868 → **38.741** | zeichengleich bis 38.683, danach +58 (Fußzeile angehängt) |
| **#633** | 🔴 `gh api` | 47.187 → **42.313** | zeichengleich bis 42.255, danach +58 (dito) |

**#442** neu gesetzt (Nebenbedingung, Kopf, Gates, fünf Funde, PR-Bestand,
Sperren, Startbar, Norm-Tabelle, Wellen, zwei neue Weichen, drei neue Regeln,
Fußzeile). **#1150**: Titel nachgezogen (Regel 59) + Kommentar.

**Als Kommentar, mit benanntem Grund** (Regel 62 — `needs-decision` /
`human-only` / `epic`, nicht aufgreifbar): **#1150** (Weiche 67), **#540**
(Kriterien einzeln, drei widerlegte Aussagen, 20 Zeiger), **#542** (Weiche 63 —
der gebaute Weg ist keine der drei Optionen), **#338** (O2 zu zwei Dritteln
erledigt), **#535**, **#454**, **#428**, **#435**.

**Kein Code angefasst, kein Issue geschlossen, kein Label gewechselt, nichts
gemergt.**

## Vorgeschlagene Regeln

- **84** — *Ein Gate, das Umgebungs-Marker auflöst, misst die Umgebung des
  Prüfers, nicht die erklärte Unterstützung des Projekts.* Messweg: Positiv-
  Kontrolle ohne Marker, und den Marker-Bereich gegen `requires-python` lesen.
  (Gefangen an `soupsieve`.)
- **85** — *Ein Fenster, das sich nach fünfzehn leeren Läufen bewegt, bewegt
  mehr als den Baum.* 2 Merges und 35 Schließungen haben vier Weichen
  beantwortet, drei Sperr-Tabellen entwertet und einen Posten aufgelöst — bei
  zwei Commits. Messweg: erst den PR-Bestand differenzieren, dann die Bodies,
  die die Abgänge zitieren, dann die Gates.
- **86** — *Ein delegierter Schreibvorgang erbt die Grenzen des Auftraggebers
  nicht von allein.* Der erlaubte Weg steht VOR jeder Optimierung, mit dem
  Satz, dass bei Kollision die Optimierung weicht. (Gefangen am eigenen Fehler.)

## Nachlese für den nächsten Lauf

- 🔴 Die vier Body-Schreiber haben je **einige** nicht gelistete Stellen stehen
  gelassen, die nun im Widerspruch zu den neuen Aussagen stehen (u. a. in #632
  der Verweis auf die gestrichene Vier-Pakete-Liste, in #1001 §Scope „Welle 0:
  #1120 + #1141 + #1142 + #1150"). **Eine Ersetzungsliste, die einen Absatz
  ersetzt, muss die Absätze mitnennen, die auf ihn verweisen** (Regel 153).
- 🔴 Mehrere Schreiber haben im gemeinsamen Scratchpad **dieselben Dateinamen**
  benutzt und sich gegenseitig überschrieben. Je Schreiber ein eigenes Präfix.
- ⚪ Die Check-Runs von #1157, #1158, #1160, #1122, #1127, #1148 sind nicht
  gelesen. Gemessen ist nur #1124.
- ⚪ Die Wertegleichheit `plans.md` ↔ `BillingPanel` ↔ Code (#535 AK2) ist nicht
  neu durchgerechnet; die Zeiger `plans.md:26-29` und `BillingPanel.tsx:40-42`
  sind verrottet.
