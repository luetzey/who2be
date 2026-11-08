# Backlog-Aufbereitungslauf 75

**Datum:** 2026-11-08
**Gemessen gegen:** `main` @ `f89acf87` (Baum `c751ed64`), Fenster seit Lauf 74 **0 Commits**
**Offene PRs:** 25 _(waren 24; +#1125)_
**Warteschlange:** [#442](https://github.com/luetzey/who2be/issues/442)

## Der Lauf in einem Satz

Das Fenster war leer — und genau deshalb ist aufgefallen, dass **alle drei startbaren
Pakete eine Startfreigabe trugen, die auf einem grünen `main` ruht**, während `main`
seit dem 2026-11-06 rot ist.

## Umgebung

| | |
|---|---|
| Node / npm / uv | v22.23.4 / 10.9.9 / 0.11.32 |
| Klon | shallow (50) → **1676** Commits nach `--unshallow` (Regel 90) |
| Container-Laufzeit | `docker info` → **Exit 1**, kein `podman` — **51. Messung in Folge** |
| `/usr/bin/time` | nicht vorhanden → ohne Wrapper gemessen (Regel 177) |
| Who2Be-MCP | 🔴 **nicht erreichbar** (`Who2Be---Coder` braucht Autorisierung) — keine Persona-, Playbook-, Resource- oder Memory-Tools, keine Kurations-Rückmeldung |

Arbeitsbaum sauber (`git status --porcelain` leer), `HEAD == origin/main`,
Baum-OID `c751ed64` — die Baum-Gates sind an einem **bitgleichen** Baum gemessen.

## Gates (selbst gefahren, Exit-Codes am unverketteten Befehl)

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | Exit 0, „All checks passed!" |
| `uv run mypy .` | Exit 0, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | Exit 0, **5034** Tests |
| 🔴 `changelog_fragments.py check` | Exit 0, **405** Fragmente — **Lauf 74 nannte 406** |
| 🔴 `pip-audit` (`main`-Stand) | **Exit 1** — `oauthlib 4.0.0`, CVE-2026-49272, Fix 4.0.1, 398 Requirements |
| 🟢 `pip-audit` (Ergebnisbaum #1120) | **Exit 0**, „No known vulnerabilities found", `oauthlib==4.0.1` |
| `npm run lint` | Exit 0, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe **0 Byte** |
| `npm run i18n:check` | Exit 0, **156** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | Exit 0, 0 vulnerabilities |
| `npm audit` (voll) | Exit 1, **28 moderate** (Ranges `glob 9.0.0 - 14.0.1`, `minimatch 7.0.0 - 11.0.0`) |
| `npm run test:coverage` | ⚪ **nicht gefahren, mit Grund** (Regel 160: Fenster 0 Commits, `apps/web/src` 0× bewegt) |
| 🔴 `main`-CI am Kopf | **Lauf `42178623925`**, `conclusion: failure` — `audit` + `all-green`, 2 von 14 Jobs |

## Selbst erledigt

### 1. Drei Paket-Bodies korrigiert — falsche Startfreigabe (Weiche 50, Regel 189)

Alle drei startbaren Pakete schlossen mit einer **Erlaubnis**, gestützt auf einen grünen
`main`:

| Issue | Wortlaut bis Lauf 74 | Stelle |
|---|---|---|
| #632 | „Regel 80 greift nicht" **und** „ein roter Check ist ein Signal und **kein Erbe**" | §Startbedingung + §Eskalation |
| #1001 | „`main` ist gemessen grün … Regel 80 greift nicht" | §Zusätzliche Grenzen |
| #633 | dasselbe **plus** „Ausweichweg: … `all-green` ist auf `main` grün, **der Weg steht**" | §Startbedingung 5 + 2 |

Lauf 74 hat diese Zeilen gesehen und als „Bezugswert, keine Freigabe" übernommen —
**nachgelesen schließt jede mit einer Erlaubnis.** Übernahme ohne Beleg (Regel 178).

Bei **#633** war es nicht nur falsch, sondern teuer: sein **einziger** Weg ohne
Container-Laufzeit war als offen beschrieben. Korrigiert auf den tragfähigen Messweg —
**die einzelnen E2E-Job-Conclusions lesen, nicht das aggregierte `all-green`**.

Alle drei Bodies vollständig neu geschrieben (Weiche 45 Option A): `all-green` in
§Verifikation/§DoD **ausgesetzt**, §Eskalation sagt ausdrücklich, dass dieses Rot ein
**Erbe** ist, und jede Stelle nennt den `audit`-Job-**LOG** als Beurteilungsgrundlage
statt der Conclusion.

### 2. Fragmentzahl: 405, nicht 406 (Regel 187)

`#442` §Pflege-Regel 8 führte die Zahl als **abgehakt**: „eingelöst: 406, nicht 407 —
die 407. Datei ist `README.md`". Gemessen am bitgleichen Baum:

```
$ uv run python scripts/changelog_fragments.py check   # "405 Fragment(e) ... in Ordnung", Exit 0
$ ls changelog.d/*.md | wc -l                          # 406
$ git ls-tree origin/main changelog.d/ | grep -c README  # 1
```

**Beide Werte der Regel waren um eins zu hoch** — und die Regel war genau die Stelle, die
das verhindern sollte. Dieselbe Zahl stand in #1001 und #632 als `403`. Alle drei Stellen
korrigiert, und die Regel trägt die Zahl nicht mehr als abgehakten Wert.

### 3. Merge-Wirkung am Ergebnisbaum messen (Regel 188)

`git diff origin/main pr/1120` zeigt **17 Dateien / 345+ / 466−** und liest sich als
Rückabwicklung (`setup-uv` v10.3.3 → v10.3.0, −76 Zeilen in `test_account_lifecycle.py`).
**Nichts davon passiert beim Merge.** Die Wirkung ist:

```bash
T=$(git merge-tree --write-tree origin/main pr/1120)
git diff --stat origin/main $(git commit-tree $T -p origin/main -m probe)
#   uv.lock | 6 +++---
#   1 file changed, 3 insertions(+), 3 deletions(-)
```

Auch der Drei-Punkt-Diff ist es nicht (4+/4−). Lauf 74 nannte die richtige Zahl; dieser
Lauf nennt den Weg, auf dem sie richtig bleibt.

### 4. Weiche 46 billiger belegt — ohne fremde Datenbank

Lauf 74 brauchte npms Advisory-API (`api.osv.dev` ist per Proxy gesperrt). **`npm audit`
druckt die verwundbaren Ranges selbst:**

| | glob | minimatch |
|---|---|---|
| Verwundbare Range | `9.0.0 - 14.0.1` | `7.0.0 - 11.0.0` |
| `main` | `13.0.6` ×1 — **innen** | `10.2.5` ×7 + `10.2.6` ×1 **innen**, `3.1.5` ×1 **außen** |
| #1124 | `14.0.3` ×1 — **außen** | `11.0.3` ×8 **außen**, `3.1.5` ×1 per Override gehalten |

Der `reason`-String in `apps/web/osv-scanner.toml:20` nennt `minimatch@3.1.5` weiter
falsch als betroffen. **#1124 hat recht**, und #1124 behebt den Node-Boden **nicht**
(`apps/web/package.json:8` trägt an seinem Baum unverändert `">=22 <23"` — Weiche 47).

### 5. Norm-Prüfung und Warteschlange

- **Norm 4/4 bei allen vier `agent-ready`-Issues**, Zeiger: #632 **13/13**,
  #1001 **5/5**, #633 **10/10**, #989 AK1-Zeiger `:6313` gültig — **null verrottet**.
- **Kein `agent-ready` vergeben, keines entzogen; kein `needs-decision` vergeben,
  keines entzogen.** Der Fund war eine falsche **Angabe**, kein fehlendes Feld — er
  gehört in den Body (Regel 170), nicht auf ein Label.
- Datei-Sperren über alle 25 PRs am vollen, zuvor auf Existenz belegten Pfad gemessen
  (30 Pfade). **Kein einziger der 25 PRs fasst `apps/web/src/**` an.**
- #442 §Warteschlange, §Wellen, §Gates, §Weichen und §Pflege-Regeln neu geschrieben.

## Braucht eine Owner-Antwort

**31 offene Weichen** (+50). Neu:

**Weiche 50 — Darf ein Paket-Body überhaupt ein Urteil über die Farbe von `main`
tragen?** Drei Optionen mit Trade-offs als Kommentar an #442, **Empfehlung B**
(Messung ja, Schlussfolgerung nie) plus die billige Gegenprobe
`grep -nE "Regel 80 greift nicht|der Weg steht|kein Erbe"` in jedem Lauf.
Option C ist inhaltlich besser und hängt an **Weiche 5**.

🔴 **Der dringendste Posten ist unverändert #1120** — dritter Lauf in Folge als
oberster Posten gemeldet, und der erste mit einem Fenster von null Commits. Drei Zeilen
Merge-Wirkung, konfliktfrei, `all-green` namentlich `success` bei 15 ausgeführten
Checks, Wirkung am Ergebnisbaum gemessen (`pip-audit` → Exit 0). **Mergen ist nach
Persona-Grenze ohne Freigabe verboten** (Weiche 11/34).

## Reihenfolge und Wellen

**#632 → #1001 → #633 → #989** (unverändert).

| Welle | Inhalt | Bedingung |
|---|---|---|
| **0** (Owner) | #1120 | der CVE-Fix, vor allem anderen |
| **A** | #632 + #1001 | code-disjunkt (Vitest gegen pytest), beide Flächen frei; gemeinsame DoD-Fläche `STATE.md` → Basis #1103 |
| **B** | #633 | nach #632 (hart) + Container-Laufzeit **oder** CI-Lauf mit gelesenen E2E-Job-Conclusions |
| **C** | #989 | erst Weiche 48, dann die Fläche |
| **M** (Owner) | #1120 → #1124 → #1123 → Domain-Doku | #1106/#1122 nicht beide (Weiche 49) |
| **N** (Owner) | 16 Protokoll-PRs beliebig, danach seriell #1103 → #1090 → #1078 | `STATE.md` ist 37 Tage alt |
| **P** (Owner) | #1107, #1078, #831 per Branch-Update heilen | erst nach #1120 neu messen |
| **Q** (Owner) | #674 | kollidierend (`rc 1`) und rot |

## Neue Regeln

- **187** — Eine Zahl, die eine Pflege-Regel als „eingelöst" abhakt, ist damit nicht
  nachgemessen. Eine Regel hält die Lehre fest, nicht die Messung.
- **188** — Die Wirkung eines Merges wird am Ergebnisbaum gemessen, nicht am Branch.
- **189** — Ein Body darf eine Messung tragen, aber keine Freigabe, die auf einer
  Fremd-Tatsache ruht. Eine verrottete Zahl wird zu einer alten Zahl; eine verrottete
  Erlaubnis wird zu einer falschen Erlaubnis.
