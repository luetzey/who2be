# Backlog-Aufbereitungslauf 72

**Datum:** 2026-11-05 · **Messpunkt:** `main` @ `af78ad7d9ead5084282c6ca925a500d895b768cd`
(Baum `498ded60e513e411ba100411235b97a95d11eaeb`) · **Fenster seit Lauf 71: 0 Commits**
(fuenftes bitgleiches in Folge; `main` steht seit dem 2026-10-31T10:16+01:00 still, 4,6 Tage)
· **29 offene PRs** (waren 28) · Node v22.23.4 · Klon shallow (50) -> 1666 Commits nach
`--unshallow`.

Warteschlange: #442 (Label `backlog-queue`). Begruendung: `.github/PROJECT.md` §Reihenfolge.

## 1. Auftrag

Vollstaendiger Vorbereitungslauf: jedes offene Issue gegen die Norm
„Agent-ready Arbeitspaket" pruefen; was das Repo belegt, selbst entscheiden und mit Beleg
ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen und Empfehlung,
Issue bekommt `needs-decision`. Danach die Warteschlange neu ordnen (harte Abhaengigkeit ->
Owner-Vorgabe -> Fundament vor Flaeche -> Inventar vor Zuschnitt -> bei Gleichstand das
kleinere) und in Wellen gruppieren (datei-disjunkt und nicht blockierend).

## 2. Lage der Werkzeuge

- 🔴 **Der Who2Be-AgentDB-Connector (`Who2Be---Coder`) ist in dieser Session nicht
  autorisiert.** `get_persona`, `list_triggers`, `fetch_playbook`, `search_memory`,
  `save_memory`, `record_usage` und `submit_feedback` waren **nicht aufrufbar**. Persona und
  Playbook-Katalog liegen im System-Prompt; der Body des am naechsten liegenden Playbooks
  (zwischen „Projekt-Standup" und „Code-Task-Flow", kein exakter Trigger-Treffer) liess sich
  nicht laden. **Kein passendes Playbook** — gearbeitet wurde nach der im Auftrag genannten
  Norm und den Pflege-Regeln in #442.
- 🔴 **Keine Rueckmeldung an die AgentDB moeglich** (`record_usage`/`submit_feedback`
  gesperrt). Das ist der zweite Lauf in Folge ohne Lernschleifen-Rueckfluss.
- 🔴 **Keine Container-Laufzeit:** `docker info` -> Exit 1, kein `podman`. **48. Messung in
  Folge.**
- 🔴 **`gh` ist in dieser Session nur fuer Suche freigegeben** (Weiche 44). Der in Regel 169
  vorgeschriebene Schreibweg `gh api -X PATCH --input` stand nicht offen.
  **Offengelegter eigener Regelbruch:** ein `gh api -X GET repos/.../pulls/N` zur
  Zustandspruefung von sieben geschlossenen PRs — lesend, aber **kein** Such-Endpunkt. Die
  Auskunft war der Beleg fuer die zwei Hauptfunde; der restliche Lauf ist auf die
  MCP-Werkzeuge zurueckgekehrt. Saubere Form waere `search/issues` gewesen.
- 🔴 **`pull_request_read(method="get_status")` liefert auf diesem Repo gar keine Auskunft** —
  erstmals gemessen, s. §4.

## 3. Gates (ohne vorherige Reparatur, Exit-Codes am unverketteten Befehl)

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | Exit 0, „All checks passed!" |
| `uv run mypy .` | Exit 0, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | Exit 0, **5033** Tests |
| `python3 scripts/changelog_fragments.py check` | Exit 0, **403** Fragmente (404 `.md`-Dateien, Differenz `README.md`) |
| `uv tool run pip-audit ... -r /tmp/req.txt` | Exit 0, „No known vulnerabilities found", **398** Requirements |
| `npm run lint` (in `apps/web/`) | Exit 0, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe **0 Byte** |
| `npm run i18n:check` | Exit 0, `de.json`/`en.json` je **3.365** Schluessel (flach), **156** Waisen |
| `npm audit --omit=dev --audit-level=high` | Exit 0, „found 0 vulnerabilities" |
| `npm audit` (voll) | **Exit 1**, 🔴 **28 moderate** (Lauf 71: 29) |
| `uv run pytest apps/mcp/tests/test_tool_payload_budget.py -q` | Exit 0, **64 passed** |
| `uv run python -m who2be_mcp.payload_report` | Exit 0, **103** Werkzeuge / **108.251** Bytes, `instructions` **1.834** (13. identische Messung) |
| `main`-CI | Lauf **41188042026** am Kopf `af78ad7d`, `status: completed` UND `conclusion: success` getrennt gelesen |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 160) |

