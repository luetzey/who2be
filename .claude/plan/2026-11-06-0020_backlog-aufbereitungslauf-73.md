# Backlog-Aufbereitungslauf 73

**Datum:** 2026-11-06
**Messpunkt:** `main` @ `af78ad7d` (Baum `498ded60`)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — **sechstes bitgleiches Fenster in Folge**.
`main` steht seit dem **2026-10-31T10:16+01:00** still (**6,0 Tage**).
**Warteschlange:** #442 (Label `backlog-queue`).
**Offene PRs:** **31** (waren 29 bei Lauf 72; +#1119 = dessen eigenes Protokoll, +#1120 neu).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt,
selbst entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit
drei Optionen und Empfehlung. Danach die Warteschlange neu ordnen (harte Abhängigkeit,
Owner-Vorgabe, Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere)
und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — der Server verlangt eine
Autorisierung, die diese Session nicht selbst anstoßen kann.** Persona und Playbook-Katalog lagen
im System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`, `fetch_resource`
(darunter die Norm „Agent-ready Arbeitspaket"), `record_usage` und `search_memory` nicht.
Der Lauf fährt deshalb nach dem Body von #442 und nach `.github/PROJECT.md` §Constraints.
**Keine Kurations-Rückmeldung an die eigene AgentDB — unverändert der Dauerzustand dieser
Lauf-Reihe.** Das ist nichts, was der Lauf von innen heilen kann; der Zugang muss in den
Connector-Einstellungen freigegeben werden.

## Messgrundlage

Alle Werte am 2026-11-06 auf `main` @ `af78ad7d` erhoben, **ohne vorherige Reparatur**,
Exit-Codes am unverketteten Befehl, `npm`-Gates in `apps/web/`, Node **v22.23.4**, npm **10.9.9**,
uv **0.11.32**. Klon war shallow (50) → **1666** Commits nach `--unshallow`.

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **Exit 0**, **5033** Tests |
| `changelog_fragments.py check` | **Exit 0**, **403** Fragmente _(`ls changelog.d/*.md` sagt 404; die 404. ist `README.md`)_ |
| `npm run lint` | **Exit 0**, **94** problems / **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | **Exit 0**, 0 vulnerabilities |
| `npm audit` (ohne Schwelle) | **Exit 1**, **28 moderate** — ausschließlich `glob` + `minimatch` |
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2849** Tests, Dauer **288,44 s** |
| Coverage | **89,89 / 83,95 / 86,81 / 91,75** (Statements 13163/14642, Branches 9179/10933, Functions 3793/4369, Lines 12049/13132) |

🟢 **Die Coverage-Suite ist in diesem Lauf selbst gefahren — und bestätigt die Übernahme.**
Lauf 72 hatte die Werte nach Regel 160 aus Lauf 68 **übernommen** und als übernommen
gekennzeichnet. **Alle vier Absolutpaare sind zeichengleich mit der heutigen Messung.**
Die Übernahme war also richtig; sie ist jetzt belegt statt angenommen. Abweichend ist nur die
**Dauer** (288,44 s gegen 404,04 s) — Maschinenlast, kein Inhalt.

🔴 **Ein Messfehler dieses Laufs, offengelegt:** der erste Coverage-Aufruf meldete **Exit 127**.
Ursache war **nicht** Vitest, sondern `/usr/bin/time`, das in dieser Umgebung nicht existiert —
die Shell brach ab, bevor npm startete. Neu gemessen ohne das Wrapper-Programm: Exit 0.
**Ein Exit-Code gehört dem Programm, das ihn erzeugt hat; 127 heißt „Kommando nicht gefunden"
und ist fast immer ein Fehler des Messenden.** → Regel 177.

## PR-Bestand

Scope je PR über `git merge-base` + `git diff --name-only` (Nicht-leer-Prüfung je PR),
Konfliktfreiheit über `git merge-tree --write-tree`, Rückstand über `git rev-list --count`.

- 🟢 **Alle 31 mergen konfliktfrei** (rc 0), alle 31 merge-bases rechnen.
- 🟢 **16 PRs stehen 0 Commits hinter `main`.**
- 🆕 **#1120** (`deps: bump oauthlib 4.0.0 → 4.0.1`) ist neu und **merge-fertig**:
  `all-green` namentlich `success` bei **15** ausgeführten Checks, 0 dahinter, konfliktfrei,
  kein Draft, `secrets`-Check vorhanden (gate-aktuell). ⚠️ `CodeQL` trägt `neutral` — nicht rot.
  **Damit sind es zehn merge-fertige PRs, nicht neun.**
- 🔴 **Die Zahl 29 aus Lauf 72 war richtig, nicht zu klein.** Differenz zu heute vollständig
  erklärt: **#1119** (Lauf 72s eigenes Protokoll, bei seiner Messung noch nicht offen) und
  **#1120** (eröffnet 2026-11-05T23:51Z, 21 Minuten vor diesem Lauf).
- 🔴 **Protokoll-Rückstand: 17** (#1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104,
  #1103, #1090, #1089, #1078, #1056, #1025, #1002, #990, #831); dieser Lauf legt das
  **achtzehnte** dazu.
- 🟢 **Die Verdikte für die übrigen zehn merge-fertigen und die drei eigen-roten sind aus Lauf 72
  übernommen — und die Übernahme ist belegt, nicht angenommen:** bei **jedem** dieser PRs liegt
  `updated_at` **vor** dem Messzeitpunkt von Lauf 72 (2026-11-05T00:4x), es ist seither also
  weder gepusht noch neu geprüft worden. → **Regel 178.**
  #1114 habe ich zusätzlich selbst nachgemessen: `all-green` `success`, **15** Checks, `CodeQL`
  `neutral`. 🟢 **Regel 59 selbst reproduziert:** `get_status` liefert auf #1114
  `state: pending, total_count: 0` — unbrauchbar, `get_check_runs` ist der Weg.

### Datei-Sperren — gemessen gegen alle 31 offenen PRs

Die 31 PRs bewegen zusammen **48** Dateipfade. Die vollständige Trägertabelle:

| Pfad | Träger |
|---|---|
| `.claude/context/STATE.md` | **#1078, #1090, #1103** (unverändert drei) |
| `.github/PROJECT.md` | **#1105** |
| `uv.lock` | 🔴 **#1080, #1108, #1115, #1120** — **vier, waren drei** |
| `apps/web/package.json` + `package-lock.json` | **#674, #1114** |
| `.github/workflows/ci.yml` | **#1091** |
| `deploy/monitor/compose.yml` | **#1097, #1116** |
| `apps/web/src/**` | 🟢 **kein einziger PR** — der ganze Vitest-Baum ist frei |
| `docs/mcp-payload-budget.md`, `apps/mcp/**` | 🟢 **frei** |
| `apps/web/osv-scanner.toml`, `changelog.d/osv-*` | 🟢 **frei** |

## Die vier Funde des Laufs

### 1. 🔴 #989 schreibt einen Befehl vor, der das Gegenteil seines Zwecks tut

#989s §Vorentschieden sagt: „*`npm audit fix`, weil der Dry-Run genau einen transitiven Sprung
liefert*". **Heute in `apps/web/` selbst gefahren (`--dry-run`, Baum nachweislich unverändert):**

| Befehl | echte Änderungen | bewegt `http-cache-semantics`? |
|---|---|---|
| `npm audit fix --dry-run` | 🔴 **22** | 🔴 **nein, 0×** |
| `npm update http-cache-semantics --dry-run` | 🟢 **1** | 🟢 **ja: `4.2.0 => 4.3.0`** |

Die 22 Änderungen von `audit fix`: `minimatch` 10.2.5→10.2.6 (**7** Kopien), `eslint`
10.12.0→10.14.0, die **elf** Pakete der `@typescript-eslint`-Familie 8.71.2→8.72.1, dazu
`typescript-eslint`, `semver`, `pacote`, `ignore`. _(Die je 42 `add`-Zeilen beider Dry-Runs sind
Plattform-Optionals — `lightningcss`, `@tailwindcss/oxide`, `fsevents`; **null** davon ist ein
Nicht-Plattform-Paket. Sie sind ein Artefakt des Dry-Runs, kein Diff.)_

🔴 **Ein Agent mit leerem Kontext, der diesem Body folgt, verletzt AK5 („genau zwei
Produktivdateien") mit einem 22-Paket-Diff und erfüllt AK1 trotzdem nicht.** Das ist keine
verrottete Zahl, das ist ein Mechanismus, der nicht zum Ziel führt — dieselbe Klasse wie die
schädliche AK2, die Lauf 68 aus diesem Body entfernt hat.

🟢 **Der funktionierende Weg ist belegt und liegt im Range der Eltern:**
`make-fetch-happen@15.0.6` deklariert `http-cache-semantics: ^4.1.1` (aus dem Lockfile gelesen),
`4.3.0` ist auf der Registry `latest` — der Sprung braucht **kein** `overrides`.
Kette: `who2be-web → license-checker-rseidelsohn@5.0.1 → @npmcli/arborist@9.6.0 →
npm-registry-fetch@19.1.1 → make-fetch-happen@15.0.6 → http-cache-semantics@4.2.0`.
**Im Body korrigiert** (Regel 152/153/170).

⚠️ **Nebenbefund zu AK2:** `audit fix` hebt `minimatch` auf **10.2.6** — und **10.2.6 ist im
`reason`-String der Ausnahme selbst als betroffen genannt** (`minimatch@10.2.5/10.2.6/3.1.5`).
Dieser Teil des „Fixes" bewegt den Baum, ohne den Fund zu entfernen. Bestand heute:
`minimatch` 10.2.5 ×7, 10.2.6 ×1, 3.1.5 ×1; `glob` 13.0.6 ×1.

### 2. 🔴 Eine Zahl in #632 trennt nicht zwischen Vorkommen und Aufrufstelle

#632 §Vorentschieden 4 sagt: „*`createUser` kommt in sieben davon vor, die **37** der Körper
tragen*". **Heute Datei für Datei gezählt:**

| Messung | Wert |
|---|---|
| Vorkommen der Zeichenkette `createUser` | **39** |
| davon Aufrufstellen `await createUser(` | 🟢 **31** |
| Dateien mit mindestens einem Aufruf | **7** von 9 |

**37 ist keine von beiden Zahlen.** Richtig ist: **31 Aufrufstellen**, **39** Vorkommen.
Im Body korrigiert.

🟢 **Die Testzahl 43 aus Lauf 72 hält — und die Partition schließt jetzt dreifach:**
`^test(` → **42**, `^test.skip(` → **1**, zusammen **43** Deklarationen; naiv `test(` irgendwo →
**44**, die 44. ist `expectedName.test(…)` in `scroll-guard.spec.ts`. **Meine erste Sonde las 42
und war das engere Muster, nicht ein Widerspruch** — notiert, bevor daraus ein Fund wurde.

### 3. 🔴 NEU: `package.json` widerspricht sich in einer Datei — und niemand hat ein Issue dafür

`apps/web/package.json` sagt an **`:8`** `engines.node` `">=22 <23"` (und `.nvmrc` im Repo-Root
sagt `22`). Dieselbe Datei deklariert an **`:74`** `license-checker-rseidelsohn` als `^5.0.1`,
aufgelöst auf **5.0.1** — und dessen `engines` verlangen **`node >=24`, `npm >=11`**
(von der Registry gelesen). Die Umgebung fährt Node **v22.23.4** und npm **10.9.9**.

**Folge, heute beobachtet:** jeder Install-Lauf schreibt
`npm warn EBADENGINE Unsupported engine { package: 'license-checker-rseidelsohn@5.0.1',
required: { node: '>=24', npm: '>=11' }, current: { node: 'v22.23.4', npm: '10.9.9' } }`.
Es ist eine **Warnung**, kein Fehler — das Gate bleibt grün. Aber das Werkzeug wird im CI-Job
`audit` scharf ausgeführt (`npm run license:check`, `package.json:19`, `ci.yml:1029`), also läuft
ein Lizenz-Gate auf einer Node-Version, die der Hersteller nicht mehr stützt.

🔴 **Kein offenes Issue deckt das ab**, und es verschränkt sich mit Weiche 46: der
`glob`/`minimatch`-Fix-Pfad führt über dieselbe Paket-Familie, und #632s Body hält fest, dass
**Node 25+ rund 135 Vitest-Tests kippt**. Die Frist ist in **24 Tagen**.
→ **Weiche 47**, neu, als Kommentar an #442.

### 4. 🟢 Der Protokoll-Rückstand ist kleiner als er aussieht — 14 der 17 sind in einem Zug mergebar

Aus der Trägertabelle folgt eine Eigenschaft, die bisher nicht ausgesprochen war: **von den 17
offenen Protokoll-PRs berühren 14 genau eine Datei — ihre eigene, neu angelegte Plan-Datei** und
sonst nichts. Sie sind damit **paarweise und gegen jeden anderen offenen PR konfliktfrei** und in
**beliebiger Reihenfolge** mergebar. Nur **drei** (#1078, #1090, #1103) fassen zusätzlich
`.claude/context/STATE.md` an und müssen seriell laufen.

**Das macht aus dem größten Posten der Warteschlange eine Aufgabe von einem Durchgang:**
14 Merges ohne Reihenfolge-Zwang, dann drei serielle. Weiche 18 („in welcher Kadenz?") und
Weiche 11/34 („wer mergt?") bekommen damit erstmals eine Mengen-Aussage statt einer Klage.
→ im Kommentar zu Weiche 11/34 nachgetragen.

🟢 **Dieser Lauf hält die Eigenschaft bewusst aufrecht:** sein PR fasst **nur** die eigene
Plan-Datei an, nicht `STATE.md` und nicht `.github/PROJECT.md` — damit er der fünfzehnte
konfliktfreie ist und nicht der vierte serielle.

## Norm-Prüfung „Agent-ready Arbeitspaket" — 4 von 4 vollständig

Vier Pflichtabschnitte (`.github/PROJECT.md` §Constraints): **Outcome** · **prüfbare
Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**.

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Zeiger | Urteil |
|---|---|---|---|---|---|---|
| **#632** | ✅ | ✅ 5 | ✅ `**Out:**` | ✅ | 🟢 **13/13 gültig** | 🟢 vollständig — 🔴 `createUser`-Zahl korrigiert |
| **#633** | ✅ | ✅ 6 | ✅ `**Out:**` | ✅ | 🟢 E2E-Rechnung dreifach geschlossen | 🟢 vollständig |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **5/5 gültig** | 🟢 vollständig |
| **#989** | ✅ | ✅ 6 | ✅ | ✅ | 🟢 alle AK-Zeiger gültig | 🟢 vollständig — 🔴 **Mechanismus korrigiert** _(`needs-decision`, Weichen 40/46/47)_ |

**Einzeln nachgemessen am 2026-11-06:** `MfaSection.tsx` **297** · `MfaSection.test.tsx` **284** ·
`MfaSection.a11y.test.tsx` **45** · `SessionProvider.tsx` **267** · `audit.test.ts` **371** ·
`LoginPage.tsx` **399** · `apps/web/package.json` **82** (`engines.node` `:8`) ·
`vite.config.ts` **107** · `e2e/helpers/auth.ts` **199** (`createUser` `:33`) ·
`api/client.ts` **1849** · `api/types.ts` **2407** · `test/a11y.test.ts` **77** ·
`orphan-baseline.json` **156** (flache Liste) · `de.json`/`en.json` je **4.661** Zeilen und je
**3.365** flache Schlüssel (Parität nachgerechnet) · `ci.yml` **1259** (`:325` `test:a11y`,
`:780` `changelog-guard`, `:1029` `license:check` — wörtlich bestätigt) ·
`osv-scanner.toml` **26** (`ignoreUntil = 2026-11-30` an `:11` und `:19`, `IgnoredVulns` 2×) ·
`docs/mcp-payload-budget.md` **609** (`104.777` an `:233`/`:292`/`:327`/`:487`, `108.262` an
`:234`/`:331`, `71.738` an `:236`/`:335`, Kopf `:254` „Stand 2026-10-27" ohne Commit) ·
`package-lock.json` `http-cache-semantics` **4.2.0** an `:6295`/`:6296`.

🟢 **#632: siebter Lauf in Folge mit null verrotteten Zeigern.**
**Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben, keines entzogen.**
Begründung: die Funde betrafen einen **Mechanismus** (#989) und eine **Bezugszahl** (#632),
keinen Pflichtabschnitt — und beide sind korrigiert, nicht kommentiert.

**Norm-Stand der acht übrigen Bodies — unverändert, bewusst nicht umgebaut:** Outcome fehlt in
#542, #535, #428; Verifikations-Abschnitt fehlt in #535 und #428; #454 hat ihn mit „Kein
Testkommando — die Verifikation ist die Produktions-Smoke-Reise"; #338 trägt keine
Abschnitts-Überschriften; #540 trägt alle vier und bleibt `needs-decision`, weil die
Mechanismus-Entscheidung fehlt, nicht ein Feld; #435 trägt Outcome nur inline.
**Ein `size/M`-Issue wird nicht durch Nachtragen von Feldern startbar** (PROJECT.md §Constraints).

## Reihenfolge und Wellen

Kriterien: **1** harte Abhängigkeit · **2** Owner-Vorgabe · **3** Fundament vor Fläche ·
**4** Inventar vor Zuschnitt · **5** bei Gleichstand das kleinere.

| Pos | Issue | Größe | Baum | Kriterium | Stand |
|---|---|---|---|---|---|
| **1** | **#632** Passkey registrieren | `size/S` | Web/Vitest | 3 (öffnet #633) | 🟢 startbar ohne Nebenbedingung |
| **2** | **#1001** Payload-Budget | `size/S` | Python/pytest | 4 | 🟢 startbar ohne Nebenbedingung |
| **3** | **#633** Step-up mit Passkey | `size/S` | Web | 1 (nach #632) | 🔴 zwei Blocker: #632 + Container-Laufzeit **oder** CI |
| **4** | **#989** `http-cache-semantics` | `size/S` | Web/Lockfile | 1 (nach #1114) | 🔴 Lockfile-Sperre #1114/#674 + offene Weichen 40/46/47 |

| Welle | Inhalt | Bedingung |
|---|---|---|
| 🟢 **A** | **#632 + #1001** | Web/Vitest gegen Python/pytest, code-disjunkt, beide Flächen über alle 31 PRs frei. ⚠️ gemeinsame DoD-Fläche `STATE.md` → wer zweiter fertig wird, rebasiert (Basis **#1103**) |
| **B** | **#633** | nach #632 (hart) und nach Container-Laufzeit **oder** CI |
| **C** | **#989** | nach **#1114** (merge-fertig) — die Lockfile-Sperre ist der einzige mechanische Blocker, jetzt mit belegtem Ein-Zeilen-Weg |
| **M** _(Owner)_ | **zehn merge-fertige PRs** | #1063, #1080, #1091, #1100, #1106, #1108, #1114, #1115, #1116, **#1120**. Seriell: `uv.lock` **vierfach** (#1115 → #1108 → #1080 → #1120, jeweils neu messen) · `apps/web/package*.json` (#1114 vor/gegen #674) · `deploy/monitor/compose.yml` (#1097/#1116). **#1114 zuerst — es entsperrt Welle C** |
| **N** _(Owner)_ | **14 Protokoll-PRs in einem Zug** | #1119, #1118, #1117, #1113, #1112, #1107, #1105, #1104, #1089, #1056, #1025, #1002, #990, #831 — je **eine** Datei, paarweise konfliktfrei, **beliebige Reihenfolge**. Danach seriell #1103 → #1090 → #1078 (`STATE.md`) |
| **P** _(Owner)_ | #1107, #1078, #831 durch Branch-Update heilen | alle drei rot an `audit` + `all-green`, dieselbe Ursache; #1120 belegt heute erneut, dass ein aktueller Stand grün ist |

🔴 **Mehr als drei gleichzeitige Pakete gibt der Backlog nicht her** — vier offene
Arbeitspakete, zwei davon blockiert. **Der Engpass ist der Abfluss, nicht die Parallelität:**
zehn merge-fertige PRs und achtzehn Protokolle warten, und `main` steht seit sechs Tagen still.

## Offene Weichen

**27 bestehende werden nicht erneut gestellt.** Dieser Lauf ändert zwei und legt eine dazu:

- 🆕 🔴 **47 NEU: Wie wird der Node-Boden aufgelöst — `license-checker-rseidelsohn@5.0.1`
  verlangt Node ≥24, `package.json` erlaubt `<23`?** Drei Optionen + Empfehlung als Kommentar
  an #442. Empfehlung **B** (Werkzeug auf die letzte Node-22-Fassung pinnen, den Node-Sprung als
  eigenes Paket hinter Weiche 46).
- 🔄 🔴 **40 (behält #989 einen Platz?): Empfehlung wechselt von B zu A** — neu gerechnet, nicht
  fortgeschrieben. B („auf `size/XS` zuschneiden, den 4.3.0-Bump streichen") stand auf der
  Annahme, der Bump habe keinen sauberen Weg. **Das ist heute widerlegt:**
  `npm update http-cache-semantics` bewegt genau eine Zeile, im Range der Eltern, ohne
  `overrides`. Der einzige Blocker ist die Lockfile-Sperre von #1114 — und #1114 ist
  merge-fertig. **A: Paket ganz behalten, nach #1114 starten.**
- 🔄 🔴 **46 (`glob`/`minimatch`-Frist): die Frist ist jetzt 24 Tage entfernt**, und der
  Fix-Pfad ist durch Weiche 47 teurer als gedacht — die Major-Migration hängt am Node-Boden.
  Empfehlung **B** bleibt, mit dem Zusatz: Fristverlängerung und Node-Entscheidung gehören in
  **einen** Vorgang.
- 🔄 🔴 **11/34 (wer mergt?): erstmals mit Mengen-Aussage** — 14 der 17 Protokoll-PRs sind in
  beliebiger Reihenfolge mergebar (Fund 4), nur drei seriell.

## Neue Pflege-Regeln

- **177. Ein Exit-Code gehört dem Programm, das ihn erzeugt hat.** `127` heißt „Kommando nicht
  gefunden" und ist fast immer ein Fehler des Messenden, nicht ein Fund am Baum. Wrapper
  (`/usr/bin/time`, `timeout`, `stdbuf`) vor der Messung auf Existenz belegen — sonst misst man
  die eigene Shell. _(Dieser Lauf hat den Fehler selbst gemacht.)_
- **178. Ein übernommenes Verdikt braucht einen Beleg, dass es übernehmbar ist.**
  Für PR-Zustände ist das `updated_at`: liegt es vor dem Messzeitpunkt des Laufs, von dem
  übernommen wird, ist seither nicht gepusht und nicht neu geprüft worden. Ohne diesen Abgleich
  ist eine Übernahme eine Fortschreibung.
- **179. Ein vorgeschriebener Befehl ist eine Zusicherung und wird wie ein Zeiger geprüft.**
  Ein `--dry-run` kostet Sekunden und belegt, ob der Befehl die Änderung macht, die das Paket
  beschreibt. #989 trug zwei Läufe lang einen Befehl, der sein eigenes AK1 nicht erreicht.
- **180. Plattform-Optionals in einem npm-Dry-Run sind kein Diff.** `lightningcss`,
  `@tailwindcss/oxide`, `fsevents` erscheinen als `add`, weil sie für andere Plattformen gelten.
  Gezählt werden `change`/`remove`, nicht `add`.

## Doku-Nachzug

Keiner nötig: dieser Lauf ändert kein öffentliches Verhalten (keine API-Signatur, kein
CLI-Flag, keine Konfig, kein Setup). Die Änderungen liegen in Issue-Bodies auf GitHub und in
diesem Protokoll. **Kein CHANGELOG-Fragment** — der Fragment-Bestand bleibt bei **403**.
