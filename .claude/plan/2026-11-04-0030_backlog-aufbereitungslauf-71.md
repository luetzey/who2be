# Backlog-Aufbereitungslauf 71

**Datum:** 2026-11-04
**Messpunkt:** `main` @ `af78ad7d` (Baum `498ded60`), `deps(security): pypdf 6.21.4 + joserfc 1.7.7 …` (#1111)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — **viertes bitgleiches Fenster in Folge**;
`main` steht seit dem 2026-10-31T10:16+01:00 still.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.
**Offene PRs:** **28** (waren 27).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und
in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar.** Der Server steht in dieser
Session als autorisierungsbedürftig; `ToolSearch` liefert keine seiner Werkzeuge. Persona und
Playbook-Katalog lagen im System-Prompt vor, die Bodies der Playbooks und die Norm-Resource
„Agent-ready Arbeitspaket" nicht — ebenso nicht `get_persona`, `list_triggers`,
`fetch_playbook`, `fetch_resource`, `record_usage`, `submit_feedback`, `search_memory`.
Der Lauf fährt deshalb nach `.github/PROJECT.md` §Constraints (dort stehen die vier
Pflichtabschnitte wörtlich) und nach dem Body von #442. **Keine Kurations-Rückmeldung an die
AgentDB möglich** — `record_usage`/`submit_feedback` sind nicht erreichbar.

⚠️ **Der `gh`-Schreibweg stand diesem Lauf nicht offen.** Die Werkzeug-Regeln dieser Session
lassen `gh` ausdrücklich **nur für Suche** zu. Weiche 44 (Freigabe von `gh api -X PATCH
--input` für Issue-Bodies) ist damit in diesem Lauf nicht nur unbeantwortet, sondern
**praktisch versperrt**: Body-Schreibvorgänge dieses Laufs gingen über MCP `issue_write`.
Das ist zugleich eine Gegenprobe auf Regel 169 — s. §Funde.

## Gates — ohne vorherige Reparatur (Regel 120), Exit-Codes ohne Pipe (Regel 94)

Node **v22.23.4**. Klon war shallow (50) → **1666** Commits nach `--unshallow` (Regel 90).
`npm`-Gates in `apps/web/`, Python-Gates im Repo-Root, jede sequenziell mit `pwd`-Beleg
(Regel 164).

| Gate | Ergebnis | gegen Lauf 70 |
|---|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed!" | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien | gleich |
| `uv run pytest --collect-only -q` | **Exit 0**, **5033** Tests | gleich |
| `python3 scripts/changelog_fragments.py check` | **Exit 0**, **403** Fragmente | 🔴 **Lauf 70 nannte 404 — korrigiert** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen in `de.json` und `en.json` | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** | gleich |
| `npm audit` (voll) | ⚠️ **Exit 1**, **29 moderate** (`glob`, `minimatch`) | gleich — **erwartet** |
| `uv run python -m who2be_mcp.payload_report` | **Exit 0**, **103** Werkzeuge / **108.251** Bytes, `instructions` **1.834** | gleich (**12.** identische Messung) |
| `main`-CI (`ci.yml`) | Lauf **41188042026** am Kopf `af78ad7d`, `status: completed` **und** `conclusion: success` getrennt gelesen (Regel 91) | gleiches Urteil |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 160) | — |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **47. Messung in Folge** |

⚪ **Coverage bewusst nicht gefahren (Regel 160).** Fenster **0 Commits**, Baum bitgleich
(`498ded60`). Die Bezugswerte aus Lauf 68 gelten unverändert: **282** Dateien / **2849**
Tests, **89,89 / 83,95 / 86,81 / 91,75**, **404,04 s**. **Wer ein Paket startet, misst den
Startwert selbst** (Regel 128).

🔴 **Die Fragmentzahl war um eins zu hoch.** `changelog.d/` enthält **404** `.md`-Dateien, das
Skript zählt **403** Fragmente — die Differenz ist `changelog.d/README.md`, keine Änderung.
Zitiert wird ab jetzt die Eigenzahl des Werkzeugs (Regel 143).

## Eigener Messfehler, offengelegt

