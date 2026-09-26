# CI-Gate: Tests, die nur Zeichenketten prüfen statt Wirkung auszuführen

Karte: `t_3a17f078` · Branch: `who2be/t_3a17f078-ci-gate-tests-erkennen-die-nur-zeichenke`
Basis: `origin/main` @ 1b55cdcc (Worktree war 95 Commits alt, nachgezogen)

## Outcome

Ein deterministischer CI-Schritt markiert **neu hinzugefügte** Python-Testfunktionen,
die Dateiinhalte lesen und darauf Zeichenketten-Zusicherungen machen, ohne den
Prüfling aufzurufen. Startet als **Warnung** (blockiert nicht), mit
dokumentiertem Ausnahmeweg am Einzeltest.

## Messung vor dem Bau (entscheidet das Design)

Prototyp unter `~/.hermes/profiles/coder/cache/scratch/proto_gate.py`, gemessen
gegen die echte Historie. **Kein erfundener Fall.**

### Trefferquote an den drei historischen Fällen

| Fall | Commit | Ergebnis |
|---|---|---|
| Access-Logs (`t_a8ffa436`) | 8d4161cf | **7 neue Treffer** — u. a. `test_caddy_access_log_rotates_by_size`, `test_access_log_retention_is_enforced_by_a_documented_cron` ✓ |
| Access-Logs Nachschärfung | 22371628 | **3 neue Treffer** ✓ |
| Deploy-Wächter (`t_95da585b`) | d00c1088 | **3 neue Treffer** — u. a. `test_deploy_skript_prueft_die_container_anzahl` ✓ |
| Backup (`t_efdeef07`) | a52f7555 | **0 Treffer — nicht erfasst.** Die 13+17 Testfälle liegen in `deploy/hetzner/tests/test_backup_alarm.sh`, also in Shell, nicht in Python-AST. |

**Zwei von drei Fällen werden erfasst, der dritte prinzipbedingt nicht.** Das ist
eine Methodengrenze, keine Kalibrierungsfrage: eine AST-Heuristik über Python
sieht eine Bash-Testsuite nicht. Sie wird benannt, nicht versteckt.

### Fehlalarmquote (Diff-Modus, wie das Gate läuft) — finale Fassung

80 Commits First-Parent auf `origin/main`, davon 27 mit Testdatei-Änderung:

- **10 von 27 Commits (37 %)** hätten mindestens eine Warnung gezeigt
- **25 neue Treffer** insgesamt

Klassifikation der 25:

| Art | Zahl | Bewertung |
|---|---|---|
| Die historischen Fälle + Nachschärfungen (Access-Logs 8, Nachschärfung 4, Deploy-Wächter 3) | 15 | **echter Fund** |
| Konfigurationstext-Prüfungen (Caddy-Header/CSP, Compose-Override) | 4 | **Grauzone** — prüfen eine Zusage in der Datei; im Header-Fall wurde in derselben Welle eine wirkungsprüfende Shell-Suite daneben gestellt |
| Golden-File-Verträge (`gate_inventory`, 3×) | 3 | **Fehlalarm** |
| Doku-Drift-Wächter (`test_documented_tool_count_matches_registry`) | 1 | **Fehlalarm** — von der Karte ausdrücklich als zulässiger String-Test benannt |
| Quelltext-Scan-Wächter (`test_every_content_write_also_maintains_content_bytes`) | 1 | **Fehlalarm** |
| Negativ-Nachweis (`test_leaves_tree_untouched`) | 1 | **Fehlalarm** |

**Fehlalarmquote: 6 von 25 (24 %) klar, plus 4 Grauzone.** Ohne Ausnahmeweg
wäre das Gate nach der ersten Woche abgeschaltet — genau die von der Karte
vorhergesagte Lage. Mit Ausnahmeweg ist das Signal tragfähig: 60 % der Treffer
sind echte Funde, und die Grauzonen-Fälle sind *genau die*, bei denen ein Mensch
zweimal hinsehen soll.

Vollbestand zum Vergleich: 30 von 2016 Testfunktionen (1,5 %) — das Gate läuft
deshalb **diff-basiert**, nicht gegen den Bestand. Kein Baseline-Bestand nötig,
keine Alt-Last-Welle.

### Ein Fehler, den die eigenen Tests gefunden haben

