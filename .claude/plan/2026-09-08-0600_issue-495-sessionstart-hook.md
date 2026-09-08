# #495 — SessionStart-Hook stellt die in CLAUDE.md verlangte Umgebung her

**Issue:** [#495](https://github.com/luetzey/who2be/issues/495) · `agent-ready` · `size/S`
**Branch:** `claude/autonomous-code-agent-role-c932qx`
**Betriebsmodus:** `produktiv` (kein `.claude/project.json` in der Cloud-Session →
Default greift, wird nie stillschweigend unterschritten) → **kein Auto-Merge**.

## Ausgangslage — Baseline gemessen (2026-09-08, `main` @ `a39df09`)

Nach dem regulären Hook-Lauf dieser Session:

| Messung | Ergebnis |
|---|---|
| `import who2be_billing` | `ModuleNotFoundError` |
| `pytest --collect-only` | **1812 tests collected** (statt 1901) |
| `127.0.0.1:5432` | `Connection refused` |

Der Befund aus #495 ist damit unabhängig reproduziert.

## Recherche — drei Angaben im Issue stimmen nicht

Das Issue ist agent-ready, aber drei seiner Einstiegspunkte bzw. Empfehlungen
halten der Messung nicht stand. Alle drei ändern die Lösung, nicht nur die Prosa:

1. **`apps/api/tests/conftest.py` existiert nicht.** Die conftest liegt im
   **Repo-Root** (`./conftest.py`); der Guard sitzt dort in
   `pytest_collection_modifyitems` (Z. 103–125).
2. **`pg_ctlcluster 16 main start` ist der falsche nächste Schritt.** Der lokale
   Cluster (`16 main`, Status `down`) hat **keine `vector`-Extension**
   (`/usr/share/postgresql/16/extension/` führt sie nicht). CI nutzt deshalb
   bewusst `pgvector/pgvector:pg16` (`ci.yml:87`, ADR-0046, Migration 0071).
   Ein gestarteter Cluster würde die Integrationstests also **an der Migration**
   scheitern lassen statt an der Verbindung — das stille Scheitern wandert nur.
3. **Ein `export` im Hook persistiert nicht.** Der Hook läuft als Command in
   einer Subshell (`.claude/settings.json` → `scripts/install_pkgs.sh`); spätere
   Tool-Calls starten eine neue Shell aus dem Profil. `WHO2BE_REQUIRE_DB=1` im
   Skript zu setzen wirkt daher **nur innerhalb des Hooks** und ist wirkungslos
   für die Suite, die der Agent später fährt.

## Weiche 2 des Issues — entschieden (Frage → Entscheidung → weil)

Das Issue lässt bewusst offen, ob der Hook die DB **startet**, **warnt** oder
`WHO2BE_REQUIRE_DB` **setzt** ("Warnung ist das Minimum, Starten die Kür").
Gemessen ist in dieser Umgebung **kein** DB-Weg gangbar:

| Weg | Warum er hier nicht trägt |
|---|---|
| `pg_ctlcluster` starten | Cluster ohne `vector`-Extension → Migration 0071 bricht |
| Testcontainers (`WHO2BE_TEST_TESTCONTAINERS=1`) | `conftest.py:44-70` hat den Opt-in fertig und zieht das **richtige** Image — aber der **Docker-Daemon läuft nicht** |
| `WHO2BE_REQUIRE_DB=1` im Hook exportieren | persistiert nicht über die Subshell hinaus (Punkt 3 oben) |

→ **Entscheidung: sichtbare Warnung mit dem korrekten nächsten Schritt** →
weil sie in dieser Umgebung nicht das Minimum, sondern das einzig Ehrliche ist.
Die Warnung nennt den vom Repo vorgesehenen Weg (`WHO2BE_TEST_TESTCONTAINERS=1`,
sobald Docker läuft), **nicht** `pg_ctlcluster`. Sie prüft den Daemon zur
Laufzeit, damit die Meldung sagt, was gerade tatsächlich fehlt.

**Nicht gewählt:** Schreiben nach `~/.bashrc`, um `WHO2BE_REQUIRE_DB` zu
persistieren. Das würde jede Suite ohne DB **hart** brechen — auch den
bewussten Unit-Lauf — und widerspricht Weiche 3 des Issues ("eine Session, die
gar nicht startet, ist schlechter als eine, die weiß, was ihr fehlt").

## Muster-Benennung

Der Guard-Test folgt dem **bestehenden** Muster der statischen, DB-freien
Repo-Guards: `test_no_billing_in_core.py`, `test_docs_toggle.py`,
`test_single_writer_guard.py`, `test_db_rls_guard.py` — vier Vorkommen, die
Variabilität ist belegt. **Keine neue Abstraktion**, kein Helper: der Test liest
`scripts/install_pkgs.sh` mit `Path(...).resolve().parents[...]` und assertet
gegen den Inhalt, exakt wie `test_no_billing_in_core.py:23-40`.

## Arbeitspakete

### WP-1 — Regressionstest zuerst (TDD, rot vor grün)
`apps/api/tests/test_session_hook_env.py` (neu): der Hook synct mit
`--group billing`. Muss **vor** dem Fix rot sein.

### WP-2 — `scripts/install_pkgs.sh`
- Z. 9: `uv sync` → `uv sync --group billing` (CLAUDE.md §Befehle, `ci.yml:104`).
- Danach: DB-Erreichbarkeit prüfen; fehlt sie, eine Warnung ausgeben, die
  Docker-Status und den nächsten Schritt nennt.
- `|| true` bleibt überall erhalten (AK 4, Weiche 3).

**Nicht anfassen:** `conftest.py` und der Skip-Guard · `.github/workflows/**` ·
`docker-compose*.yml` · die Test-Suite selbst · `~/.bashrc`.

## Verifikation (aus dem Issue, Pfad korrigiert)

```bash
bash scripts/install_pkgs.sh
uv run python -c "import who2be_billing; print('billing ok')"
uv run pytest -q --collect-only | tail -1          # 1901, nicht 1812
uv run pytest apps/api/tests/test_session_hook_env.py -v
uv run ruff check . && uv run ruff format --check . && uv run mypy .
```

Grün heißt: billing importierbar, Sammlung meldet 1901, der neue Guard ist grün,
Lint/Format/Typecheck Exit 0. Der DB-lose Lauf bleibt ein Skip — jetzt aber
**angekündigt** statt still.

## Offen / Nebenfunde

- Die drei falschen Issue-Angaben oben gehören als Kommentar an #495.
- `WHO2BE_REQUIRE_DB` in dieser Session weiterhin nicht setzbar → die 481
  Integrationstests laufen hier nicht. Das ist nach dem Fix **sichtbar**, nicht
  behoben; behoben wäre es erst mit laufendem Docker-Daemon.