🔴 **Mein erstes Gate-Skript hat jeden Befehl nach `tail` gepipet und danach `EXIT=$?`
gelesen** — das ist der Exit-Code von `tail`, nicht der des Gates. Das Skript meldete
`npm audit` (voll) als **Exit 0**; der wahre Wert ist **Exit 1** bei 29 moderate Funden.
Alle Exit-Codes der Tabelle oben sind danach **ohne Pipe** neu gemessen. Regel 94 verlangte
bisher „Exit-Codes ohne Pipe" als Leseregel; sie gilt für die **Form des Messskripts**.
→ **Regel 172**.

## PR-Bestand — 28 offene PRs

Scope je PR über `git merge-base` + `git diff --name-only`, Konfliktfreiheit über
`git merge-tree --write-tree`, CI über die Check-Runs am Head mit `all-green` **namentlich**
und positivem Filter auf `failure`/`timed_out`/`cancelled`. **Alle 28 selbst gerechnet, alle
28 CI-Lagen selbst gemessen — auch die fünf gate-alten.**

- 🟢 **Alle 28 mergen konfliktfrei** (rc 0), alle 28 merge-bases rechnen.
- **Die einzige Änderung im Bestand ist #1117** — das Protokoll von Lauf 70, Draft, bei 0.
  Nichts geschlossen, nichts anderes neu. Bei bitgleichem Baum trotzdem selbst gemessen
  (Regel 168).
- **Rückstand auf `main`:** **0** → #1117, #1116, #1115, #1114, #1113, #1112, #1108, #1106,
  #1100, #1091, #1080, #1063, #674 _(dreizehn)_ · **5** → #1107, #1105, #1104, #1103 ·
  **9** → #1097, #1096, #1095, #1090, #1089 · **23** → #1078 · **38** → #1056 ·
  **63** → #1025 · **79** → #1002 · **104** → #990 · **227** → #831.
- 🟢 **24 grün** (`all-green` namentlich `success`).
- 🔴 **4 rot:** **#1107**, **#1078** und **#831** je an **`audit` + `all-green`** ·
  **#674** an **`all-green` + 7 weiteren** (`e2e`, `e2e-mobile` ×3, `web`, `compose-smoke`,
  `e2e-billing-cloud`; Vite/Vitest-Major, **Weiche 12**).
- Kein PR hat einen laufenden Check, und **jeder** der 28 trägt einen Check-Run namens
  `all-green`. CodeQL stand auf #1116, #1115, #1114, #1097, #1096, #1095, #1091 auf
  `neutral` — neutral ist nicht rot.

### 🔴 „Nicht gemessen, mit Grund" hat ein echtes Rot verdeckt

