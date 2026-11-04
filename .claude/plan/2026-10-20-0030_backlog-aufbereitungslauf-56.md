# Backlog-Aufbereitungslauf 56 — 2026-10-20

**Basis:** `main` @ `a6027b88` — **0 Commits** seit der Lauf-55-Basis, drittes
bitgleiches Fenster am Arbeitsbaum. Alle Zahlen gegen `origin/main`-Refs
gemessen, nach `git fetch --unshallow` (50 → **1562** Commits, Regel 90).

## Der zentrale Befund: das Fenster ist NICHT leer

Lauf 55 schloss aus einem bitgleichen Baum auf ein stilles Fenster. Diesmal ist
der Baum erneut bitgleich — **und das Fenster trägt fünf neue PRs, zwei davon
Sach-PRs, die fünf der sechs Warteschlangen-Pakete umsetzen.** Der Fehler wäre
gewesen, nur `git log` zu messen.

| PR | Inhalt | Deckt | Zustand |
|---|---|---|---|
| **#988** | Job-Timeouts, `concurrency`-Kommentar, Skip-Gate-Meldung, sauberer Web-Install | **#849, #923, #949, #959** | 18 Checks, **alle grün**, gate-aktuell, 0 hinter `main`, konfliktfrei, kein Draft |
| **#987** | axe-Test-Timeout zentral im a11y-Helfer | **#975** | 18 Checks, **alle grün**, gate-aktuell, 0 hinter, konfliktfrei, kein Draft |
| #986 | `axllent/mailpit` v1.30 → v1.31 | — | grün |
| #985 | python-minor-patch, 6 Updates | — | grün (ersetzt #955) |
| #984 | web-minor-patch, 21 Updates | — | grün (ersetzt #954) |

Beide Sach-PRs tragen englische `Closes #NNN`-Keywords (Regel 61 erfüllt).
#987s Body nennt eine **PM-Entscheidung vom 2026-10-16** → **Weiche 14 ist
außerhalb des Repos beantwortet** (Regel 119) und umgesetzt, mit einem
**vierten** Weg, den die Warteschlange nicht gelistet hatte (zentrales
`vi.setConfig` im Helfer statt globaler Anhebung oder 43 Einzelstellen).

**Folge für die Warteschlange:** von sechs Positionen sind **fünf in Review**.
Startbar bleibt **#632**; dahinter **#633** (harte Abhängigkeit + Docker).

## Konsolidierung von #988 gegen die Akzeptanzkriterien

Substanz vollständig geliefert, **vier Kriterien im Buchstaben unerfüllbar —
ausschließlich wegen der Bündelung** (Regel 19: melden, nicht umbauen):

| Issue | Kriterium | Messung |
|---|---|---|
| #849 | AK1 je Job ein Timeout | ✅ YAML-Parser: **12 von 12**, `ohne Timeout: []` |
| #849 | AK2 „die Werte aus der Tabelle" | 🔴 **zwei Abweichungen:** Tabelle `python` **30**/`web` **25**, PR setzt **40**/**30** — bewusst nach `max(Issue-Wert, 2× gemessenes Max)`; **AK3 wird dadurch besser erfüllt, AK2 verfehlt** (die beiden Kriterien widersprechen sich) |
| #849 | AK4 „12 Einfügungen, 0 Löschungen", `grep -c '^-[^-]'` → 0 | 🔴 gemessen **20/4**, `^-[^-]` → **4**. Substanz hält: **12** hinzugefügte Nicht-Kommentarzeilen, **0** entfernte |
| #923 | AK1 `run_id` → 0 | ✅ `grep -c` am PR-Head → **0** |
| #923 | AK2 kein Scheduler-Versprechen | ✅ neuer Block `:8-15` nennt `cancel-in-progress`, die Ref-Gruppe und die drei gemessenen Gegenfälle |
| #923 | AK3 „ausschließlich `#`-Zeilen" | 🔴 verfehlt (die 12 Timeout-Zeilen). Substanz hält: `concurrency`-Wert vor/nach **identisch** (YAML-Parser) |
| #949 | AK1 kein pytest in `::error::`/`help=` | ✅ **0** Treffer |
| #949 | AK2 Pfad + `::error::` + Exit 2 | ✅ ohne Pipe gemessen: **Exit 2**, Pfad genannt |
| #949 | AK3 alle Exit-Pfade getestet | ✅ neue `scripts/tests/test_assert_skips_within_budget.py`, **6** Tests |
| #949 | AK4 „insbesondere kein `ci.yml`" | 🔴 verfehlt (Bündelung) |
| #959 | AK1–AK4 | ✅ `rm -rf node_modules` vor `npm ci`; stderr-Warnung nennt `npm run test:coverage`; pnpm/yarn und Python-Zweig unberührt. ⚠️ das wörtliche `\|\| true` ist weg, die Nicht-Abbruch-Semantik durch `if !` erhalten |
| #959 | **AK5 Rot-Probe** | 🔴 **nicht herstellbar — der PR sagt es selbst:** mit npm 10.9.9 und 11.19 löscht schon das `npm ci` des ALTEN Hooks `node_modules` und holt das Binding zurück. Beide Richtungen **Exit 0** |