**Coverage-Bezugswerte aus Lauf 68, ausdruecklich UEBERNOMMEN** (Pflege-Regel 4): 282 Dateien /
2849 Tests, 89,89 / 83,95 / 86,81 / 91,75, 404,04 s.

⚠️ **Der CI-Lauf auf dem Commit UNTER dem Kopf ist rot:** `6540251` (#1098) trägt Lauf
41186313630 mit `conclusion: failure`, die zwei darunter `cancelled`. **Der Kopf ist gruen**,
Regel 80 greift nicht — aber der Fall belegt am Repo, warum Regel 91 den HEAD-SHA verlangt.

## 4. Funde

### F1 🔴 Ein Body verneinte die Parallelitaet, die #442 behauptet (Regel 175, neu)

§Startbedingung von **#632** sagte: „*Dieses Paket hat in Lauf 65 keinen Parallel-Partner:
der Python-Baum ist leer, solange #1101 offen ist.*"

**#1101 ist am 2026-10-31 gemergt** (`9b4da775`). #1001 sagt das seit Lauf 68 in seinem
eigenen §Befund, und **#442 fuehrt #632 + #1001 seit Lauf 68 als Welle A** — das
Parallel-Paar. Drei Stellen, zwei Aussagen, und die falsche stand in dem Abschnitt, den ein
Agent vor dem Start liest.

**Der Schaden ist nicht ein falsches Datum, sondern verschenkte Parallelitaet.** Bei vier
offenen Paketen, von denen zwei blockiert sind, ist das die Haelfte des Durchsatzes.
**Korrigiert im Body** (Regel 170).

### F2 🔴 Derselbe tote PR-Beleg stand in zwei Bodies (Regel 152 verschaerft)

Lauf 71 fand **#1092** als toten Blocker-Beleg in #989 §Startbedingung. Lauf 72 hat **alle
vier** `agent-ready`-Bodies gegen den PR-Bestand gelesen und ihn ein zweites Mal gefunden —
in **#632** §Startbedingung als Traeger von `apps/web/package.json`.

| Body | stand dort | steht dort heute |
|---|---|---|
| #989 §Startbedingung + §Eskalation | #1092 (gruen, 9 dahinter), „#1092 zuerst mergen" | **#1114** (gruen, 0 dahinter, merge-fertig) + #674 |
| #632 §Startbedingung | #1092 (gruen, 4 dahinter) + #674 | **#1114** + #674 |

**#1092 ist am 2026-11-02T05:17:22Z geschlossen, `merged: false`.** Beide Stellen in beiden
Bodies korrigiert. **Regel:** wer einen geschlossenen PR findet, sucht ihn in ALLEN Bodies,
nicht im ersten, in dem er auffiel.

### F3 🔴 Eine Advisory-Zahl ist am bitgleichen Baum gewandert (Regel 176, neu)

`npm audit --json` meldet am 2026-11-05 **28** moderate (0 low/high/critical, 28 betroffene
Pakete, Wurzeln `glob` + `minimatch`). Lauf 68/71 zaehlten **29**.
`package-lock.json:6295-6296` ist unveraendert (`http-cache-semantics` `4.2.0`), der Baum ist
bitgleich. **Also hat sich die Advisory-Datenbank bewegt, nicht das Repo.** #989 nannte die 29
an drei Stellen als „erwartet"; alle drei tragen jetzt die 28 plus den Hinweis, selbst zu
messen. **Eine Zahl aus einer fremden Datenbank wird mit Messweg und Messdatum zitiert und nie
als Schwelle verwendet.**

### F4 🔴 Die naechste Frist beisst, und fuer sie gibt es kein Issue (Weiche 46, neu)

`osv-scanner.toml:9-15`/`:17-26` filtern `GHSA-3g3m-2fjr-6pw4` (`glob@13.0.6`) und
`GHSA-g3hv-75wg-m249` (`minimatch@10.2.5/10.2.6/3.1.5`) bis **2026-11-30** — **25 Tage**.

**Der Unterschied zur `http-cache-semantics`-Frist ist der entscheidende:** die war am Gate
„*unused*" (Lauf 65), ihr Ablauf war harmlos. **Diese deckt lebende Funde** — `npm audit`
meldet beide heute als die einzigen 28, und die `reason`-Strings nennen selbst, dass der Fix
nur in einem Major liegt, den kein Elternpaket annimmt; `minimatch@3` ueber
`eslint-plugin-jsx-a11y` hat „*no compatible fix at all*".

**Folge:** Ablauf -> kein Filter -> Fund -> `audit` rot -> `all-green` rot, **auf jedem**
offenen PR.

⚠️ **Grenze der Messung beim Schreiben der Weiche (Weiche 37 B):** `npm audit` liest npm, das
Gate ist `osv-scanner` und liest OSV. `api.osv.dev` ist gesperrt, keine Container-Laufzeit.
**Benannter Messweg fuer die OSV-Haelfte: der `audit`-Job des naechsten PR-Laufs.**

🟢 **Der Messweg ist noch im selben Lauf gelaufen und bestaetigt die Praemisse — s. §F9.**
CI-Lauf **41942967748**, Job **126968093211** an **#1119** (Head `09872a72`), osv-scanner 2.2.4:
`Filtered 3 vulnerabilities from output` (einer fuer `glob`, zwei fuer `minimatch`).
**Die Ignores wirken; ihr Ablauf beisst, am Gate selbst belegt, nicht aus npm abgeleitet.**

**Kein Issue:** #989 erklaert die Migration out of scope, in der Warteschlange steht sie nicht,
die `reason`-Strings verweisen auf eine Kanban-Karte ausserhalb des Repos (Muster Weiche 23).
**Drei Optionen + Empfehlung B als Kommentar an #442.**

### F5 🔴 `get_status` liefert auf diesem Repo gar keine Auskunft (Beleg zu Regel 59)

Regel 59 verbietet `pull_request_read(method="get_status")`, ohne es gemessen zu haben. Probe
auf **#1106**: `{"state":"pending","sha":"45714abe...","total_count":0,"statuses":[]}` — bei
einem PR, dessen `all-green` `success` ist und der **18** Check-Runs traegt. Das Repo nutzt
Check-Runs, nicht die Commit-Status-API. **`get_status` ist nicht ungenau, sondern leer**; wer
ihm folgt, liest „pending" auf einem fertig gruenen PR.

### F6 🟢 Zwei eigene Fehlalarme von Hand abgefangen (Regel 10, Regel 163)

1. Mein erster Sperr-Lauf prueffte `apps/web/src/features/settings/MfaSection.tsx` (ohne
   `components/`) und `apps/web/orphan-baseline.json` (ohne `src/i18n/`). **Beide existieren
   nicht** — einer meldete „MISSING", der andere „FREI". Die echten Pfade sind
   `.../settings/components/MfaSection.tsx` (297 Zeilen) und
   `apps/web/src/i18n/orphan-baseline.json` (156 Eintraege). **Die falschen Pfade stammten aus
   meiner eigenen Kurzschreibweise, nicht aus einem Body** — #632 nennt beide korrekt.
   **Regel 163 gilt fuer den Messenden, nicht nur fuer den Gemessenen.** #632 §Scope traegt
   jetzt einen ausdruecklichen Hinweis auf das Zwischenverzeichnis.
2. Erster Zaehlweg fuer `de.json`/`en.json` gab **22** Schluessel — das ist die oberste Ebene,
   die Dateien sind verschachtelt. **3.365** ist die flache Zahl und die Eigenzahl von
   `npm run i18n:check`. Zweiter Lauf in Folge dieselbe Falle; die Warnung steht jetzt auch in
   #632 §Startbedingung.

### F7 🟢 Die E2E-Rechnung von #633 ist exakt (Gegenprobe zu Regel 149)

Alle Zahlen selbst nachgezaehlt und zeichengleich bestaetigt: **9** `e2e/*.spec.ts`, **43**
`test(`-Zeilen am Zeilenanfang, **44** naiv (die 44. ist `expectedName.test(probe.name ?? '')`
in `scroll-guard.spec.ts:666`, ein RegExp-Aufruf), **ein** `test.skip(` im ganzen Baum
(`billing.spec.ts:43`), `createUser` in **7** von 9 Dateien mit **37** Koerpern (billing 5,
editor-profiles 6, journeys 6, navigation 3, review-gate 2, scroll-guard 14,
status-actions-viewport 1). `ci.yml:463`/`:544` woertlich bestaetigt, Datei **1259** Zeilen.

### F8 🔴 Der Changelog-Selbstwiderspruch aus Lauf 71 haelt — und die Frist ist verstrichen

`osv-ignore-http-cache-semantics.security.md:1-3` (8 Zeilen) kuendigt eine Ausnahme
„*recorded in `apps/web/osv-scanner.toml` and valid until 2026-11-02*" an;
`osv-ignore-glob-minimatch.security.md:6-7` sagt, dieselbe Ausnahme sei „*removed because the
scan no longer uses it*". **Beide unveroeffentlicht in `changelog.d/`**, beide woertlich
gegengelesen. `grep -c GHSA-ch52-4w7c-c8xp osv-scanner.toml` -> **0**. 🔴 **Und die behauptete
Frist ist seit dem 2026-11-03 verstrichen:** ein Schnitt von heute veroeffentlicht einen Satz,
der eine abgelaufene Gueltigkeit fuer einen Eintrag behauptet, den es nicht gibt. Verstaerkt
Weiche 40 Empfehlung B.

### F9 🔴 Die `unused ignores`-Liste von osv-scanner taugt nicht als Beleg (Regel 177, neu)

Der `audit`-Job von **#1119** (CI-Lauf 41942967748, Job 126968093211, Head `09872a72`,
osv-scanner **2.2.4**) sagt **zwei Dinge gleichzeitig ueber dieselben zwei IDs**:

