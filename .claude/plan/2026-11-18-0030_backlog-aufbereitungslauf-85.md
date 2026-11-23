# Backlog-Aufbereitungslauf 85 — 2026-11-18

**Messpunkt:** `main` @ `f89acf87` (Baum `c751ed64`, `git status --porcelain` leer)
**Fenster seit Lauf 84:** **0 Commits — zum zehnten Mal in Folge.** `main` steht
seit dem 2026-11-06T08:05:51+01:00 still, **12 Tage**.
**Auftrag:** vollständiger Vorbereitungslauf — Norm-Prüfung aller offenen
Issues, Neuordnung der Warteschlange (`backlog-queue`), Wellen-Gruppierung,
Bericht in drei Blöcken.

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — zwanzigster Lauf in
Folge.** Die Autorisierung kann diese Session nicht selbst anstoßen. Nicht
verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket"), `record_usage`,
`submit_feedback`, `search_memory`/`save_memory`. Der Lauf fuhr nach dem
Queue-Issue #442 und `.github/PROJECT.md` §Constraints. **Kein
Playbook-Trigger traf** (kein Playbook abrufbar). **Keine Kurations-Rückmeldung
an die eigene AgentDB.**

---

## Der Fund des Laufs — die zwei Gates, die Welle 0 grün machen soll, laufen seit 12 Tagen überhaupt nicht

Das Queue-Issue führt Welle 0 als „die vier Schritte, die `audit` grün machen"
und begründet ihren Vorrang damit, dass sie „das Gate für alle 42 PRs
entsperrt". **Am Schritt-Protokoll des `main`-Laufs gemessen ist das zu
optimistisch**, und zwar aus einem Grund, den acht Läufe nicht benannt haben.

### Was am Job wirklich steht

`main`-Lauf **`42178623925`** (`status: completed` **und** `conclusion: failure`
getrennt gelesen), **14 Jobs**, davon **2 rot** (`audit`, `all-green`), an der
Job-Liste gezählt. Die Schrittliste des Jobs `audit`
(`job 127764639171`, **10 Schritte** in der Runner-Liste):

| # | Schritt | Conclusion |
|---:|---|---|
| 5 | `pip-audit (Python)` | 🔴 **failure** |
| 6 | `actions/setup-node` | ⚪ skipped |
| 7 | `Install web deps` | ⚪ skipped |
| 8 | `npm audit (Web, prod-only, high+)` | ⚪ **skipped** |
| 9 | `License check (Web · Deny-Liste)` | ⚪ skipped |
| 10 | `OSV-Scan (Web-Lockfile, unabhaengig von der npm-Registry)` | ⚪ **skipped** |

🔴 **Seit dem 2026-11-06 hat weder `npm audit` noch der OSV-Scan auf `main` ein
einziges Mal gelaufen.** 🟢 **Und das liegt nicht an einem Pfad-Filter** — die
Gegenprobe an der Definition (Regel 10, Regel 155: auch die Begründung prüfen):
der ganze `audit`-Job trägt **keine einzige `if:`-Bedingung** an einem seiner
**9** Schritte, weder auf `changes.outputs.web` noch sonst. Die fünf
übersprungenen Schritte fallen **allein** weg, weil Schritt 5 rot ist. Beide
hängen im selben Job hinter `pip-audit`
(Regel 183: ein Gate, das vor dem interessanten Schritt abbricht, macht ihn
unbeobachtbar). **Die Lage ist also nicht „ein rotes Gate", sondern ein rotes
Gate plus zwei blinde Flecken.**

### Warum das diesmal mehr als eine Formalie ist

Im selben Fenster hat sich die **npm**-Advisory-Datenbank bewegt — am
bitgleichen Baum, selbst gefahren in `apps/web/`:

```
npm audit --omit=dev --audit-level=high   -> Exit 0, "found 0 vulnerabilities"
npm audit (voll)                          -> Exit 1, 33 Funde: 25 moderate, 8 HIGH
npm audit --package-lock-only (Gegenprobe) -> zeichengleich 25 moderate / 8 high
```

🔴 **Acht `high`-Funde, wo Lauf 84 noch „27 moderate, 0 high" gemessen hat.**
Wurzel ist **genau eine** Advisory:

| Advisory | Paket | Reichweite im Baum |
|---|---|---|
| **GHSA-fc5q-39xc-vjpf** — „picomatch vulnerable to ReDoS through single-branch repeated extglobs", CVSS **7.5**, CWE-1333, betroffener Bereich **`<=4.0.7`** | `picomatch@4.0.7` | `tinyglobby`, `vite` (direkt), `vite-node`, `vitest`, `@typescript-eslint/typescript-estree`, `node-gyp`, `@npmcli/run-script` |