→ **Weiche 20** (Bündelung) und **Weiche 21** (#959s Prämisse).

## Vier Werte aus Lauf 55 richtiggestellt

Der Baum ist bitgleich, also kann keine dieser Zahlen sich geändert haben —
jede Abweichung liegt am Verfahren, nicht am Repo.

1. **#831 ist gate-alt.** Lauf 54 hatte recht, Lauf 55 hat einen richtigen Wert
   in einen falschen „korrigiert". Zwei Wege, gleiches Ergebnis: Head-SHA über
   `git` und über `gh api .../pulls/831` identisch (`fa0f6a50`), darauf **15**
   Checks, **kein** `secrets`, und `e2e-mobile` als **ein** Check statt der drei
   Profile. **Gate-alt sind #831 und #823** → 22 von 24 PRs gate-aktuell.
2. **Der Fragment-Bestand ist 323, nicht 324.** `changelog.d` trägt **324**
   Dateien; `IGNORED_NAMES` in `scripts/changelog_fragments.py:84` nimmt
   `README.md` heraus (Regel 18/85).
3. **Die „zwei widersprüchlichen Glob-Schreibweisen" sind keine.**
   `vite.config.ts:15` ist **eine** Konstante, benutzt als Include des Projekts
   `a11y` (`:58`) und als Exclude des Projekts `unit` (`:51`); `:72` steht in
   `coverage.exclude` — eine andere Liste für einen anderen Zweck, bewusst
   breiter. Die haltbare Fassung: das **Projekt**-Glob ist `.tsx`-only, eine
   künftige `*.a11y.test.ts` landet im Projekt `unit` — genau der Fall, den
   #987 über den Helfer jetzt abdeckt.
4. **#947 und #674 sind 0 Commits hinter `main`, nicht 18** — Dependabot hat
   beide am 2026-10-19 rebased.

## Weiche 5: die Prämisse ist widerlegt

`apps/web/osv-scanner.toml:9-15` begründet den Ignore mit
„http-cache-semantics@4.2.0 has no fixed release yet". Gemessen:

- Advisory-Range **`<=4.2.0`**, `fixAvailable: **true**` (npm-Audit-JSON).
- **`http-cache-semantics@4.3.0` ist am 2026-10-04 erschienen** — 16 Tage vor
  diesem Lauf und nach dem Schreiben der Begründung.
- `npm audit fix --dry-run`: genau **`change http-cache-semantics 4.2.0 =>
  4.3.0`**, ein transitiver Sprung, kein Major, keine direkte Abhängigkeit.
  (Die Ausgabe mischt `add lightningcss-android-arm64` und „43 packages" hinein
  — das ist optionale Plattform-Auflösung, nicht Teil des Fixes.)
- **Weder #984 noch #674 trägt ihn** — alle drei Lockfiles stehen auf `4.2.0`.
- Nebenbefund: der von npm heute gemeldete Pfad
  (`license-checker-rseidelsohn → @npmcli/arborist → npm-registry-fetch →
  make-fetch-happen → http-cache-semantics`) weicht in den Mittelgliedern von
  dem in der `reason` dokumentierten ab (`pacote → sigstore → @sigstore/sign`).

Damit ist der einzige `audit`-Fund **reparierbar statt Politik** — und #831s
rotes `audit` hat eine Ursache mit Fix. → als Arbeitspaket geschnitten
(neues Issue), Sperre: `apps/web/package-lock.json` hält **#674 UND #984**.

## Weiche 10: #823s Nutzlast ist selbst verrottet

Seine `PROJECT.md`-Reihenfolge-Tabelle nimmt das geschlossene #624 heraus
(richtig), **kennt aber #849/#923/#949/#959/#975 nicht** und führt #540 weiter
als „needs-decision und umgebungsblockiert", obwohl der Mechanismus entschieden
und in #980 umgesetzt ist. Seine `STATE.md` ist vom **2026-10-05** (Lauf 41),
ohne die ganze ADR-0053-Phase-E-Serie. **Ein Merge behebt einen Teil der
Verrottung und zieht neue ein.**

## Weiche 19: fünf Schreibvorgänge, ein belastbarer Satz

Die Fußzeile steht am 2026-10-20 in **genau vier** Bodies — #540, #535, #435,
#428 — also unverändert in denen, die kein Lauf neu geschrieben hat (Regel 129
in der Wirkung bestätigt). Darüber hinaus hat dieser Lauf fünf Schreibvorgänge
an #442 byte-genau gegengelesen:

| # | Schreibweg | Nutzlast | Ergebnis |
|---|---|---|---|
| 1 | `gh api -X PATCH` | ohne Fußzeile, ohne Erwähnung | 🟢 **angehängt**: 65.177 → **65.236** (**+59**) |
| 2 | `gh api -X PATCH` | ohne Fußzeile, **Zeichenkette in der Prosa zitiert** | 🔴 nichts angehängt, Differenz **0** |
| 3 | `gh api -X PATCH` | Erwähnung entfernt | 🔴 **weiterhin** nichts, Differenz **0** |
| 4 | `gh api -X PATCH` | Fußzeile **ausdrücklich** am Ende | 🔴 **entfernt**: 68.212 → **68.154** (**−58**), 0 Vorkommen |
| 5 | `gh api -X PATCH` | ohne Fußzeile | 🔴 nichts angehängt, zeichengenau identisch |
| — | `issue_write` (MCP) | ohne Fußzeile (#989) | 🔴 keine, 7.644 Zeichen |
| — | `issue_write` (MCP), Lauf 55 | **mit** Fußzeile, fünfmal | 🔴 keine, fünf von fünf |

**Was belastbar ist:** wer die Fußzeile selbst mitschreibt, verliert sie — jetzt
auf **beiden** Schreibwegen belegt. **Regel 129s Gegenmaßnahme ist damit
bestätigt, nicht widerlegt.** 🟢 **Was 129 im Wortlaut zu weit ging:** ein Body
**kann** sie tragen, Schreibvorgang 1 beweist es.

🔴 **Was dieser Lauf NICHT geschafft hat: den Mechanismus erklären.** Ich habe
zwei Erklärungen gebaut und beide im selben Lauf widerlegt — erst „der
`gh api`-Weg hängt an, der MCP-Weg strippt" (Schreibvorgang 2), dann „der
Anhänger prüft auf Anwesenheit der Zeichenkette" (Schreibvorgang 3, nachdem die
Erwähnung entfernt war). **Die erste Fassung dieses Befundes stand schon im
Body von #442, als Schreibvorgang 3 sie widerlegte** — genau der Fehler, den
Regel 12 verbietet. Beide Fassungen sind richtiggestellt. → **Regel 133.**

🟢 **Praktische Folge: Option B, und das Thema schließen.** Die Zeile „Zuletzt
gepflegt: Aufbereitungslauf N" hat alle fünf Schreibvorgänge überlebt;
Kommentare behalten die Fußzeile durchgehend (vier von vier in diesem Lauf).

## Eine eigene Einheitenverwechslung, gefangen bevor sie zur Behauptung wurde

Nach den Label-Schreibvorgängen an #975 und #959 sahen die Bodies um 386 bzw.
237 **kürzer** aus — ein Label-Write ohne `body`-Parameter, der Text löscht,
wäre ein schwerer Fund gewesen (Regel 117). Ursache war die Messung, nicht der
Schreibvorgang: `wc -c` zählt **Bytes**, `.body|length` zählt **Zeichen**, und
die Bodies sind voller Mehrbyte-Zeichen. Zeichengenau gegengelesen sind beide
Bodies vor und nach dem Write **identisch**. **Genau die Falle aus Regel 18** —
diesmal in der eigenen Messung.

## Arbeitspakete dieses Laufs

### A — selbst entschieden (Repo belegt es)
1. #442 neu ordnen + Wellen neu schneiden; die vier Lauf-55-Werte
   richtigstellen; Body kürzen (Regel 10, **hinterher** gemessen:
   **77.430 → 68.611 Zeichen, −8.819**).
2. #975: `needs-decision` entfernt — Weiche 14 ist beantwortet und umgesetzt.
   Dazu die Glob-Richtigstellung als Kommentar.
3. **#989** angelegt — `agent-ready`, `size/S`, vier Pflichtfelder, fünf Kriterien,
   exakte Verifikations-Kommandos (Regel 34/65).
