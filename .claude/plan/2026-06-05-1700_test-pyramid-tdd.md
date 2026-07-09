# Plan — Vollständige Test-Pyramide (TDD)

**Status:** ✅ **UMGESETZT** (2026-06-05) — alle 6 Phasen auf
`claude/laughing-lovelace-0OWCg` / PR #149. CI grün (Python 86.92 % Coverage,
722 Tests; Web ~81 %); E2E-Spitze als Soft-Gate (Public-Smokes live,
Journeys als `test.fixme`-Scaffolds bis Auth-Seed-Helper steht).
**Erstellt:** 2026-06-05. **Branch:** `claude/laughing-lovelace-0OWCg`.
**Entscheidungen (User 2026-06-05):** E2E **dünn** (3–5 Journeys) · Integration via
**Testcontainers** (lokal+CI) · Coverage als **Ratchet-Floor** in CI.
**Geplanter ADR:** `docs/adr/0041-test-strategie-pyramide.md` (bei Erstellung
als „ADR-0032" nummeriert; 2026-07-08 wegen Doppelvergabe auf 0041 umnummeriert
— die ADR-0041-Verweise in diesem Plan entsprechend nachgezogen).

## Ziel (DoD)

Eine ehrliche, messbare Test-Pyramide mit durchgängigen Gates:

- Coverage instrumentiert in **beiden** Stacks, Baseline gemessen, **Ratchet-Floor**
  in CI (jede Senkung bricht den Build).
- Integration-Tier läuft **wirklich** (lokal + CI) via ephemerer Postgres — kein
  stilles Skippen mehr; gemeinsames `conftest.py` statt 40× dupliziertem Bootstrap.
- Naht-/Contract-Tests an den drei Driftstellen (OpenAPI-Snapshot, REST↔MCP-Parität,
  Web-Client↔OpenAPI).
- **Dünne** E2E-Spitze (Playwright, 3–5 Journeys) gegen den Compose-Stack.
- Alle Gates grün: `uv run pytest/ruff/mypy` + `npm lint/tsc/test/build` + neue
  e2e/contract-Jobs. Draft-PR mit verlinktem ADR-0041.

## Diagnose — gemessene Ist-Form (Stand 2026-06-05)

| Tier | Bestand | Bewertung |
|------|---------|-----------|
| Models-Unit (pur) | 12 Dateien | ✅ solide Basis |
| API-Service-Unit (ohne DB) | 19 Dateien | ✅ gut |
| MCP In-Process | 6 Dateien | 🟡 Write-Tools (ADR-0030) dünn abgedeckt |
| Billing-Unit | 6 Dateien | ✅ |
| API-Integration (echte DB) | ~40 Dateien | 🟠 **skippen still ohne DB** |
| Web Component/Page/Hook (jsdom) | 88 Dateien, inkl. a11y (axe) | ✅ breit, ✅ a11y stark |
| **E2E (Browser)** | **0** | ❌ **Spitze fehlt** (nur `scripts/smoke.sh`, 4 Curl-Checks) |
| **Coverage-Messung** | **keine** | ❌ Pyramidenform faktisch unbekannt |

### Kritische Befunde (Hinterfragt)

1. **Blindflug ohne Coverage.** Weder `pytest-cov` noch `@vitest/coverage` installiert
   → niemand kennt die wahre Abdeckung; kein TDD-Ratchet möglich.
2. **Stille Skips untergraben das DoD.** 40 Integrationstests nutzen ein dupliziertes
   `_db_reachable()` und skippen ohne DB. Lokal „grün durch Skip" → die Repo-Regel
   „lokal verifiziert vor jedem Push" ist hier unwahr. Kein `conftest.py` ⇒ Bootstrap
   40× kopiert (Wartungslast + Flockungsrisiko).
3. **Ungetestete Nähte.** MCP-Read garantiert `status='active'`-Filter — REST kann
   abweichen, kein Paritätstest. `apps/web/src/api/client.ts` mockt Shapes, die vom
   echten OpenAPI driften können. Kein OpenAPI-Snapshot.
4. **Spitze fehlt.** Kein End-to-End-Durchlauf durch einen echten User-Journey.

### Bewusste Nicht-Ziele (Anti-Ice-Cream-Cone)

- **Keine** breite E2E-Schicht. E2E bleibt absichtlich dünn (3–5 Journeys); Logik wird
  unten in Unit/Integration getestet, nicht durch den Browser.
- **Kein** Last-/Performance-Test in diesem Plan (separater Block, falls gewünscht).

## Arbeitsweise (TDD, pro Schritt)