🔴 **Es gibt keine Fix-Version.** `npm view picomatch versions` endet bei
**4.0.7**, `dist-tags.latest` ist **4.0.7** — der betroffene Bereich deckt den
gesamten veröffentlichten Bestand. **Kein Bump behebt das heute**, auch nicht
der offene Gruppen-PR **#1147** (hebt `vite` 8.3.5 → **8.3.8**, lässt
`picomatch` bei **4.0.7** — an beiden Lockfiles gemessen).

### 🔴 Und der Weg, den npm selbst vorschlägt, ist ein Rückbau um zwei Majors

`npm audit` druckt in jeder Session (auch im SessionStart-Hook dieses Repos)
„To address all issues (including breaking changes), run: `npm audit fix
--force`". **Gemessen** (`npm audit fix --force --dry-run`, gezählt werden
`change` und `remove`, Regel 180):

```
125 add · 47 change · 132 remove
  change vite     8.3.5  => 6.2.7     (zwei Majors zurück)
  change vitest   4.1.12 => 3.1.4     (ein Major zurück)
  change vite-node 6.0.0 => 3.2.4
  change glob     13.0.6 => 10.5.0
  change license-checker-rseidelsohn 5.0.1 => 4.4.2
  change chai     6.3.0  => 5.3.3     … u. a.
```

