# Backlog-Aufbereitungslauf 69

**Datum:** 2026-11-02
**Messpunkt:** `main` @ `af78ad7d` (Baum `498ded60`) — `deps(security): pypdf 6.21.4 + joserfc 1.7.7 …` (#1111)
**Fenster seit dem letzten Messpunkt:** **0 Commits** — der Baum ist bitgleich mit dem von Lauf 68.
**Warteschlange:** #442 (Label `backlog-queue`), Body in diesem Lauf zweimal geschrieben (s. §Eigenfehler).

---

## Auftrag

Jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket" prüfen; was das Repo belegt, selbst
entscheiden und mit Beleg ins Issue schreiben; was Urteil braucht, als Kommentar mit drei Optionen
und Empfehlung stellen. Danach die Warteschlange neu ordnen (harte Abhängigkeit, Owner-Vorgabe,
Fundament vor Fläche, Inventar vor Zuschnitt, bei Gleichstand das kleinere) und in Wellen
gruppieren.

## Boot

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — elfter Lauf in Folge.** Der Server
verlangt eine OAuth-Autorisierung, die aus dieser Session nicht gestartet werden kann. Persona und
Playbook-Katalog lagen im System-Prompt vor; `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket", `73a86231`), `record_usage` und
`search_memory` nicht. Der Lauf fährt deshalb nach dem reduzierten Kern des Bootstrap-Skills, nach
dem Body von #442 und nach `.github/PROJECT.md` §Constraints. **Elfter Lauf ohne
Kurations-Rückmeldung an die eigene AgentDB.**

**Kein Playbook geladen** — der Trigger-Abgleich lief gegen den eingebetteten Katalog; das passende
Playbook wäre „Projekt-Standup"/„Code-Task-Flow", beide nicht ladbar.

## Messgrundlage

Alle Werte am 2026-11-02 auf `main` @ `af78ad7d` erhoben, **sequenziell** (ein Schreiber je Baum,
Regel 164), Node **v22.23.4**, **ohne vorherige Reparatur** (Regel 120), **Exit-Codes ohne Pipe**
(Regel 94), `npm`-Gates in `apps/web/` (Regel 146). Der Klon war **shallow** (50 Commits); nach
`git fetch --unshallow`: **1666** Commits (Regel 90).

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | **Exit 0**, „All checks passed" |
| `uv run mypy .` | **Exit 0**, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | **5033** Tests |
| `changelog_fragments.py check` | **Exit 0**, **404** Fragmente |
| `npm run lint` | **Exit 0**, **94** problems, **0 errors**, **7** `--fix`-bar |
| `npx tsc -b` | **Exit 0**, Ausgabe **0 Byte** |
| `npm run i18n:check` | **Exit 0**, `de.json`/`en.json` je **3.365** Schlüssel, **156** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | **Exit 0** |
| `npm audit --audit-level=high` | **Exit 0** |
| `npm audit` (voll) | ⚠️ **Exit 1**, **29 moderate** — ausschließlich `glob` + `minimatch`, dev-only |
| `pip-audit` (selbst gefahren, Regel 159) | 🟢 **Exit 0**, „No known vulnerabilities found", **398** Requirements-Zeilen |
| `payload_report` | **103** Werkzeuge / **108.251** Bytes, `instructions` **1.834** (10. identische Messung) |
| `npm run test:coverage` | ⚪ **nicht gefahren** — Fenster 0 Commits, Baum bitgleich (Regel 160) |
| `docker info` | 🔴 **Exit 1** — keine Container-Laufzeit, kein `podman` (**45.** Messung in Folge) |

**Fundstellen, einzeln wörtlich gelesen:** `osv-scanner.toml` **26** Zeilen, `IgnoredVulns` **2×**
(`:9` `glob`/`GHSA-3g3m-2fjr-6pw4`, `:17` `minimatch`/`GHSA-g3hv-75wg-m249`), beide
`ignoreUntil = 2026-11-30` (`:11`/`:19`), „turns red again" **1×** auf `:6`,
`GHSA-ch52-4w7c-c8xp` **0×**; `package-lock.json` `http-cache-semantics` **4.2.0** an `:6295`;
`docs/mcp-payload-budget.md` **609** Zeilen (`104.777` an `:233`/`:292`/`:327`/`:487`, `108.262` an
`:234`/`:331`, `71.738` an `:236`/`:335`, Kopf `:254`, `instructions` `:267`/`:309`);
`MfaSection.tsx` **297**; `LoginPage.tsx` **399**; `SessionProvider.tsx` **267**;
`audit.test.ts` **371**; `e2e/helpers/auth.ts` **199**; `client.ts` **1849**; `types.ts` **2407**;
`ci.yml` **1259** (`:463` `--project=chromium`, `:544` `billing.spec.ts`, beide wörtlich);
`vite.config.ts` **107**, Schwellen `:100-103` (`thresholds:` `:99`, Klammer `:104`);
`a11y.test.ts` **77**, Untergrenze `toBeGreaterThanOrEqual(20)` auf `:74`;
`orphan-baseline.json` **156** Einträge / 158 Zeilen; `apps/web/package.json` **82**;
`CLAUDE.md` `pip-audit` **0×**; `docs/cloud-erstinbetriebnahme.md` in #1106 **1021** Zeilen,
`<DOMAIN>` **54×**, Befund auf `:627`.

## PR-Bestand

**26 offene PRs** (waren 25; neu nur **#1112**, das Protokoll von Lauf 68). Scope je PR über
`git merge-base` + `git diff --name-only` mit Nicht-leer-Prüfung, Konfliktfreiheit über
`git merge-tree --write-tree`, Gate-Alter über `git diff --name-only <merge-base> main --
.github/workflows/ci.yml` (Regel 158).

- 🟢 **Alle 26 mergen konfliktfrei** (rc 0), alle 26 merge-bases rechnen.
- **0 dahinter:** #1112, #1106, #1100, #1063 · **5:** #1108, #1107, #1105, #1104, #1103 ·
  **9:** #1089–#1097, #674 · **23:** #1080, #1078 · **38:** #1056 · **63:** #1025 ·
  **79:** #1002 · **104:** #990 · **227:** #831.
- 🔴 **Gate-alt: fünf** (#1056, #1025, #1002, #990, #831) — **alle fünf Protokoll-PRs.** Die Kante
  liegt unverändert zwischen **23** (nicht gate-alt) und **38** (gate-alt).
- 🟢 **#1106 frisch gemessen:** **18** Check-Runs, alle `success`, `all-green` namentlich
  `success` (`45714abe`, Lauf `41188077235`).
- ⚪ **Die CI-Lage der übrigen 24 PRs ist von Lauf 68 übernommen, nicht neu gemessen** — zulässig,
  weil ihre Heads unverändert sind (`updated_at` aller ≤ `2026-11-01T00:46Z`) und `main` sich nicht
  bewegt hat. **#1112 nicht gemessen.** Das ist in #442 ausdrücklich als übernommen gekennzeichnet.
- 🔴 **Protokoll-Rückstand: 13**; dieser Lauf legt das **vierzehnte** dazu. **Zu Lauf 63 existiert
  weiter kein Protokoll.**
- 🔴 **`.claude/context/STATE.md` ist auf `main` auf den 2026-10-02 datiert — 31 Tage**, dreifach
  gehalten (#1103, #1090, #1078).

## Die Funde des Laufs

### 1. Verrottung im verbindlichen Teil eines quarantänisierten Bodys (Regel 166)

#632 und #633 tragen je einen ⛔-Kopfblock, der sauber als „nicht befolgen" markiert ist. **Die
drei falschen Aussagen stehen nicht dort, sondern darunter** — in §Verweise und §Definition of
Done, also im Teil, den beide Bodies ausdrücklich für verbindlich erklären:

| Stelle | steht da | gemessen |
|---|---|---|
| §Verweise (beide) | „#793 … Ausnahme bis **2026-11-02**, `apps/web/osv-scanner.toml:11`" | 🔴 `:11` trägt `glob` bis **2026-11-30**; die genannte Ausnahme hat #1111 entfernt |
| §DoD (beide) | „`.github/PROJECT.md` ist über alle 23 PRs **frei**" | 🔴 gehalten von **#1105** |
| §DoD (beide) | „#1078 … **18** Commits hinter `main`" | ⚠️ heute **23** |

🔴 **Die erste ist die gefährliche, und sie ist auf den Tag genau fällig:** sie nennt **2026-11-02**
— das Datum dieses Laufs. Ein Agent liest dort eine Frist, die heute abläuft, für ein Gate, das
nicht existiert. **Lauf 68 hat 13 Zeiger in #632 geprüft und alle 13 als gültig befunden — richtig,
aber unvollständig:** die 13er-Liste deckt §Scope und §Verifikation ab, nicht §Verweise und §DoD.
**Die Norm-Prüfung muss alle Abschnitte lesen.**

→ Je ein Korrektur-Kommentar an #632 und #633; die korrigierten Werte stehen zusätzlich in #442.

### 2. Regel 144 gilt auch mit Fußzeile in der Nutzlast — und Weiche 19 B ist zum zweiten Mal belegt

Die Attributions-Fußzeile stand **ausdrücklich** im `body` des MCP-`issue_write` auf #442. Nach dem
Zurücklesen endet der Body mit `_Zuletzt gepflegt: …_` — **die Fußzeile ist weg.** Lauf 54 fand den
Verlust, Lauf 68 bestätigte ihn an fünf Bodies; **dieser Lauf zeigt, dass Mitschreiben nicht
hilft.**

🟢 **Gegenprobe in die andere Richtung** (Regel 32): die Herkunftszeile `_Zuletzt gepflegt: …_` —
ohne `---`, ohne Link — hat **beide** Schreibvorgänge dieses Laufs überlebt. **Das ist Option B von
Weiche 19, zum zweiten Mal an einem Fall belegt.** → **Weiche 42**, Empfehlung **B**.

### 3. Der Lauf hat sich dreimal selbst belogen

**a) Parallel gesendete Bash-Aufrufe teilen ein Arbeitsverzeichnis (Regel 164).** Zwei gleichzeitig
gesendete Messungen mit unterschiedlichem `cd` zogen einander das Verzeichnis weg:

| Messung | gemeldet | richtig |
|---|---|---|
| `npm audit --omit=dev --audit-level=high` | 🔴 **Exit 1** | 🟢 **Exit 0** (aus `apps/web/`) |
| `npm audit --audit-level=high` | 🔴 **Exit 1** | 🟢 **Exit 0** |
| `npm audit` (voll) | 🔴 `ENOLOCK` | ⚠️ Exit 1, 29 moderate |
| `npm run i18n:check` | 🔴 `ENOENT package.json` | 🟢 **Exit 0** |
| `uv run pytest --collect-only -q` | 🔴 **„no tests collected"** | 🟢 **5033** (aus der Wurzel) |

**Fünf Messungen, alle aus dem falschen Baum, alle nicht von einem roten Gate zu unterscheiden** —
dieselbe Klasse wie Regel 162. Gates laufen ab jetzt sequenziell und mit `pwd`-Beleg.

**b) Ein Domain-Grep ohne rechten Anker (Regel 165).** `grep "app\.who2be\.de"` trifft
**`app.who2be.dev`** (`apps/api/tests/test_invitations.py:533`, `:534`, `:560`). Dieser Lauf hätte
damit Lauf 68 („Betriebs-Subdomain kommt auf `main` 0× vor") fälschlich widersprochen. Rechts
geankert: Apex `who2be.de` **40×**, Betriebs-Subdomains `app.|api.|mcp.|supabase.who2be.de` **0×**
— **Lauf 68 hatte recht**, und Weiche 39 ist damit präziser gestellt als bisher: es geht nicht um
den Apex (der steht als Test-Fixture und als Loadtest-Schutzkonstante `PRODUCTION_DOMAIN` längst
im Repo), sondern um die vier Betriebs-Subdomains.

**c) Eine halb beantwortete Weiche als erledigt geführt (Regel 167).** Die erste Fassung des
#442-Bodys führte **Weiche 41** als **ERLEDIGT**, weil der von Lauf 68 korrigierte
`pip-audit`-Befehl **lief** (Exit 0). Die Weiche fragte aber **zwei** Dinge: die Befehlszeile **und**
den Weg in die Befehlsliste. `grep -c pip-audit CLAUDE.md` → **0**. **Die zweite Hälfte ist offen**,
der Messweg lebt weiter nur in einem Issue-Body, den jeder Lauf überschreibt — genau das, wogegen
Option C argumentiert. **Im Body korrigiert, Weichen-Zahl von 23 auf 24.**

🟢 **Regel 10 hat alle drei abgefangen.** Zusätzlich zwei Fehlalarme verhindert: die
`mcp-payload-budget`-Datei-Sperre (trifft nur eine **Plan**-Datei in #1106, Regel 163) und die
axe-Zahl **33** in #632 (ein grober `grep -rl "axe("` liefert 34 und zählt den Wächter mit —
**schlechteres Werkzeug ist kein Gegenbeleg**, Regel 127).

## Entscheidungen dieses Laufs

| Was | Beleg |
|---|---|
| **#1001: `needs-decision` entzogen, `agent-ready` vergeben** | Weiche 35 ist durch den Merge von #1101 beantwortet (Lauf 68, im Body festgehalten) — **das Label war nur stehen geblieben und hätte einen Agenten grundlos abgehalten.** Norm **4/4**, **5/5** Zeiger heute gültig, Fläche über alle 26 PRs frei, AK1 zeichengleich erfüllt |
| **#632: drei falsche Aussagen kommentiert** | s. Fund 1 |
| **#633: drei falsche Aussagen + ein Selbstwiderspruch kommentiert** | s. Fund 1; dazu „#632 = Position 2" in §Startbedingung gegen „#632 … Position 1" in §Verweise — **zwei Stellen, ein Body, zwei Zahlen** |
| **#989: Nachtrag zu Weiche 40, keine neue Frage** (Regel 9) | Das verwaiste Fragment `changelog.d/osv-ignore-http-cache-semantics.security.md:1-3` sagt „valid until **2026-11-02**" — **ab heute auch nach seiner eigenen Rechnung überholt.** Alle Zeiger und AK gültig und **gefahrlos** (Regel 161 hält) |
| **Weiche 42 neu gestellt** | Pflege-Regel 9 schreibt `gh api --input` vor; diese Session darf `gh` nur für Suche nutzen. Drei Optionen, Empfehlung **B** |
| **Coverage-Suite nicht gefahren** | Fenster 0 Commits, Baum bitgleich `498ded60` (Regel 160). **404 s** für ein garantiert identisches Ergebnis gespart; Bezugswerte von Lauf 68 stehen mit Messdatum in #442 |

## Reihenfolge und Wellen

**Unverändert zum zweiten Mal** — und das ist eine Aussage, kein Stillstand: alle Zeiger neu
gemessen, alle Flächen neu gegen 26 PRs geprüft.

| Pos | Issue | Baum | Kriterium | Stand |
|---|---|---|---|---|
| **1** | **#632** Passkey registrieren | Web | 3 Fundament vor Fläche | ✅ startbar ohne Nebenbedingung |
| **2** | **#1001** Payload-Budget-Rest | Python | 4 Inventar vor Zuschnitt | ✅ startbar, 🆕 `agent-ready` |
| **3** | **#633** Step-up mit Passkey | Web | 1 harte Abhängigkeit | 🔴 nach #632 + Container/CI |
| **4** | **#989** `http-cache-semantics` | Web | — | 🔴 Weiche 40 + Lockfile-Sperre |

| Welle | Pakete | Bäume |
|---|---|---|
| 🟢 **A — jetzt, parallel** | **#632 ‖ #1001** | **Web ‖ Python**, vollständig datei-disjunkt, zwei Suiten |
| **B — nach A** | #633 | Web; hart nach #632, plus Container-Laufzeit **oder** CI-Lauf |
| **C — nach B** | #989 | Web; derselbe Vitest-Baum, deshalb nicht parallel; + #1092 mergen |
| **D — parallel, kein Agent** | **Merges**, 15 grüne PRs bei ≤ 9 dahinter | — |

⚠️ **Würde Weiche 40 mit B entschieden**, wäre #989 ein **drittes** Paket in Welle A.

## Was dieser Lauf nicht geleistet hat

- 🔴 **Die drei falschen Aussagen stehen weiter in den Bodies von #632 und #633.** Sie sind
  kommentiert und in #442 korrigiert, aber nicht an der Stelle behoben, an der ein Agent zuerst
  liest. **Das ist der ehrliche Preis dieses Laufs und der Grund für Weiche 42.**
- ⚪ **Die CI-Lage von 24 PRs ist übernommen, nicht gemessen** — begründet, aber kein Beleg.
- 🔴 **Kein Implementierungs-Issue geschnitten** (Weiche 31, Empfehlung B) — und bei einem Fenster
  von 0 Commits kam der Erkenntnisgewinn dieses Laufs aus Body-Verrottung und aus drei Eigenfehlern,
  **nicht aus dem Repo**. Das ist das härteste Argument für Weiche 18 bisher: **die Pakete sind
  fertig, was fehlt, sind Merges.**