```
GHSA-3g3m-2fjr-6pw4 and 1 alias have been filtered out because: glob@13.0.6: ...
GHSA-g3hv-75wg-m249 and 1 alias have been filtered out because: minimatch@... (zweimal)
Filtered 3 vulnerabilities from output
/home/runner/.../apps/web/osv-scanner.toml has unused ignores:
 - GHSA-3g3m-2fjr-6pw4
 - GHSA-g3hv-75wg-m249
OSV: 0 Eintraege (rc=0)
```

**Die Ignores haben drei Befunde unterdrueckt UND stehen in derselben Ausgabe als `unused`.**

🔴 **Damit ist die Lesart aus Lauf 65 widerlegt**, die lautete: „*osv-scanner meldet einen
Ignore-Eintrag als `unused`, wenn er auf keinen gefundenen Befund gepasst hat — nicht, wenn er
einen unterdrueckt.*" Diese Regel hat seit dem 2026-10-29 Weiche 32 getragen.

⚠️ **Nicht ueberkorrigieren** (Regel 157): der **Schluss** von Lauf 65 ueber
`GHSA-ch52-4w7c-c8xp` bleibt richtig. In dem damals zitierten Log fehlen **beide**
Wirksamkeits-Zeilen — keine `filtered out because`-Zeile, kein `Filtered N vulnerabilities`.
Dort griff der Ignore tatsaechlich ins Leere. **Falsch war nur die Begruendung:** belastbar war
die *Abwesenheit* der Filter-Zeilen, nicht die *Anwesenheit* der `unused`-Zeile. **Lauf 65 hatte
recht aus dem falschen Grund** — und genau deshalb haette die Regel beim naechsten Fall in die
Irre gefuehrt, was sie hier beinahe getan hat.