Lauf 70 führte die fünf gate-alten PRs (#1056, #1025, #1002, #990, #831) als **nicht
gemessen** und begründete das mit „eine Farbe daran wäre keine Aussage". Dieser Lauf hat
alle fünf gemessen: **vier sind grün, #831 ist rot** (`audit` + `all-green`) — dieselbe
Rot-Ursache wie #1107 und #1078 und damit dieselbe Therapie. Die Gate-Alt-Frage (Weiche 2)
betrifft die **Deutung** einer grünen Farbe; sie ist kein Grund, die Messung zu unterlassen.
→ **Regel 171**.

### 🔴 Grün auf einem Protokoll-PR heißt „nichts gelaufen"

Auf **elf** PRs — #1117, #1113, #1112, #1104, #1103, #1090, #1089, #1056, #1025, #1002,
#990 — sind die schweren Jobs (`python`, `web`, `e2e*`, `compose-smoke`, `backup-alarm`)
**`skipped`**, und `all-green` steht trotzdem auf `success`. Alle elf sind Doku-/Protokoll-PRs:
die Pfadfilter der CI lassen die Jobs gar nicht anlaufen. **Ihr Grün belegt nicht, dass die
Suiten durchlaufen — es belegt, dass sie nicht nötig waren.** Die neun merge-fertigen PRs
sind davon unberührt (15–18 ausgeführte Checks). Eine Farbe wird deshalb nur zusammen mit der
**Zahl der ausgeführten Checks** zitiert. → **Regel 173**.

### Merge-fertig — **neun**, unverändert

0 Commits hinter `main` · konfliktfrei · `all-green` namentlich `success` · kein Draft:
**#1063, #1080, #1091, #1100, #1106, #1108, #1114, #1115, #1116.**
#1117, #1113 und #1112 liegen ebenfalls bei 0, sind aber **Drafts**; #674 liegt bei 0 und ist
**rot**.

⚠️ **#1080, #1108 und #1115 fassen alle drei `uv.lock` an** — nach dem ersten Merge rechnen
die beiden anderen neu. Dasselbe gilt für #1114 gegen #674. **Die Reihenfolge innerhalb der
neun ist eine Owner-Entscheidung** (Weiche 11): Mergen ist nach Persona-Grenze ohne Freigabe
verboten.

### Protokoll-Rückstand — **15**, Loch bei Lauf 63

Auf `main` liegen Protokolle für Lauf **31** und **43–55** (plus das unnummerierte erste).
**Für die Läufe 56–70 — fünfzehn — liegt auf `main` keines.** Vierzehn davon stecken in
offenen Drafts (#990=56, #1002=57, #1025=58, #1056=59, #1078=60, #1089=61, #1090=62,
#1103=64, #1104=65, #1105=66, #1107=67, #1112=68, #1113=69, #1117=70). **Zu Lauf 63
existiert nirgends ein Protokoll** — Weiche 38 hält. Dieser Lauf legt das sechzehnte dazu.

🔴 **`.claude/context/STATE.md` ist auf `main` zuletzt am 2026-10-02 geschrieben**
(`e39d05eb`), Kopfzeile „_Stand: 2026-10-02_". **Dreifach gehalten** (#1103 bei 5, #1090
bei 9, #1078 bei 23). **Wer ein Paket abschließt, nimmt #1103 als Basis** (grün, geringster
Rückstand).

## Datei-Sperren — gegen alle 28 PRs, am vollen Pfad, Existenz zuerst belegt (Regel 163)

| Datei | Träger |
|---|---|
| 🔴 `.claude/context/STATE.md` | 🔴 **#1078**, **#1090**, **#1103** — dreifach, alle drei Protokolle |
| `uv.lock` | ⚠️ **#1080**, **#1108**, **#1115** — dreifach |
| `apps/web/package.json` · `apps/web/package-lock.json` | ⚠️ **#1114** (grün, 0) und **#674** (rot, 0) |
| `deploy/monitor/compose.yml` | ⚠️ **#1097**, **#1116** |
| 🔴 `.github/PROJECT.md` | 🔴 **#1105** |
| `.github/workflows/ci.yml` (**1259** Zeilen) · `.github/workflows/deploy.yml` | 🔴 **#1091** |
| 🟢 `docs/mcp-payload-budget.md` · `apps/mcp/src/who2be_mcp/payload_report.py` · `apps/mcp/tests/test_tool_payload_budget.py` | 🟢 **FREI** |
| 🟢 `apps/web/osv-scanner.toml` (**26** Zeilen) · `changelog.d/osv-ignore-http-cache-semantics.security.md` (**8** Zeilen) | 🟢 **FREI** |
| 🟢 `apps/web/src/features/settings/components/MfaSection.tsx` · `apps/web/src/auth/SessionProvider.tsx` · `apps/web/src/i18n/locales/{de,en}.json` | 🟢 **FREI** |
| 🟢 `apps/web/e2e/helpers/auth.ts` · `LoginPage.tsx` · `apps/web/src/api/client.ts` · `apps/web/vite.config.ts` | 🟢 **FREI** |
| 🟢 `deploy/hetzner/Caddyfile` | 🟢 **FREI** |

**Jede als FREI gemeldete Datei wurde vor der Prüfung auf Existenz belegt** — ein falscher
Pfad meldet immer „FREI" (Regel 163, verschärft in Lauf 70).

## Zeiger-Prüfung — gegen den heutigen Dateiinhalt

### #632 / #633 — **13 von 13 gültig, fünfter Lauf in Folge nichts verrottet**

| Zeiger | gemessen |
|---|---|
| `apps/web/src/features/settings/components/MfaSection.tsx` | **297** Zeilen |
| `apps/web/src/auth/SessionProvider.tsx` | **267** Zeilen |
| `apps/web/src/i18n/audit.test.ts` | **371** Zeilen |
| `apps/web/src/features/auth/pages/LoginPage.tsx` | **399** Zeilen |
| `apps/web/package.json` | **82** Zeilen |
| `apps/web/vite.config.ts` | **107** Zeilen, Thresholds `:99-103` — statements **80**, branches **79**, functions **75**, lines **80** |
| `apps/web/e2e/helpers/auth.ts` | **199** Zeilen |
| `apps/web/src/api/client.ts` | **1849** Zeilen |
| `apps/web/src/api/types.ts` | **2407** Zeilen |
| `.github/workflows/ci.yml` | **1259** Zeilen |
| `apps/web/src/i18n/orphan-baseline.json` | **156** Einträge, **158** Zeilen |
| `apps/web/src/test/a11y.test.ts` | **77** Zeilen, Untergrenze an **`:74`** (`expect(axeFiles.length).toBeGreaterThanOrEqual(20)`) |
| `de.json` / `en.json` | je **3.365** Schlüssel — Eigenzahl von `npm run i18n:check` (Regel 143) |

🟢 **Ein eigener Fehlalarm abgewendet (Regel 10).** Mein erster Zählweg las die Locale-Dateien
mit `json.load` und gab **22** aus — das sind die Schlüssel der **obersten** Ebene, die
Dateien sind verschachtelt. Die **3.365** sind die flache Zahl, und sie ist die Eigenzahl des
Gates. Ein „Widerspruch" hätte hier nur meine Messmethode gemeldet, nicht das Repo.

### #1001 — **5 von 5 Zeigergruppen gültig**, rott-fest

`docs/mcp-payload-budget.md` hat **609** Zeilen. `104.777` an **`:233`, `:292`, `:327`,
`:487`** (**4×**) · `108.262` an **`:234`, `:331`** (**2×**) · `71.738` an **`:236`, `:335`**
(**2×**). Zusätzlich steht `108.251` an **`:262`** und **`:265`**.

🟢 **AK1 ist durch meinen eigenen `payload_report`-Lauf zeichengleich bestätigt:**
**103** Werkzeuge / **108.251** Bytes, `instructions` **1.834**.
🔴 **AK3 unabhängig nachgerechnet:** `180.000 − 108.251 = ` **71.749**. Die Doku trägt
**71.738** — **11 Bytes zu wenig**, weil sie mit `108.262` statt `108.251` rechnet. Deckt
sich mit Lauf 70; der Wert stammt aus eigener Rechnung, nicht aus dessen Body.

### #989 — Zeiger gültig, Befund schärfer als in Lauf 70

- `apps/web/osv-scanner.toml`: **26** Zeilen, `grep -c IgnoredVulns` → **2**.
  `GHSA-3g3m-2fjr-6pw4` (`glob@13.0.6`) an `:9-15` und `GHSA-g3hv-75wg-m249` (`minimatch`)
  an `:17-26`, **beide `ignoreUntil = 2026-11-30T00:00:00Z`**. Die
  `http-cache-semantics`-Ausnahme ist weg — **#1111** hat sie entfernt.
- Lockfile: der Knoten `"node_modules/http-cache-semantics"` beginnt an **`:6295`**,
  `"version": "4.2.0"` an `:6296`. **Zeiger gültig.** (Der zweite Treffer an `:7602` ist eine
  Abhängigkeitsangabe `^4.1.1`, keine installierte Version — von Hand gegengelesen.)

🔴 **NEU — die beiden Changelog-Fragmente widersprechen sich gegenseitig.** Beide liegen
unveröffentlicht in `changelog.d/`:

- `changelog.d/osv-ignore-http-cache-semantics.security.md` (**8** Zeilen) kündigt eine
  Ausnahme für `GHSA-ch52-4w7c-c8xp` an, „recorded in `apps/web/osv-scanner.toml` and
  **valid until 2026-11-02**" — ein Eintrag, den es nicht mehr gibt, mit einer Frist, die
  seit **zwei Tagen** verstrichen ist.
- `changelog.d/osv-ignore-glob-minimatch.security.md` sagt in **Zeile 6–7** das Gegenteil,
  wörtlich: „The exception for `http-cache-semantics` (GHSA-ch52-4w7c-c8xp) **was removed
  because the scan no longer uses it**."

**Ein Changelog-Schnitt von heute veröffentlicht beide Sätze nebeneinander.** Das ist kein
Urteil über eine alte Frist mehr, sondern ein **aus dem Repo allein beweisbarer
Selbstwiderspruch** — und er stärkt Weiche 40, Empfehlung **B**: das Fragment löschen macht
aus einem blockierten `size/S` ein sperrfreies `size/XS`. → **Regel 174**.

### Stehende Posten, heute nachgemessen

- `grep -c pip-audit CLAUDE.md` → **0**. Weiche 41, zweite Hälfte, unverändert offen.
- **MB/MiB (Weiche 9):** `docs/licensing/plans.md` schreibt in der Kundentabelle `:28`/`:29`
  **„100 MB"** und **„10 GB"**, rechnet aber ab `:37` mit `FREE_STORAGE_QUOTA_BYTES = `
  **100 MiB** und `PRO_STORAGE_QUOTA_BYTES = ` **10 GiB**, ebenso `:78` („Free 1 × 100 MiB,
  Pro 5 × 10 GiB = 50 GiB"), `:94` (20 MiB) und `:126` (100 MiB). **Der Widerspruch steht
  unverändert und bleibt der billigste offene Posten.**
- `apps/web/src/test/a11y.test.ts` hängt weiter bewusst an keiner der beiden
  Glob-Schreibweisen; der Kommentar über `:74` nennt **25** als Beobachtung vom 2026-10-19
  (Regel 118).

## Norm-Prüfung „Agent-ready Arbeitspaket" — alle 12 Bodies selbst gelesen

Vier Pflichtabschnitte nach `.github/PROJECT.md` §Constraints: **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|
| **#632** | ✅ | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **4/4**, Zeiger **13/13** |
| **#633** | ✅ | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 **4/4** |
| **#1001** | ✅ | ✅ 5 | ✅ `**Out of Scope:**` | ✅ | 🟢 **4/4**, Zeiger **5/5** |
| **#989** | ✅ | ✅ 6 | ✅ `**Out of Scope:**` | ✅ | 🟢 **4/4** — 🔴 toter Blocker-Beleg in §Startbedingung |
| **#540** | ✅ | ✅ 7 | ✅ | ✅ | 🟢 **4/4**, bleibt `needs-decision` (Mechanismus-Weiche 17, kein Feld fehlt) |
| **#435** | ⚠️ inline in §Proposed solution | ✅ 6 | ✅ `**Out:**` | ✅ | Epic, `size/M` |
| **#454** | ✅ | ✅ 5 | ✅ | ⚠️ „Kein Testkommando — die Verifikation ist die Produktions-Smoke-Reise" | `human-only` |
| **#542** | 🔴 fehlt | ✅ 5 | ✅ | ⚠️ teilweise | `human-only` |
| **#535** | 🔴 fehlt | ✅ 3 (Tracking) | ✅ | 🔴 fehlt | Epic |
| **#428** | 🔴 fehlt | ✅ 5 (Tracking) | ✅ | 🔴 fehlt | Epic |
| **#338** | 🔴 fehlt | 🔴 fehlt | 🔴 fehlt | 🔴 fehlt | **0 von 4**, `human-only` |
| **#442** | — | — | — | — | Queue, kein Arbeitspaket |

Scope-„In" fehlt in #542, #540, #535, #454, #428, #338. **Bewusst nicht umgebaut** (Regel 7,
Weiche 4): ein `size/M`-Issue wird nach Constraint nie durch Nachtragen von Feldern startbar.

**Kein Label vergeben, keines entzogen.** Begründung: die vier Pakete erfüllen die Norm
vollständig; #989s Befund betrifft einen **Beleg** in §Startbedingung, keinen Pflichtabschnitt.

🟢 **Lauf 70s Body-Korrekturen sind angekommen und sachlich richtig.** Die OSV-Frist steht in
#632/#633 heute nur noch im HIST-Kopfblock (als Korrektur formuliert) und in §Verweise mit dem
richtigen `2026-11-30`; **in keinem anderen verbindlichen Abschnitt.** Regel 170 hat
funktioniert.

## Reihenfolge — unverändert, viertes Mal

Sortierkriterien: harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche → Inventar vor
Zuschnitt → bei Gleichstand das kleinere.

1. **#632** Passkey registrieren — Kriterium **3** (Fundament vor Fläche, öffnet #633).
   Startbar ohne Nebenbedingung.
2. **#1001** Payload-Budget — Kriterium **4** (Inventar vor Zuschnitt). Startbar ohne
   Nebenbedingung. Gleichstand mit #632 bei `size/S`; Kriterium 3 schlägt Kriterium 4.
3. **#633** Step-up mit Passkey — harte Abhängigkeit auf #632, zusätzlich Container-Laufzeit
   oder CI.
4. **#989** `http-cache-semantics` — Weiche 40 offen (Zuschnitt), Empfehlung **B**.

**Wellen:** **A** = #632 + #1001 (code-disjunkt, verschiedene Verifikations-Bäume, alle
Schreibflächen frei; gemeinsame DoD-Fläche `STATE.md` → seriell abschließen) · **B** = #633
nach #632 · **C** = #989 nach Weiche 40 Option B, dann sperrfrei `size/XS` und als drittes
Glied neben A möglich · **M** (Owner) = die neun merge-fertigen PRs · **P** (Owner) = #1107,
#1078 **und #831** durch Branch-Update heilen.

