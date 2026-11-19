# Backlog-Aufbereitungslauf 86 — 2026-11-19

**Auftrag:** vollständiger Vorbereitungslauf für `luetzey/who2be` — jedes offene
Issue gegen die Norm „Agent-ready Arbeitspaket", Repo-belegbare Funde mit Beleg
in den Body, Urteilsfragen als Kommentar mit drei Optionen + `needs-decision`,
danach die Warteschlange (`backlog-queue`, #442) neu ordnen und in Wellen
gruppieren. Bericht in drei Blöcken.

**Messpunkt:** `main` @ `f89acf87`, Baum `c751ed64`, `status --porcelain` leer.
**Fenster:** 0 Commits — **elftes Mal in Folge**; `main` steht seit
2026-11-06T08:05:51+01:00 (**13 Tage**). **48 offene PRs** über **53** Pfade.
**Umgebung:** Node v22.23.5, npm 10.9.9, uv 0.11.32, CPython 3.11.18;
Klon war shallow (50) → 1676 Commits nach `--unshallow`.

🔴 **Der Who2Be-MCP (`Who2Be---Coder`) war nicht erreichbar — 21. Lauf in
Folge.** Nicht verfügbar: `get_persona`, `list_triggers`, `fetch_playbook`,
`fetch_resource` (darunter die Norm „Agent-ready Arbeitspaket"),
`record_usage`, `submit_feedback`, `search_memory`/`save_memory`. Der Lauf fuhr
nach #442 und `.github/PROJECT.md` §Constraints. Kein Playbook ladbar, keine
Kurations-Rückmeldung an die eigene AgentDB.

## Ergebnis in fünf Sätzen

1. 🟢 **Die `npm`-Lage hat sich am bitgleichen Baum von selbst erholt:** aus
   25 moderate + **8 high** (Lauf 85) sind wieder **27 moderate + 0 high**
   geworden; `GHSA-fc5q-39xc-vjpf` (picomatch) wird nicht mehr gemeldet,
   während `picomatch` unverändert auf 4.0.7 steht
   (`apps/web/package-lock.json:8502`). **Weiche 56 ist einen Tag nach ihrer
   Eröffnung durch Messung erledigt statt beantwortet** → Regel 73.
2. 🟢 **Welle 0 ist erstmals Ende-zu-Ende als `pip-audit` Exit 0 gemessen** —
   drei Merges (je `rc 0`) + #1150 Option A + `uv lock --upgrade-package
   soupsieve` → **ein** `soupsieve==4.1.2` ohne Marker. Diff: 5 × 1+/1− plus
   **42+/113−**.
3. 🔴 **Der blanke Upgrade-Befehl bleibt keine Lösung, jetzt zweiseitig
   belegt:** `soupsieve==2.10` ohne Marker → Exit 1 / 3 Funde; dieselbe Zeile
   mit nicht passendem Marker → Exit 0. `pip-audit` überspringt
   marker-gefilterte Zeilen stillschweigend.
4. 🔴 **Zwei Zusagen der Liste halten nicht:** „nichts geschlossen" (#1128 und
   #1131 am 2026-11-16 geschlossen, `merged: false`) → Regel 74; und der
   Messweg zum Betreiber-Host (nackter Hostname, kein Schema — ein
   Domain-Grep findet ihn nicht) → Regel 75.
5. 🟢 **#1124 verlässt beide Advisory-Bereiche** (glob **14.0.3** > 14.0.1,
   minimatch **11.0.3** ≥ 11.0.1, Pin 3.1.5 unterhalb `>=7.0.0`) — Weiche 46
   Option A ist damit gemessen statt angenommen. Frist: 11 Tage.

## Gates — alle selbst gefahren, Exit-Codes unverkettet

| Gate | Ergebnis |
|---|---|
| `uv run ruff check .` | Exit 0, „All checks passed!" |
| `uv run mypy .` | Exit 0, 0 Funde in **659** Dateien |
| `uv run pytest --collect-only -q` | Exit 0, **5034** Tests |
| `changelog_fragments.py check` (voller Pfad) | Exit 0, **405** Fragment(e); `ls changelog.d/*.md \| wc -l` = **406** (Differenz `README.md`) |
| 🔴 `pip-audit` | **Exit 1 — 7 CVEs in 4 Paketen**, bei **125** Requirements / **124** Namen (`wc -l` = 398 = Zeilenzahl) |
| `npm run lint` | Exit 0, **94** problems, **0 errors**, 7 `--fix`-bar |
| `npx tsc -b` | Exit 0, Ausgabe **0 Byte** |
| `npm run i18n:check` | Exit 0, **156** bekannte Waisen |
| `npm audit --omit=dev --audit-level=high` | Exit 0, „found 0 vulnerabilities" |
| 🟢 `npm audit` (voll) | Exit 1, **27 moderate / 0 high**; `--package-lock-only` zeichengleich, Exit 1 |
| `playwright --list --project=chromium` | **44** Tests in **9** Dateien |
| `payload_report` | Exit 0, Builder **103 / 108.251**, Guard **103 / 108.251**, `instructions` **1.834** B — 21. identische Messung |
| `pytest test_tool_payload_budget.py -q` | Exit 0, **64 passed** |
| `npm run test:coverage` | ⚪ nicht gefahren, mit Grund (Fenster 0 Commits, `apps/web/src` unbewegt) |
| 🔴 `main`-CI | Lauf `42178623925`, `completed` **und** `failure` getrennt gelesen, **2 von 14** Jobs rot |
| `docker info` | **Exit 1**, kein `podman` — 62. Messung in Folge |

## Der Fund des Laufs — eine Advisory kann auch verschwinden

```
npm audit --json -> {info:0, low:0, moderate:27, high:0, critical:0, total:27}
distinct advisories: GHSA-3g3m-2fjr-6pw4 glob      >=9.0.0 <=14.0.1
                     GHSA-g3hv-75wg-m249 minimatch >=7.0.0 <11.0.1
grep -c GHSA-fc5q-39xc-vjpf <audit.json> -> 0
picomatch im Lockfile -> 4.0.7 (package-lock.json:8502), unveraendert
```

Von Hand gegengelesen auf vier Wegen (Regel 10): voller Lauf, `--package-lock-only`,
JSON-Zähler, Advisory-Liste. ⚠️ Ob die Advisory zurückgezogen oder ihr Bereich
korrigiert wurde, ist von hier **nicht** messbar — als Grenze geführt.

## Die Marker-Mechanik, zweiseitig belegt

```
printf 'soupsieve==2.10\n'                               -> EXIT=1, 3 Funde
printf "soupsieve==2.10 ; python_full_version < '3.11.5'\n" -> EXIT=0
```

`soupsieve >= 4.0` verlangt Python `>=3.11.5` (PyPI: 2.10 → `>=3.10`,
4.0.0/4.1.2 → `>=3.11.5`); der Workspace deklariert 5× `requires-python =
">=3.11"`. Deshalb spaltet `uv` per Marker, und `pip-audit` sieht den
verwundbaren Zweig nie. Das ausgelieferte Artefakt fährt 4× `FROM
python:3.14-slim` (`apps/api/Dockerfile:14`/`:49`, `apps/mcp/Dockerfile:9`/`:33`),
kein Workflow pinnt eine `python-version`, `.python-version` fehlt — **der
Preis von Option A ist an jeder geprüften Stelle 0.**

🟢 **#1150 trägt diese Route bereits als gemessene Option A und empfiehlt sie.**
Neu ist nur: Zielversion heute **4.1.2**, nicht 4.1.1 — und sie steht in einem
vorgeschriebenen `# erwartet:`-Befehl (Regel 179).

## Norm-Prüfung — alle 13 offenen Issues, keine Zeile übernommen

4/4: #632, #1001, #633, #989, #1150, #540 · 4/4 formal (Outcome inline): #435 ·
3/4: #454 (Verifikation ohne Befehl), #542 (Outcome fehlt) · 2/4: #535 ·
1/4: #428 · 0/4: #338 (Checkliste). **Kein Label vergeben, keines entzogen.**

⚠️ Weiche 55 (Quelle der Spanne „2–5 AK") bleibt unbelegt — 22. Lauf ohne
lesbare Quelle.

## Schreibvorgänge

**In den Body** (zweite Sichtung, Paket aufgreifbar — je ein eigener Sub-Agent
mit dem Originaltext, statt eines Laufs, der aus einer Zusammenfassung neu
tippt):

| Issue | Zeichen vorher → nachher | Hunks | korrigiert |
|---|---|---|---|
| #632 | 38.818 → 39.828 | 8 | 398→125/124 (2×), Fix je CVE + Träger #1150, „#1120 → Exit 0" (4×), npm-Zahl datiert + Selbst-Mess-Befehl |
| #1001 | 21.566 → 23.461 | 8 | 398→125/124 (3×), Welle-0-Schritt 4 (2×), „#1120 → Exit 0" (4×), `pip-audit`-Zahlen datiert |
| #633 | 44.564 → 44.961 | 6 | 398→125/124 (2×), Fix je CVE (2×), „nach #1120 wieder billig" (2×), npm-Zahl datiert |
| #989 | 27.333 → 30.444 | — (Rücklesung byte-identisch) | 398/400→125/124, Fix je CVE + Träger (3×), **DoD-gegen-AK5 aufgelöst** (DoD-Seite gewählt), npm-Zahl (4×) |

**#442** selbst: 71.604 → **56.948** Zeichen, gestrafft neu geschrieben. **Keine
Weichen- und keine Regel-Nummer entfernt** (gegengelesen: 75 Pflege-Regeln,
37 Weichen-Einträge, Labels/Titel unberührt, Fußzeile letztes Element);
gekürzt sind nur Mess-Historien, die hier stehen.

**Als Kommentar, mit benanntem Grund** (Regel 62 — nicht aufgreifbar):
**#1150** (Zielversion 4.1.2, Welle-0-Stapel, Zweiweg-Kontrolle) und **#540**
(acht verrottete Zeiger + Widerspruch „4 von 7 erfüllt" über sieben ungehakten
Kästchen).

🔴 **Nicht korrigiert, als Entscheidung:** die Zeiger-Verrottung in #428, #435,
#535, #454, #542, #338 (`ci.yml` 1212→**1259**, `BillingPanel.tsx` `:42`→**`:49`**,
`docs/cloud-hosting-owner-guide.md` **existiert nicht**, Caddy-Pin `:452`→**`:480`**
bei 573→**605** Zeilen, `RUNBOOK.md` 2700→**3244**, `router.py` 453→**732**,
`gobd-verfahrensdokumentation.md` 137→**231** mit totem §6-Zeiger,
`CONTRIBUTING.md` 469→**499**) → **Weiche 57**.

## Reihenfolge — unverändert, und das ist das Ergebnis

Kriterien: harte Abhängigkeit → Owner-Vorgabe → Fundament vor Fläche →
Inventar vor Zuschnitt → bei Gleichstand das kleinere.

**#632 → #1001 → #633 → #989.** Im Fenster ist kein Issue geschlossen, keines
der vier bewegt, keine Weiche beantwortet, kein PR gemergt — es gibt nichts,
was eine Position verschieben könnte.

**Wellen:** 0 = #1120 + #1141 + #1142 + #1150 (Owner) · A = **#632 + #1001**
(datei-disjunkt, Web/Vitest gegen Python/pytest, beide Flächen über alle 48 PRs
frei) · B = #633 (nach #632 + Container) · C = #989 (nach Weiche 48) ·
M/N/P/Q/R = Owner-PR-Arbeit, s. #442.

## Neue Regeln

**73.** Eine Advisory kann auch verschwinden — eine Weiche, die auf einem
einzigen Advisory-Schnappschuss ruht, kann vor ihrer Antwort gegenstandslos
werden. Für einen Fund ohne Fix-Version ist „erst messen" die richtige, nicht
die vorsichtige Option.

**74.** „Nichts gemergt" und „nichts geschlossen" sind zwei Messungen mit zwei
Akteuren. Messweg: `state` + `merged` + `closed_at` je PR, und der Bestand wird
gegen die Vorlauf-Liste differenziert — Zugänge **und** Abgänge.

**75.** Ein Host-Grep, der eine Domain annimmt, ist keine Messung. Ein nackter
Hostname ohne Schema fällt durch jedes URL-Muster und durch jeden rechts
geankerten Domain-Grep; vor „erledigt" wird die zuletzt benannte Stelle
nachgelesen.

## Prozess-Notiz (Umgebung, kein Repo-Problem)

Die vier parallelen Schreib-Agenten teilen das Session-Scratchpad und haben
sich gegenseitig Arbeitsdateien gleichen Namens überschrieben. Beide betroffenen
Agenten haben das erkannt, neu geladen und in eigenen Unterordnern
weitergearbeitet; die Schreibvorgänge waren davon nicht betroffen (je
Rücklesung bestätigt). **Lehre für den nächsten Lauf: parallele Sub-Agenten
bekommen je ein eigenes Scratchpad-Unterverzeichnis vorgegeben.**

## Offen an den Owner — die vier dringendsten

1. 🔴 **Weiche 11 / 2 — die Merge-Reihenfolge.** 13 Tage ohne Merge, 48 offene
   PRs, 29 davon Protokolle dieses Verfahrens, `main`-CI rot. **#1120** ist
   18/18 grün bei Rückstand 0. Größter Hebel, und der einzige Posten, den kein
   Agent bewegen kann.
2. 🔴 **#1150 / Weiche 54 — Option A, B oder C?** Empfehlung **A**, jetzt
   Ende-zu-Ende gemessen. Ohne diese Antwort bleibt Welle 0 unerreichbar.
3. 🆕 **Weiche 57 — Zeiger in nicht-startbaren Bodies weiter messen?**
   Empfehlung **A** (einmal festschreiben, künftig nur Abschnitts-Prüfung).
4. **Weiche 46** — `glob`/`minimatch`-Ausnahmen, **Frist in 11 Tagen**; Arbeit
   liegt in #1124, dessen Zielversionen heute erstmals gegen beide Bereiche
   gemessen sind.

**Weiche 56** ist geschlossen, ohne beantwortet zu werden.