Red → Green → Refactor. Bei jedem Bugfix zuerst ein **reproduzierender, failing Test**
(Repo-DoD). Neue Tests werden vor der Implementierung geschrieben; Refactors (z. B.
conftest-Extraktion) halten die bestehende Suite grün als Sicherheitsnetz.

---

## Phase 0 — Fundament: Sichtbarkeit & Gates (zuerst)

Ohne Messung kein TDD-Ratchet. Diese Phase ändert keine Produktlogik.

1. **Python-Coverage.** `pytest-cov` in die `dev`-Group; `[tool.coverage.run]`
   (`source = apps/api/src, apps/mcp/src, packages/models/src, packages/billing/src`,
   `branch = true`) + `[tool.coverage.report]` in `pyproject.toml`. Baseline messen
   (`uv run pytest --cov --cov-report=term-missing`).
2. **Web-Coverage.** `@vitest/coverage-v8` als devDep; `test.coverage` (provider
   `v8`, `reporter` text+json+html, `include: src/**`) in `vite.config.ts`. Baseline
   via `vitest run --coverage`.
3. **Gemeinsames `conftest.py`** unter `apps/api/tests/` (+ ggf. `apps/mcp/tests/`):
   `_db_reachable`, `_prepare_db`, JWT-Secret/Token-Fixtures, `setup_workspace`/
   `cleanup_workspaces` als Fixtures aus `who2be_api.testing.workspace_setup`
   herausgezogen. **Refactor-only** — bestehende 40 Dateien auf Fixtures umstellen,
   Duplikat-Bootstrap entfernen, Suite bleibt grün.
