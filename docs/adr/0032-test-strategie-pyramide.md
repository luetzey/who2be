# ADR-0032 — Test-Strategie & Test-Pyramide

- Status: Accepted
- Datum: 2026-06-05
- Kontext: Phase 3 abgeschlossen; breite Test-Basis (162 Dateien) vorhanden,
  aber unvermessen und ohne E2E-Spitze
- Bezug: ADR-0005 (MCP als HTTP-Client), ADR-0023 (Token-Snapshot-Rolle),
  ADR-0030 (MCP-Write-Tools)

## Kontext

Der Bestand war breit, aber die Pyramide war faktisch **unbekannt** und an drei
Stellen unehrlich:

1. **Keine Coverage-Messung** in beiden Stacks → die Pyramidenform liess sich
   nicht belegen, ein TDD-Ratchet war unmoeglich.
2. **Stille DB-Skips:** ~40 Integrationstests prueften per dupliziertem
   `_db_reachable()` selbst auf eine DB und uebersprangen sich ohne sie. Lokal
   meldeten sie „gruen durch Skip"; die Repo-Regel „lokal verifiziert vor jedem
   Push" war damit fuer den Integration-Tier unwahr. Kein `conftest.py` ⇒
   Bootstrap 40× kopiert.
3. **Ungetestete Naehte:** MCP-Read garantiert `status='active'`-Filterung; ein
   Paritaetstest gegen REST fehlte. `apps/web/src/api/client.ts` mockt Shapes,
   die vom echten OpenAPI driften koennen. Kein OpenAPI-Snapshot.
4. **Keine E2E-Spitze** — nur `scripts/smoke.sh` (4 Curl-Checks).

## Entscheidung

Eine ehrliche, gemessene Pyramide mit durchgaengigen Gates. Bewusst **keine**
fette E2E-Schicht (Anti-Ice-Cream-Cone).

- **Coverage als Ratchet-Floor.** Python via `pytest-cov`
  (`--cov-fail-under`), Web via `@vitest/coverage-v8` (`thresholds`). Baselines
  DB-los gemessen (Python 66 %, Web ~81 %); CI-Floor konservativ (Python 65,
  Web 80/78/70/80). Floors werden nur in dedizierten Coverage-PRs angehoben,
  nie gesenkt.
- **Zentrales `conftest.py` + Skip-Guard.** DB-Erreichbarkeit wird einmal
  gecacht; `@pytest.mark.integration`-Tests werden an *einer* Stelle
  uebersprungen. Mit `WHO2BE_REQUIRE_DB=1` (CI gesetzt) fuehrt eine fehlende DB
  zum **harten Fehlschlag** — „gruen durch Skip" ist in CI ausgeschlossen.
  `--strict-markers` verhindert vertippte Marker.
- **Integration via Postgres-Quelle.** CI nutzt **den vorhandenen
  Postgres-Service** (eine DB-Quelle, nicht zusaetzlich Testcontainers).
  Lokal nutzen Entwickler entweder `docker compose` oder — opt-in — eine
  Testcontainers-Fixture; Default bleibt „reach `database_url`".
  *Begruendung:* zwei parallele DB-Quellen (Service **und** Container) im selben
  CI-Job sind eine Fehlerquelle; der Service ist bereits erprobt.
- **Contract-Tests** an den drei Driftstellen: OpenAPI-Snapshot (Golden-File),
  REST↔MCP-Paritaet (`status='active'`-Vertrag), Web-Client↔OpenAPI.
- **Duenne E2E-Spitze** (Playwright, 3–5 Journeys) gegen den Compose-Stack —
  Logik bleibt unten in Unit/Integration.

## Konsequenzen

- CI bricht bei Coverage-Regression (Floor) und bei fehlender DB im
  Integration-Tier (Skip-Guard) — beide Lecks sind geschlossen.
- Der Floor ist zunaechst **locker** (CI-Coverage liegt mit DB ueber dem
  DB-los gemessenen Floor). Anhebung auf den CI-gemessenen Wert erfolgt in einem
  Folge-PR, sobald die erste gruene CI-Messung vorliegt.
- Neue Integrationstests nutzen die `conftest.py`-Fixtures statt eigenem
  Boilerplate; die 40 Alt-Dateien bleiben funktional (zentraler Skip macht ihre
  Inline-Skips redundant) und werden inkrementell migriert.
