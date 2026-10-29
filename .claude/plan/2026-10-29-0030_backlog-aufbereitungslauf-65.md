# Backlog-Aufbereitungslauf 65

**Datum:** 2026-10-29
**Messpunkt:** `main` @ `14234887` (`deps(security): authlib 1.9.1 + dnspython 2.9.0 in uv.lock`, #1099)
**Fenster seit dem letzten Messpunkt (Lauf 64, `14234887`):** **0 Commits** — der Baum ist bitgleich.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf neu geschrieben.

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" pruefen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhaengigkeit, Owner-Vorgabe,
Fundament vor Flaeche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — der Server verlangt eine
Autorisierung, die diese Session nicht selbst starten kann.** Weder `get_persona`, `list_triggers`,
`fetch_playbook`/`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket", `73a86231`) noch
`record_usage`/`search_memory` standen zur Verfuegung. Persona und Playbook-Katalog lagen im
System-Prompt vor. Der Lauf faehrt deshalb nach `.github/PROJECT.md` §Constraints (die dort
kodifizierte Norm) und nach den Pflege-Regeln im Body von #442. **Kein passendes Playbook
geladen — und zum wiederholten Mal keine Kurations-Rueckmeldung an die eigene AgentDB.**

## Messgrundlage

Alle Werte am 2026-10-29 auf `main` @ `14234887` erhoben, Exit-Codes **ohne Pipe** (Regel 94),
ohne vorherige Reparatur (Regel 120), `npm`-Gates in `apps/web/` (Regel 146). Node **v22.22.0**.
Der Klon war **shallow** (50 Commits); nach `git fetch --unshallow`: **1661** Commits (Regel 90).

| Gate | Ergebnis | gegen Lauf 64 |
|---|---|---|
| `npm run test:coverage` | **Exit 0**, **282** Dateien / **2849** Tests, **282,28 s** | Dateien/Tests **gleich**, Dauer −22,10 s |
| Coverage | **89,89 / 83,95 / 86,81 / 91,75** — Statements 13163/14642, Branches **9179/10933**, Functions 3793/4369, Lines 12049/13132 | **alle vier Absolutpaare bitgleich** |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar | gleich |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** | gleich |
| `npm run i18n:check` | **Exit 0**, **156** bekannte Waisen; `de.json`/`en.json` je **3.365** Schluessel | gleich |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** | gleich |
| `npm audit` (voll, ohne Pipe) | 🟢 **Exit 0, 0 vulnerabilities** | 🔴 **war rc 1 / 1 high — siehe Fund 1** |
| `uv run ruff check .` | **Exit 0**, 0 Funde | gleich |
| `uv run mypy .` | **Exit 0**, 0 Funde in **655** Dateien | gleich |
| `uv run pytest --collect-only -q` | **4971** Tests, **312** unter `packages/billing/` | gleich |
| `changelog_fragments.py check` | **Exit 0** | gleich |
| `payload_report` | **103** Werkzeuge / **108.251** Bytes, `instructions` 1.732 | **sechste** identische Messung |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` | **41. Messung in Folge** |
| `main`-CI | `14234887`: **24** `success`, **1** `skipped` (`deploy`), **0** rot; `all-green` success, `status`/`conclusion` getrennt gelesen (Regel 91) | gleich |

**Fundstellen, einzeln gelesen:** `ci.yml` **1259** Zeilen · `vite.config.ts` **107** · `package.json`
(web) **82** · `MfaSection.tsx` **297** · `LoginPage.tsx` **399** · `SessionProvider.tsx` **267** ·
`e2e/helpers/auth.ts` **199** (`createUser` auf `:33`) · `api/client.ts` **1849** ·
`api/types.ts` **2407** · `i18n/audit.test.ts` **371** · `orphan-baseline.json` **156** (flache
Liste) · `Caddyfile` **208**, `rate` **0×** · `plans.md` **271** · `src/test/a11y.test.ts` **77** ·
GoTrue **v2.197.0** an allen drei Stellen (`docker-compose.yml:63`,
`deploy/hetzner/supabase/docker-compose.yml:92`, `deploy/dokploy/docker-compose.yml:115`).

## PR-Bestand

**23 offene PRs** (waren 22; **+1**, und das ist #1103, das Protokoll von Lauf 64).
🔴 **Gemergt im Fenster: 0. Gestartet: 0.** Scope je PR ueber `git merge-base` + `git diff
--name-only` mit Nicht-leer-Pruefung, Konfliktfreiheit ueber `git merge-tree --write-tree`,
CI ueber die Check-Runs am Head mit positivem Filter auf `failure`/`timed_out` (Regel 101).

- 🟢 **Alle 23 mergen konfliktfrei** (rc 0).
- 🟢 **Elf grün bei hoechstens 4 Commits Rueckstand:** #1101, #1102, #1098, #1085 (je **0**),
  #1091, #1092, #1093, #1094, #1095, #1096, #1097 (je **4**).
- 🔴 **Drei rot:** **#674** (8 Checks, 4 hinter), **#1100** (`audit` + `all-green`, **1** hinter),
  **#1080** (`audit` + `all-green`, 18 hinter).
- 🔴 **Protokoll-Rueckstand: 9** (#1103, #1090, #1089, #1078, #1056, #1025, #1002, #990, #831);
  dieser Lauf legt das **zehnte** dazu.
- Gate-alt im harten Sinn bleibt **#831** (**222** hinter).

## Die vier Funde des Laufs

### 1. 🔴 Die Frist, die das Backlog seit neun Laeufen treibt, hat ihre Grundlage verloren — an einem Baum, der sich nicht bewegt hat

`npm audit` in `apps/web/` meldet **Exit 0, 0 vulnerabilities**. Die Laeufe **63 und 64** haben an
**demselben** Baum **rc 1, 1 high** gemessen, `http-cache-semantics <=4.2.0`, mit dem Zusatz
„fix available via `npm audit fix`" — Lauf 64 hat diesen Satz ausdruecklich als Widerlegung der
Ignore-Begruendung angefuehrt.

**Der Baum ist nicht die Ursache:**

| Beleg | Wert |
|---|---|
| `main` im Fenster | **0** Commits |
| `apps/web/package-lock.json:6296` | weiter **4.2.0** |
| `npm ls http-cache-semantics --all` | **ein** Pfad, unveraendert: `license-checker-rseidelsohn@5.0.1 → @npmcli/arborist@9.6.0 → npm-registry-fetch@19.1.1 → make-fetch-happen@15.0.6 → http-cache-semantics@4.2.0` |
| `apps/web/osv-scanner.toml:11` | `ignoreUntil = 2026-11-02T00:00:00Z`, unveraendert |

**Was sich bewegt hat, liegt ausserhalb des Repos.** Gegenprobe direkt an der Quelle, die
`npm audit` liest:

```
POST https://registry.npmjs.org/-/npm/v1/security/advisories/bulk
{"http-cache-semantics":["4.2.0"]}
→ {} (leer)
```

**Die npm-Advisory-Datenbank fuehrt fuer `http-cache-semantics@4.2.0` kein Advisory mehr.**
GHSA-ch52-4w7c-c8xp ist dort also zurueckgezogen oder in seinem Versionsbereich eingeengt worden,
und zwar zwischen dem 2026-10-28 und dem 2026-10-29.

🔴 **Was dieser Lauf NICHT belegen kann, und das ist der entscheidende Teil:** das Gate ist nicht
`npm audit`, sondern **`osv-scanner`** (`ci.yml:1077`), und der liest **OSV**, nicht die
npm-Registry. Drei Wege, das zu messen, sind in dieser Umgebung zu:

1. `api.osv.dev` ist durch die Netz-Policy gesperrt (`connect_rejected`).
2. Der Advisory-Endpunkt von GitHub ist fuer diese Session nicht erreichbar (repo-gebunden, 403).
3. Die osv-scanner-Binary **v2.2.4** liess sich laden und ihr SHA256 stimmt byte-genau mit dem
   CI-Pin (`ci.yml:1060`) ueberein — **ihre Ausfuehrung wurde verweigert**, und es gibt keine
   Container-Laufzeit als Ausweichweg (41. Messung).

🟢 **Und es gibt einen vierten Weg, der von selbst laeuft:** seit dem 2026-10-28T00:31 ist
**kein** CI-Lauf gestartet. **Der `audit`-Job des Protokoll-PRs dieses Laufs ist damit die
Messung** — er faehrt osv-scanner gegen dieselbe Lockfile-Zeile und beantwortet die Frage, ohne
dass jemand etwas anfassen muss.

**Folge fuer #989:** Akzeptanzkriterium 3 („`npm audit --audit-level=high` → Exit 0, 0
vulnerabilities"; der Body sagte „heute: Exit 1, 1 high") ist **ohne jede Aenderung erfuellt**.
AK1 (Lockfile auf 4.3.0) und AK2 (Ignore-Block weg) sind unberuehrt — **und AK2 ist jetzt besser
begruendet als vorher**: ein Ignore-Eintrag fuer ein Advisory, das seine Datenbank nicht mehr
fuehrt, ist tote Konfiguration. **Das Paket ist nicht entfallen, es ist billiger geworden.**

🔴 **Die Lehre liegt nicht bei `http-cache-semantics`.** Neun Laeufe haben eine Frist als
haertestes Sortierkriterium gefuehrt (Owner-Vorgabe, Weiche 32, Position 1) und ihre Grundlage
**nie** nachgemessen — weil sie ausserhalb des Repos liegt und das Verfahren nur den Baum prueft.
→ **Weiche 37 (neu).**

### 2. 🔴 Zwei `agent-ready`-Bodies tragen seit zehn Tagen eine Anweisung, die das Repo zurueckweist

§Zusaetzliche Grenzen in **#632** und **#633** sagt wortgleich:

> **Einen neuen axe-Fall nur mit explizitem Timeout oder in der Namensform `*.a11y.test.tsx`**
> (#975 — **43** offene Stellen in **20** Dateien, Stand 2026-10-19).

**#975 ist seit dem 2026-10-28 geschlossen (`completed`) — und seine Umsetzung hat die Regel
umgedreht.** Auf `main` liegt `apps/web/src/test/a11y.test.ts` (**77** Zeilen), ein Waechter mit
genau dieser Zusicherung:

> *„jede axe-Testdatei ausserhalb von `*.a11y.test.tsx` nutzt den Helfer"* — und im Kommentar:
> *„Wer `vitest-axe` direkt importiert, laeuft wieder mit 5 s — genau der Fall, der main rot
> gemacht hat."*

🔴 **Wer der Anweisung in den Bodies folgt, macht `web` rot.** Ein „explizites Timeout" mit
direktem `vitest-axe`-Import ist genau der Fall, den `bypassesHelper` als Verstoss meldet. Richtig
ist heute: **axe ueber `@/test/a11y` beziehen** (Alias oder relativ), dann setzt
`A11Y_TEST_TIMEOUT_MS` das Timeout selbst.

Die Zahlen im selben Satz stimmen ebenfalls nicht mehr: axe-Aufrufe liegen heute in **33** Dateien
ausserhalb des a11y-Projekts (**nicht 20**), und die Untergrenze im Waechter steht auf **20**.

⚠️ **Der Nebenbefund aus Lauf 55 ist unveraendert wahr, nur verschoben:** `vite.config.ts` schreibt
das Glob an zwei Stellen verschieden — `:20` `src/**/*.a11y.test.tsx`, `:90`
`src/**/*.a11y.test.{ts,tsx}`. Der Waechter haengt an **keinem** von beiden (eigenes RegExp), die
Warnung in #633 bleibt also berechtigt — **mit neuen Zeigern**.

**In beiden Bodies korrigiert.** → **Weiche 37** betrifft genau diesen Mechanismus: die Anweisung
stand in einem Issue-Body, ihre Wahrheit in einem anderen Issue, und das Schliessen des einen hat
das andere nicht erreicht.

### 3. 🔴 Der STATE.md-Vermerk in #632 und #633 nennt einen PR, der seit neun Tagen geschlossen ist — und die Sperre ist in Wahrheit dreifach

Beide Bodies sagen in §Definition of Done:

> ⚠️ **`STATE.md` ist weiterhin von PR #823 belegt** (Draft, gate-alt …, **126** Commits hinter
> `main`, Inhalt vom 2026-10-02) — vor dem Schreiben den Stand von #823 pruefen; zu #823 selbst
> steht **Weiche 10** in #442.

| Aussage | gemessen |
|---|---|
| #823 ist ein offener PR | 🔴 **geschlossen, nicht gemergt**, `closed_at 2026-10-20T05:06:23Z` |
| #823 haelt `STATE.md` | 🔴 **nein** — #823 ist nicht in der Liste der 23 offenen PRs |
| **126** Commits hinter `main` | 🔴 gegenstandslos |
| Traeger von `.claude/context/STATE.md` | 🔴 **drei offene PRs: #1103, #1090, #1078** — alle drei Protokolle dieses Verfahrens |

🔴 **Die Lage ist schlechter, nicht besser, als der Vermerk sagt.** Jedes Paket schreibt in seiner
DoD `STATE.md`, und diese Datei wird von **drei** offenen PRs gehalten — der Protokoll-Rueckstand
ist damit nicht nur ein Zaehler im Bericht, er ist eine **dreifache Schreibsperre auf der Datei,
die jedes Paket laut DoD anfassen muss**. Dieser Lauf legt den vierten Traeger dazu.
🟢 `.github/PROJECT.md` ist ueber alle 23 PRs **frei**.

**In beiden Bodies korrigiert.**

### 4. ⚠️ Zwoelf Zeiger in #632/#633 sind verrottet, und einer der Fehler ist in #442 selbst

`ci.yml` ist von **1212** auf **1259** Zeilen gewachsen, `vite.config.ts` von **89** auf **107** —
jeder Zeiger darin ist gewandert. #632/#633 standen auf dem Stand von Lauf 58 (2026-10-22).

| Zeiger | stand (Body) | gemessen | Datei |
|---|---|---|---|
| `--project=chromium`, scharfer E2E-Job | `:423` | **`:463`** | `ci.yml` |
| `--project=chromium`, Billing-Job | `:503` | **`:544`** | `ci.yml` |
| Job `changelog-guard` | `:737` | **`:780`** | `ci.yml` |
| zweiter Step (prueft den **Bestand**), Step-Name | `:784` | **`:828`** | `ci.yml` |
| dessen `run`-Zeile | `:800` | **`:844`** | `ci.yml` |
| `npm run license:check` | `:983` | **`:1029`** | `ci.yml` |
| `npm run test:a11y` | `:296` | **`:325`** | `ci.yml` |
| `thresholds:` | `:81` bzw. `:93` | **`:99`** | `vite.config.ts` |
| die vier Schwellenwerte | `:82-85` bzw. `:93-98` | **`:100-103`** | `vite.config.ts` |
| `coverage`-Block beginnt | `:67` | **`:85`** | `vite.config.ts` |
| `A11Y_TEST_GLOB` / Coverage-Exclude | `:15` / `:72` | **`:20`** / **`:90`** | `vite.config.ts` |
| `api/client.ts` | 1772 | **1849** | — |
| `api/types.ts` | 2402 | **2407** | — |
| `e2e/helpers/auth.ts` | 180 | **199** | — |
| Locale-Schluessel je Datei | 3216 | **3.365** | — |
| `orphan-baseline.json` | 160 | **156** | — |
| Branches-Abstand zum Boden | **4,67** (83,67 / `7993/9553`) | **4,95** (**83,95** / `9179/10933`) | — |

🔴 **Und in #442 selbst:** Lauf 64 nennt die Schwellen `apps/web/vite.config.ts:100-104`.
Gemessen sind **`:100-103`** — `:99` ist der `thresholds:`-Schluessel, `:104` ist die schliessende
Klammer. Eine Zeile zu weit, in genau der Datei, die die Pflege-Regeln als Beispiel fuer
nachgemessene Zeiger fuehren. **Richtiggestellt.**

🟢 **Unveraendert richtig und einzeln gegengelesen:** `MfaSection.tsx` **297**, `LoginPage.tsx`
**399**, `SessionProvider.tsx` **267**, `audit.test.ts` **371**, `createUser` auf
`e2e/helpers/auth.ts:33`.
⚠️ **Nicht mehr aktuell, aber harmlos:** die Eskalation in #633 nennt einen Versatz
`vitest` 4.1.11 gegen `coverage-v8` 4.1.10 — beide stehen heute auf **`^4.1.12`**
(`apps/web/package.json:66`/`:79`). **Entfernt.**

## Gegenprobe zu Lauf 64s Coverage-Warnung (Regel 148)

Lauf 64 hat seine Prozente als „zeichengleich mit Lauf 63 bei veraendertem Baum" markiert und als
Zufall gefuehrt, weil Lauf 63 keine Absolutzahlen festgehalten hat. **Dieser Lauf misst denselben
Baum und bekommt alle vier Absolutpaare bitgleich zurueck** (13163/14642 · 9179/10933 ·
3793/4369 · 12049/13132) bei **282** Dateien / **2849** Tests.

🟢 **Damit ist die Suite an einem unveraenderten Baum als deterministisch belegt** — und ab jetzt
ist eine veraenderte Prozentzahl ein Beleg fuer einen veraenderten Baum, nicht fuer Rauschen.
🔴 **Fuer das Paar 63 ↔ 64 bleibt es unentscheidbar**, weil Lauf 63 seine Absolutzahlen nicht
festgehalten hat. Regel 148 ist also richtig und kam einen Lauf zu spaet. → **Regel 150.**

## Norm-Stand ueber alle 12 offenen Issues

Geprueft werden die vier Pflichtabschnitte aus `.github/PROJECT.md` §Constraints: **Outcome** ·
**pruefbare Akzeptanzkriterien** · **Out-of-Scope** · **exakte Verifikations-Kommandos**. Jeder
maschinelle Negativ-Befund von Hand gegengelesen (Pflege-Regel 10).

| Issue | Outcome | AK | Out-of-Scope | Verifikation | Urteil |
|---|---|---|---|---|---|
| **#989** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **vollstaendig** |
| **#1001** | ✅ | ✅ 5 | ✅ | ✅ | 🟢 **vollstaendig** |
| **#632** | ✅ | ✅ | ✅ (`**Out:**`) | ✅ | 🟢 **vollstaendig** |
| **#633** | ✅ | ✅ | ✅ (`**Out:**`) | ✅ | 🟢 **vollstaendig** |

**4 von 4 — unveraendert.** ⚠️ Die Schreibvariante `**Out:**` statt `**Out of Scope**` in
#632/#633 ist zum vierten Mal von Hand gegengelesen und bleibt eine Variante, keine Luecke.

🔴 **Aber: Vollstaendigkeit ist nicht Richtigkeit.** #632 und #633 waren in jedem Lauf seit 58
„4 von 4" — und trugen dabei eine Anweisung, die `main` rot macht (Fund 2), einen Vermerk auf
einen geschlossenen PR (Fund 3) und zwoelf verrottete Zeiger (Fund 4). **Die Norm prueft, ob die
vier Abschnitte DA sind, nicht ob ihr Inhalt heute noch gilt.** → **Regel 151.**

**Norm-Stand der acht uebrigen Bodies — unveraendert:** Scope-„In" fehlt in #542, #540, #535,
#454, #428, #338 · Verifikations-Abschnitt fehlt in #535, #428, #338 · #454 hat ihn, sagt dort
aber woertlich „Kein Testkommando" · #338 traegt ueberhaupt keine Abschnitts-Ueberschriften.
**Bewusst nicht umgebaut** (Regel 7, Weiche 4): #542/#454/#338 sind `human-only`, #535/#428/#435
sind `size/M` und werden laut Constraint **nie** durch Nachtragen von Feldern startbar.

## Reihenfolge

Sortierkriterien in dieser Ordnung: **harte Abhaengigkeit → Owner-Vorgabe → Fundament vor Flaeche
→ Inventar vor Zuschnitt → bei Gleichstand das kleinere.**

| Pos | Issue | Groesse | Baum | Kriterium | Zustand |
|---|---|---|---|---|---|
| **1** | **#989** `http-cache-semantics` → 4.3.0 | `size/S` | Web | **2** (Owner-Vorgabe: Frist im Repo) | 🟢 **startbar und in diesem Lauf billiger geworden** — AK3 ist ohne Aenderung erfuellt, AK2 besser begruendet. ⚠️ Die Frist steht weiter in `osv-scanner.toml:11`; ob sie beisst, beantwortet der `audit`-Job des Protokoll-PRs (Fund 1). Lockfile-Sperre: **#1092** (grün, 4 hinter) und **#674** (rot) |
| **2** | **#632** Passkey registrieren und entfernen (#435 W2a) | `size/S` | Web | **3** (Fundament vor Flaeche: oeffnet #633) | 🟢 **startbar ohne Nebenbedingung.** Alle drei Schreibflaechen ueber alle 23 PRs **frei**. ⚠️ Nicht parallel zu Position 1 (gleicher Vitest-Baum) |
| **3** | **#633** Step-up mit Passkey (#435 W2b) | `size/S` | Web | **1** (harte Abhaengigkeit) | 🔴 **Zwei Blocker:** #632 (hart) · Container-Laufzeit (41. Messung Exit 1) |

**Position 1 bleibt bei #989, und das ist eine Entscheidung mit Gegenargument.** Fuer #989 spricht
Kriterium 2: die Frist steht als Datum **im Repo**, und Kriterium 2 schlaegt Kriterium 3
unbedingt. Dagegen spricht, dass ihre Grundlage heute fraglich ist (Fund 1) — **entscheidet der
Owner, sie herunterzustufen, nimmt #632 Position 1**, denn es ist das einzige Paket ohne jede
Nebenbedingung.

🟢 **Kein `needs-decision` auf #989** — bewusst, und gegen die Voreinstellung des Auftrags: Fund 1
hat das Paket nicht unklarer gemacht, sondern **belegt billiger**. Alle vier AK bleiben fahrbar,
AK3 ist schon gruen, AK2 ist besser begruendet als vorher. Was Urteil braucht, ist nicht das
Paket, sondern das **Verfahren** (Weiche 37) — und das gehoert nach #442, nicht als Sperre auf
den einzigen datierten Posten des Backlogs.

**Wartestand (Paket vorhanden, Flaeche belegt — Regel 7/142):** **#1001**, unveraendert seit
Lauf 64. **#1101** haelt `docs/mcp-payload-budget.md`, `payload_report.py` und
`test_tool_payload_budget.py`; am Head von #1101 bleiben AK3 (`71.738` **2×**, `:236`/`:335`;
richtig ist **71.749**) und AK4 (Historien-Tabelle endet bei `2026-10-23 … 103 … 108.262`)
unberuehrt. `108.251` ist in diesem Lauf die **sechste** identische Messung. Label `needs-decision`
seit Lauf 64 (Weiche 35).

**Nicht in der Warteschlange:** #442 (diese Liste) · #428, #435, #535 (Tracking) · #338, #454,
#542 (`human-only`) · #540 (`needs-decision`, Weiche 17, zusaetzlich umgebungsblockiert).

## Wellen

Gemeinsam startbar ist, was **datei-disjunkt** ist **und** sich nicht blockiert **und** in
**verschiedenen Verifikations-Baeumen** liegt (`pytest` sammelt den ganzen Python-Baum ein,
Vitest den ganzen Web-Baum — zwei Schreiber je Baum verfaelschen die Messung).

| Welle | Pakete | Baum | Bedingung |
|---|---|---|---|
| **A — jetzt** | **#989** _(allein)_ | Web | `apps/web/{osv-scanner.toml,package-lock.json}`; `osv-scanner.toml` ueber alle 23 PRs frei |
| **B — nach A** | **#632** | Web | derselbe Vitest-Baum wie A, deshalb nicht parallel |
| **C — parallel, kein Paket** | **Merges.** Elf gruene PRs bei hoechstens 4 Commits Rueckstand | — | Klicks, kein Agent |
| **D — nach B** | **#633** | Web | hart nach #632; zusaetzlich Container-Laufzeit **oder** ein CI-Lauf |
| **E — nach dem Merge von #1101** | **#1001**, neu zugeschnitten auf AK2-Rest + AK3 + AK4 | Python | **vorher nicht** |

🔴 **Zum zweiten Lauf in Folge kein Parallel-Paar.** A → B → D ist eine Kette, und der Python-Baum
hat kein startbares Paket, solange #1101 offen ist. **Welle E ist das Parallel-Paar, das ein
einziger Merge zurueckbringt** — und #1101 ist gruen, 0 Commits hinter `main`, konfliktfrei.

**Welle C, billigste Reihenfolge:** **#1101** (hoechste Hebelwirkung: macht E moeglich und
erledigt AK1/AK2 von #1001) → **#1092** (raeumt die halbe Lockfile-Sperre vor #989) → **#1091**
(gibt `ci.yml` frei, entsperrt #540) → **#1093–#1097** (fuenf Klicks ohne Vorbedingung) →
**#1102**, **#1098**, **#1085** (je 0 dahinter; #1085 traegt Weiche 28) → **#1100**, **#1080**
(erst Branch-Update, dann gruen — Weiche 36) → **#674** (Weiche 12) → die **9** Protokolle.

## Was dieser Lauf selbst erledigt hat

Alle Aenderungen per `gh api --input` geschrieben (Regel 144) und byte-exakt zurueckgelesen.

| Issue | behoben |
|---|---|
| **#632** | axe-Anweisung auf den Helfer umgestellt (Fund 2) · STATE.md-Vermerk: #823 → #1103/#1090/#1078 (Fund 3) · §Startbedingung komplett neu gegen alle 23 PRs · sieben `ci.yml`/`vite.config.ts`-Zeiger · Locale-Schluessel 3216 → 3.365 · Waisen 160 → 156 · Branches-Abstand 4,67 → **4,95** |
| **#633** | axe-Anweisung (Fund 2) · STATE.md-Vermerk (Fund 3) · §Startbedingung komplett neu · `ci.yml` 1212 → **1259** mit `:423`/`:503` → `:463`/`:544` · `client.ts` 1772 → **1849**, `types.ts` → **2407**, `auth.ts` 180 → **199** · E2E **43** Koerper in **9** Dateien, hoechstens **37** ueber `createUser` · Versatz-Hinweis `vitest`/`coverage-v8` entfernt (beide `^4.1.12`) |
| **#989** | 🟢 **Fund 1 vollstaendig in den Body**: AK3 ohne Aenderung erfuellt, AK2 neu begruendet, Grenzen der Messbarkeit benannt · Frist als Datum statt Tageszahl · #674 und #1092 je **0 → 4** Commits hinter `main`, #1092 **15** Check-Runs · „alle 21 offenen PRs" → **23** · AK5-Bezugswerte auf die eigene Messung |
| **#1001** | Fussnote „Zuletzt gepflegt: Lauf 60" widersprach der eigenen §Startbedingung (Lauf 64) · Inventar-Tabelle ergaenzt um die fehlende `104.777`-Stelle `:291` · `108.251` als **sechste** Messung bestaetigt |
| **#442** | Body neu geschrieben: Reihenfolge, Wellen, Sperren, Weichen (**37** neu), Norm-Pruefung, Pflege-Regeln; Zeiger `vite.config.ts:100-104` → **`:100-103`** richtiggestellt |

## Offen an den Owner

**22 Weichen**, eine neu. Vollstaendig mit Optionen und Empfehlungen in #442. Die drei, die
diesen Lauf unmittelbar betreffen:

1. **Weiche 37 (neu) — wie prueft das Verfahren eine Tatsache, die ausserhalb des Repos liegt?**
   Zwei der vier Funde dieses Laufs haben dieselbe Form: die Aussage stand im Repo, ihre Wahrheit
   nicht (Advisory-Datenbank, Fund 1) oder in einem anderen, inzwischen geschlossenen Issue
   (Fund 2). **Empfehlung: B** — jede Fremd-Tatsache bekommt im Body einen benannten Messweg und
   ein Messdatum, und der Lauf prueft die, deren Messweg er hat.
2. **Weiche 32 — wie wird die Frist am 2026-11-02 bedient?** 🔴 **Neu gerechnet: die Empfehlung
   kippt von A auf B.** Die Frist sind noch **4 Tage**, es ist **0×** gemergt worden, seit A
   („#1092 zuerst mergen") empfohlen wird — und Fund 1 nimmt der Dringlichkeit die Grundlage. **B
   (#989 sofort ausfuehren, Lockfile-Konflikt in Kauf nehmen)** kostet jetzt weniger als das
   Warten auf einen Merge, der seit fuenf Laeufen nicht kommt.
3. **Weiche 34 / 18 — der Engpass ist der Durchsatz.** **23** offene PRs, **alle** konfliktfrei,
   **elf** gruen bei hoechstens 4 Commits Rueckstand, **0** gemergt im Fenster, **0** gestartet.
   Ein einziger Merge (#1101) bringt das Parallel-Paar zurueck.

## Neue Regeln

- **150 — Determinismus belegt man am unveraenderten Baum, nicht an der gleichen Prozentzahl.**
  Vier bitgleiche Absolutpaare bei 0 Commits Fenster sind der Beleg; zwei gleiche Prozentzahlen
  bei veraendertem Baum sind keiner. Regel 148 war richtig und kam einen Lauf zu spaet.
- **151 — Die Norm prueft Anwesenheit, nicht Gueltigkeit.** #632 und #633 waren sieben Laeufe lang
  „4 von 4" und trugen dabei eine Anweisung, die `main` rot macht. **Ein `agent-ready`-Body wird
  nicht nur auf seine vier Abschnitte geprueft, sondern auf jeden Zeiger und jede Fremd-Referenz
  darin** — vor allem auf Referenzen auf Issues, die inzwischen geschlossen sind.
- **152 — Wer ein Issue schliesst, sucht jeden Body, der es zitiert.** #975 ist geschlossen; seine
  Regel steht in zwei anderen Bodies und ist dort seit zehn Tagen falsch.

## Belege dieses Laufs

- Queue-Issue: **#442** (Body neu geschrieben, nach dem Schreiben gegengelesen)
- Entrottet: **#632**, **#633**, **#989**, **#1001**
- Kommentiert: **#442** (Weiche 37, drei Optionen und Empfehlung)
- Nicht angefasst, mit Begruendung: #435, #428, #535, #542 (Regel 7, Weiche 4), #454, #338
  (`human-only`), #540 (entscheidungs- und umgebungsblockiert)
- Nicht messbar, ausdruecklich offengelassen: der OSV-Stand von GHSA-ch52-4w7c-c8xp (drei Wege zu,
  vierter laeuft ueber den `audit`-Job des Protokoll-PRs)

---

## Nachtrag, 2026-10-29 00:37 — das Gate hat geantwortet und die Reihenfolge gedreht

Der Protokoll-PR dieses Laufs (**#1104**, Head `a9dce956`) ist der Messweg, den Fund 1 als
einzigen offenen benannt hat. **Er ist innerhalb derselben Stunde gelaufen.**

**CI-Lauf 40795213278, Job `audit` (123189921876), Step 10 „OSV-Scan (Web-Lockfile, unabhaengig
von der npm-Registry)":**

```
osv-scanner osv-scanner version: 2.2.4
Scanned /home/runner/work/who2be/who2be/apps/web/package-lock.json file and found 700 packages
Loaded filter from: /home/runner/work/who2be/who2be/apps/web/osv-scanner.toml
/home/runner/work/who2be/who2be/apps/web/osv-scanner.toml has unused ignores:
 - GHSA-ch52-4w7c-c8xp
OSV: 0 Eintraege (rc=0)
```

🔴 **`has unused ignores` ist die Auskunft, auf die es ankommt.** osv-scanner meldet einen
Ignore-Eintrag als *unused*, wenn er auf **keinen gefundenen Befund** gepasst hat — nicht, wenn
er einen unterdrueckt. Der Eintrag ist am 2026-10-29 **aktiv** (`ignoreUntil` ist noch nicht
erreicht) und greift ins Leere. **Also fuehrt auch OSV GHSA-ch52-4w7c-c8xp fuer dieses Lockfile
nicht mehr** — dieselbe Aussage, die der Bulk-Endpunkt der npm-Registry in die eine Richtung
macht, macht das **Gate selbst** in der anderen.

### Vier Folgen

1. 🟢 **Die Frist beisst nicht.** Laeuft `ignoreUntil = 2026-11-02T00:00:00Z` ab, passiert
   nichts: ein wirkungsloser Ignore kann bei seinem Ablauf keinen Befund freigeben, den es nicht
   gibt. 🔴 **Die Praemisse aller Fassungen seit Lauf 56 — „danach wird `audit` rot, ohne dass
   jemand eine Zeile anfasst" — war falsch.**
2. 🟢 **Weiche 32 ist durch Messung beantwortet, nicht durch Entscheidung** — und die Empfehlung
   dreht sich am selben Tag ein zweites Mal: **nicht B** (sofort ausfuehren, Lockfile-Konflikt in
   Kauf nehmen), sondern **A** (#1092 zuerst mergen, dann #989 ohne Konflikt). Nicht weil das
   Warten besser geworden ist, sondern **weil die Eile weg ist**. Zum Schliessen vorgeschlagen.
3. 🔴 **#989 verliert Kriterium 2 und damit Position 1.** Eine Frist ohne Konsequenz ist keine
   Owner-Vorgabe; es greift nur noch Kriterium 5. **Neue Reihenfolge: #632 (Kriterium 3) →
   #989 (Kriterium 5) → #633 (Kriterium 1).** Wellen entsprechend: **A = #632**, **B = #989**,
   **D = #633** — alle drei im Vitest-Baum, also weiterhin eine Kette.
4. 🟢 **AK2 von #989 ist jetzt so stark begruendet, wie es geht, und AK3 zweifach gruen.** Fuer
   AK2 spricht nicht mehr eine Einschaetzung dieses Laufs, sondern die Ausgabe des Werkzeugs, das
   das Gate stellt: `unused`. Und das Entfernen ist gefahrlos — ohne Filter findet derselbe Scan
   weiter **0** Eintraege. AK3 ist lokal (`npm audit` Exit 0) **und** am Gate (`OSV: 0 Eintraege`)
   erfuellt.

### Was das ueber das Verfahren sagt

🟢 **Weiche 37 Option B hat sich innerhalb einer Stunde selbst belegt.** Der Kommentar in #442
nannte als Messweg „der `audit`-Job des naechsten PR-Laufs" — **genau dieser Job hat Weiche 32
beantwortet und die Reihenfolge gedreht.** Ein benannter Messweg war hier keine Buchhaltung,
sondern die Antwort. **Die Empfehlung bleibt B, jetzt mit einem Fall.**

🔴 **Und der Preis des Fehlens ist jetzt bezifferbar:** die Frist hat **neun Laeufe** lang
Kriterium 2 und Position 1 getragen — eine Reihenfolge, die sie nicht tragen durfte. Gekostet hat
die Aufklaerung einen CI-Lauf, der ohnehin lief.

### Zustand von PR #1104

🟢 **Voll gruen und mergebar:** **24** Check-Runs, davon **16** am Head gelesen — `all-green`
**success**, `audit` **success**, `secrets`/`changelog-guard`/`changes`/`CodeQL` **success**, die
Web-/E2E-/Python-Jobs **skipped** (docs-only, Klassifikation durch den Job `changes`).
`mergeable_state: clean`, Base `main`, **0** Review-Kommentare, **0** rote Checks.
**Kein `.claude/skills/steward/` oder `babysit/` im Repo** — es gilt die Standard-Posture.

### Nachgetragen

- **#989** — Abschnitt „Was dieser Lauf NICHT belegen kann" durch den Gate-Beleg ersetzt; Titel,
  AK2, AK3, Frist-Absatz und Weiche-32-Absatz entsprechend. Byte-exakt zurueckgelesen.
- **#442** — Satz 1, Startbar-Tabelle (Positionen getauscht), Begruendungs-Absatz, Wellen A/B/D,
  Weiche 32 (zum Schliessen vorgeschlagen), Weiche 37 (Nachtrag), Fund 1. Byte-exakt
  zurueckgelesen.

### Gegenprobe: der Gate-Beleg steht zweimal, an zwei Heads

Der Nachtrags-Commit `cc46da9e` hat `audit` ein zweites Mal gefahren. **Zweiter CI-Lauf
(40795719660), zweiter Head, zweiter Job (123191602667) — wortgleiche Ausgabe:**

```
osv-scanner osv-scanner version: 2.2.4
Scanned /home/runner/work/who2be/who2be/apps/web/package-lock.json file and found 700 packages
Loaded filter from: /home/runner/work/who2be/who2be/apps/web/osv-scanner.toml
/home/runner/work/who2be/who2be/apps/web/osv-scanner.toml has unused ignores:
 - GHSA-ch52-4w7c-c8xp
OSV: 0 Eintraege (rc=0)
```

🟢 **Damit steht der entscheidende Fund dieses Laufs auf drei Messungen:** dem Bulk-Endpunkt der
npm-Registry (leer), dem lokalen `npm audit` (Exit 0) und **zweimal dem Gate selbst**
(`unused ignores`, je `OSV: 0 Eintraege`).
⚠️ **Ehrlich zur Unabhaengigkeit** (Regel 127): die beiden Gate-Lesungen sind **dasselbe Werkzeug
auf demselben Lockfile** — eine Wiederholung, kein zweiter Messweg. Sie schliessen einen
einmaligen Aussetzer aus, nicht einen systematischen Fehler von osv-scanner. **Der zweite Messweg
bleibt die npm-Registry**, und sie sagt dasselbe.

### Was beim Lesen von Job-Logs in dieser Umgebung gilt (Regel 153)

🔴 **Der Roh-Log eines Actions-Jobs ist hier nicht abrufbar:** `gh api
repos/.../actions/jobs/<id>/logs` folgt auf eine Azure-Blob-URL, und die Netz-Policy antwortet
**403 Forbidden** (0 Byte, rc 1). **Lesbar ist der Log nur ueber `get_job_logs` mit
`return_content`** — und das liefert **nur den Schwanz**. Bei einem gruenen Job besteht der
Schwanz aus dem `Post job cleanup`-Block (~35 Zeilen), **der die eigentliche Step-Ausgabe
verdeckt**: `tail_lines=12` und `=30` lieferten nur Cleanup, **erst `=48` reichte bis zur
OSV-Ausgabe zurueck**.

**Regel: wer die Ausgabe eines Steps aus einem gruenen Job braucht, liest mit `tail_lines` von
mindestens 48** — und wenn nichts Fachliches auftaucht, ist das **kein Beleg fuer eine leere
Ausgabe**, sondern fuer einen zu kurzen Schwanz (Regel 10: jeder maschinelle Negativ-Befund wird
gegengelesen, bevor er ein Fund wird).

### Zustand von PR #1104 am Ende dieses Laufs

🟢 **Voll gruen am Head `cc46da9e`:** **16** Check-Runs, **0** rot, **0** laufend —
`all-green` **success**, `audit` **success**, `CodeQL` **success** (nicht `neutral` wie in den
Vorlaeufen), `secrets`/`changelog-guard`/`changes` **success**, die Web-/E2E-/Python-Jobs
**skipped** (docs-only). `mergeable_state: clean`, **0** Review-Kommentare.
**Nichts an diesem PR ist offen.** Er ist Protokoll-Nummer **10** des Rueckstands — und faellt
damit selbst unter Weiche 18.