Der erste Entwurf der Assert-Prüfung verwarf jede Zusicherung, die irgendwo
einen Aufruf enthält — mit der Begründung, `assert normalise(x) == y` führe
Verhalten aus. Das ist richtig, verwirft aber auch
`assert "x" in path.read_text()`, also **die häufigste Form des gesuchten
Fehlertyps**. Drei der vier Historien-Testfälle wurden rot; erst dadurch fiel es
auf. Die Fassung prüft jetzt die Struktur der Zusicherung, und ob ein Aufruf
Wirkung ausführt, entscheidet allein `_executes_effect`.

### Ein zweiter Fehler, den die CI gefunden hat

Einer der Kalibrierungs-SHAs (`22371628`) war ein Commit auf einem
Arbeitsbranch. Lokal lag er im Klon, alles war grün; im frischen CI-Klon fehlte
er, und der Testfall wurde **übersprungen** — das Skip-Budget-Gate hat es
gemeldet. Ein übersprungener Kalibrierungsfall ist genau die Sorte stilles Grün,
gegen die diese Karte antritt.

Drei Korrekturen, nicht eine:

1. SHA auf den inhaltsgleichen Commit auf `main` getauscht (`c405ca2c`).
2. Der Skip-Pfad ist jetzt ein **Fehler** (`pytest.fail`) — ein nicht
   auflösender Ref darf die Suite nicht grün lassen.
3. Zwei neue Testfälle halten das nach:
   `test_every_history_sha_lives_on_main` prüft die Bedingung selbst, und
   `test_unresolvable_ref_fails_instead_of_skipping` belegt, dass der
   Fehlerpfad wirklich rot wird — sonst wäre (2) eine Behauptung.

Das ist derselbe Fehlertyp, den der Prüfer sucht, begangen beim Bauen des
Prüfers. Er steht hier, weil er die Karte belegt statt sie zu widerlegen: nur
ein Gate hat ihn gefunden, kein Dokument.

### Nebenbefund: Negativnachweis mechanisieren (Bewertung, nicht Bau)

Der Vorbericht schlägt vor, jeden neuen Test gegen die unveränderte Vorfassung
laufen zu lassen und Rot zu verlangen. **Bewertung: in dieser CI nicht
praktikabel.**

1. Die Vorfassung ist nicht isolierbar. Ein PR ändert Test und Prüfling im
   selben Commit; „Test neu, Produktivcode alt" erzeugt in diesem Repo einen
   Zustand, der nicht kompiliert (neue Symbole, neue Migrationen) — der Test
   wäre dann rot aus dem falschen Grund, und das ist ein grünes Gate wert.
2. Die drei historischen Fälle wären davon **nicht** gefangen worden: sie prüfen
   Konfigurationsdateien, und die Vorfassung dieser Dateien enthielt die
   geprüfte Zeichenkette nicht — der Negativnachweis wäre korrekt rot gewesen
   und hätte den Test trotzdem durchgelassen.
3. Kosten: jeder PR fährt die Suite zweimal.

Als **Handlauf** bleibt er wertvoll (der Coder hat damit seinen eigenen Fehler
gefunden) — als CI-Mechanik ist er teurer als die AST-Heuristik und fängt
weniger.

## Zuschnitt — sieben Dateien

1. `scripts/check_effectful_tests.py` — der Prüfer
2. `scripts/tests/test_check_effectful_tests.py` — Tests inkl. Rot-Probe
3. `.github/workflows/ci.yml` — ein Schritt im `python`-Job, meldend
4. `docs/effectful-tests.md` — Regel + Ausnahmeweg
5. `changelog.d/t3a17f078-wirkungs-gate.added.md`
6. `.claude/plan/2026-09-26-1830_wirkungs-gate-tests.md` (dieses Dokument)
7. `CONTRIBUTING.md` — Verweis in der Definition of Done

## Ausnahmeweg

Marker-Kommentar in der `def`-Zeile oder unmittelbar darüber:

    # effect-exempt: <Begründung>
    def test_documented_tool_count_matches_registry() -> None:

**Begründung ist Pflicht** (leerer Marker zählt nicht). Bewusst ein Kommentar
und kein pytest-Marker: kein Eingriff in `pyproject.toml`, sichtbar im Diff an
genau der Stelle, an der die Entscheidung getroffen wird, und der
Ausnahmegrund steht neben dem Test statt in einer entfernten Liste.

