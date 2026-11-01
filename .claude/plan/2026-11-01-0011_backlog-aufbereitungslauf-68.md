# Backlog-Aufbereitungslauf 68

_2026-11-01, gegen `main` @ `af78ad7d` (Baum `498ded60`). Fenster seit Lauf 67
(`14234887`): **5 Commits**. Klon war shallow (50) → **1666** Commits nach
`--unshallow` (Regel 90)._

## Ausgangslage

Lauf 67 endete mit zwei roten Befunden: ein **latent rotes `main`**
(`pip-audit`: `joserfc 1.7.2`, `pypdf 6.21.2`, 9 Advisories) und **Weiche 39**
— ein PR (#1106), der die Betriebs-Hosts der laufenden Installation in eine
öffentliche Betreiber-Doku schrieb und gleichzeitig der einzige Träger des
Security-Fixes war. Beide sind in diesem Fenster bearbeitet worden, und zwar
**nicht** auf dem Weg, den Lauf 67 vorhergesagt hat.

## Das Fenster — der Owner hat gehandelt

Nach vier Läufen am bitgleichen Baum hat sich `main` um **5 Commits** bewegt:

| Commit | PR | Inhalt |
|---|---|---|
| `af78ad7d` | **#1111** | `pypdf 6.21.4` + `joserfc 1.7.7`, befristete OSV-Ignores für `glob`/`minimatch` |
| `65402517` | #1098 | Regressionstest Rechnungs-Schalter in den Cloud-Overlays |
| `524161ac` | #1102 | `tools-overview` im System-Prompt mit Werkzeug-Profil (ADR-0059 Q4) |
| `9b4da775` | **#1101** | Werkzeug-Profil im Policy-Filter, `whoami`-Cache 60 s (ADR-0059 Q3) |
| `f7e22454` | #1085 | Werkzeug-Profile verwalten und zuordnen (ADR-0059 Q2b) |

Dazu, ohne Commit auf `main`: **drei Branch-Updates** (#1106, #1100, #1063 —
alle drei jetzt **0** Commits hinter `main` und grün) und **ein
wiedereröffneter PR** (#1063, am 2026-10-23 geschlossen, am 2026-10-31 um
09:00 wieder offen).

🟢 **#1111 ist in diesem Fenster entstanden und sofort gemergt** — es kommt in
Lauf 67 nicht vor, weil es nach dessen Messpunkt angelegt wurde.

## Gates — ohne vorherige Reparatur (Regel 120), Exit-Codes ohne Pipe (Regel 94)

Node **v22.23.4**. `npm`-Gates in `apps/web/` (Regel 146).

| Gate | Ergebnis | gegen Lauf 67 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | 655 → **659** |
| `uv run pytest --collect-only -q` | **5033** Tests | 4971 → **5033** |
| `changelog_fragments.py check` | **Exit 0**, **404** Fragmente | 380 → **404** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, `de.json`/`en.json` je **3.365** Schlüssel, `orphan-baseline.json` **156** Einträge (158 Zeilen) | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** | gleich |
| `npm audit --audit-level=high` | **Exit 0** | gleich |
| `npm audit` (voll) | 🔴 **Exit 1**, **29 moderate** (`glob`, `minimatch`) | 🔴 **war Exit 0** |
| 🟢 `pip-audit` (CI-Job `audit`) | 🟢 **Exit 0**, „No known vulnerabilities found" | 🟢 **war Exit 1, 9 Advisories** |
| `payload_report` | **103** Werkzeuge / **108.251** Bytes, `instructions` **1.834** | Bytes gleich (**9.** Messung), `instructions` 1.732 → **1.834** |
| `pytest test_tool_payload_budget.py` | **Exit 0**, **64** Tests | neu gemessen |
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2849** Tests, **89,89 / 83,95 / 86,81 / 91,75**, **404,04 s** | **absolut bitgleich** |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **44. Messung in Folge** |

### 🟢 Das latente Rot ist geschlossen — Regel 80 greift nicht mehr

`pip-audit` am unveränderten `main`-Baum: **Exit 0**. `uv.lock` trägt
`joserfc 1.7.7` und `pypdf 6.21.4`. Der Fund, den Lauf 67 vier Läufe lang
nicht gesehen hat, ist **einen Lauf später erledigt** — und zwar durch #1111,
nicht durch #1106.

### 🟢 Die Coverage-Suite ist gefahren, obwohl der Baum sich bewegt hat — und ist bitgleich

Lauf 67 hat sie bewusst weggelassen (bitgleicher Baum, Determinismus bei n=3
belegt). Dieser Lauf hat sie gefahren, weil `main` sich um 5 Commits bewegt
hat — **und alle vier Absolutpaare sind identisch** (13163/14642,
9179/10933, 3793/4369, 12049/13132). 🟢 **Das ist kein Zufall, sondern ein
Beleg mit Grund:** die 5 Commits berühren vom Web-Teilbaum **nur**
`apps/web/osv-scanner.toml` — keine Zeile unter `apps/web/src/**`. **Eine
Bewegung auf `main` ist nicht automatisch eine Bewegung im geprüften
Teilbaum.** → **Regel 160.**

## Funde dieses Laufs

### 🔴 1. Die AK2 von #989 ist nicht nur verrottet, sie ist schädlich geworden

#989 verlangt wörtlich `grep -c "IgnoredVulns" apps/web/osv-scanner.toml` →
**0**. Auf `main` steht dort heute **2** — und zwar **zu Recht**: #1111 hat den
`http-cache-semantics`-Eintrag entfernt **und zwei neue befristete Ausnahmen
angelegt** (`GHSA-3g3m-2fjr-6pw4` für `glob@13.0.6`, `GHSA-g3hv-75wg-m249` für
`minimatch`, beide `ignoreUntil = 2026-11-30`, beide dev-only).

🔴 **Ein Agent mit leerem Kontext, der AK2 wörtlich erfüllt, löscht einen
funktionierenden Security-Filter und macht `osv-scanner` rot.** Das ist nicht
ein veralteter Zeiger, das ist eine Anweisung, die Schaden anrichtet. Die
Norm-Prüfung nach Regel 151 fragt „ist der Zeiger gültig?" — sie fragt nicht
„richtet die Anweisung Schaden an, wenn sie gültig befolgt wird?".
→ **Regel 161.**

🟢 **Zwei Teile von AK2 sind durch #1111 ohne dieses Paket erfüllt:**
`grep -c GHSA-ch52-4w7c-c8xp` → **0**, und „*has no fixed release yet*" ist mit
dem Block verschwunden. 🔴 **Einer ist offen:** „*turns red again*" steht
weiter in `osv-scanner.toml:6`.

### 🔴 2. Zwei Changelog-Fragmente widersprechen sich, beide unveröffentlicht

- `changelog.d/osv-ignore-http-cache-semantics.security.md:1-3` sagt, die
  Ausnahme sei „*recorded in `apps/web/osv-scanner.toml` and valid until
  2026-11-02*".
- `changelog.d/osv-ignore-glob-minimatch.security.md:6-7` sagt, dieselbe
  Ausnahme „*was removed because the scan no longer uses it*".

Beide liegen in `changelog.d/` und gehen damit **in dieselben Release Notes**.
Der `changelog-guard` ist **Exit 0** — er prüft Form und Typ, nicht
Widerspruchsfreiheit. #1111 hat den Eintrag entfernt und das Fragment dazu
stehen gelassen. → in den Scope von #989 geschrieben.

### 🔴 3. Die Befehlszeile von Regel 159 läuft nicht

Regel 159 wurde in Lauf 67 eingeführt, damit ein advisory-gefüttertes Gate
nicht mehr aus Check-Runs abgelesen wird. Ihr hinterlegter Befehl ist

```
uv export --format requirements-txt --no-emit-workspace --no-hashes --group billing | uv tool run pip-audit --disable-pip --no-deps -r -
```

🔴 **Er scheitert:** `ERROR:pip_audit._cli:invalid requirements input: -` —
`pip-audit` liest die Requirements mit `-r -` nicht von stdin. Gemessen wurde
deshalb über eine Datei:

```bash
uv export --format requirements-txt --no-emit-workspace --no-hashes --group billing > /tmp/req.txt
uv tool run pip-audit --disable-pip --no-deps -r /tmp/req.txt ; echo "EXIT=$?"
```

🔴 **Und das ist die unangenehme Hälfte:** ein scheiternder Befehl liefert
Exit ≠ 0 und sieht damit aus wie ein **roter Gate**, nicht wie ein kaputter
Messweg. Eine Regel, die ein ungemessenes Gate verhindern sollte, hätte in
diesem Lauf ein Rot erfunden, das es nicht gibt. → **Regel 162**: ein neu
eingeführter Messbefehl wird im Lauf seiner Einführung **einmal ausgeführt**,
nicht nur aufgeschrieben.

### 🟢 4. Weiche 39 ist zu zwei Dritteln durch Handeln beantwortet — ein Satz bleibt

Lauf 67 fand in #1106 **zwei** Zeilen (`:622`/`:623`) mit den Betriebs-Hosts
und empfahl **Option A** (auf `<DOMAIN>` ziehen). Am Head von heute
(`45714abe`, **0** Commits hinter `main`, grün, konfliktfrei):

| Messung | Lauf 67 | **2026-11-01** |
|---|---|---|
| `<DOMAIN>`-Platzhalter in der Datei | 43 | **54** |
| Datei-Länge | — | **1021** Zeilen |
| echte Hosts (URL-Form) | 2 Betriebs-Zeilen | **nur** `api.mollie.com` (3×), `supabase.example.com`, `github.com` |
| bloße Hostnamen, nicht Platzhalter | — | 🔴 **einer, 1×, an `:627`** |

🔴 **Die verbleibende Zeile an `:627`** setzt die `DOMAIN`-Variable auf den
**konkreten Wert** der laufenden Installation und zählt dahinter die vier
Subdomains auf. **Eine davon ist die MCP-Subdomain, die auf `main` 0× vorkommt**
(gemessen mit `git grep -l <host> origin/main` → **0** Dateien; der Host selbst
wird hier bewusst nicht wiedergegeben — CLAUDE.md §Security gilt auch für
Plan-Dateien unter `.claude/`). Die Basis-Domain steht auf `main` in **38**
Dateien, aber in den Kategorien, die Lauf 67 zu Recht als „kein Betriebs-Host"
eingeordnet hat (Fehler-Typ-URI, Beispiel-Mailadresse, alte Plan-Dateien).

🟢 **Die Kopplung ist weg, und das ändert die Lage grundlegend.** Lauf 67
schrieb, **A** sei „nicht nur die saubere, sondern **die entsperrende**
Option", weil #1106 der einzige Träger des Security-Fixes war. #1111 hat diesen
Fix unabhängig gelandet. **#1106 trägt jetzt kein Gate mehr — es gibt keine
Frist und keinen Tausch.** Es bleibt eine Hygiene-Frage mit einer
Irreversibilität (der Merge). → Weiche 39, neu gefasst, als Kommentar an #1106.

### 🟢 5. #1001 ist entsperrt — das Parallel-Paar ist zurück

**#1101 ist gemergt.** Damit ist die Datei-Sperre, die #1001 seit Lauf 64 zum
Wartestand gemacht hat, aufgehoben. Gegen die Dateilisten **aller 25** offenen
PRs gemessen:

| Fläche von #1001 | Träger |
|---|---|
| `docs/mcp-payload-budget.md` | 🟢 **FREI** |
| `apps/mcp/src/who2be_mcp/payload_report.py` | 🟢 **FREI** |
| `apps/mcp/tests/test_tool_payload_budget.py` | 🟢 **FREI** |

⚠️ **Fehlalarm, von Hand abgewendet** (Regel 10/157): ein Grep auf
`mcp-payload-budget` trifft in #1106 — aber auf
`.claude/plan/2026-09-26-2030_mcp-payload-budget-inventar.md`, eine **Plan**-Datei
ähnlichen Namens. `docs/mcp-payload-budget.md` hält kein offener PR.
→ **Regel 163**: eine Datei-Sperre wird am vollen Pfad geprüft, nicht am
Namensfragment.

**Und #1001 ist kleiner geworden, wie Lauf 64 vorhergesagt hat:**

| AK | Stand auf `main` @ `af78ad7d` |
|---|---|
| **1** Referenzprofil-Tabelle aus eigenem Lauf | 🟢 **erfüllt durch #1101.** `:260-265` trägt `38/31.131`, `42/34.683`, **`103/108.251`**, `86/92.384`, `99/104.699`, `103/108.251` — **zeichengleich mit dem `payload_report`-Lauf dieses Laufs**. Kopf `:254` nennt ein Datum, **keinen Commit** |
| **2** genau ein gültiger Stand | 🔴 **zwei Zeilen offen:** `:327` („*zusammen 1.638 Bytes im Gesamtkatalog (104.777 -> 106.415)*") und `:487` (Vergleichstabelle „**101 / 104.777 (−9.426)**"). 🟢 `:233` und `:292` sind **datiert** und damit AK2-konform |
| **3** `71.738` → 0 Treffer | 🔴 **unberührt, 2×:** `:236` und **`:335`**. Korrekt ist **71.749** (180.000 − 108.251) |
| **4** Historien-Zeile für heute | 🔴 **unberührt.** Tabelle endet `:234` mit `2026-10-23 … 103 … 108.262` |
| **5** Gates Exit 0 | 🟢 neu gemessen: Budget-Test **64 passed, Exit 0**; Fragmente **404**; Collection **5033** |

🔴 **Weiche 35 ist durch den Merge beantwortet, nicht durch eine
Entscheidung.** Ihre Empfehlung **B** lautete „Restzeilen als
Review-Kommentar an #1101". **#1101 ist gemergt — B ist mechanisch nicht mehr
verfügbar.** Der Rest muss eine eigene Änderung werden, also **A**.

### 🟢 6. Weiche 36 ist durch Messung korrigiert — ein Branch-Update genügt wieder

Lauf 67 trug einen Nachtrag: „*ein Branch-Update genügt nicht mehr … diese PRs
werden erst durch den Sprung aus #1106 grün*". **Das gilt nicht mehr**, und
zwar belegt am Log, nicht geschlossen:

Der `audit`-Job von **#1108** (Head `4b2d95dc`, Job `124452890861`,
2026-10-31T05:23:17Z) nennt wörtlich