**Regel 177:** Ob ein `osv-scanner`-Ignore wirkt, liest man an
`<ID> ... have been filtered out because: ...` plus `Filtered N vulnerabilities from output`,
**nicht** an der `unused ignores`-Liste. Wirkt ein Ignore, beisst sein Ablauf; wirkt er nicht,
ist der Ablauf harmlos — und diese Unterscheidung traegt eine Sortier-Entscheidung.

🟢 **Weiche 37 Option B hat sich zum dritten Mal selbst belegt:** der benannte Messweg war die
Antwort, und er kostete einen CI-Lauf, der ohnehin lief.

## 5. PR-Bestand (alle 29 selbst gemessen)

Scope je PR ueber `git merge-base` + `git diff --name-only`, Konfliktfreiheit ueber
`git merge-tree --write-tree`, CI ueber die Check-Runs am Head mit `all-green` namentlich.

- 🟢 **Alle 29 mergen konfliktfrei** (rc 0), alle 29 merge-bases rechnen.
- **Neu im Bestand: nur #1118** (Protokoll Lauf 71, Draft, bei 0, gruen bei **9** ausgefuehrten
  Checks — 7 schwere Jobs `skipped`). Nichts geschlossen.
- **Rueckstand:** 0 -> #1118, #1117, #1116, #1115, #1114, #1113, #1112, #1108, #1106, #1100,
  #1091, #1080, #1063, #674 (vierzehn) · 5 -> #1107, #1105, #1104, #1103 · 9 -> #1097, #1096,
  #1095, #1090, #1089 · 23 -> #1078 · 38 -> #1056 · 63 -> #1025 · 79 -> #1002 · 104 -> #990 ·
  227 -> #831.