🔴 **`fixAvailable` meldet für `picomatch` wörtlich `{"name":"vitest",
"version":"3.1.4","isSemVerMajor":true}`** — eine *Herabsetzung*, als „Fix"
etikettiert. Wer dem Hinweis folgt, baut die Build-Kette des Frontends zurück
und senkt dabei kein Risiko, das in einem ausgelieferten Artefakt liegt.
**Das ist die zweite Anweisung in zwei Läufen, die formal gültig und
inhaltlich schädlich ist** (Lauf 84: der `soupsieve`-Schritt; Lauf 81: der
„einziger Fund"-Satz) → neue **Regel 70**.

### Was davon Welle 0 betrifft

Der CI-Schritt 8 fährt `--omit=dev --audit-level=high` (`ci.yml:1001`) — die
acht Funde sind **dev-only**, dieser Schritt bliebe also grün (heute lokal
Exit 0 gegengemessen). 🔴 **Schritt 10 ist der scharfe:** der OSV-Scan ist
laut eigener Begründung im Workflow „**bewusst STRENGER** als `npm audit`
daneben: voller Lockfile-Umfang (inkl. dev) und **jeder** Schweregrad",
**BLOCKIEREND**, und seine einzigen Ausnahmen sind zwei zeitlich befristete
Einträge in `apps/web/osv-scanner.toml` (26 Zeilen):
`GHSA-3g3m-2fjr-6pw4` (glob) und `GHSA-g3hv-75wg-m249` (minimatch), **beide
`ignoreUntil = 2026-11-30`, also in 12 Tagen fällig.**
**`GHSA-fc5q-39xc-vjpf` steht dort nicht.**

⚠️ **Ob der OSV-Scan die picomatch-Advisory tatsächlich meldet, ist in dieser
Session nicht messbar** — und das wird hier als Grenze geführt, nicht als
Fund. Der gepinnte Scanner lief, die Datenbank nicht:

```
osv-scanner 2.2.4 (SHA256 gegen ci.yml geprüft: OK)
Scanned .../package-lock.json file and found 700 packages
Loaded filter from: .../osv-scanner.toml
error when retrieving vulns: ... Post "https://api.osv.dev/v1/querybatch": Forbidden
scan_rc=127
```

`api.osv.dev` ist für diese Session egress-gesperrt (vier abgewiesene
Verbindungen über den Agent-Proxy). **Der CI-Schritt hätte diesen Lauf als
„OSV-Scan nicht gelaufen" rot gemeldet, nicht als Fund** — die
`jq -e 'has("results")'`-Wache im Workflow greift genau hier (`ci.yml`
§OSV-Scan). Das ist ein Qualitätsmerkmal des Gates und zugleich der Grund,
warum diese Frage offen bleiben muss.

**Die belastbare Fassung, und sie ist die Korrektur an der Warteschlange:**
> Welle 0 ist **notwendig**, aber nach heutiger Messung **nicht hinreichend**.
> Sie macht `pip-audit` grün und **entsperrt damit zum ersten Mal seit 12 Tagen
> die Schritte 8–10** — gegen einen Lockfile, der 8 high + 25 moderate
> npm-Advisories trägt, von denen eine (picomatch) **keine** Ausnahme und
> **keine** Fix-Version hat, und zwei weitere (glob, minimatch) in 12 Tagen
> ihre Ausnahme verlieren. **Der erste grüne `audit`-Lauf nach Welle 0 ist
> keine Zusage, sondern die erste echte Messung.**

→ **Weiche 56** (neu, drei Optionen mit Empfehlung, im Kommentar zu #442).

---

## Zweiter Fund — die Projekt-Kontextdateien behaupten seit 166 Tagen den falschen Frontend-Stack

| Stelle | Behauptung | Repo-Stand | Delta |
|---|---|---|---|
| `CLAUDE.md:185` | „Framework: **Vite 7** + React 18" | `apps/web/package.json:77` → **`"vite": "^8.3.5"`**, installiert **8.3.5** | 🔴 falsch |
| `.claude/context/ARCHITECTURE.md:9` | „**React 18 + Vite 7**, TypeScript strict, Tailwind v4" | dito | 🔴 falsch |

Der Übergang ist datiert: **`9af60619`, 2026-06-05** („deps(web): bump the
web-vite-major group in /apps/web with 5 updates"). **166 Tage.**

🟢 **Die Nachbar-Behauptungen derselben Zeilen sind gegengeprüft und stimmen**
(Regel 153 — ein Fund wird an jeder Stelle korrigiert, aber auch nicht
weiter): `react`/`react-dom` **^18.3.1** (`:46`/`:47`, installiert 18.3.1),
`react-router-dom` **^7.18.5** (`:50`), `@tailwindcss/vite` **^4.3.3** (`:39`,
also Tailwind v4), TypeScript `strict` unverändert.

**Warum das kein Schönheitsfehler ist:** das sind die beiden Dateien, die das
Projekt selbst als Agenten-Gedächtnis ausweist — `CLAUDE.md` („wird jede
Session geladen") und `.claude/context/` („persistentes Projekt-Gedächtnis
**gegen Session-Drift**"). Eine falsche Stack-Angabe dort ist genau die Drift,
die sie verhindern sollen. **Repo-belegt, keine Urteilsfrage → in diesem Lauf
selbst korrigiert** (beide Dateien über alle **47** offenen PRs **FREI**, am
vollen Pfad gemessen).

---

## Messgrundlage — alle Werte heute selbst erhoben

Sequenziell, **ohne vorherige Reparatur** (Regel 120), Exit-Codes am
unverketteten Befehl (Regel 36/94/172), Ausgaben getrennt in Dateien.
Node **v22.23.5** _(Lauf 84: v22.23.4 — Umgebung, nicht Repo)_, npm **10.9.9**,
uv **0.11.32**, Interpreter **CPython 3.11.18**. Klon war shallow (50) →
**1676** Commits nach `--unshallow`. `npm`-Gates in `apps/web/` mit
`pwd`-Beleg, Python-Gates im Repo-Root.

| Gate | Ergebnis | gegen Lauf 84 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5034** Tests | gleich |
| `uv run --no-project python scripts/changelog_fragments.py check` | **Exit 0**, **405** Fragment(e); `ls changelog.d/*.md \| wc -l` → **406** (Differenz: `README.md`) | gleich |
| 🔴 `uv tool run pip-audit --disable-pip --no-deps -r <reqs>` | 🔴 **Exit 1 — 7 CVEs in 4 Paketen** (`dnspython`, `oauthlib`, `opentelemetry-api`, `soupsieve`×4) | gleich |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, 7 `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, „found 0 vulnerabilities" | gleich |
| 🔴 `npm audit` (voll) | 🔴 **Exit 1**, **33** Funde: **25 moderate, 8 HIGH** | 🔴 **verschlechtert: war 27 moderate / 0 high** |
| `npx playwright test --list --project=chromium` | **44** Tests in **9** Dateien | gleich |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** B | 🟢 **20. identische Messung** |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 30/160) — Fenster **0 Commits**, `apps/web/src` unbewegt | 🟢 Lauf 84 hat sie selbst gefahren und bestätigt |
| Coverage | ⚪ **89,89 / 83,95 / 86,81 / 91,75** — **als übernommen gekennzeichnet**, Beleg: Baum bitgleich zu Lauf 84, der sie gefahren hat (282 Dateien / 2849 Tests) | — |
| 🔴 `main`-CI am Kopf `f89acf87` | 🔴 Lauf **`42178623925`**, **14 Jobs**, **2 rot** (`audit`, `all-green`) | 🔴 **unverändert rot, 12 Tage** |
| 🔴 `audit`-Job, Schritt 8 + 10 | 🔴 **beide `skipped` seit 12 Tagen** (s. §Fund) | 🔴 **neu benannt** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **61. Messung in Folge** |
| 🔴 `osv-scanner 2.2.4` (CI-gepinnt, SHA256 OK) | 🔴 **nicht lauffähig**: `api.osv.dev` egress-gesperrt, `scan_rc=127`, 700 Pakete erkannt, Filter geladen | **neu gemessen** |

🟢 **Zeichengleiche Baum-Gates sind an einem bitgleichen Baum die Erwartung,
kein Befund** (Regel 20/150). 🔴 **Die Ausnahme (Regel 45/181 —
advisory-gefütterte Gates jeden Lauf selbst fahren) hat zum zweiten Mal in
Folge den teuersten Fund geliefert:** `pip-audit` zeichengleich, `npm audit`
**von 27/0 auf 25/8**, beides am selben Baum.

### Offenlegung: ein eigener Messfehler

🔴 **Die Requirements-Zählung dieses Verfahrens war acht Läufe lang die
falsche Zahl.** Das Queue-Issue und die Läufe 81–84 führen „**398**
Requirements" als Beleg gegen den Leer-Export (Lauf 84 §Offenlegung). Gemessen:

```
wc -l            -> 398   (Zeilen der Datei, inkl. Kommentar-/`# via`-Zeilen)
grep -c '=='     -> 125   (tatsächliche Requirements)
distinct names   -> 124   (eine Doppelung: beartype, Marker-Split)
```

🔴 **„398" ist die Zeilenzahl, nicht die Zahl der geprüften Pakete** — derselbe
Fehlertyp wie Regel 67 (Zeiger am Vorkommen statt am Deklarationsort). Die
Wache funktioniert weiter (ein Leer-Export fällt bei 125 genauso auf wie bei
398), **aber sie wurde mit einer Zahl zitiert, die sie nicht misst** →
**Regel 71**. Hier korrigiert; die verbindliche Zahl ist **125** bei
**124** Namen.

Ein zweiter, derselben Art: die erste Sperren-Messung dieses Laufs lief über
**46** statt 47 PRs, weil die PR-Nummern-Liste ohne abschließenden Zeilenumbruch
geschrieben wurde und `while read` die letzte Zeile (**#1151**) verwarf.
🟢 **Gefangen von der Vollständigkeits-Gegenprobe, die Lauf 84 eingeführt hat**
(„Zahl der gemessenen PRs gegen Zahl der offenen PRs") — nachgeholt, jetzt
**47 von 47**. **Die Gegenprobe aus Lauf 84 hat sich am ersten Tag ihrer
Geltung bezahlt.**

---

## PR-Landschaft — 47 offen, Delta vollständig erklärt

Scope je PR über `git merge-base` + `git diff --name-only`, Konfliktfreiheit
über `git merge-tree --write-tree`, Rückstand über `git rev-list --count`.
**Alle 47 heute selbst gerechnet**, zusammen **50** bewegte Pfade.

- 🟢 **46 → 47, Differenz benannt: +#1151** (Protokoll Lauf 84, 2026-11-17).
  **Nichts gemergt, nichts geschlossen.**
- 🔴 **Seit dem 2026-11-06 ist kein PR gemergt — 12 Tage, zehntes leeres
  Fenster.**
- 🟢 **Alle 47 mergen konfliktfrei** (`rc 0`), **keiner bewegt 0 Dateien**.
- **Rückstand auf `main`:** **0** → 25 PRs · **10** → #1106, #1112, #1113,
  #1117, #1118, #1119, #1121, #1122 (8) · **15** → #1103, #1104, #1105, #1107
  (4) · **19** → #1089, #1090 · **33** → #1078 · **48** → #1056 · **73** →
  #1025 · **89** → #1002 · **114** → #990 · **237** → #831.
- 🔴 **Protokoll-Lage:** auf `main` liegen **15** (das unnumerierte vom
  2026-09-06 = Lauf 31, dann 43–55), **28** stecken in offenen PRs (#831=42,
  #990=56, #1002=57, #1025=58, #1056=59, #1078=60, #1089=61, #1090=62,
  #1103=64, #1104=65, #1105=66, #1107=67, #1112=68, #1113=69, #1117=70,
  #1118=71, #1119=72, #1121=73, #1125=74, #1126=75, #1137=77, #1138=78,
  #1139=79, #1140=80, #1143=81, #1144=82, #1145=83, **#1151=84**).
  🔴 **Zu Lauf 63 UND 76 existiert nirgends eines** (beide heute gegen `main`
  und gegen alle 47 PR-Dateilisten gemessen). Dieser Lauf legt das
  **neunundzwanzigste** Draft dazu.
- 🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02
  geschrieben** (`e39d05eb`) — **47 Tage**, dreifach von Protokoll-PRs gehalten
  (#1103 bei 15, #1090 bei 19, #1078 bei 33). **Wer ein Paket abschließt, nimmt
  #1103 als Basis.**

### Datei-Sperren — gegen alle 47 PRs, am vollen Pfad, Existenz zuerst belegt

| Pfad | Existenz | Träger |
|---|---|---|
| 🔴 `uv.lock` | belegt | **#1120, #1141, #1142, #1148** |
| 🔴 `apps/web/package.json` · `apps/web/package-lock.json` | belegt | **#674, #1124, #1129, #1130, #1147** |
| 🔴 `apps/web/osv-scanner.toml` | belegt | **#1124** |
| 🔴 `apps/api/Dockerfile` · `apps/mcp/Dockerfile` | belegt | **#1146** |
| 🔴 `.claude/context/STATE.md` | belegt | **#1078, #1090, #1103** |
| 🔴 `.github/PROJECT.md` | belegt | **#1105** |
| 🟢 `apps/web/src/**` · `apps/web/e2e/**` | belegt | 🟢 **KEIN** der 47 PRs |
| 🟢 `apps/api/src/**` · `packages/**` | belegt | 🟢 **FREI** |
| 🟢 `docs/mcp-payload-budget.md` · `apps/mcp/src/who2be_mcp/payload_report.py` · `apps/mcp/tests/test_tool_payload_budget.py` | je belegt | 🟢 **FREI** (die drei Hebel von #1001) |
| 🟢 die fünf `pyproject.toml` · `.github/dependabot.yml` | belegt | 🟢 **FREI** (die Fläche von #1150) |
| 🟢 `CLAUDE.md` · `.claude/context/ARCHITECTURE.md` | belegt | 🟢 **FREI** (die Fläche dieses Laufs) |

⚠️ **`apps/mcp/**` als Glob ist KEINE freie Fläche** — #1146 hält
`apps/mcp/Dockerfile`. Die Korrektur aus Lauf 84 gilt und ist hier am vollen
Pfad wiederholt; für #1001 ändert sie nichts.

🟢 **Gegenprobe, dass die Gruppen-PRs die Sicherheits-Bumps nicht
zurückdrehen:** #1148 (`python-minor-patch`, 11 Updates) bewegt **keines** der
vier CVE-Pakete — die Namen im `uv.lock`-Diff sind
`backports-tarfile`, `importlib-metadata`, `jaraco-*`, `jeepney`, `keyring`,
`more-itertools`, `pywin32-ctypes`, `secretstorage`, `zipp`. #1147
(`web-minor-patch`, 16 Updates) hebt `vite` **8.3.5 → 8.3.8**, `eslint`
**10.13.0 → 10.14.0**, `typescript-eslint` **8.72.1 → 8.72.2**, lässt
`picomatch` und `vitest` unberührt. **Welle 0 bleibt reihenfolge-frei.**

---

## Norm-Prüfung „Agent-ready Arbeitspaket"

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** ·
**prüfbare Akzeptanzkriterien** · **Out-of-Scope** · **exakte
Verifikations-Kommandos**. Die Norm-Resource selbst ist seit zwanzig Läufen
nicht lesbar (MCP), geprüft wird gegen diese vier Felder.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|
| **#632** | ✅ `### Fertig heißt` | ✅ **5** | ✅ `**Out:**` | ✅ Codeblock | 🟢 norm-vollständig |
| **#1001** | ✅ `## Fertig heißt` | ✅ **5** | ✅ `**Out of Scope:**` | ✅ Codeblock | 🟢 norm-vollständig |
| **#633** | ✅ `### Fertig heißt` | ⚠️ **6** | ✅ `**Out:**` | ✅ Codeblock | 🟢 norm-vollständig |
| **#989** | ✅ `## Fertig heißt` | ⚠️ **6** | ✅ `**Out of Scope:**` | ✅ Codeblock | 🟢 norm-vollständig |
| **#1150** | ✅ `## Fertig heißt` | ✅ **5** | ✅ `**Out of Scope:**` | ✅ Codeblock | 🟢 norm-vollständig, bewusst ohne `agent-ready` |

⚠️ **Die „6 AK"-Markierung bleibt kein belegter Verstoß**, solange **Weiche 55**
offen ist: die Spanne „2–5" hat im Repo keine Quelle (heute erneut gegengeprüft,
`grep -rn '2–5\|2-5\|bis 5' .github/PROJECT.md` → kein Treffer).
**Einundzwanzigster Lauf, in dem die einzige mögliche Quelle — die
AgentDB-Resource — nicht lesbar ist.** #633 führt den Punkt selbst als
Norm-Befund im Body.

**Die sieben übrigen** (#428, #435, #535, #540, #454, #542, #338) sind **nicht
neu an den Stellen gelesen**; ihr `updated_at` liegt sämtlich vor dem
Lesezeitpunkt von Lauf 84 (#540 2026-10-27, #535/#435 2026-10-17, #428
2026-10-15, #542/#454/#338 2026-10-12), ihre Bodies sind also byte-identisch zu
dem, was Lauf 84 gelesen hat. **Als übernommen gekennzeichnet.**

### 🟢 Die „Verbindliche Überschreibung" in #442 ist überholt — die Bodies sind längst korrigiert

#442 führt im Kopf: „**Alle vier offenen `agent-ready`-Bodies (#632, #1001,
#633, #989) tragen diesen Satz**" — den „einziger Fund `oauthlib`"-Satz aus
Lauf 81. 🟢 **Heute an allen fünf Bodies gelesen: sie tragen ihn nicht mehr.**
In #632, #1001 und #633 steht er je **einmal** als kursiver Korrekturvermerk
(„_Bis Lauf 82 stand hier …_, in Lauf 83 im Body korrigiert"), in #989 und
#1150 **überhaupt nicht**. Die lebende Fassung in allen Bodies ist die
Vier-Pakete-Liste plus „nennt er ein Paket, das **nicht** in dieser Liste
steht …". 🟢 **Lauf 83 hat die Korrektur also wirklich in die Bodies
geschrieben** — der Vollschrieb-Verzicht der Läufe 84/85 betrifft nur #442
selbst. **Die Überschreibung schadet nicht, aber sie beschreibt einen Zustand,
den es nicht mehr gibt** → erste Sichtung, kommentiert.

### 🔴 Was in den Bodies heute wirklich falsch ist — fünf Stellen, alle aus dem Welle-0-Text

| Fund | Wo | Lage |
|---|---|---|
| 🔴 **„398 Requirements"** | #632, #633, #1001, #989 (#989 zusätzlich „**400** Requirements") | **Zeilenzahl statt Paketzahl** — gemessen **125** Requirements / **124** Namen. Zweiter, unabhängiger Messweg zu Regel 71 |
| 🔴 **Welle-0-Schritt 4 als Lösung** (`uv lock --upgrade-package soupsieve`) | #632, #633, #1001, #989 | Durch **#1150** widerlegt: der Befehl **spaltet** `soupsieve` in `2.10` + `4.1.1`, und `2.10` trägt drei der vier CVEs; das grüne `pip-audit` ist ein Interpreter-Marker-Artefakt |
| 🔴 **„#1120 bringt `pip-audit` auf Exit 0"** | #632, #633, #1001 | Steht **im selben Body** neben der Korrektur „#1120 allein macht `audit` NICHT grün (Exit 1, 6 CVEs)" — ein Body, der sich selbst widerspricht (Regel 191) |
| ⚠️ **`soupsieve`-Fix-Version uneinheitlich** | „ab 4.0.0" (#632, #633, #1001) gegen „ab 2.10 / 4.x" (#989) | #1150 trägt die differenzierte Fassung: 2.10.0 für 126192, 3.0.2 für 126191/126193, **4.0.0** für 126190 |
| ⚠️ **npm-Zahl veraltet** | „28 moderate" (#632, #989), „27 moderate" (#1150) | Heute **25 moderate + 8 high**. **Keine der drei Zahlen ist heute richtig** — eine Advisory-Zahl im Body ist strukturell veraltet (Regel 176) |

🟢 **Kein Fund an den Zeigern, die frühere Läufe korrigiert haben:**
`:308` steht in #633 nicht mehr und in #632 nur als Korrekturvermerk (aktiv ist
`:309`); die Herkunftszeile `…aufbereitungslauf-76.md` ist aus #1001
verschwunden; die Fragment-Zahl **405** steht in #989 an **sechs** Stellen
jeweils richtig als Eigenzahl des Skripts, **406** nur als `wc -l`-Wert mit
benannter Differenz (`README.md`). **Die Korrekturen der Läufe 79–83 halten.**

🟢 **Die Ordinal-Angaben zum `audit`-Job sind heute gegengemessen und stimmen,
mit Zählweise:** `pip-audit` ist in der **Definition** der **4. von 9**
Schritten — `name:` auf **`ci.yml:974`**, `run:` auf **`:975`** (das löst die
scheinbare Abweichung zwischen #632/#633/#1001 mit `:974` und #989/#1150 mit
`:975` auf: **beide Zeiger sind richtig, sie zeigen auf verschiedene Zeilen
desselben Schritts**) — und in der **Runner-Numerierung** der **5. von 13**
Einträgen. Der OSV-Scan ist der **9. und letzte** der Definition und der
**10.** der Runner-Liste. **Alle vier Angaben am Job-Protokoll von Lauf
`42178623925` nachgezählt.**

⚠️ **#989 trägt `agent-ready` UND `needs-decision`** und sagt im Body „ohne
diese Antwort nicht starten". Das ist formal ein Widerspruch zweier Labels,
inhaltlich aber die richtige Lage und seit Läufen so geführt — **kein Fund,
sondern eine benannte Doppelmarkierung** (das Label sagt „norm-vollständig",
die Startbedingung sagt „nicht ohne Antwort"). **Bewusst nicht entzogen.**

⚠️ **Die Pflege-Fußzeilen von #632 (2026-11-13), #633 (2026-11-11) und #1001
(2026-11-09) sind älter als ihr eigener Inhalt** (die Vier-Pakete-Liste trägt
Messungen vom 2026-11-16). **Erste Sichtung, kommentiert.**

**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision`
vergeben, keines entzogen.** Begründung: die Pflichtfelder stehen in allen
vier startbaren Bodies, die bekannt schädliche Anweisung ist in #442
verbindlich überschrieben, und ein Entzug würde die zwei startbaren Pakete
stilllegen, ohne ein Risiko zu senken.

---

## Reihenfolge — unverändert, und das ist das Ergebnis

Kriterien in dieser Ordnung: **harte Abhängigkeit → Owner-Vorgabe → Fundament
vor Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.**

**#632 → #1001 → #633 → #989.**

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen (#435 W2a) | `size/S` | Web/Vitest | **3** Fundament vor Fläche (öffnet #633) | ✅ **startbar**, Fläche über alle 47 frei |
| **2** | **#1001** Payload-Budget, Rest ADR-0058 P4b | `size/S` | Python/pytest | **4** Inventar vor Zuschnitt | ✅ **startbar**, alle drei Hebel frei |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web/E2E | **1** harte Abhängigkeit | ⛔ **#632** + Container-Laufzeit (61. Messung) |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **1** + Owner | ⛔ **Weiche 48** + **fünf** Schreiber auf der Fläche |

**Im Fenster ist kein Issue geschlossen, keines der vier bewegt, keine Weiche
beantwortet, kein PR gemergt. Es gibt nichts, was eine Position verschieben
könnte — zum zehnten Mal.**

**Nicht in der Warteschlange:** #442 (ist die Liste) · #428/#435/#535
(Tracking-Epics) · #338/#454/#542 (`human-only`) · #540 (`needs-decision`,
Weiche 17) · **#1150** (`needs-decision`, Welle-0-/Owner-Arbeit) · die **47**
offenen PRs (ein PR ist kein Issue, Regel 34a/65a).

## Wellen — was gemeinsam startbar ist

Gemeinsam startbar ist, was **datei-disjunkt** ist und sich **nicht gegenseitig
blockiert**.

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🔴 **0** _(Owner, dringend)_ | **#1120 + #1141 + #1142 + #1150** | Die vier Schritte, die `pip-audit` grün machen. **Reihenfolge-frei**, Gegenprobe gegen #1148 gefahren. 🔴 **Neu und wichtig: sie machen den `audit`-Job NICHT automatisch grün** — sie entsperren Schritt 8 und 10 nach 12 Tagen Blindheit → **Weiche 56**. #1150 braucht zusätzlich die Options-Antwort A/B/C |
| 🟢 **A** | **#632 + #1001** | **Das echte Parallel-Paar:** Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle **47** PRs frei. ⚠️ Gemeinsame DoD-Fläche `STATE.md` (dreifach gehalten) — wer zweiter fertig wird, rebasiert auf **#1103** |
| **B** | **#633** | nach **#632** (hart) **und** Container-Laufzeit **oder** einem CI-Lauf mit **einzeln** gelesenen E2E-Job-Conclusions. 🔴 Billig wird dieser Weg erst, wenn `audit` wirklich grün ist — und das ist nach Welle 0 eine Messung, keine Zusage |
| **C** | **#989** | erst **Weiche 48**, dann die Fläche (fünf Schreiber: #674, #1124, #1129, #1130, #1147; #1124 gegenläufig auf `osv-scanner.toml`). 🔴 **Und ab heute mit Weiche 56 verschränkt:** wer `osv-scanner.toml` anfasst, entscheidet mit, ob picomatch dort einen Eintrag bekommt. **Ohne Antwort nicht starten** |
| **M** _(Owner)_ | Welle 0 → **#1124** → **#1148** → **#1133–#1136 / #1149** → **#1146** → Domain-Doku | #1149 fasst **5** Compose-Pfade an und überschneidet #1133–#1136 — nacheinander. #1148 nach Welle 0 neu messen. **#1106/#1122 nicht beide** → Weiche 49, **und einer von beiden muss kommen** (Betreiber-Host auf `main`) |
| **N** _(Owner)_ | **28 Protokoll-PRs** in beliebiger Reihenfolge | #1151, #1145, #1144, #1143, #1140, #1139, #1138, #1137, #1126, #1125, #1121, #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — je genau eine Datei außer #1105 (zwei). Danach **seriell** #1103 → #1090 → #1078 (`STATE.md`). 🟢 Einziger Weg, die Herkunftszeilen der Paket-Bodies wieder auf existierende Dateien zeigen zu lassen |
| **P** _(Owner)_ | **#1107, #1078, #831** durch Branch-Update heilen | Rückstand 15 / 33 / 237. #831 zusätzlich: grünes `all-green` aus einer CI-Definition **ohne `secrets`-Job**. **Erst nach Welle 0 neu messen** |
| **Q** _(Owner, entscheidbar)_ | **#674** | konfliktfrei, 0 hinter `main`, eigene Checks rot. **Empfehlung B (schließen)** |
| **R** _(Owner)_ | **#1129, #1130, #1147** | zwei Major plus Gruppen-PR, dieselbe Fläche wie #1124. **Nach #1124, einzeln und nacheinander** — #674 ist der Beleg, warum nicht als Gruppe |

🔴 **Mehr als zwei gleichzeitige Pakete gibt der Backlog nicht her** — vier
`agent-ready`, zwei davon blockiert. **Zum zehnten Mal unverschoben.**

---

## Was dieser Lauf selbst geändert hat

1. **`CLAUDE.md:185` und `.claude/context/ARCHITECTURE.md:9`:** „Vite 7" →
   **„Vite 8"**, belegt an `apps/web/package.json:77` (`^8.3.5`) und am
   Übergangs-Commit `9af60619` (2026-06-05). Beide Dateien über alle 47 PRs
   frei. **Repo-belegt, keine Urteilsfrage.**
2. **Dieses Protokoll** als neunundzwanzigstes Draft.
3. **Kommentar an #442** mit den Lauf-85-Zahlen, der Norm-Tabelle, der
   korrigierten Requirements-Zahl (**125**, nicht 398) und **Weiche 56**.

**Nicht geändert:** der Body von #442 (71.604 Zeichen, Vollschrieb-Risiko —
Weiche 44/53 unverändert offen, **fünfte Quittung**), kein Label, kein Issue
neu angelegt. 🟢 **Begründung für „kein neues Issue zu picomatch":** es gibt
heute **keine** Fix-Version, also kein zuschneidbares Arbeitspaket — nur eine
Weichen-Entscheidung. Ein Issue ohne möglichen Outcome wäre genau das, was
`.github/PROJECT.md` §Constraints verbietet.

## Neue Regeln aus diesem Lauf

70. **Ein Werkzeug-Vorschlag ist eine Fremd-Anweisung und wird wie ein Zeiger
    geprüft.** `npm audit` etikettiert als „fix" auch eine Herabsetzung
    (`fixAvailable: vitest 3.1.4, isSemVerMajor` bei installiertem 4.1.12);
    `npm audit fix --force` wäre hier **47 change / 132 remove** und zwei
    Majors zurück. **Vor dem Befolgen `--dry-run` fahren und `change`/`remove`
    zählen** (Regel 180), **und gegen die deklarierte Version im Repo lesen.**
71. **Eine Zahl, die als Wache zitiert wird, muss messen, was die Wache
    prüft.** „398 Requirements" war die **Zeilenzahl** des Exports; die Wache
    gegen den Leer-Export misst **125** Requirements bei **124** Namen.
    **Messweg: `grep -c '=='`, nicht `wc -l`** — Regel 67 auf eine
    Mengenangabe angewandt.
72. **Ein rotes Gate verdeckt nicht nur sein eigenes Urteil, sondern den
    Zustand aller Schritte nach ihm — und das über Wochen.** `npm audit` und
    der OSV-Scan sind seit 12 Tagen `skipped`; in genau diesem Fenster sind im
    Lockfile 8 `high`-Advisories entstanden. **„Das Gate wieder grün machen"
    ist deshalb keine Entsperrung, sondern die erste Messung seit dem Abbruch.**
