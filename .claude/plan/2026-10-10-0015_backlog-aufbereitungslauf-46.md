# Backlog-Aufbereitungslauf 46

**Datum:** 2026-10-10, 00:15 UTC
**Basis:** `main` @ `6858f707` (25 Commits seit der Lauf-45-Basis `7590c335`)
**Auftrag:** jedes offene Issue gegen die Norm „Agent-ready Arbeitspaket"
(`.github/PROJECT.md` §Constraints) pruefen; Belegbares mit Beleg ins Issue,
Urteilsbeduerftiges als Kommentar mit drei Optionen + Empfehlung + `needs-decision`;
danach die Warteschlange (#442) neu ordnen und in Wellen gruppieren.

**Umgebungs-Vorbehalt:** Der MCP-Server `Who2Be---Coder` ist in dieser Session
nicht erreichbar (CONNECT_TIMEOUT nach 30 s). Persona und Playbook-Katalog
liegen im System-Prompt vor und sind verankert; `fetch_playbook`,
`search_memory`/`save_memory` und `record_usage`/`submit_feedback` sind
nicht aufrufbar. Kein passendes Playbook ladbar — der Lauf faehrt nach dem
in #442 §Pflege-Regeln kodifizierten Verfahren der Laeufe 12-45.

## Lage vor dem Lauf (bereits gemessen)

- Klon war **shallow** (50 Commits), nach `git fetch --unshallow` **1497** (Regel 90).
- `main` @ `6858f707`: CI-Lauf **38007771495** ist **`in_progress`** (Start
  2026-10-10 00:08:58 UTC) — `status` und `conclusion` getrennt gelesen
  (Regel 91). Vorgaenger `8b1b0b5d` ist `success`. **`main` ist nicht rot,
  sondern ausstehend** (Regel 102/103) → Regel 80 greift nicht.
- **#869 ist gemergt** (`6aa50df4`). Die einzige Datei-Sperre von #632 **und**
  #633 aus Lauf 45 ist gefallen — **Regel 87 bestaetigt** („eine Sperre aus
  einem Zustand erledigt sich ohne Antwort").
- `ci.yml`: **1212** Zeilen, `timeout-minutes` → **0**, letzte Aenderung
  `11a243ff` (#839, 2026-10-06) — **unbewegt**, Adresse von #849 frei.
- `docker info` → **Exit 1** (22. Lauf). Node **v22.22.0**.
- Bewegung auf `main` seit `7590c335` (Regel 100): `locales/{de,en}.json`
  **11x**, `deploy/hetzner/RUNBOOK.md` **2x**, `apps/web/e2e` **1x**,
  `api/types.ts` **1x**; `ci.yml`, `MfaSection.tsx`, `LoginPage.tsx`,
  `SessionProvider.tsx`, `vite.config.ts`, `package.json`, `Caddyfile`,
  `plans.md`, `ROADMAP.md`, `README.md`, `PROJECT.md`, `STATE.md`,
  `orphan-baseline.json` je **0x**.
- PR-Bestand **12 offen**: #870 (Protokoll 45, neu), #851, #841, #831, #823
  (Protokolle 44/43/42/41), #827, #825, #824, #686, #683, #682, #674.
  **Der Protokoll-Rueckstand ist auf fuenf gewachsen**; dieser Lauf legt den
  sechsten dazu (Regel 2).

## Arbeitspakete (datei-disjunkt, ein Schreiber je Baum — Regel 30/31/76)

| WP | Inhalt | Baum | Modell | Begruendung der Modellwahl |
|---|---|---|---|---|
| **A** | Web-Gates: `npm run lint` (+ `eslint -f json`: Regelverteilung, `fixableWarningCount`), `npx tsc -b`, `npm run test:coverage`, `npm run i18n:check` | `apps/web` (allein) | Sonnet | vier Gates, Aggregation ueber JSON — mechanisch, aber zahlen-kritisch |
| **B** | Python-Gates: `import who2be_billing`, `pytest --collect-only`, `changelog_fragments.py check` (ohne Pipe, Regel 94), `ls changelog.d/*.md` | Repo-Root (Python) | Haiku | drei Kommandos, feste Ausgabeform — kleinstes ausreichendes Modell |
| **C** | PR-Inventar: je PR Head-SHA, Datei-Scope ueber explizite merge-base, `all-green` **namentlich**, Conclusions positiv auf `failure`/`timed_out` (Regel 101), Gate-Alter gegen `11a243ff`, `behind`, `git merge-tree --write-tree` | git read-only | Sonnet | 12 PRs x 6 Messungen, Klassifikation nach Regel 95 |
| **D** | Norm-Pruefung der 11 offenen Issues (vier Pflichtteile) + Nachmessen **jedes** Zeigers in #632/#633/#849/#540/#535/#428/#435 (Regel 93/97/98) | lesend | Sonnet | Urteil bleibt beim Orchestrator, der Agent liefert Fakten |
| **E** | CI-Spruch-Luecke ueber alle 25 Commits (Regel 104-Nachmessung) + zweite Achse der Sammelpunkte | API + git read-only | Sonnet | API-Paginierung + Zuordnung Commit → Lauf |

**Wellen:** A und B parallel (verschiedene Stacks), C/D/E parallel dazu
(lesend, kein Werkzeug-Zwischenstand). Kein Beteiligter setzt einen
git-Schreibbefehl (`add`, `commit`, `checkout`, `stash`, `restore`, `reset`).

## Danach (Orchestrator, Review-Phase)

1. Konsolidieren: Zahlen gegen Lauf 45 stellen, Abweichungen benennen.
2. Norm-Entscheidung je Issue: Beleg in den Body (eigene Entscheidung) vs.
   drei Optionen + Empfehlung als Kommentar + `needs-decision` (Urteil).
   **Regel 7:** `size/M` wird nie durch Nachtragen von Feldern startbar.
3. #442 neu ordnen (fuenf Kriterien) + Wellen neu schneiden.
4. Bericht in drei Bloecken: selbst erledigt · braucht Owner-Antwort · Reihenfolge + Wellen.
5. Protokoll committen, Draft-PR auf `claude/upbeat-mayer-svf19g`.

## Completion-Condition (messbar)

- [ ] Jedes der 11 offenen Issues ist gegen die vier Pflichtteile geprueft, Ergebnis belegt.
- [ ] Jeder Zeiger in den sieben Issue-Bodies ist mit dem Kommando nachgemessen, das ihn erzeugt hat.
- [ ] #442 traegt eine Reihenfolge, die aus den fuenf Kriterien folgt; Praeferenzen stehen getrennt.
- [ ] Jede Welle nennt Dateien, Stack und Vorbedingung.
- [ ] Protokoll liegt als Datei im Repo, PR offen.

---

# Protokoll (nach dem Lauf)

## Ergebnis der Messwellen

Alle fuenf Messpakete zurueckgegeben, danach zwei Schreibpakete und ein
Verifikationspaket. **Kein Code angefasst, kein Issue angelegt, kein Issue
geschlossen, kein Label gewechselt.**

### Messwerte (sequenziell, ein Schreiber je Baum; Node v22.22.0)

| Gate | Exit | Messwert | gegen Lauf 45 |
|---|---|---|---|
| `npm run lint` | 0 | **94** problems, 0 errors, **62** von 645 Dateien, **9** `--fix`-bar | 93 → **94** |
| `npx tsc -b` | 0 | Ausgabe leer | unveraendert |
| `npm run test:coverage` | 0 | **253 Dateien / 2162 Tests**; **88,78 / 82,73 / 85,2 / 90,5** | 251/2056; **alle vier gestiegen** |
| `npm run i18n:check` | 0 | **159** Waisen (geteilte Baseline), keine neuen, keine Duplikate | unveraendert |
| `uv run pytest --collect-only -q` | 0 | **3362** Tests, 135 Zeilen unter `packages/billing/` | 3166 → **3362** |
| `uv run ruff check .` | 0 | 0 Funde | erstmals gemessen |
| `uv run mypy .` | 0 | 0 Funde in **575** Dateien | erstmals gemessen |
| `changelog_fragments.py check` | 0 | **265** Fragmente (`ls` zaehlt 266, Differenz `README.md`) | 240 → **265** |
| `docker info` | 1 | keine Container-Laufzeit, **22. Lauf** | unveraendert |

### Die drei tragenden Funde

**1. Die einzige Sperre des Bestands hat sich von allein geloest.** #869 ist als
`6aa50df4` gemergt; `locales/{de,en}.json` ist ueber alle zwoelf offenen PRs
frei. **#632 und #633 haben erstmals seit Lauf 44 keine Datei-Sperre** —
Regel 87 mit Ausgang bestaetigt.

**2. Die Praemissen-Korrektur von Lauf 45 traegt nicht.** 25 Commits in
23 h 24 min = **1,07 Commits/h** (Lauf 45: 0,69/h), davon **24 x `success`,
0 x `cancelled`**; zwei Push-Paare mit **1 min 30 s** und **4 min 24 s**
Abstand behielten je ihren Spruch. Der Beleg-Lauf `37822973287` hat
`created_at` = `run_started_at` = 18:16:15 — **er hat nie gewartet** — und
`ci.yml:14` setzt auf `main` `cancel-in-progress: false`, verbietet den
Abbruch also. **Ursache des einen Abbruchs: ungemessen.** Nebenbefund: der
Kommentar `ci.yml:7-11` begruendet die Einstellung mit einer „run_id-Gruppe",
die der Code (`:13`) nicht hat. → **Regel 105**, Weiche 1 neu gestellt,
Einschraenkung aus #849 entfernt.

**3. Vier verrottete Zeiger — alle in Dateien ohne mitgefuehrte
Gesamtzeilenzahl.** `who2be/docker-compose.yml:352` → **`:414`** (Datei +62
Zeilen durch #885/#890), `cloud-prod-smoke.md:166` → **`:168`** und
`:285` → **`:287`**, `deploy.yml:83` → **`:185`/`:214`**. **Keine** der
Zeilenzahlen, die die Bodies ausdruecklich nennen, ist abgewichen — Regel 98
greift genau dort, wo sie nicht angewandt wurde.

### Norm-Befund (alle elf offenen Issues gegen die vier Pflichtteile)

| Issue | Pflichtteile | Lücke |
|---|---|---|
| #849, #633, #632 | **4/4** | — (`agent-ready`, `size/S`); #849 fuehrt 6 Kriterien statt 2–5 und weist das nicht aus |
| #435 | **4/4** | aber `size/M` → Regel 7 |
| #540 | 3/4 | **Scope-In fehlt**; 7 Kriterien, mind. 4 ohne Schwelle |
| #454 | 2 voll, 2 teilweise | `human-only` |
| #542 | 0 voll | Outcome fehlt, 5 Kriterien ohne Kommando; `human-only` |
| #535, #428 | je 0 voll | **Outcome und Verifikation fehlen ganz**; `size/M` → Regel 7 |
| #338 | 0/4 | `human-only`, Owner-Checkliste |

**Regel 7 angewandt:** an den `size/M`-Bodies wurden **keine Felder
ergaenzt**, nur Zeiger repariert — ein `size/M`-Issue wird nicht durch
Nachtragen startbar, der naechste Schritt ist ein Zuschnitt.

## Geschrieben

- **#540** — Caddy-Zeiger an vier Fundstellen auf `:414`, Messsatz ergaenzt.
- **#428** — zwei Zeiger auf `:168`/`:287`, OSV-Restlaufzeit an zwei Stellen auf 23 Tage.
- **#454** — Deploy-Zeiger auf `:185`/`:214` (reine Tatsachen-Korrektur, `human-only` unberuehrt).
- **#632** — Sperre als gefallen, zweite Achse 11x, Zahlen, Coverage-Richtung korrigiert.
- **#633** — Sperre als gefallen, genau zwei Blocker, Herleitung 26/35 nachgezogen.
- **#849** — Praemisse korrigiert, Einschraenkung aus Lauf 45 entfernt.
- **#442** — Body neu (76.106 Zeichen) + zwei Kommentare (Weiche 1 neu gestellt, neue Weiche zu #823).
- **Nicht angefasst:** #535, #435, #542, #338 — alle Zeiger und Dateigroessen halten.

## Qualitaetssicherung des Laufs selbst

Das Schreibpaket W2 hat die drei `agent-ready`-Bodies **vollstaendig neu
getippt** (die API nimmt nur den ganzen Body) und keinen Abschluss-Lesecheck
gemacht. Ein Verifikationspaket mit frischen Augen hat daraufhin alle drei
geprueft: **kein zerstoerender Schaden**, alle Pflichtteile und
Kriterienzahlen vorhanden (6/6/5), Fences und Tabellenspalten konsistent, nur
ein datierter Standblock je Issue. **Zwei Funde wurden korrigiert:** eine
Aussage in #849, die den Haenger-Mechanismus als „zweimal eingetreten"
auswies (belegt ist er **einmal**), und eine Zahlenreihe in #632, deren Summe
nicht aufging (`12/14→15` und ein fehlendes `scroll-guard` 3).

**Lehre fuer kuenftige Laeufe:** ein Issue-Body ueber ~10.000 Zeichen wird
nicht von einem Modell abgetippt. Entweder chirurgisch per Suchen-Ersetzen
auf dem abgerufenen Body, oder mit anschliessender Verifikation durch einen
zweiten Agenten. Beides wurde in diesem Lauf gebraucht.

## Completion-Condition — Nachweis

- [x] Alle 11 offenen Issues gegen die vier Pflichtteile geprueft, Ergebnis in der Tabelle oben.
- [x] Jeder Zeiger in den sieben Bodies nachgemessen; 4 verrottet, 4 repariert, Rest haelt.
- [x] #442 traegt eine Reihenfolge aus den fuenf Kriterien; Praeferenzen stehen getrennt.
- [x] Zehn Wellen (A–J) mit Dateien, Stack und Vorbedingung; A und C erstmals beide ohne Vorbedingung.
- [x] Protokoll liegt als Datei im Repo, PR offen.