4. #959: Prämisse-Befund als Kommentar, `needs-decision` setzen.
5. Konsolidierungs-Bericht als Kommentar an #988.

### B — braucht eine Owner-Antwort
- **Weiche 20** — #988 bündelt vier Issues; vier Kriterien sind dadurch im
  Buchstaben unerfüllbar, die Substanz ist geliefert.
- **Weiche 21** — #959s Rot-Probe ist auf zwei npm-Versionen nicht herstellbar;
  #988 schließt #959 per Keyword trotzdem.
- **Weiche 22** — nach #632/#633 ist der Vorrat an `agent-ready`-Arbeit leer;
  zwanzig Posten warten auf Weichen-Antworten.
- Weiche 5 mit widerlegter Prämisse neu gestellt; Weiche 10 mit neuem Beleg.

### Drei neue Pflege-Regeln
- **131** — Ein „kein Fix verfügbar" in einer befristeten Ausnahme ist ein
  Datum, kein Zustand: die Begründung verrottet unabhängig von der Frist.
- **132** — Ein gebündelter PR macht jedes Diff-Scope-Kriterium seiner Issues
  unerfüllbar; die Substanz kann vollständig geliefert sein.
- **133** — Ein Mechanismus, den zwei Beobachtungen zu erklären scheinen,
  braucht die dritte. Hier hat die dritte ihn umgebracht — zweimal.

## Messwerte des Laufs

Sequenziell, ein Schreiber je Baum, Node **v22.22.0**, **ohne vorherige
Reparatur** (Regel 120), Exit-Codes **ohne Pipe** (Regel 94):

`npm run test:coverage` → **Exit 0**, **267 Dateien / 2517 Tests**, Coverage
**89,47 / 83,67 / 86,13 / 91,2** (Statements 11419/12762, Branches
**7993/9553**, Functions 3325/3860, Lines 10507/11520), Dauer **350,98 s** —
**dritte exakte Reproduktion auf bitgleichem Baum**, Branches in **5 von 6**
Beobachtungen auf `7993` (Lauf 52 mit 7994 bleibt der Ausreißer), Abstand zur
Schwelle **4,67** Punkte · `npm run lint` → **Exit 0, 90 problems, 0 errors**,
8 Regeln, **7** `--fix`-bar, Verteilung unverändert (`set-state-in-effect` 48 ·
`classnames-order` 18 · `only-export-components` 12 · `incompatible-library` 5 ·
`preserve-manual-memoization` 4 · `use-memo`/`refs`/`exhaustive-deps` je 1) ·
`npx tsc -b` → **Exit 0**, Ausgabe **0 Byte** · `npm run i18n:check` → **Exit
0**, **160** bekannte Waisen · `npm audit --omit=dev --audit-level=high` →
**Exit 0, 0** (der eine `high`-Fund ist dev-only) · `uv run ruff check .` →
**Exit 0, 0 Funde** · `uv run mypy .` → **Exit 0, 0 Funde in 608 Dateien** ·
`uv run pytest --collect-only -q` → **3648** Tests, **135** unter
`packages/billing/` · `changelog_fragments.py check` → **Exit 0, 323**
Fragmente · `docker info` → **Exit 1**, kein `podman` · `ci.yml` **1212**
Zeilen, **12** Jobs, **0** mit `timeout-minutes` (am #988-Head: **1228**
Zeilen, **12 von 12**) · `main` `all-green` **success** (Run 38953392933),
**0** rote Checks, **0** `cancelled` unter den letzten zehn `main`-Läufen.

Zeiger von #632/#633 einzeln nachgemessen, **alle unverändert**:
`MfaSection.tsx` **297** · `e2e/helpers/auth.ts` **180** · `package.json`
**80** · `vite.config.ts` **89** · `SessionProvider.tsx` **267** ·
`api/types.ts` **2402** · `client.ts` **1699** · `LoginPage.tsx` **394** ·
`i18n/audit.test.ts` **371** · `orphan-baseline.json` **160** Einträge.

## Bedingungen

Read-only am Arbeitsbaum außer dieser Plan-Datei. Kein Docker (nicht
vorhanden), keine Reparatur vor der Messung. Der MCP-Server der eigenen AgentDB
war zum **elften** Lauf nicht erreichbar (`Who2Be---Coder` liefert über
`ToolSearch` keine Werkzeuge) — Persona und Playbook-Katalog lagen im
System-Prompt vor, `fetch_playbook`, `fetch_resource` (Norm „Agent-ready
Arbeitspaket"), `record_usage` und `search_memory` nicht.