## Heuristik

Markiert wird eine Testfunktion, wenn **alle drei** zutreffen:

1. **Liest Dateien** — `open(...)`, `.read_text()`, `.read_bytes()`,
   `.readlines()`, oder ein lokaler Helfer, der das tut (transitiv).
2. **Ruft keine Wirkung auf** — kein Aufruf eines erstparteilich importierten
   Symbols, kein `subprocess`-Start, kein HTTP-Aufruf gegen die App, kein
   Helfer, der das tut (transitiv).
3. **Alle Zusicherungen sind Vergleiche/Containment** — `in`, `==`, `not in`,
   Wahrheitswert einer Liste. Kein `pytest.raises`, kein Aufruf in der
   Zusicherung.

Die transitive Auflösung über Helfer ist nicht Kosmetik: ohne sie schlüpfte
`test_caddy_access_log_rotates_by_size` (Fall 3) durch, weil sein Lesevorgang
zwei Helferebenen tief liegt — beim ersten Prototyp-Lauf gemessen.

## Verifikation — gemessen

- `uv run pytest scripts/tests/test_check_effectful_tests.py` → **26 passed, 0 skipped**
- Rot-Probe: absichtlich schlechter Test wird markiert, guter nicht — als
  Testfälle (`test_string_only_test_is_flagged` /
  `test_test_that_calls_the_subject_is_not_flagged`), nicht als Behauptung
- Historien-Beleg: vier Testfälle fahren den Prüfer gegen die Commit-Fassungen
  (`git show 8d4161cf:…`, `c405ca2c`, `d00c1088`) — alle vier markiert
- Grenze als Testfall: `test_backup_case_is_out_of_reach_and_says_so`
- `uv run ruff check . && uv run ruff format --check .` → **All checks passed**
- `uv run mypy .` → **Success: no issues found in 495 source files**
- `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85` →
  **2250 passed, Coverage 91.73 %** (Postgres lokal via podman/pgvector:pg16)
- `scripts/ci/assert_skips_within_budget.py` → 0 übersprungen
- `changelog_fragments.py check` + `guard --base origin/main` → in Ordnung
- Selbsttest des Gates am eigenen PR:
  `check_effectful_tests.py --base origin/main` → **keine Befunde** (die 24
  Prüfertests rufen `analyse_source` auf, also Wirkung); `--strict` gegen den
  Bestand → Exit 1, der Prüfer unterscheidet also messbar

## Review-Runde 1 — nachgelegt

Der Reviewer hat jede Handoff-Behauptung eigenständig nachgemessen (alle vier
Historienfälle selbst markiert, Fehlalarmquote reproduziert, CI-Lauf belegt) und
zwei Stellen gefunden, die unter genau den Fehlertyp dieser Karte fallen: sie
behaupteten eine Regel, die ohne sie grün blieb.

**Blocker 1 — `new_findings_against()` war von keinem Testfall gedeckt.**
Das ist der Pfad, den die CI fährt. Den Basisabzug ersatzlos zu entfernen
(`findings.extend(after)`) ließ 26/26 Tests grün — die Unterscheidung „neu
hinzugefügt" vs. „Bestand" war unbelegt, und ohne sie meldet der Schritt statt
einer Handvoll Diff-Treffer den gesamten Altbestand an jedem PR. Behoben mit
zwei Fällen, die sich ein Wegwerf-Repository bauen (`tmp_path` + `git init` +
zwei Commits + `monkeypatch.chdir`):
`test_finding_already_in_the_base_is_not_reported` prüft beide Richtungen in
einem Fall — der Bestandsbefund wird nicht gemeldet, der neu hinzugefügte schon
— mit einer Zwischenzusicherung auf `analyse_source`, damit der Fall nicht grün
sein kann, weil die Heuristik den zweiten Test gar nicht sieht.
`test_unchanged_test_file_yields_nothing` hält fest, dass ein Commit ohne
Testdatei-Änderung nichts meldet.