## Was dieser Lauf selbst entschieden und geschrieben hat

- **#442** neu geschrieben (Reihenfolge, Wellen, Gates, PR-Bestand, Sperren, Norm-Tabelle,
  26 Weichen, Funde, 38 Pflege-Regeln).
- **#989** kommentiert: der Fragment-Selbstwiderspruch und der tote Blocker-Beleg, beide mit
  Beleg; die drei Optionen zu Weiche 40 **nicht** erneut gestellt (Regel 9).
- **Vier neue Pflege-Regeln** (171–174) aus den Funden dieses Laufs.
- **Eine neue Weiche (45)** zum Schreibweg, weil Weiche 44 in dieser Session versperrt ist.

## Was eine Owner-Antwort braucht

**26 offene Weichen**, vollständig in #442. Die vier mit dem größten Hebel:

1. **Weiche 11/34** — wer mergt die **neun** merge-fertigen PRs, in welcher Reihenfolge.
   Vierter Lauf mit derselben Zahl.
2. **Weiche 18 + 43 + 10** — Kadenz und `STATE.md`: **15 fehlende Protokolle**, Loch bei
   Lauf 63, dreifache Datei-Sperre. Dieser Lauf legt das sechzehnte dazu.
3. **Weiche 44 + 45** — der Schreibweg für Issue-Bodies. **In diesem Lauf durch Messung
   sachlich entschieden** (s. unten), es fehlt nur die Freigabe.