4. **CI-Gates** (`.github/workflows/ci.yml`):
   - Python-Job: `pytest --cov --cov-fail-under=<Baseline>` (Ratchet-Floor).
   - Web-Job: `vitest run --coverage` mit `thresholds` = Baseline.
   - **Skip-Guard:** CI hat immer Postgres ⇒ Step, der bricht, wenn Integrationstests
     skippen (z. B. `--strict-markers` + Assertion „0 skipped in DB-Suite"). So kann
     der stille Skip nie wieder als grün durchrutschen.
   - Coverage-Artefakte hochladen (HTML).

**Gate Phase 0:** beide Suites grün mit Coverage; Floors gesetzt; conftest-Refactor
ohne Verhaltensänderung.

## Phase 1 — Unit-Basis verbreitern (test-first für Lücken)

Aus dem Phase-0-Report die ungedeckten Branches gezielt schließen — pro Lücke erst
failing Test:

- **API-Services:** `placeholder_renderer` (Edge-Cases/fehlende Platzhalter),
  `version_diff` (leere/identische/große Diffs), Composition-**Zyklenerkennung**
  (Playbook/Resource), `entitlement`-Source-Guards (nur erlaubte Schreibquellen),
  `licensing_crypto` (Fehlerpfade: ungültige Signatur/abgelaufen), Token-Bucket-
  Grenzen im Rate-Limiter.
- **Models:** Validierungs-Randfälle, die im Coverage-Report fehlen
  (Status-Übergänge, Locale-Defaults, Pagination-Grenzen).
- **Web-Libs/Hooks:** alle `lib/`+`hooks/` ohne Test (Report-getrieben);
  reine Funktionen ohne jsdom.

## Phase 2 — Integration-Tier härten & entflocken (Testcontainers)

5. **Testcontainers-Postgres.** `testcontainers[postgres]` in `dev`; conftest-Fixture
   startet ephemere DB pro Session, wendet `apply_migrations` an, setzt
   `database_url`. Lokal **ohne** laufende DB nutzbar (nur Docker nötig) ⇒ Skips
   verschwinden, DoD wird ehrlich. CI nutzt weiterhin den Service **oder** den
   Container (eine Quelle wählen, im ADR festhalten).
6. **Integration-Lücken füllen (test-first):**
   - **MCP-Write-Tools (ADR-0030)** end-to-end: Autorisierung (editor / admin für
     promote/retire), Owner-Scoping, Draft→active-Workflow, **kein** delete.
   - **Status-Invarianten:** partial-unique-index-409 (PUT auf active erzeugt Draft;
     zweiter Draft → 409), Transition-Matrix.
   - **RLS-Isolation** Vollständigkeit über alle Entitäten/Workspaces.
   - **Rate-Limit-Mutations** unter Nebenläufigkeit.
   - **GDPR Export/Purge** vollständiger Pfad; **Invitations** single-use/expired/
     email-mismatch.

## Phase 3 — Contract-Tests (die ungetesteten Nähte)

7. **OpenAPI-Snapshot.** Test friert `app.openapi()` als Golden-File ein; Diff bricht
   bei unbeabsichtigter Schema-Änderung (bewusste Änderungen aktualisieren das Golden).
8. **REST↔MCP-Parität.** Dieselbe Entität, die REST als active-Read liefert, muss von
   MCP `fetch_*` identisch geliefert werden (Vertrag `status='active'`). Ein
   gemeinsamer Fixture-Seed, beide Pfade, Felder-Vergleich.
9. **Web-Client↔OpenAPI.** Contract-Test, der die in `api/client.ts` erwarteten
   Request/Response-Shapes gegen das echte OpenAPI prüft (Mock-Server gegen Schema
   validiert), damit Frontend-Mocks nicht stillschweigend driften.
10. **Models als SSoT.** Assertion, dass API + MCP dieselben Pydantic-Models
    importieren (erweitert das Muster aus `test_no_billing_in_core`).

## Phase 4 — Dünne E2E-Spitze (Playwright, bewusst klein)

11. **Playwright-Setup** unter `apps/web/` (`@playwright/test`, eigene
    `playwright.config.ts`, **nicht** in Vitest mischen). Läuft gegen den per
    `docker compose up --wait` gestarteten Stack (Wiederverwendung des
    `compose-smoke`-Jobs).
12. **3–5 kritische Journeys:**
    1. **Login** (Magic-Link **oder** Passwort) → Dashboard sichtbar.
    2. **Persona-Lifecycle:** anlegen (Draft) → BlockNote editieren →
       Transition Draft→Review→Active; Status-Action-Bar reflektiert.
    3. **Playbook→Resource-Block-Ref:** verknüpfen → Backlink in Resource-Detail.
    4. **MCP-Active-Read:** MCP-Client liefert die **aktive** Version (gegen den
       laufenden Stack) — bestätigt den Vertrag end-to-end.
    5. **Invitation-Accept:** inkl. Email-Mismatch-Guard / `next`-Open-Redirect-Härtung.
13. **CI-Job `e2e`:** zunächst non-blocking (`continue-on-error`) für 1–2 Läufe zur
    Stabilisierung, dann hart schaltend. `scripts/smoke.sh` bleibt als schneller
    Infra-Smoke; UI-Journeys wandern nach Playwright.

## Phase 5 — Querschnitt (klein halten)

14. **A11y:** für jede in Phase 1/4 berührte neue Page einen axe-Test (bestehendes
    `test:a11y`-Gate). Keine Regression.
15. **Security-Authz-Matrix:** `test_rbac_matrix` zu einer parametrisierten Rolle×
    Endpoint-Matrix ausbauen; Review über Subagent `security-reviewer` (Repo-Security-
    Regel).

## CI-Endzustand (`ci.yml`)

- `python`: Testcontainers/Service + `--cov-fail-under` (Ratchet) + Skip-Guard.
- `web`: `vitest --coverage` mit Thresholds (Ratchet) + bestehende lint/tsc/build/a11y.
- **neu** `e2e`: Playwright gegen Compose (erst soft, dann hart).
- **neu** `contract`: OpenAPI-Snapshot + REST↔MCP-Parität (kann im python-Job laufen).
- bestehende `compose-smoke`/`audit` bleiben.

## Risiken / offene Punkte

- **Testcontainers in CI:** entweder Service **oder** Container, nicht beides — im
  ADR-0041 festschreiben, sonst doppelte DB-Quelle.
- **Playwright-Flake:** Journeys idempotent seeden (frischer Workspace pro Lauf),
  feste `data-testid`-Hooks statt Text-Selektoren.
- **Ratchet-Reibung:** Baseline ehrlich (nicht zu hoch) setzen, sonst blockiert das
  Floor legitime PRs; Anhebung nur in dedizierten Coverage-PRs.
- **Reihenfolge ist bindend:** Phase 0 zuerst — ohne Messung kein sinnvoller Ratchet
  und keine priorisierte Lückenliste.

## Reihenfolge & Schnitt in PRs

1. PR-A: Phase 0 (Coverage + conftest-Refactor + Gates) — klein, reviewbar.
2. PR-B: Phase 2 Testcontainers + Integration-Lücken.
3. PR-C: Phase 1 Unit-Lücken (report-getrieben).
4. PR-D: Phase 3 Contract-Tests.
5. PR-E: Phase 4 Playwright-E2E.
6. PR-F: Phase 5 Querschnitt + ADR-0041 final.

(Alle als Draft, je mit Session-Link; ADR-0041 begleitet PR-A und wird in PR-F finalisiert.)