**Blocker 2 — ein Testfall belegte seinen eigenen Docstring nicht.**
`test_test_that_starts_a_process_is_not_flagged` war grün, weil für seinen
Quelltext `_reads_files = False` war, nicht weil die Wirkungsregel greift: er
wäre auch grün geblieben, wenn `_executes_effect` konstant `False` zurückgäbe.
Behoben, indem der Fall nun wirklich liest und Text zusichert — plus
`test_the_same_case_without_the_process_start_is_flagged` als Gegenprobe, die
belegt, dass der Prozess-Start der Grund für das Nicht-Markieren ist.

**Nits — drei von fünf umgesetzt, einer widerlegt.**
- `ast.Call` in der Assert-Strukturliste war ungedeckt. Gedeckt mit einem echten
  Fehlertyp statt einem konstruierten Fall:
  `assert read_text().startswith(...)` ist dieselbe wirkungslose Textprüfung,
  hat aber einen Aufruf als Wurzelknoten.
- `root == "open"` sei redundant — **das trifft nicht zu.**
  `yaml.safe_load(open(p))` liest eine Datei, ohne dass irgendwo ein
  `read`-Attribut im Quelltext steht; ohne den Zweig fällt diese Form durch.
  Nachgemessen und als `test_bare_open_without_a_read_attribute_counts_as_reading`
  festgehalten, statt den Zweig auf eine Vermutung hin zu entfernen.
- Die handgepflegte `_FIRST_PARTY_PREFIXES`-Liste war ein leiser
  Fehlalarmgeber: sie nannte vier von neun Skripten, und nichts im Repo hätte
  daran erinnert, ein neues nachzutragen — dessen Tests wären fortan markiert
  worden, obwohl sie den Prüfling aufrufen. Die Skriptnamen werden jetzt aus dem
  Verzeichnis **abgeleitet**; `test_every_script_module_counts_as_first_party`
  hält die Ableitung fest, `test_a_script_under_test_is_not_flagged` belegt die
  Wirkung.
- Offen und bewusst so gelassen: der Namensvergleich in `new_findings_against`
  läuft je Datei, ein verschobener Bestandstest gilt also als neu. Im meldenden
  Modus verkraftbar; vor `--strict` neu zu bewerten. Ebenso die ungedeckten
  Filter für Testnamen-Präfix und Testdatei-Muster (geringes Risiko).

### Rot-Proben zu den Nachbesserungen — gemessen, nicht behauptet

Jede neue Regel gegen die Mutation gefahren, die sie verletzt:

| Mutation | Erwartung | Ergebnis |
|---|---|---|
| Basisabzug entfernt (`findings.extend(after)`) | rot | **1 failed, 28 passed** |
| Prozessstart-Zweig aus `_executes_effect` gestrichen | rot | **1 failed, 28 passed** |
| `ast.Call` aus der Assert-Strukturliste entfernt | rot | **1 failed, 29 passed** |
| `open`-Zweig aus `_reads_files` entfernt | rot | **1 failed, 30 passed** |

Alle vier Mutationen waren vor dieser Runde grün.

### Fehlalarmquote nach der Prefix-Ableitung — unverändert

Die Ableitung verändert `_FIRST_PARTY_PREFIXES` und damit potentiell die
Befundmenge. Gegengemessen statt angenommen: Bestandslauf vor und nach der
Änderung (`--json`, `git stash` dazwischen) → **bitgleiche Ausgabe**. Die
gemessene Quote (30 Befunde im Bestand; im Diff-Modus über 80 Commits 10
meldende Commits / 25 Treffer) gilt unverändert.

### Verifikation dieser Runde

- `uv run pytest scripts/tests/test_check_effectful_tests.py` → **33 passed, 0 skipped**
- `uv run ruff check . && uv run ruff format --check .` → All checks passed
- `uv run mypy .` → Success: no issues found in 495 source files
- `WHO2BE_REQUIRE_DB=1 uv run pytest --cov --cov-fail-under=85` →
  **2259 passed, 0 skipped**, Coverage **91.73 %** (podman/pgvector:pg16)
- `scripts/ci/assert_skips_within_budget.py junit-python.xml` →
  2259 Testfälle, **0 übersprungen** (Budget 0/0)
- OSS-Lizenz-Gate (`piplicenses --fail-on GPL;AGPL;…`) → Exit 0
- `check_effectful_tests.py --base origin/main` → keine Befunde (der Prüfer
  markiert seine eigenen neuen Tests nicht)