4. **Weiche 40** — Zuschnitt von #989. **Vom Urteil zur Tatsache geworden.**

## Funde — vier neue Regeln

### Regel 171 — eine Messung wird durchgeführt, auch wenn ihre Deutung offen ist

Lauf 70 ließ #1056, #1025, #1002, #990 und #831 ungemessen („eine Farbe daran wäre keine
Aussage"). Gemessen: **vier grün, #831 rot** (`audit` + `all-green`). Die Gate-Alt-Frage
(Weiche 2) betrifft die Deutung eines **Grüns**; ein **Rot** ist von ihr unabhängig
aussagekräftig und war einen Lauf lang unsichtbar. „Nicht gemessen, mit Grund" ist zulässig
für eine **teure** Suite (Regel 160), nicht für eine billige Abfrage mit strittiger Deutung.

### Regel 172 — ein Gate-Skript, das pipet, misst nicht

`cmd 2>&1 | tail -3; echo "EXIT=$?"` liefert den Exit-Code von `tail`. Mein erstes Skript
meldete so durchgängig 0, auch für `npm audit` (voll) mit wahrem **Exit 1**. Exit-Codes werden
am unverketteten Befehl genommen, die Ausgabe getrennt in eine Datei. Verschärft Regel 94 von
einer Leseregel zu einer Regel über die **Form des Messskripts**.