```
Found 9 known vulnerabilities in 2 packages
joserfc 1.7.2   CVE-2026-119283 / CVE-2026-119284
pypdf   6.21.2  CVE-2026-119203 … CVE-2026-119209
```

🟢 **Genau der Stand, den `main` seit `af78ad7d` nicht mehr trägt.** Alle vier
PRs, die nur an `audit` + `all-green` rot sind (#1107, #1108, #1080, #1078),
werden durch ein Branch-Update grün. #831 zusätzlich gate-alt.

### 🔴 7. #1108 ist neu rot — auf einer Welle, die `main` schon geschlossen hat

Der Dependabot-PR `pillow 12.3.0 → 13.0.0` (angelegt 2026-10-31T05:22) ist rot,
ohne etwas falsch zu machen: sein Merge-Base liegt **5** Commits vor `af78ad7d`
und damit vor dem Fix. **Ein Branch-Update genügt.**

### ⚠️ 8. `npm audit` voll ist neu Exit 1 — und das ist erwartet, kein Fund

**29 moderate**, ausschließlich `glob` (`GHSA-3g3m-2fjr-6pw4`) und `minimatch`
(`GHSA-g3hv-75wg-m249`) — **genau die zwei Advisories, für die #1111 die
befristeten OSV-Ignores angelegt hat.** `--omit=dev --audit-level=high` bleibt
**Exit 0**: das ausgelieferte Bundle ist unberührt. 🟢 **`http-cache-semantics`
kommt in der Ausgabe gar nicht mehr vor** — die Rücknahme des Advisories, die
Lauf 65/66 über den Bulk-Endpunkt belegt haben, ist jetzt am lokalen Gate
sichtbar.

⚠️ **Die neuen Ignores laufen am 2026-11-30 ab.** Das ist eine echte Frist mit
Folge (anders als die alte): für `glob`/`minimatch` gibt es laufende Advisories,
der Fix liegt nur in neuen Majors, die kein Parent akzeptiert. **Nicht dieses
Lauf-Thema, aber vorzumerken.**

### 🔴 9. Der Protokoll-Rückstand ist auf 12 gewachsen, Lauf 63 fehlt weiter

Offen: #1107 (67), #1105 (66), #1104 (65), #1103 (64), #1090 (62), #1089 (61),
#1078 (60), #1056 (59), #1025 (58), #1002 (57), #990 (56), #831 (42) —
**zwölf**; dieser Lauf legt das **dreizehnte** dazu. **Zu Lauf 63 existiert
weiter kein Protokoll** (`git log --all` → 0, `.claude/plan/` → 0,
`search/issues` → 0 passende). Auf `main` liegen **15** Protokoll-Dateien,
jüngste `2026-10-19-0030_backlog-aufbereitungslauf-55.md`.

🔴 **`.claude/context/STATE.md` ist auf `main` auf den 2026-10-02 datiert —
30 Tage**, letzter Commit `e39d05eb` (#783). Sie wird von **drei** offenen
Protokoll-PRs gehalten (#1103, #1090, #1078). **Wer ein Paket abschließt, nimmt
#1103 als Basis** (grün, 5 dahinter).

## PR-Bestand — 25 offen _(waren 26)_

Scope je PR über `git merge-base` + `git diff --name-only`, Konfliktfreiheit
über `git merge-tree --write-tree`, CI über die Check-Runs am Head.

- 🟢 **Alle 25 mergen konfliktfrei** (rc 0).
- 🟢 **Grün und 0 Commits dahinter — sofort mergebar: #1106, #1100, #1063.**
  Alle drei hat der Owner in diesem Fenster aktualisiert.
- 🟢 **Grün bei 5 dahinter:** #1105, #1104, #1103.
- 🟢 **Grün bei 9 dahinter:** #1097, #1096, #1095, #1094, #1093, #1092, #1091, #1090, #1089.
- 🟢 **Grün, aber weit hinten und gate-alt:** #1056 (**38**), #1025 (**63**), #1002 (**79**), #990 (**104**).
- 🔴 **Rot, nur an `audit` + `all-green`:** #1107 (5), **#1108 (5, neu)**, #1080 (23), #1078 (23) — **alle vier durch Branch-Update heilbar** (Fund 6).
- 🔴 **Rot und gate-alt:** #831 (227).
- 🔴 **Rot aus eigener Sache:** #674 — **8** Checks (`web`, `e2e`, `e2e-mobile`×3, `compose-smoke`, `e2e-billing-cloud`, `all-green`), **kein** `ci.yml`-Drift. Der Vitest-5-Sprung selbst (Weiche 12).
- 🔴 **Gemergt im Fenster: 5** (#1111, #1098, #1102, #1101, #1085). Gestartet: **0**.

### Gate-alt an der richtigen Variable (Regel 158)

`git diff --name-only <merge-base> main -- .github/workflows/ci.yml`:

| PR | Rückstand | `ci.yml` bewegt? | Gate-alt? |
|---|---:|---|---|
| #1106, #1100, #1063 | 0 | nein | 🟢 nein |
| #1107, #1108, #1105, #1104, #1103 | 5 | nein | 🟢 nein |
| #1089–#1097, #674 | 9 | nein | 🟢 nein |
| **#1080**, **#1078** | **23** | **nein** | 🟢 **nein — trotz 23 Commits** |
| **#1056** | 38 | **ja** | 🔴 **ja** |
| **#1025** | 63 | **ja** | 🔴 **ja** |
| **#1002** | 79 | **ja** | 🔴 **ja** |
| **#990** | 104 | **ja** | 🔴 **ja** |
| **#831** | 227 | **ja** | 🔴 **ja** |

🟢 **Die Kante ist mitgewandert, der Befund hält:** Lauf 67 fand sie zwischen
18 und 33 Commits, dieser Lauf zwischen **23 und 38**. **Der Abstand ist
weiter nicht das Kriterium**, und alle fünf gate-alten sind **Protokoll-PRs**.

### Datei-Sperren — gegen alle 25 PRs

| Datei | Träger |
|---|---|
| `uv.lock` | ⚠️ **#1108**, **#1093**, **#1080** — dreifach |
| 🔴 `.claude/context/STATE.md` | 🔴 **#1103** (grün, 5), **#1090** (grün, 9), **#1078** (rot, 23) — **dreifach, alle drei Protokolle** |
| `deploy/monitor/compose.yml` | ⚠️ **#1097**, **#1094** — disjunkte Hunks |
| `apps/web/package.json` · `apps/web/package-lock.json` | ⚠️ **#1092** (grün, 9) und **#674** (rot, 9) |
| `.github/workflows/ci.yml` | 🔴 **#1091** |
| 🟢 `apps/web/osv-scanner.toml` | 🟢 **FREI** |
| 🟢 `docs/mcp-payload-budget.md` · `payload_report.py` · `test_tool_payload_budget.py` | 🟢 **FREI** _(#1101 gemergt)_ |
| 🟢 `features/settings/**` · `i18n/locales/{de,en}.json` · `orphan-baseline.json` | 🟢 **FREI** |
| 🟢 `e2e/helpers/auth.ts` · `LoginPage.tsx` · `SessionProvider.tsx` · `src/api/**` | 🟢 **FREI** |
| 🟢 `deploy/hetzner/Caddyfile` | 🟢 **FREI** |

## Norm-Prüfung „Agent-ready Arbeitspaket"

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** ·
**prüfbare Akzeptanzkriterien** · **Out-of-Scope** · **exakte
Verifikations-Kommandos**. Jeder maschinelle Negativ-Befund von Hand
gegengelesen (Regel 10) — **zwei Fehlalarme der eigenen Regex** (`**Out of
Scope:**` mit Doppelpunkt matchte nicht) an #1001 und #989 abgewendet.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger gültig? | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ | ✅ | ✅ `**Out:**` | ✅ | 🟢 **ja — 13 von 13 nachgemessen, null verrottet** | 🟢 **vollständig und gültig** |
| **#633** | ✅ | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 **ja** — 399 / 267 / 199, `ci.yml` `:463`/`:544` wörtlich | 🟢 **vollständig und gültig** |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🔴 **fünf verrottet** (Datei 573 → **609** Zeilen) | ⚠️ **korrigiert in diesem Lauf** |
| **#989** | ✅ | ✅ 5 | ✅ | ✅ | 🔴 **AK2 schädlich, 1 Zeiger verrottet** | 🔴 **korrigiert in diesem Lauf** |

**#632 — alle 13 Zeiger am 2026-11-01 gegen `main` nachgemessen:**
`MfaSection.tsx` **297** · `src/auth/SessionProvider.tsx` **267** ·
`src/i18n/audit.test.ts` **371** · `LoginPage.tsx` **399** ·
`apps/web/package.json` **82** · `vite.config.ts` **107**, Schwellen
**`:100-103`** · `e2e/helpers/auth.ts` **199** · `src/api/client.ts` **1849** ·
`src/api/types.ts` **2407** · `ci.yml` **1259** · `orphan-baseline.json`
**156** Einträge · `src/test/a11y.test.ts` **77** · `de.json`/`en.json` je
**3.365**.

🟢 **Zweiter Lauf in Folge ohne verrotteten Zeiger in #632/#633** — und
diesmal an einem Baum, der sich bewegt hat.

**Verrottete Zeiger in #1001, in diesem Lauf korrigiert:**
Referenzprofil-Tabelle `:258-263` → **`:260-265`** · Kopf `:254` → **gültig** ·
Rest-Rechnung `:236`,`:299` → **`:236`,`:335`** · P3-Vergleichstabelle `:451` →
**`:487`** · Historien-Zeile `:235` → **`:234`** · AK2-Rest `:262`,`:264`,`:317`
→ **`:327`,`:487`**.

**Norm-Stand der acht übrigen Bodies — am 2026-11-01 unverändert:** Scope-„In"
fehlt in #542, #540, #535, #454, #428, #338 · Verifikations-Abschnitt fehlt in
#535, #428 · #454 hat ihn, sagt dort „Kein Testkommando" · #338 trägt keine
Abschnitts-Überschriften. **Bewusst nicht umgebaut** (Regel 7, Weiche 4):
#542/#454/#338 sind `human-only`, #535/#428/#435 sind `size/M` und werden laut
Constraint **nie** durch Nachtragen von Feldern startbar.

## Reihenfolge

Sortierkriterien (`.github/PROJECT.md`): harte Abhängigkeit → Owner-Vorgabe →
Fundament vor Fläche → Inventar vor Zuschnitt → bei Gleichstand das kleinere.

🟢 **Regel 80 greift nicht mehr** — `main` ist gemessen grün (`pip-audit`
Exit 0). Der erste Posten ist deshalb wieder ein Paket, keine Owner-Antwort.

| Pos | Issue | Größe | Baum | Kriterium | Lage |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren/entfernen | `size/S` | **Web** | **3** Fundament vor Fläche (öffnet #633) | 🟢 **startbar, ohne Nebenbedingung.** Fläche über alle 25 PRs frei, 13/13 Zeiger gültig |
| **2** | **#1001** Payload-Budget, Rest von ADR-0058 P4b | `size/S` | **Python** | **4** Inventar vor Zuschnitt | 🟢 **neu startbar** (#1101 gemergt), Fläche dreifach frei, AK1 bereits erfüllt, Rest = AK2 (2 Zeilen) + AK3 + AK4. ⚠️ Weiche 35 ist durch den Merge auf **A** reduziert |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web | **1** harte Abhängigkeit nach #632 | ⚠️ Zusätzlich Container-Laufzeit (`docker info` Exit 1, **44.**) **oder** ein CI-Lauf |
| **4** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **5** bei Gleichstand das kleinere | ⚠️ **Body in diesem Lauf korrigiert**, AK2 entschärft. Lockfile-Sperre #1092/#674. 🔴 **Offene Weiche 40** (Zuschnitt) |

## Wellen

**Regel:** gemeinsam startbar ist, was **datei-disjunkt** ist **und** sich nicht
blockiert **und** in **verschiedenen Verifikations-Bäumen** liegt (`pytest`
sammelt den ganzen Python-Baum, Vitest den ganzen Web-Baum).

| Welle | Pakete | Bäume | Disjunktheit |
|---|---|---|---|
| 🟢 **A — jetzt, parallel** | **#632 ‖ #1001** | **Web ‖ Python** | ✅ `features/settings/**`, `i18n/locales/**`, `orphan-baseline.json` gegen `docs/mcp-payload-budget.md` — **vollständig disjunkt, zwei verschiedene Suiten** |
| **B — nach A** | **#633** | Web | hart nach #632; nicht parallel zu C (gleicher Vitest-Baum) |
| **C — nach B** | **#989** | Web | gleicher Vitest-Baum wie A/B; zusätzlich #1092 mergen |
| **D — parallel, kein Paket** | **Merges** | — | Klicks, kein Agent |

🟢 **Das Parallel-Paar ist zurück, und zwar genau so, wie Lauf 67 es
vorhergesagt hat:** „Welle E ist das Parallel-Paar, das ein einziger Merge
zurückbringt". Der Merge war #1101. **Vier Läufe ohne Parallel-Paar sind
beendet.**

### Welle D im Einzelnen — die billigste Merge-Reihenfolge

1. 🟢 **#1100** — grün, **0** dahinter. Billigster Merge des Backlogs, keine Sperre.
2. 🟢 **#1063** — grün, **0** dahinter. In diesem Fenster wiedereröffnet.
3. ⚠️ **#1106** — grün, **0** dahinter, konfliktfrei. 🔴 **Erst Weiche 39 (`:627`), dann mergen.** Keine Frist mehr.
4. **#1103** — grün, 5 dahinter. **Höchste Hebelwirkung auf die DoD:** jüngster `STATE.md`-Stand, nimmt den ersten der drei Träger aus der Sperre.
5. **#1105**, **#1104** — grün, 5 dahinter.
6. **#1092** — grün, 9 dahinter. **Räumt die halbe Lockfile-Sperre vor Position 4.**
7. **#1091** — grün, 9 dahinter. **Gibt `ci.yml` frei** (#540 / Weiche 17; danach `:463`/`:544` in #633 neu messen, Regel 98).
8. **#1093–#1097**, **#1089**, **#1090** — grün, 9 dahinter. **#1090 ist der zweite `STATE.md`-Träger.**
9. 🟢 **#1107**, **#1108**, **#1080**, **#1078** — **erst Branch-Update, dann grün** (Fund 6, am Log belegt). **#1078 ist der dritte `STATE.md`-Träger.**
10. **#1056**, **#1025**, **#1002**, **#990** — grün, aber 38/63/79/104 dahinter und **gate-alt**: Branch-Update vor dem Merge.
11. **#831** — rot, 227 dahinter, gate-alt.
12. **#674** — Weiche 12. Rot bei 9 dahinter, vorher rot bei 0 — ein Branch-Update löst es nicht.

## Offene Weichen — neu und geändert

| Weiche | Stand 2026-11-01 |
|---|---|
| 🆕 **40. Behält #989 einen Platz im Backlog, nachdem #1111 die Hälfte erledigt hat?** Empfehlung **B** | Als Kommentar an #989, drei Optionen. Der Sicherheitswert ist **0** (Advisory zurückgezogen, am lokalen Gate belegt); was bleibt, ist Hygiene |
| 🔄 **39. Betriebs-Hosts in öffentlicher Doku** Empfehlung **A** | 🟢 **Zu zwei Dritteln eingelöst.** Ein Satz bleibt (`:627`). 🟢 **Die Kopplung an das Security-Gate ist weg** (#1111). Neu gefasst als Kommentar an #1106 |
| 🟢 **35. Was passiert mit #1001 nach #1101?** → **beantwortet** | **Durch den Merge, nicht durch Entscheidung.** B („Review-Kommentar an #1101") ist mechanisch weg. **A gilt.** In #1001 geschrieben |
| 🟢 **36. Wer aktualisiert einen PR, dessen Rot nur Rückstand ist?** Empfehlung **A** | 🟢 **Der Nachtrag aus Lauf 67 ist zurückgenommen:** ein Branch-Update genügt wieder, am `audit`-Log von #1108 belegt. Betrifft #1107, #1108, #1080, #1078 |
| 🟢 **80 / latentes Rot** → **erledigt** | `pip-audit` Exit 0 am unveränderten `main`-Baum |
| 🆕 **41. Wird die Befehlszeile von Regel 159 korrigiert?** Empfehlung **C** | Der hinterlegte Befehl scheitert (Fund 3). Als Kommentar an #442 |
| 🔴 **18. Kadenz des Laufs** Empfehlung **C** | 🔴 **Rückstand 12, Lauf 63 fehlt ganz, drei halten `STATE.md`, alle fünf gate-alten sind Protokolle.** 🟢 **Aber: der Owner hat in diesem Fenster gehandelt** (5 Merges, 3 Branch-Updates) — der Stau ist nicht mehr total |
| 🔴 **2. Darf ein gate-alter PR mergen?** Empfehlung **B** | Unverändert fünf Fälle; Kante von 18–33 auf **23–38** gewandert |
| 🔴 **34. Dependabot-PRs bündeln?** Empfehlung **B** | #1091–#1097 alle grün bei 9 dahinter, keiner gemergt; **#1108 neu dazu, rot aus Rückstand** |
| 🔴 **12. #674 (Vitest 5)** Empfehlung **C** | Unverändert: 8 Checks rot, kein `ci.yml`-Drift |
| 🔴 **5. Bleibt `audit` im Required Check?** Empfehlung **A**/**C** | 🔴 **Die zweite Hälfte schadet weiter:** der Abbruch beim ersten Fund verbirgt an fünf PRs die npm-Hälfte |
| **8.** ESLint-Warnungen | 94, unverändert, 0 errors, 7 `--fix`-bar |
| **6.** Coverage-Boden | n = **17**; engster Abstand **4,95** Punkte (Branches 83,95 gegen Boden 79). Schwellen `vite.config.ts:100-103` |
| **9.** MB/MiB-Zeile | Unverändert der billigste offene Posten |
| 🔴 **15.** Valkey-Ignore sichtbar machen | Unverändert |
| 🔴 **17.** Wie wird #540 geschlossen? | Doppelt blockiert: `ci.yml` von #1091, `docker info` Exit 1 (**44.**) |
| 🔴 **23.** Kein PR nennt ein Issue | Unverändert, auch #1106/#1108 nicht |
| 🔴 **30.** Weichen-Antwort in die ADR | Unverändert: `docs/adr/0061-*.md` führt W61-1/-2/-3 als offen |
| 🔴 **31.** Schneidet der Lauf noch Issues? Empfehlung **B** | Erneut keines geschnitten; die Gegenmaßnahme aus B hat in diesem Lauf Fund 1 und Fund 5 geliefert. **Sechster belegter Nutzen** |
| 🔴 **38.** Historischer Kopfblock in `agent-ready`-Bodies Empfehlung **C** | Unverändert ⚠️; die axe-Gegenbeispiele stehen weiter als ausdrücklich falsch markiert da (Regel 157 hält) |
| **4.** Gilt der Vertrag für Tracking-Issues? Empfehlung **B** | Unverändert |
| **#542** Rechnungsmodell/USt. `human-only` | Unverändert fällig |

## Neue Regeln

- **160.** Eine Bewegung auf `main` ist nicht automatisch eine Bewegung im
  geprüften Teilbaum. Vor dem Fahren einer teuren Suite wird gemessen, ob das
  Fenster ihren Teilbaum **überhaupt** berührt (`git diff --name-only A B --
  <pfad>`); berührt es ihn nicht, ist ein identisches Ergebnis **erwartet** und
  taugt als Determinismus-Beleg, nicht als Überraschung.
- **161.** Die Norm prüft Anwesenheit (Regel 151 ergänzt: und Gültigkeit) — sie
  prüft **nicht**, ob eine gültige Anweisung Schaden anrichtet. Ein AK, das
  einen Zustand auf `0` zwingt, wird gegen den **heutigen** Inhalt der Datei
  gelesen: ist dort inzwischen etwas Legitimes dazugekommen, ist das AK nicht
  veraltet, sondern **schädlich**.
- **162.** Ein neu eingeführter Messbefehl wird im Lauf seiner Einführung
  **einmal ausgeführt**, nicht nur aufgeschrieben. Ein kaputter Messbefehl
  liefert Exit ≠ 0 und ist von einem roten Gate nicht unterscheidbar.
- **163.** Eine Datei-Sperre wird am **vollen Pfad** geprüft, nicht am
  Namensfragment. `.claude/plan/…-mcp-payload-budget-inventar.md` ist nicht
  `docs/mcp-payload-budget.md`.

## Was dieser Lauf geschrieben hat

- **#989** — Body korrigiert: AK2 entschärft (der schädliche Teil), AK2b/AK2d
  als durch #1111 erfüllt markiert, AK1-Zeiger `:6296` → `:6295`, AK3 als
  erfüllt belegt, das widersprüchliche Changelog-Fragment in den Scope
  aufgenommen, AK5-Bezugswerte neu gemessen.
- **#1001** — Body korrigiert: Wartestand aufgehoben, fünf Zeiger nachgezogen,
  AK1 als erfüllt markiert, AK2-Rest auf `:327`/`:487` präzisiert, AK3 auf
  `:236`/`:335`, Weiche 35 als durch den Merge beantwortet festgehalten.
- **#442** — Warteschlange, Wellen, Gates, Funde, Regeln 160–163.
- **Kommentare mit drei Optionen:** #989 (Weiche 40), #1106 (Weiche 39 neu
  gefasst), #442 (Weiche 41).

---
_Aufbereitungslauf 68, 2026-11-01, gegen `main` @ `af78ad7d` (Baum `498ded60`,
Fenster 5 Commits). Alle Zahlen am genannten Datum gegen den genannten Commit
gemessen, nicht fortgeschrieben._