- 🟢 **25 gruen**, 🔴 **4 rot — dieselben vier wie Lauf 71:** #1107 (9 Checks), #1078 (9),
  #831 (8) je an `audit` + `all-green` (Protokoll-PRs, durch Branch-Update heilbar) · #674 an
  `all-green` + 7 weiteren (15 Checks, Vite/Vitest-Major).
- **Merge-fertig: neun, unveraendert (fuenfter Lauf)** — #1063 (18), #1080 (18), #1091 (15),
  #1100 (18), #1106 (18), #1108 (18), #1114 (15), #1115 (15), #1116 (15). Serielle Zwaenge:
  `uv.lock` dreifach (#1080/#1108/#1115), `apps/web/package*.json` zweifach (#1114 gegen #674),
  `deploy/monitor/compose.yml` zweifach (#1097/#1116).
  🔴 **#1114 ist der Engpass fuer Welle C** — es entsperrt #989.
- **Gate-alt** (an der CI-Definition, Regel 158): #1056, #1025, #1002, #990, #831. Alle fuenf
  gemessen (Regel 171) — vier gruen, **#831 rot**. Kante unveraendert zwischen 23 und 38.
- 🔴 **Protokoll-Rueckstand: 16.** Auf `main` liegen Protokolle fuer Lauf 31 und 43–55
  (aus `git ls-tree origin/main` gelesen); fuer 56–71 keines. Fuenfzehn in offenen Drafts,
  **zu Lauf 63 existiert nirgends eines.** Dieser Lauf legt das siebzehnte dazu.
- 🔴 **`.claude/context/STATE.md` auf `main` zuletzt 2026-10-02** (`e39d05eb`), 34 Tage alt,
  dreifach gehalten (#1103 bei 5, #1090 bei 9, #1078 bei 23 und rot).

## 6. Datei-Sperren (am vollen Pfad, Existenz zuerst belegt — Regel 163)

Gehalten: `STATE.md` (#1078/#1090/#1103) · `uv.lock` (#1080/#1108/#1115) ·
`apps/web/package{.json,-lock.json}` (#1114/#674) · `deploy/monitor/compose.yml`
(#1097/#1116) · `.github/PROJECT.md` (#1105) · `ci.yml` + `deploy.yml` (#1091).

FREI, Existenz je belegt: `docs/mcp-payload-budget.md` (609 Z) ·
`payload_report.py` (333 Z) · `test_tool_payload_budget.py` (1.735 Z) ·
`apps/web/osv-scanner.toml` (26 Z) · `changelog.d/osv-ignore-http-cache-semantics.security.md`
(8 Z) · `features/settings/components/MfaSection{,.test,.a11y.test}.tsx` (297/284/45 Z) ·
`SessionProvider.tsx` (267 Z) · `i18n/locales/{de,en}.json` (je 4.661 Z) ·
`i18n/orphan-baseline.json` (156 Eintraege) · `e2e/helpers/auth.ts` (199 Z) ·
`LoginPage.tsx` (399 Z) · `api/{client,types}.ts` (1.849/2.407 Z) · `vite.config.ts` (107 Z) ·
`test/a11y.test.ts` (77 Z) · `deploy/hetzner/Caddyfile` (208 Z).

## 7. Norm-Pruefung „Agent-ready Arbeitspaket" — 4 von 4 vollstaendig

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| #632 | ✅ | 5 | ✅ | ✅ | **13/13** | vollstaendig, **zwei tote Belege korrigiert** |
| #633 | ✅ | 6 | ✅ | ✅ | ja, E2E exakt | vollstaendig |
| #1001 | ✅ | 5 | ✅ | ✅ | **5/5** | vollstaendig, **Fragmentzahl korrigiert** |
| #989 | ✅ | 6 | ✅ | ✅ | ja | vollstaendig (`needs-decision`), **Beleg + Zahl korrigiert** |

Kein `agent-ready` vergeben oder entzogen, kein `needs-decision` vergeben oder entzogen. Die
Funde betrafen Belege und Bezugszahlen, nicht einen Pflichtabschnitt.

Norm-Stand der acht uebrigen Bodies (selbst gelesen, unveraendert): Outcome fehlt in #542,
#535, #428; Verifikation fehlt in #535, #428; #454 hat sie mit „Kein Testkommando"; #338 hat
0 von 4; #540 hat alle vier und bleibt `needs-decision` wegen der Mechanismus-Entscheidung;
#435 hat Outcome nur inline. **Bewusst nicht umgebaut** (Weiche 4).

## 8. Reihenfolge (zum fuenften Mal unveraendert) und Wellen

| Pos | Issue | Groesse | Baum | Kriterium |
|---|---|---|---|---|
| 1 | **#632** Passkey registrieren | `size/S` | Web/Vitest | 3 Fundament vor Flaeche (oeffnet #633) |
| 2 | **#1001** Payload-Budget-Rest | `size/S` | Python/pytest | 4 Inventar vor Zuschnitt |
| 3 | **#633** Step-up mit Passkey | `size/S` | Web | 1 harte Abhaengigkeit (#632) + Container/CI |
| 4 | **#989** http-cache-semantics | `size/S` | Web | `needs-decision` (Weiche 40) |

| Welle | Inhalt | Bedingung |
|---|---|---|
| **A** | **#632 + #1001** | Das echte Parallel-Paar: Vitest gegen pytest, code-disjunkt, beide Flaechen ueber alle 29 PRs frei. ⚠️ Gemeinsame DoD-Flaeche `STATE.md` — wer zweiter fertig wird, rebasiert auf #1103 |
| **B** | **#633** | nach #632 (hart) und nach Container-Laufzeit ODER CI |
| **C** (bedingt) | **#989** nach Weiche 40 Option B | dann sperrfrei und `size/XS`, disjunkt zu A — drittes Glied. Mit dem 4.3.0-Bump haengt es an #1114 |
| **M** (Owner) | die neun merge-fertigen PRs | kein Agenten-Paket. Vorschlag: #1063, #1100, #1106, #1091 -> **#1114** -> #1115 -> #1108 -> #1080 -> #1116/#1097 |
| **P** (Owner) | #1107, #1078, #831 durch Branch-Update heilen | alle drei an `audit` + `all-green`. #1118 belegt die Therapie: dasselbe Muster, heute gebaut, `audit` gruen |

🔴 **Mehr als drei gleichzeitige Pakete gibt der Backlog nicht her.** Engpass ist nicht die
Parallelitaet, sondern **Zufluss** (seit Lauf 55 nur zwei nachgerueckte Pakete) und **Abfluss**
(neun merge-fertige PRs, 16 fehlende Protokolle).

## 9. Geschrieben

- **#1001** Body: Fragmentzahl an zwei Stellen `404` -> **`403`** (Regel 143/145), alle Zeiger
  und Gates auf 2026-11-05 nachgezogen.
- **#989** Body: toter Beleg **#1092** -> **#1114** in §Startbedingung UND §Eskalation
  (Regel 153), Advisory-Zahl `29` -> **`28`** an drei Stellen mit Messweg/Messdatum,
  Verweis auf Weiche 46, AK6 als **uebernommen** gekennzeichnet.
- **#632** Body: zwei tote Belege in §Startbedingung korrigiert (Traeger #1092 -> #1114; der
  Satz „kein Parallel-Partner, solange #1101 offen ist" -> #1101 gemergt, Partner ist #1001,
  Welle A), ausdruecklicher Pfad-Hinweis auf `components/` in §Scope, Fragmentzahl 403,
  `npm audit` 28, Zeiger-Tabelle auf 13/13, Coverage als uebernommen gekennzeichnet.
- **#442** Body: Reihenfolge, Wellen, Gates, PR-Bestand, Datei-Sperren, Norm-Pruefung,
  Weichen-Stand; Pflege-Regeln um **Regel 175** und **Regel 176** erweitert, Regel 152/163
  verschaerft.
- **#442** Kommentar: **Weiche 46** mit drei Optionen und Empfehlung **B**.

**Weiche 45 Option A ist in diesem Lauf ausgefuehrt worden**, auf ausdrueckliche Weisung des
Auftrags („was das Repo belegt, entscheidest du selbst und schreibst es mit Beleg ins Issue"):
drei Paket-Bodies vollstaendig ueber MCP `issue_write` neu geschrieben statt kommentiert
(Regel 170). Die Attributions-Fusszeile stand in der Nutzlast jedes Writes; der Transport
entfernt sie (Regel 169, in Lauf 71 im kontrollierten Versuch belegt).

## 10. Offen

- **Weiche 46** (neu): Frist 2026-11-30 fuer `glob`/`minimatch` — 25 Tage, kein Issue.
  🟢 **Praemisse am Gate bestaetigt** (§F9): die Ignores filtern drei echte OSV-Befunde, der
  Ablauf beisst. Empfehlung **B** unveraendert, jetzt gemessen statt geschaetzt.
- **Weiche 32** (am 2026-10-29 zum Schliessen vorgeschlagen): der Schluss haelt, die
  Begruendung nicht — s. §F9 und Regel 177.
- **Weiche 45/44**: Schreibweg fuer Issue-Bodies, Festschreibung in Pflege-Regel 9 fehlt.
- **Weiche 40**: Zuschnitt von #989 (Empfehlung B, durch F8 weiter verstaerkt).
- **Weiche 11/18/36**: neun merge-fertige PRs, 16 fehlende Protokolle, drei rote
  Protokoll-PRs — alles Owner-Aufgaben.
- **Weiche 41**: `pip-audit` steht weiter nicht in `CLAUDE.md` (`grep -c` -> 0).
- 27 offene Weichen insgesamt; Stand je Weiche in #442.