### Regel 173 — ein `all-green`-Grün wird nur mit der Zahl der ausgeführten Checks zitiert

Auf **elf** Doku-/Protokoll-PRs sind `python`, `web`, `e2e*`, `compose-smoke` und
`backup-alarm` **`skipped`**, `all-green` steht trotzdem auf `success`. Die Pfadfilter lassen
die Jobs nicht anlaufen. **Das Grün belegt, dass die Suiten nicht nötig waren — nicht, dass
sie durchliefen.** `skipped` ist nicht `success`, `neutral` (CodeQL auf sieben PRs) ist nicht
rot.

### Regel 174 — ein Changelog-Fragment wird gegen seine Geschwister geprüft

`changelog.d/osv-ignore-http-cache-semantics.security.md` kündigt eine Ausnahme „valid until
**2026-11-02**" an; `changelog.d/osv-ignore-glob-minimatch.security.md` sagt in Zeile 6–7,
dieselbe Ausnahme sei „**removed because the scan no longer uses it**". Beide unveröffentlicht
im selben Verzeichnis — **ein Schnitt veröffentlicht beide.** Zwei Fragmente können sich
widersprechen, ohne dass der Code widersprüchlich ist.

## Regel 169 im kontrollierten Versuch bestätigt

Dieser Lauf konnte den in Regel 169 vorgeschriebenen `gh`-Schreibweg nicht nutzen und hat
#442 deshalb über MCP `issue_write` geschrieben — mit der Attributions-Fußzeile in der
Nutzlast. Danach gemessen:

| | Quelle | live nach dem Schreiben |
|---|---:|---:|
| Zeichen (UTF-8) | **41.927** | **41.868** |
| Zeilen | **273** | **270** |
| Letzte Zeile | `_Generated by [Claude Code](…)_` | `_Zuletzt gepflegt: …_` |
| 11 Marker-Zählungen | — | **alle unverändert** |
| 6 Emoji-Zählungen | — | **alle unverändert** |

**Die Differenz sind genau die 59 Zeichen des Fußzeilen-Blocks** (`\n\n---\n_Generated …_\n`); der ganze übrige Body kommt
unbeschädigt an. Lauf 70 schrieb über `gh api -X PATCH --input` und behielt die Fußzeile,
dieser Lauf schrieb über MCP und verlor sie — **gleiche Nutzlast-Form, anderer Transport,
anderes Ergebnis.** Damit ist **Regel 169 bestätigt** und **Weiche 44 sachlich entschieden**;
offen ist nur die Freigabe. Das Ergebnis steht im Body von #442 selbst, damit der nächste
Agent nicht erneut danach sucht.

## `STATE.md` bewusst nicht angefasst

Dieser Lauf schreibt **nur** die Protokoll-Datei. `.claude/context/STATE.md` ist dreifach von
den offenen Protokoll-PRs #1078, #1090 und #1103 gehalten; ein vierter Schreiber hätte die
Sperre auf vier erhöht, ohne dass der Lauf eine Code-Änderung zu protokollieren hat. Das ist
die Linie, die Weiche 43 Empfehlung **B** vorschlägt, hier als Einzelfall angewandt — **nicht**
als Vorwegnahme der Entscheidung. Wer ein Arbeitspaket abschließt, nimmt weiter **#1103** als
Basis (grün, 5 Commits hinter `main`, konfliktfrei).

## Offen / Nächster Lauf

- **Weiche 45** beantworten, sonst bleibt der tote Blocker-Beleg in #989 §Startbedingung
  stehen (Regel 170 ist für lange Bodies ohne `gh`-Weg nicht ausführbar).
- **#831** zusammen mit #1107 und #1078 durch Branch-Update heilen (Welle P).
- `#1001` §AK5 nennt **404** Fragmente; die Eigenzahl des Werkzeugs ist **403**
  (`changelog.d/README.md` ist keines). Beim nächsten Body-Schreiben an #1001 mitziehen.
- Der Protokoll-Rückstand ist **15** und wächst mit diesem Lauf auf **16**.

