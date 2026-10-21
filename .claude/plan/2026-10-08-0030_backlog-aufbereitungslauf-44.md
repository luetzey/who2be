# Backlog-Aufbereitungslauf 44 — 2026-10-08

**Basis:** `main` @ `73ce3277` (7 Commits seit der Lauf-43-Basis `4a9918ae`: #842–#848).
Alle Zahlen in diesem Lauf sind gegen `origin/main`-Refs gemessen, nicht
fortgeschrieben. Klon war shallow (50 Commits), nach `git fetch --unshallow`
**1454** — siebter Lauf in Folge, in dem Regel 90 greift.

## Ausgangslage

Lauf 43 fand ein startbares Issue (#632), neun offene PRs und sieben offene
Owner-Weichen. Seither ist **kein** PR gemergt worden; die sieben neuen
`main`-Commits kommen aus Arbeit, die über Karten läuft und kein Issue trägt
(Messreihe 10/0 → … → 8/1 → **7/0**).

## Der zentrale Befund dieses Laufs

**`main` ist seit sechs Commits ohne CI-Spruch — nicht rot, nicht grün, sondern
unentschieden.** Regel 91 verlangt, `status` und `conclusion` getrennt zu lesen
und drei Zustände zu kennen; dies ist der dritte, und diesmal nicht als
Lesefehler, sondern als Tatsache.

| Commit | CI-Lauf | `status`/`conclusion` | `all-green` am Commit |
|---|---|---|---|
| `ac7e1971` (#842) | 37664513760 | `completed` / **`success`** | ✅ letzter Spruch, 2026-10-07 18:08 UTC |
| `8c8e55a8` (#843) | 37677041105 | **`in_progress`** seit 19:46 | — (12/13 Jobs grün) |
| `5e4e2609` (#844) | 37681285714 | `completed` / **`cancelled`** | 🔴 Check-Run existiert nicht |
| `70562e80` (#845) | 37684515544 | `completed` / **`cancelled`** | 🔴 existiert nicht |
| `410cce41` (#846) | 37689484805 | `completed` / **`cancelled`** | 🔴 existiert nicht |
| `c24746c9` (#847) | 37694886568 | `completed` / **`cancelled`** | 🔴 existiert nicht |
| `73ce3277` (#848, HEAD) | 37703027148 | **`pending`**, 0 Jobs | 🔴 existiert nicht |

**Die Ursache steckt in einem Job und in einer fehlenden Zeile.** Lauf
37677041105 hat 12 von 13 Jobs grün; `e2e` (Job `112983184503`) hängt in
Schritt 8 „Install Playwright browser" seit `19:49:00Z`. **Kein Job in
`ci.yml` trägt `timeout-minutes`** — `grep` → kein Treffer, über
`yaml.safe_load` für alle zwölf bestätigt —, also gilt die
360-Minuten-Voreinstellung.

**Gegenprobe, nachträglich gemessen (00:41 UTC):** der eigene PR dieses Laufs
(**#851**) ist auf seinem Branch vollständig durchgelaufen — `all-green` **16/16**,
gate-aktuell (mit `secrets`). Die Gruppe `ci-CI-851` ist eine andere als
`ci-CI-refs/heads/main`: **nur `main` ist blockiert, PR-Läufe sind es nicht.**
Damit ist die Diagnose von zwei Seiten belegt — und die eine Vorhersage dieses
Laufs, die daneben lag (die erste Fassung der Wellen-Zeile H in #442 nahm an,
auch ein PR-Lauf stelle sich hinter den Hänger), ist in #442 korrigiert.

**Und die Pointe:** `cancel-in-progress: ${{ github.ref != 'refs/heads/main' }}`
(`ci.yml:14`) ist auf `main` **false**, damit jeder Commit einen eigenen Spruch
bekommt. GitHub hält pro Gruppe einen **laufenden** und einen **wartenden**
Lauf; ein neuer Push verdrängt den **wartenden**. Hängt der laufende, kehrt die
Einstellung ihre eigene Begründung um — **vier Sprüche verloren, kein Check
rot.** → Regel 102, Regel 103.

## Arbeitspakete dieses Laufs

### A — selbst entschieden (Repo belegt es)

1. **#849 angelegt** — `ci: jeder Job bekommt timeout-minutes`, `agent-ready`,
   `size/S`. Werte aus den **12 jüngsten grün abgeschlossenen `main`-Läufen**
   abgeleitet (Maximum je Job verdoppelt, auf 5 gerundet, Minimum 10):
   `python` 13,8 min → 30 · `e2e-billing-cloud` 9,9 → 25 · `web` 9,4 → 25 ·
   `e2e-mobile` 4,6 → 20 · `e2e` 3,2 → 20 · `compose-smoke` 2,4 → 15 ·
   `audit` 0,6 → 15 (netzgebunden, Live-CVE-DB) · `secrets` 0,3 → 10
   (n = 3, Job existiert erst seit #839) · `changelog-guard`, `backup-alarm`,
   `changes`, `all-green` je 10. Schreibt **nur** `.github/workflows/ci.yml`
   plus ein `changelog.d/`-Fragment: zwölf eingefügte Zeilen.
2. **#442 neu geordnet** — Reihenfolge, Wellen, Kollisionen, Sammelpunkte und
   Messwerte gegen den neuen Stand; Regeln **101–103** ergänzt, die
   „NEU"-Markierungen von 98–100 entfernt.
3. **Selbstkorrektur dokumentiert** — die erste Check-Run-Messung dieses Laufs
   meldete „🔴 CodeQL" an **sieben** PRs. Dort steht **`neutral`**: kein
   Fehlschlag, nicht in `all-green`. Der Filter kannte zwei von sieben
   möglichen Conclusions. → Regel 101.

### B — bewusst **nicht** geschrieben

**An #632, #633, #428, #435, #535 und #540 wurde nichts geändert.** Alle
Zeiger und alle Dateigrößen halten — erster Lauf seit Langem ohne eine einzige
Zeiger-Korrektur. Gegengeprüft über ein Skript, das jeden
`` `pfad:zeile` ``-Zeiger aus den Bodies auflöst, die Zeile **liest** und ihren
Inhalt gegen das Label vergleicht (Regel 97), plus die Zeilenzahl jeder
getragenen Datei (Regel 98):

`ci.yml` **1212** · `MfaSection.tsx` **297** · `LoginPage.tsx` **394** ·
`SessionProvider.tsx` **267** · `auth.ts` **180** · `audit.test.ts` **371** ·
`vite.config.ts` **89** · `Caddyfile` **195** · `entitlement.py` **283** ·
`mcp_limit_service.py` **161** — alle unverändert gegenüber Lauf 43.

Die `:871`-Treffer in #632 und #435 sind historische „war → ist"-Tabellen und
kein verrotteter Zeiger; `ci.yml:802` ist in beiden Bodies korrekt als
`secrets:` gelabelt.

**#428, #535 und #435 fehlen weiterhin Pflichtteile der Norm** (#428: Outcome
und Verifikation; #535: beides; #435: kein Outcome-Abschnitt, zwei Kriterien
ohne Schwelle). Alle drei sind `size/M` — Regel 7: der nächste Schritt ist ein
Zuschnitt, kein Nachtragen von Feldern. Deshalb kein Refinement.

### C — braucht eine Owner-Antwort

| Frage | Alter | Ort |
|---|---|---|
| 🔴 **NEU — Wie bekommt jeder `main`-Commit wieder einen CI-Spruch?** (A nur Timeouts · **B** `cancel-in-progress: true` auch auf `main` · C Merge-Queue) | 0 Tage | Kommentar an #442 |
| Darf ein PR mit Gate-altem Grün mergen? **Neun von zehn** betroffen | 1 Tag | #442 |
| Gilt der Arbeitspaket-Vertrag für Tracking-Issues? | 7 Tage | #442 |
| Bleibt `audit` im Required Check? (OSV-Frist **25 Tage**) | seit Lauf 36 | #442 |
| Coverage-Boden anheben? **Prämisse geprüft, hält** | 4 Tage | #442 |
| Caddy-Versions-Widerspruch | seit Lauf 35 | #442 |
| Die 91 ESLint-Warnungen (dritter Stillstand) | seit Lauf 36 | #442 |
| MB/MiB in der Sales-Tabelle — Ja/Nein | 1 Tag | #442 |
| #540 — Mechanismus und Prüfbarkeit | 19 Tage | #540 |

### D — Funde ohne Issue (Regel 34)

- **Das Aufbereitungs-Verfahren produziert PR-Rückstand.** #823 (Lauf 41),
  #831 (Lauf 42) und #841 (Lauf 43) sind drei aufeinanderfolgende
  Protokoll-PRs, alle Draft, alle offen; dieser Lauf legt den vierten dazu.
  Kein Lauf kann den PR des Vorgängers mergen (Regel 2), also wächst der
  Bestand um einen pro Lauf. Untereinander datei-disjunkt — in einem Zug
  mergebar.
- **`locales/{de,en}.json` ist von PRs frei und auf `main` dreimal bewegt**
  (#842, #846, #847) — die Schreibfläche von #632. Regel 100 an der eigenen
  Stelle. Gegenprobe: `apps/web/e2e`, `apps/mcp`, `ci.yml`, `vite.config.ts`,
  `Caddyfile`, `plans.md`, `LoginPage.tsx`, `SessionProvider.tsx`,
  `package.json`, `uv.lock` → je **0** Commits.
- **Der Playwright-Hänger selbst** — einmal belegt. #849 macht ihn sichtbar,
  nicht weg. Eigener Posten, falls er sich wiederholt.
- **`timeout-minutes` in `deploy.yml`, `release.yml`, `_debounce-proof.yml`** —
  dieselbe Lücke ist plausibel, aber **nicht gemessen** (Regel 49).

## Messwerte

Einzeln und sequenziell erhoben (ein Schreiber im Baum), Node **v22.22.0**:

| Messung | Ergebnis | Lauf 43 |
|---|---|---|
| `npm run lint` | Exit 0, **91** Warnungen, 0 Fehler, 59 Dateien, 8 Regeln, **9** `--fix`-bar | 91 (dritter Stillstand) |
| `npx tsc -b` | Exit 0 | Exit 0 |
| `npm run test:coverage` | Exit 0, **248** Dateien / **1965** Tests; **88,27 / 82,31 / 84,47 / 89,84** | 1944; 88,19 / 82,28 / 84,37 / 89,76 |
| `npm run i18n:check` | Exit 0, keine neue Waise, **159** bekannte (beide Locales) | 159 |
| `uv run pytest --collect-only -q` | **3061** Tests, Billing in der Collection | 3042 |
| `changelog_fragments.py check` | Exit 0, **222** Fragmente (`ls` zählt 223, Differenz `README.md`) | 215 |
| `docker info` | **Exit 1** — 20. Lauf ohne Daemon | Exit 1 |
| `grep -n timeout-minutes ci.yml` | **kein Treffer** (12/12 Jobs ohne) | nicht gemessen |
| `git merge-tree --write-tree` je PR | rc 0 für **alle zehn** | rc 0 für alle neun |

**Die vier Web-Zahlen haben sich nach zwei Stillständen wieder bewegt** — drei
Commits dieses Zeitraums liegen im `include` der Unit-Messung. Damit ist die
Prämisse der Coverage-Weiche geprüft und hält.

## Reihenfolge nach dem Lauf

1. **#849** — Timeouts in `ci.yml` (Kriterium 3; zwölf Zeilen, Datei frei und
   unbewegt, keine offene Entscheidung). Es kostet #632 nichts, dass es vorn
   steht: beide sind datei-disjunkt und in verschiedenen Stacks — das einzige
   echte Parallel-Paar dieses Stands.
2. **#632** — Passkey registrieren (achter Lauf in Folge startbar).
3. **#633** — Step-up mit Passkey (nach #632, braucht Docker).
4. Trennung des `audit`-Jobs (Weiche offen; nach #849 Zeiger neu messen).
5. Caddy-Versions-Widerspruch (Weiche offen).
6. Die 9 `--fix`-baren Lint-Warnungen (falls geschnitten).
7. **#540** — dreifach blockiert.

Wellen: **A** (#632, Web-Stack) ∥ **C** (#849, CI) sind das Parallel-Paar;
**B** (#633) erst nach A; **D**/**E** nicht gleichzeitig mit C (dieselbe
`ci.yml`); **F** nicht mit A oder B (ein Vitest-Baum); **H**/**I** (Merges)
parallel zu allem, aber nicht im selben Baum. **Siebte Wellen-Dimension neu:
ob `main` zum Startzeitpunkt überhaupt einen CI-Spruch hat.**

## Bedingungen

Read-only am Arbeitsbaum außer dieser Plan-Datei. Kein Docker (nicht
vorhanden), keine Code-Änderung. Der hängende Lauf 37677041105 ist **nicht**
abgebrochen worden: der Hebel existiert
(`POST /repos/.../actions/runs/37677041105/cancel`, Rechte tragen
`actions: write`), aber ein Abbruch ist eine Zustandsänderung an `main`s CI und
damit Owner-Schritt (Regel 96). Er läuft gegen 01:47 UTC in die
360-Minuten-Voreinstellung, danach startet der wartende Lauf für HEAD.
