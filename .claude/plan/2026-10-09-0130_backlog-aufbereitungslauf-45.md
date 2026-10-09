# Backlog-Aufbereitungslauf 45 (2026-10-09)

Norm: **Agent-ready Arbeitspaket** (vier Pflichtfelder + Weichen). Auftrag: jedes
offene Issue gegen die Norm prüfen, Belegbares selbst entscheiden und mit Beleg
ins Issue schreiben, Urteilsfragen als Kommentar mit drei Optionen + Empfehlung,
danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

> **Der Who2Be-Coder-MCP war in dieser Session nicht verbunden** (kein
> `get_persona`, kein `list_triggers`, kein `fetch_playbook` im Werkzeugsatz).
> Der Lauf fährt nach dem reduzierten Kern des Bootstrap-Skills; die Prüfnorm
> und die Pflege-Regeln sind aus dem Repo und aus #442 rekonstruiert, nicht aus
> der AgentDB geladen. **Im Bericht offengelegt.**

## Ausgangslage

Basis: `main` @ **`7590c335`** (#868). Seit der Lauf-44-Basis `73ce3277` sind
**18 Commits** gelandet (#850 – #868) — fast alle aus der ADR-0053-Lernschleife
(Fälle, Muster, Feedback-Hub). Der Klon war **shallow** (`true`, 50 Commits);
nach `git fetch --unshallow` **1472** Commits — **achter Lauf in Folge**,
Voreinstellung dieser Umgebung (Regel 90).

**Zwei Dinge haben sich gegenüber Lauf 44 grundlegend gedreht:**

1. ✅ **`main` hat wieder einen CI-Spruch.** Der Hänger ist weg. Run zum
   HEAD-SHA `7590c335` (**37858949924**, 2026-10-08 23:21–23:36 UTC),
   `status: completed` und `conclusion: success` **getrennt** gelesen
   (Regel 91). Die Startsperre aus Regel 80 greift nicht.
2. 🔴 **Aber die Spruch-Lücke ist ein zweites Mal eingetreten — und diesmal
   ohne jeden hängenden Job.** Siehe unten; das ist der zentrale Fund dieses
   Laufs und er korrigiert die Prämisse der offenen Concurrency-Weiche.

## Der zentrale Fund: der Mechanismus braucht keinen Hänger, nur Merge-Dichte

Gemessen über die **12 jüngsten `ci.yml`-Läufe auf `main`** (Commits
`f7c232b3` … `7590c335`, also 12 der 18 neuen Commits; die übrigen sechs sind
**nicht** gemessen — Regel 49):

| Commit | Lauf | `status`/`conclusion` | `all-green` |
|---|---|---|---|
| `7590c335` (#868, **HEAD**) | 37858949924 | `completed` / **`success`** | ✅ |
| `a0877f5d` (#867) | 37853359495 | `completed` / `success` | ✅ |
| `29d373a5` (#866) | 37845720013 | `completed` / `success` | ✅ |
| `2789aa69` (#865) | 37837892761 | `completed` / `success` | ✅ |
| `53178a37` (#864) | 37831433971 | `completed` / `success` | ✅ |
| `b3602e52` (#862) | 37823219791 | `completed` / `success` | ✅ |
| **`e41d5d9a` (#863)** | **37822973287** | `completed` / **`cancelled`** | 🔴 **existiert nicht** |
| `795e370f` (#861) | 37822735582 | `completed` / `success` | ✅ |
| `5be56597` (#860) | 37795323201 | `completed` / `success` | ✅ |
| `bdef1f54` (#859) | 37792110810 | `completed` / `success` | ✅ |
| `22d56503` (#858) | 37777844371 | `completed` / `success` | ✅ |
| `f7c232b3` (#857) | 37769934469 | `completed` / `success` | ✅ |

**Der Ablauf, auf die Sekunde:** Lauf 1809 (#861) startet **18:14:27** und läuft
bis **18:29:43**. Lauf 1810 (#863) startet **18:16:15** und steht damit als
*wartender* Lauf der Gruppe `ci-CI-refs/heads/main`. Um **18:18:11** landet
#862 — und verdrängt den wartenden Lauf. Lauf 1810 ist **18:18:12** `cancelled`,
nach **1 Minute 57 Sekunden**.

**Was daran neu ist und warum es die Weiche verschiebt:** Lauf 44 hat diesen
Mechanismus an einem **hängenden** `e2e`-Job belegt (4 h 47 min, vier verlorene
Sprüche) und daraus das Paket **#849** (`timeout-minutes`) geschnitten. Dieser
Lauf zeigt: **der Hänger war der Anlass, nicht die Ursache.** Es genügen *drei
Pushes innerhalb der normalen Laufzeit eines Laufs* (~15 min). Bei der aktuellen
Dichte — **18 Commits in 26 Stunden**, zeitweise drei in vier Minuten — ist das
der Regelfall, nicht der Störfall.

**Daraus folgt eine Aussage über das Paket #849, die vorher nicht belegt war:**
ein Timeout macht einen Hänger billig, **er schließt die Spruch-Lücke nicht**.
Option A der offenen Weiche („nur Timeouts") ist damit nachweislich
unzureichend; von den drei Optionen adressiert nur **B**
(`cancel-in-progress: true` auch auf `main`) die gemessene Ursache.
→ Als **Prämissen-Korrektur** an #442 kommentiert (Regel 24), **nicht** als neue
Weiche gestellt (Regel 9).

## Die zweite Drehung: #632 hat zum ersten Mal seit acht Läufen eine Datei-Sperre

PR **#869** („Triage im Fall-Detail", ADR-0053 D6d, **behind = 0**, nicht Draft)
schreibt **`apps/web/src/i18n/locales/de.json` und `en.json`** — und das ist die
Schreibfläche von **#632** (Scope „In") und von **#633**.

Gegenprobe über **alle zwölf** offenen PRs: die Vereinigung ihrer Datei-Scopes
umfasst **27** Dateien; von allen in #442 geführten Schreibflächen ist
**ausschließlich** `locales/{de,en}.json` darunter. Jede andere Fläche
(`MfaSection.tsx`, `orphan-baseline.json`, `e2e/**`, `LoginPage.tsx`,
`SessionProvider.tsx`, `vite.config.ts`, `Caddyfile`, `plans.md`, `ci.yml`,
die fünf Lint-Dateien) ist von PRs **frei**.

**Einordnung, und sie ist freundlich:** #869 ist **behind = 0**, nicht Draft,
und sein Lauf 37862714348 (2026-10-09 00:02 UTC) ist gate-aktuell — 11 der 12
Jobs stehen grün, `python` lief zum Messzeitpunkt noch, `all-green` fehlt
deshalb noch. **Das ist eine Sperre aus einem Zustand, nicht aus einer
Entscheidung** (Regel 87): sie löst sich mit dem Merge von #869, ohne Antwort
von jemandem. Anders als `RUNBOOK.md`, das seit vier Tagen an #823 hängt.

**Zweite Achse (Regel 100):** `locales/{de,en}.json` ist zusätzlich **5× auf
`main` bewegt** (von 18 Commits) — die am häufigsten angefasste Datei dieses
Zeitraums. Jede Zeilenangabe von gestern ist dort eine Vermutung.

## Triage der elf offenen Issues gegen die Norm

Legende: **E** = im Repo belegt, selbst entschieden · **U** = braucht Urteil ·
**H** = `human-only`, Lauf endet dort (Playbook Schritt 1).

| Issue | Label | Norm-Stand | Befund | Ergebnis |
|---|---|---|---|---|
| **#849** | `agent-ready` `size/S` | 4/4 Pflichtfelder | **E** | Body nachgezogen: Vorfall beendet, Mechanismus zum 2. Mal eingetreten (ohne Hänger), `ci.yml` unverändert 1212 / 0 Timeouts |
| **#632** | `agent-ready` `size/S` | 4/4 | **E** | Body nachgezogen: **Datei-Sperre durch #869**, alle Basiswerte neu |
| **#633** | `agent-ready` `size/S` | 4/4 (6 AK — Norm-Befund offen) | **E** | Body nachgezogen: dieselbe Sperre, `api/types.ts` auf `main` bewegt, 35/26 neu hergeleitet |
| **#435** | `size/M` | 6 AK, zwei ohne Schwelle, kein Outcome | — | **Regel 7**: nicht durch Nachtragen startbar. Kinder #632/#633 offen. Kein Eingriff |
| **#428** | `epic` `size/M` `needs-decision` | Outcome + Verifikation fehlen ganz | — | **Regel 7**. ⚠️ AK-5-Fläche `ROADMAP.md`/`README.md` ist auf `main` bewegt (Werkzeugzahl 86 → 90), bleibt PR-frei |
| **#535** | `epic` `size/M` `needs-decision` | Outcome + Verifikation fehlen ganz | — | **Regel 7**. Zeiger halten. Begründung zeigt weiter auf die gelöschte `cloud-hosting-owner-guide.md` (10 Dateien) |
| **#540** | `size/M` `needs-decision` | 4/4 formal, Kriterium 1 ohne Kommando | **U** | Dreifach blockiert: Entscheidung + Verifizierbarkeit + Container-Laufzeit. `RUNBOOK.md` weiter von #823 gehalten |
| **#542** | `needs-decision` `human-only` | — | **H** | Lauf endet hier |
| **#454** | `human-only` | — | **H** | Lauf endet hier |
| **#338** | `human-only` | — | **H** | Lauf endet hier |
| **#442** | `backlog-queue` | — | — | Die Warteschlange selbst, kein Arbeitspaket |

**Kein Issue hat sein Label gewechselt, und das ist der richtige Zustand.**
Die drei `agent-ready`-Pakete tragen alle vier Pflichtfelder vollständig; die
vier `size/M`-Pakete werden nach **Regel 7** nicht durch Nachtragen von Feldern
startbar, sondern durch Zuschnitt — und keines hat einen ungeschnittenen Rest,
der ohne Owner-Antwort schneidbar wäre. **Kein neues Issue:** der zentrale Fund
dieses Laufs ist Gegenstand einer bereits offenen Weiche (Regel 8/13).

## Zeiger-Prüfung — jeder einzeln gelesen, Zeile UND Inhalt gegen das Label

Alle gegen `main` @ `7590c335`, Regel 93/97/98. **Kein einziger Zeiger verrottet
— zweiter Lauf in Folge ohne Korrektur.**

`ci.yml` **1212** Zeilen (unverändert seit #839 `11a243ff`, `git log 73ce3277..origin/main -- .github/workflows/ci.yml` → **kein Commit**):
`:14` = `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}` ·
`:75` = Doku-Allowlist-`grep` · `:296` = `npm run test:a11y` ·
`:737` = `changelog-guard:` · `:802` = `secrets:` · `:914` = `audit:` ·
`:983` = `npm run license:check` · `:1090` = `needs:` · `:1091-1101` = **elf**
Einträge (`:1101` = `secrets`). Über `yaml.safe_load`: **12 Jobs, keiner mit
`timeout-minutes`** — `grep -c` → **0** (Regel 102: das leere Ergebnis ist der
Befund, nicht die Entwarnung).

Dateigrößen: `MfaSection.tsx` **297** · `SessionProvider.tsx` **267**/`:57`
(`async function mfaStepUpPending`) · `LoginPage.tsx` **394**/`:38`
(`async function completeMfaChallenge`) · `e2e/helpers/auth.ts` **180**/`:33`
(`export async function createUser`)/`:55`/`:97` (`async function
enrollTotpAal2`, nicht exportiert) · `src/i18n/audit.test.ts` **371**/`:297`
(`it.each([`)/`:301`/`:308`/`:321` (blankes `it(`) · `vite.config.ts`
**89**/`:81` (`thresholds:`)/`:82-85` = **80 / 79 / 75 / 80** ·
`core/security.py:202` = `def require_aal2` · `Caddyfile` **195**,
`grep -cE "\brate\b"` → **0** · `licensing/entitlement.py` **283** ·
`services/mcp_limit_service.py` **161** · `core/config.py:83` =
`rate_limit_write`, `:159` = `ingest_max_bytes` (das gekreuzte Paar hält) ·
`billing.spec.ts:43` = `test.skip(` · `orphan-baseline.json` = flaches Array,
**159** Einträge · GoTrue **v2.197.0** ×3 · `auth-js` **2.117.1** ·
`package.json:8`/`:15`/`:17`/`:37` · Caddy: CI `2.8-alpine`
(`ci.yml:351`/`:352`/`:367`/`:368`), Betrieb `2.11.4-alpine`
(`who2be/docker-compose.yml:352`) · `osv-scanner.toml:11` =
`ignoreUntil = 2026-11-02T00:00:00Z` → **24 Tage** · `fail2ban` repo-weit
**genau ein** Treffer (neunter Lauf) · `.claude/project.json` existiert nicht.

## Messwerte des Laufs

Node **v22.22.0**, sequenziell erhoben (ein Schreiber je Baum, Regel 31/76);
Web und Python sind verschiedene Stacks und liefen nebeneinander.

| Messung | Ergebnis | Lauf 44 |
|---|---|---|
| `npm run lint` | Exit 0, **93** problems, 0 errors, **61** Dateien, 8 Regeln, **9** `--fix`-bar | 91 / 59 |
| `npx tsc -b` | **Exit 0** | Exit 0 |
| `npm run test:coverage` | Exit 0, **251 Dateien / 2056 Tests** | 248 / 1965 |
| → Statements | **88,46 %** | 88,27 |
| → Branches | **82,17 %** 🔴 **gesunken** | 82,31 |
| → Functions | **84,72 %** | 84,47 |
| → Lines | **90,18 %** | 89,84 |
| `npm run i18n:check` | Exit 0, keine neue Waise, **159** bekannt, keine Duplikate | 159 |
| `uv run pytest --collect-only -q` | **3166** Tests, Billing in der Collection | 3061 |
| `changelog_fragments.py check` | Exit 0, **240** Fragmente (`ls` zählt 241, Differenz = `README.md`, Regel 18) | 222 |
| `docker info` | **Exit 1** — 21. Lauf | Exit 1 |

**Lint-Verteilung:** `set-state-in-effect` **47** _(war 45)_ ·
`classnames-order` 22 · `only-export-components` 12 · `incompatible-library` 5 ·
`preserve-manual-memoization` 4 · `exhaustive-deps`/`refs`/`use-memo` je 1.
**Die Reihe 73 → 88 → 84 → 84 → 90 → 91 → 91 → 91 → 91 → 93 bewegt sich nach
drei Stillständen wieder** — und zwar nach oben. Die **9** `--fix`-baren liegen
unverändert in fünf Dateien (`components/ui/checkbox.tsx` 1, `ui/sheet.tsx` 4,
`playbooks/components/LinkedBlocksList.tsx` 1, `PlaybookListToolbar.tsx` 2,
`ResourceBlockLinkPicker.tsx` 1) — **alle fünf PR-frei und auf `main`
unbewegt** (je 0 Commits).

🔴 **Branches sind gefallen, während alles andere gestiegen ist** — 82,31 →
**82,17** (−0,14) bei **+91 Tests**. Der Abstand zum Gate (79) beträgt noch
**3,17** Punkte _(war 3,31)_. **Das ist genau der Fehlermodus, um den Weiche 6
geht: ein Lauf kann Coverage verlieren und Exit 0 melden.** Lauf 44 hat die
Prämisse „die Zahlen bewegen sich" geprüft und bestätigt; dieser Lauf liefert
die erste **Abwärts**-Bewegung seit der Messreihe — die Prämisse hält also nicht
nur, sie zeigt jetzt in die unangenehme Richtung. Zustand der Weiche
aktualisiert, **nicht erneut gestellt** (Regel 9).

## PR-Bestand — zwölf offene PRs, zwei gate-aktuell

Datei-Scope je PR über `git diff --name-only $(git merge-base origin/main <head>) <head>`
**nach `--unshallow`**, jede merge-base ausdrücklich auf nicht-leer geprüft
(Regel 90). Konfliktfreiheit über `git merge-tree --write-tree` (Regel 95).
Gate-Grenze: `ci.yml`-Stand `11a243ff`, 2026-10-06 **17:25 UTC** (Regel 99).

| PR | Inhalt | Schreibt nach | `all-green` | Lauf vom | Gate | hinter `main` | merge-tree |
|---|---|---|---|---|---|---|---|
| 🆕 **#869** | Triage im Fall-Detail (D6d) | **`locales/{de,en}.json`**, `CaseDetailPage`, `caseNextStep`, `CaseActions`, `TestCaseForm`, Plan, Fragment | ⏳ **läuft** (`python` `in_progress`, 11/12 grün) | 2026-10-09 00:02 | ✅ **aktuell** | **0** | rc 0 |
| **#851** | Protokoll Lauf 44 | `.claude/plan/…` | ✅ 16/16 | 2026-10-08 00:41 | ✅ aktuell | 18 | rc 0 |
| **#841** | Protokoll Lauf 43 | `.claude/plan/…` | ✅ | 2026-10-07 00:56 | ✅ aktuell | 25 | rc 0 |
| **#831** | Protokoll Lauf 42 | `.claude/plan/…` | 🔴 `audit` | 2026-10-06 00:50 | 🔴 alt | 33 | rc 0 |
| **#823** | Zeiger-Reparatur Lauf 41 | **`STATE.md`**, **`PROJECT.md`**, **`RUNBOOK.md`**, Plan | ✅ **17/17**, **ohne `secrets`** | 2026-10-05 00:44 | 🔴 alt | 36 | rc 0 |
| **#827** | nginx/seaweedfs/postgres | vier Compose-Dateien | ✅ | 2026-10-05 04:46 | 🔴 alt | 36 | rc 0 |
| **#825** | python-minor-patch ×5 | **`uv.lock`** | ✅ | 2026-10-06 06:05 | 🔴 alt | 28 | rc 0 |
| **#824** | web-minor-patch ×5 | **`apps/web/package.json`** + Lock | ✅ **14 Runs, ohne `secrets`** | 2026-10-05 04:19 | 🔴 alt | 36 | rc 0 |
| **#686** | redis 7→8 | `who2be/docker-compose.cloud.yml` | 🔴 nur `changelog-guard` | **2026-09-28** | 🔴 alt | **177** | rc 0 |
| **#683** | redis 7→8 | `dokploy/docker-compose.cloud.yml` | 🔴 nur `changelog-guard` | **2026-09-28** | 🔴 alt | **177** | rc 0 |
| **#682** | redis 7→8 | `docker-compose.cloud.yml` | 🔴 nur `changelog-guard` | **2026-09-28** | 🔴 alt | **177** | rc 0 |
| **#674** | Vitest 4 → **5** (Major) | **`apps/web/package.json`** + Lock | 🔴 `web` + 6 Folgejobs | 2026-10-05 04:32 | 🔴 alt | 36 | rc 0 |

✅ **Alle zwölf mergen konfliktfrei.** ✅ **CodeQL ist an #824 `neutral`, nicht
rot** (Regel 101, positiv auf `failure`/`timed_out` gefiltert).

**Basis für die acht unbewegten PRs:** ihre Head-SHAs sind seit Lauf 44
unverändert und `ci.yml` ist unbewegt — ein Check-Run-Satz kann sich ohne Push
oder Re-Run nicht ändern, und `rerun_failed_jobs` ist für Agenten-Sessions 403.
#823 und #824 wurden **trotzdem** frisch nachgemessen (oben); die Messung
bestätigt Lauf 44 in beiden Fällen.

🔴 **Der Protokoll-Rückstand ist auf vier gewachsen und dieser Lauf legt den
fünften dazu.** #823 (41), #831 (42), #841 (43), #851 (44) — alle offen, alle
Draft. **Kein Lauf kann den PR seines Vorgängers mergen** (Regel 2), also wächst
der Bestand um einen pro Lauf. Untereinander datei-disjunkt (fünf verschiedene
Plan-Dateien; nur #823 fasst zusätzlich drei Sammelpunkte an).

## Neue Reihenfolge

Kriterien unverändert: **1** harte Abhängigkeit · **2** Owner-Vorgabe ·
**3** Fundament vor Fläche · **4** Inventar vor Zuschnitt · **5** bei
Gleichstand das kleinere.

1. **#849 — `timeout-minutes` in `ci.yml`** _(Kriterium 3, bei Gleichstand 5)_.
   Zwölf eingefügte Zeilen in einer Datei, die **PR-frei und auf `main`
   unbewegt** ist, keine offene Entscheidung, Werte aus 12 grünen Läufen
   abgeleitet. **Bleibt Position 1 — aber mit einer ehrlicheren Begründung als
   in Lauf 44:** es macht einen Hänger billig, und das ist sein ganzer Zweck.
   Dass es die Spruch-Lücke schließt, ist durch diesen Lauf **widerlegt**; wer
   das erwartet, wartet auf die Antwort zur Concurrency-Weiche.
   **Es ist das einzige Paket ohne Datei-Sperre und ohne offene Frage.**
2. **#632 — Passkey registrieren** _(Kriterium 3)_ — Fundament vor Fläche,
   öffnet #633. 🔴 **Erstmals seit acht Läufen mit Datei-Sperre:** #869 hält
   `locales/{de,en}.json`. **Nach dem Merge von #869 startbar** — die Sperre
   löst sich ohne Antwort (Regel 87, #869 ist behind 0).
3. **#633 — Step-up mit Passkey** _(Kriterium 1)_ — nach #632, plus
   Container-Laufzeit (`docker info` → Exit 1). Dieselbe i18n-Sperre.
4. **Die Trennung des `audit`-Jobs** _(Kriterium 2 offen, dann 5)_ — Option C
   der Weiche 4. Schreibt **nur** `ci.yml`. 🔴 **Frist 2026-11-02 — 24 Tage.**
   ⚠️ Nicht gleichzeitig mit #849; danach alle `ci.yml`-Zeiger neu messen
   (Datei wächst auf 1224, Regel 98).
5. **Der Caddy-Versions-Widerspruch** _(Kriterium 2 offen)_ — Fläche frei und
   unbewegt. Drei Dateien plus `ci.yml` gegen eine, deshalb hinter Position 4.
6. **Die 9 `--fix`-baren Lint-Warnungen** _(Kriterium 5)_ — Option B der
   Weiche 7. Kleinster schneidbarer Posten; fünf Dateien PR-frei **und
   unbewegt**. **Jetzt 93 statt 91 Warnungen.**
7. **#540** _(Kriterium 1 offen, dreifach)_ — Entscheidung, Verifizierbarkeit
   und Container-Laufzeit fehlen unabhängig voneinander; `RUNBOOK.md` hängt
   seit vier Tagen an #823.

**Präferenz, nicht Kriterium (Regel 9):**

- **#849 bleibt vorn, und zwar mit geschrumpftem Versprechen.** Die zwölf
  Zeilen sind richtig; die Begründung „es repariert die Bedingung, unter der
  jeder Beleg zustande kommt" aus Lauf 44 ist durch die Messung dieses Laufs
  **nicht mehr tragfähig** — das tut nur Option B der Weiche.
- **#869 vor #632 mergen.** Ein Klick, und die einzige Sperre von #632 fällt.
  Das folgt aus keinem der fünf Kriterien, deshalb steht es hier.
- **Die fünf Protokoll-PRs in einem Zug aus dem Draft holen** (#823, #831,
  #841, #851 + der dieses Laufs). **Drei freiwerdende Sammelpunkte** — einer
  davon die einzige Datei-Sperre von #540.
- **Die `audit`-Trennung vor dem Caddy-Widerspruch**: ein stillgelegtes
  Merge-Gate ist teurer als ein falscher Pin.

**Blockiert, nicht einplanbar:** #540 (dreifach), #428/#435/#535 (`size/M`,
Zuschnitt), #542/#454/#338 (`human-only`).

## Wellen

**Datei-Disjunktheit reicht nicht — Stack-Trennung reicht.** `pytest` und
`vitest` sammeln den ganzen Baum ein; über Stack-Grenzen hinweg nicht.

| Welle | Paket | Schreibt | Bedingung |
|---|---|---|---|
| **A** | #632 | `features/settings/MfaSection.{tsx,test,a11y}`, `locales/{de,en}.json` | **nach dem Merge von #869**; allein im Vitest-Baum |
| **B** | #633 | `LoginPage.tsx`, `SessionProvider.tsx`, `e2e/**` inkl. `helpers/auth.ts`, `locales/*` | nach A; **braucht Docker**; allein fahren (26 von 35 Körpern über `createUser`) |
| **C** | #849 | **nur** `.github/workflows/ci.yml` + Fragment | ✅ **Datei PR-frei und unbewegt** — **A und C sind das einzige echte Parallel-Paar** (verschiedene Stacks) |
| **D** | `audit`-Trennung | `ci.yml` | **nicht mit C**; nach C neu messen |
| **E** | Caddy-Pin | `Caddyfile`, zwei `.sh`, `ci.yml` | **nicht mit C oder D** |
| **F** | 9 Lint-Fixes | fünf Dateien (PR-frei, unbewegt) | **nicht mit A oder B** (ein Vitest-Baum) |
| **G** | Coverage-Boden | **nur** `vite.config.ts:82-85` | nach Antwort; selber Vitest-Baum wie A/B/F |
| **H** | Branch-Updates + Merges | — | **#869 zuerst** (löst A frei), dann #823 (drei Sammelpunkte), #825, #824, #827, #831, die Protokoll-PRs. Klicks, kein Agent. Parallel zu allem — **aber ein Merge ist ein Schreiber im Baum** (Regel 31) |
| **I** | drei Redis-Einzeiler | drei `*.cloud.yml` | #682/#683/#686, **177 Commits** hinter `main`; Branch-Update |
| **J** | MB/MiB-Zeile | **nur** `plans.md:28-29` | nach einem Ja. Ein Satz, parallel zu allem |

**Keine Welle:** #540 gegen alles · #674 gegen #824 (**#824 zuerst**) ·
C gegen D gegen E (dieselbe `ci.yml`) · F gegen A oder B (ein Vitest-Baum) ·
**A gegen #869** (dieselben Locale-Dateien) · ein Merge gegen alles im selben Baum.

🔴 **Neue Kollisionszeile:** `apps/web/src/i18n/locales/{de,en}.json` ist
**von #869 belegt UND 5× auf `main` bewegt** — die erste Stelle dieses Laufs,
die beide Achsen gleichzeitig trägt, und sie ist die Schreibfläche von #632
und #633. _(Lauf 44 trug dieselbe Warnung für `RUNBOOK.md`.)_

## Was der Lauf geschrieben hat

**Selbst entschieden und mit Beleg ins Issue geschrieben** (Belegbares ist nach
Playbook-Schritt 4 keine offene Weiche, sondern unerledigte Recherche):

| Issue | Änderung |
|---|---|
| **#632** | Kopfblock neu: Datei-Sperre durch #869 statt „Fläche frei"; alle Basiswerte (Lint 93, 251/2056, vier Coverage-Zahlen, Python 3166, Fragmente 240) neu gemessen; Zeiger bestätigt |
| **#633** | Kopfblock neu: dieselbe Sperre; `api/types.ts` auf `main` bewegt; 35/26 unabhängig neu hergeleitet (fünfter Stillstand); Basiswerte neu |
| **#849** | Vorfall-Block datiert und abgeschlossen; **zweiter Eintritt ohne Hänger** ergänzt; die Reichweite des Pakets ehrlich begrenzt; `ci.yml` 1212 / 0 Timeouts bestätigt |
| **#442** | Body neu geordnet (Warteschlange, Wellen, Kollisionen, Sammelpunkte, Messwerte) + ein Kommentar mit der Prämissen-Korrektur zur Concurrency-Weiche |

**Nicht angefasst, bewusst:** #428, #435, #535, #540 — alle Zeiger halten, kein
Satz in diesen Bodies ist falsch geworden, und `size/M` wird nach Regel 7 nicht
durch Nachtragen startbar. #542, #454, #338 tragen `human-only`.

**Kein neues Issue, kein Code, kein Branch für die Pakete, kein Claim, kein
Merge, kein Branch-Update, kein Draft-Flag umgelegt.** Ein Schreibvorgang an
einem fremden PR ist kein Teil eines Aufbereitungslaufs, und ein Merge ist eine
Owner-Entscheidung — **belegt ist, dass es geht** (alle zwölf `merge-tree`
rc 0).

## Regel-Vorschlag 104

> **104. (Lauf 45): Ein Fund, der an einem spektakulären Anlass gemessen wurde,
> wird dem Anlass zugeschrieben und nicht der Ursache — und das Paket, das
> daraus geschnitten wird, verspricht dann mehr als es hält.** Lauf 44 hat vier
> fehlende CI-Sprüche an einem **4 h 47 min** hängenden `e2e`-Job gemessen und
> daraus #849 (`timeout-minutes`) geschnitten. Lauf 45 findet den **fünften**
> fehlenden Spruch — ohne jeden Hänger: Lauf 1810 (#863) stand **1 Minute
> 57 Sekunden** als wartender Lauf und wurde von #862 verdrängt. **Es genügen
> drei Pushes innerhalb einer normalen Laufzeit.** Der Hänger war die
> Verstärkung, die Merge-Dichte ist die Ursache, und ein Timeout adressiert nur
> die Verstärkung. **Gegenmaßnahme:** wer aus einem Vorfall ein Paket schneidet,
> prüft, ob der Fund **auch ohne das Spektakuläre** eintritt — und schreibt die
> Reichweite des Pakets gegen die Ursache, nicht gegen den Anlass. _102 sagt:
> ein fehlender Wert ist eine Entscheidung für den Default. 103 sagt: eine
> Maßnahme kann ihr Ziel vernichten. **104 sagt: die Gegenmaßnahme kann am
> Anlass vorbeizielen, obwohl der Fund stimmt.**_
