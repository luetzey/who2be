# Repo-Review — Remediation (Welle 1 Quick Wins)

**Stand:** 2026-06-13 · **Branch:** `claude/trusting-curie-rt7vjp`
**Quelle:** Systematisches Repo-Review (Senior-Architekt-Lauf, 2026-06-13).
Findings + Wellen-Plan im Chat-Transkript; dieses Dokument ist das Living-Doc
für die Umsetzung.

## Kontext

Codebase-Zustand gut bis sehr gut (mypy strict, ruff, 0 Source-Tech-Debt-Marker,
RLS als 2. Verteidigungslinie, Coverage-Ratchets). **Keine Critical/High-Findings.**
Größte Hebel = Wartbarkeit (Repo-Triplikation, `registry.py`-Hotspot); größte
Rest-Risiken = Härtung (fail-open MFA, Defense-in-Depth-Konsistenz).

## Welle 1 — Quick Wins (diese Iteration)

- [x] **QW-1 — Geteilte SQL-Entity-Whitelist (Security: Zero-Trust / Defense-in-Depth).**
  `gdpr_export_service._versioned` baute f-String-Tabellennamen ohne Runtime-Guard
  (nur Kommentar), während `entity_export_service` eine harte Whitelist hat.
  → Neuer geteilter Helper `services/entity_sql.py` (`safe_entity`/`ALLOWED_ENTITIES`);
  beide Services routen darüber. Fakt: heute nicht injizierbar (Call-Sites = Literale)
  → Härtung, kein aktiver Bug.
- [x] **QW-2 — MFA-Gate fail-closed in der Cloud (Security-Standards: Zero-Trust / fail-closed).**
  `require_aal2` ließ einen fehlenden `aal`-Claim immer durch (fail-open). Prod-GoTrue
  setzt `aal` immer; ein künftiger Token-Pfad ohne `aal` umginge MFA still.
  → Fail-open bleibt **nur On-Prem/Dev** (Magic-Link-/Test-JWTs ohne `aal`); in der
  Cloud wird fehlender `aal` fail-closed behandelt. Folgt dem etablierten
  `is_cloud()`-Muster (kein Pattern-Drift). Neuer Test deckt den Cloud-Block ab.
- [x] **QW-3 — Migrations-SSoT-Doku.** Kein Change nötig: `docs/architecture.md`
  dokumentiert bereits „Migrationen liegen bei der API"; `supabase/` enthält nur
  GoTrue-Auth-Schema-Bootstrap, **kein** irreführendes `supabase/migrations/`.
- [x] **QW-4 — ADR für Web-Session-Storage-Tradeoff (Security-Standards: benanntes
  Anti-Pattern „Tokens im Web-Storage").** Supabase-Session liegt bewusst im
  `sessionStorage` (Tab-Lifetime, Supabase-SPA-Norm), abgemildert durch Caddy-CSP
  (F-12). → Als akzeptiertes Rest-Risiko per ADR festgehalten.

## Welle 2 — Strukturell

- [x] **ST-1** `services/placeholders/registry.py` (1115 Z.) in `placeholders/resolvers/`-Paket
  gesplittet. Azyklische Schichtung `registry (Fassade, 72 Z.) → resolvers/{content,
  persona,tools,catalog,date}.py → _core.py` (Typen, Protocol, `SKILLS_ENABLED`,
  geteilte Helfer). Größtes Modul jetzt 349 Z. Öffentliche Import-Oberfläche
  (`placeholders/__init__`, `registry.*`) unverändert re-exportiert; `SKILLS_ENABLED`
  lebt jetzt in `_core` (4 Test-Monkeypatches + 1 `_CATALOG_LIMIT`-Import umverdrahtet).
  Verhalten unverändert: 357 API-Tests grün, mypy strict/ruff grün.
- [ ] **ST-2** E2E Soft→Hard-Gate: **bewusst zurückgestellt.** Die CI-Runner-Infra ist
  derzeit umgebungsweit defekt (kein Runner-Provisioning, siehe Welle-1-PR-Diagnose);
  ein Hard-Gate-Flip wäre untestbar und würde die ohnehin rote CI nur verschärfen.
  Erst flippen, wenn die Infra steht und 1–2 E2E-Läufe grün sind.

## Welle 3 — Strategisch (Drei-Optionen-Weiche: **Option A — generische Basisklasse** gewählt)

- [x] **STR-1a — Fundament + Persona.** `repositories/versioned_repository.py`:
  `VersionedAggregateRepository[TRead,TVersionRead]` + `AggregateTables`-Config hält
  den identischen Versionierungs-Kern (insert/update/upsert_draft/restore/list_versions/
  fetch_version/delete) als protected `_`-Methoden; Tabellennamen aus `entity` abgeleitet
  und über `entity_sql.safe_entity` whitelisted (Zero-Trust). `PgPersonaRepository` ist
  jetzt dünne Subklasse: Wrapper in die typisierten Signaturen (`PersonaUpdateOutcome`)
  + entity-spezifische Lesepfade (fetch/list_by_workspace/list_distinct_tags).
  Verifiziert: ruff, mypy strict (Protocol-Conformance grün), 72 Persona-Unit-Tests,
  generiertes SQL self-consistent. **Einschränkung:** DB-Integrationstests (28) konnten
  lokal nicht laufen (kein Docker, CI-Runner-Infra down) — SQL ist per
  Transkriptions-Äquivalenz + generierter-SQL-Inspektion + Typen verifiziert, **nicht**
  gegen echtes Postgres ausgeführt. CI/Reviewer bestätigt die Integration-Suite.
- [x] **STR-1b — Resource migriert.** `PgResourceRepository` ist jetzt Subklasse von
  `VersionedAggregateRepository` (623 → 283 Z.). Resource-spezifisch behalten:
  fetch/list_by_workspace mit `tag`-jsonb-Filter + `restrict_ids`, list_distinct_tags.
  Protocol + `ResourceUpdateOutcome` unverändert (null Service-Ripple). Verifiziert:
  ruff, mypy strict (120 Dateien), 357 Tests, generiertes Resource-SQL self-consistent.
  Gleiche DB-Ausführungs-Grenze wie STR-1a (kein Docker/CI-Runner).
- [x] **STR-1c — Playbook partiell migriert (Option B, vom User gewählt).** Recherche
  ergab: Playbook divergiert real (denormalisierte `type`/`tags`/`triggers` auf der
  Identitäts-Zeile, geschrieben in insert/update/upsert/restore; `is_composite`;
  eigene Array-/ILIKE-Filter; `list_triggers_with_playbooks`). Option A (Basis-Bloat
  für einen Ausreißer) verworfen. `PgPlaybookRepository` subclasst die Basis und erbt
  nur `list_versions`/`fetch_version`/`delete` via Wrapper; der Write-Core + Lese-Filter
  bleiben playbook-eigen. 712 → 694 Z. Verifiziert: ruff, mypy strict (120), 357 Tests.
  Gleiche DB-Ausführungs-Grenze.

**STR-1 abgeschlossen:** generische Basis über alle drei Aggregate angewandt (persona/
resource voll, playbook partiell). Verbleibende DB-Verifikation: einmal
`WHO2BE_TEST_TESTCONTAINERS=1 uv run pytest apps/api/tests -k "persona or resource or
playbook"` grün laufen lassen, sobald Docker/CI-Runner verfügbar.

## Verifikation (DoD)

`uv run ruff check .` · `uv run ruff format --check .` · `uv run mypy .` ·
betroffene Tests (`test_mfa_aal2`, `test_entity_export`, `test_gdpr_export`) grün.
