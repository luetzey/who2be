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

- `uv run pytest scripts/tests/test_check_effectful_tests.py` → **24 passed**
- Rot-Probe: absichtlich schlechter Test wird markiert, guter nicht — als
  Testfälle (`test_string_only_test_is_flagged` /
  `test_test_that_calls_the_subject_is_not_flagged`), nicht als Behauptung
- Historien-Beleg: vier Testfälle fahren den Prüfer gegen die Commit-Fassungen
  (`git show 8d4161cf:…`, `22371628`, `d00c1088`) — alle vier markiert
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
