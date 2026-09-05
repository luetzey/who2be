# Kettentest Checkout → Webhook → Entitlement → Limit (WP-4 von #428, Issue #451)

- Status: **in Arbeit**
- Datum: 2026-09-05, 20:00 UTC (21. Lauf)
- Issue: #451 (`agent-ready`, `size/S`), Eltern-Issue #428
- Branch: `claude/autonomous-code-agent-role-u3thhe`

## 1. Ask-Once-Gate

**Bestanden.** Outcome, sechs prüfbare Kriterien, explizites Out-of-Scope,
Verifikations-Kommandos und fünf vorentschiedene Weichen stehen im Body.

## 2. Umgebungsgrenze — gemessen, nicht vermutet

**In dieser Session ist kein Docker verfügbar** (`docker info` → nicht
verfügbar), also lässt sich keine Postgres-Instanz hochfahren. Gemessene Folge
für die volle Suite:

```
uv run pytest --cov --cov-fail-under=85
→ 1305 passed, 448 skipped
→ TOTAL coverage 63.08 %
→ FAIL Required test coverage of 85% not reached
```

Die 448 Skips sind die `integration`-Tests, die der Root-`conftest.py`
zentral überspringt, wenn keine DB erreichbar ist (ADR-0041). Das Gate
`--cov-fail-under=85` ist hier also **grundsätzlich** nicht erreichbar — das
gilt für jedes Python-Paket dieser Warteschlange, unabhängig von der Änderung.
Die CI fährt eine DB als Service-Container und setzt `WHO2BE_REQUIRE_DB=1`;
dort greift das Gate wie vorgesehen.

Konsequenz für dieses Paket: der Kettentest muss **ohne** `integration`-Marker
auskommen, sonst könnte er hier nicht ein einziges Mal ausgeführt werden — ein
blind gepushter Test ist schlimmer als keiner.

## 3. Weiche 3 des Issues, hier entschieden

Das Issue lässt bewusst offen, wo der Test liegt: „bei den Billing-Tests,
sofern er dort an die Entitlement-Auflösung kommt; sonst unter
`apps/api/tests/`". Die Prüfung ergibt:

| Baustein | Injizierbar? | Beleg |
|---|---|---|
| `McpLimitService(pool, usage_repo, settings)` | ja, alle drei | `services/mcp_limit_service.py:48-56` |
| `_resolve_org_id` | nutzt `self._pool.fetchval` | `:59` |
| Entitlement-Port | **nein**, intern gebaut via `build_entitlement_port(self._pool, …)` | `:80`, `licensing/service.py:24-29` |

Der Port ist nicht injizierbar, `pool` und `usage_repo` dagegen schon. Ein
Stub-Pool, der `fetchval`/`fetchrow` mit vorbereiteten Zeilen bedient, trägt
damit sowohl `_resolve_org_id` als auch `PgEntitlementRepository` — die
Entscheidungslogik (`Entitlement.is_active`, Quota-Vergleich,
`increment_if_allowed`) bleibt dabei **echt** und ungemockt.

**Entscheidung: Test bei den Billing-Tests, mit Fakes, ohne DB.** Belegt durch
Weiche 1 des Issues („Fake-Gateway, wie ihn `test_mollie_adapter.py` bereits
nutzt … weil die Tests netzfrei bleiben müssen") und durch die etablierten
Fakes derselben Suite (`FakeEntitlementRepository`, `FakeMollieGateway`,
`FakeProcessedEventRepository`).

**Was das belegt und was nicht — ausdrücklich:** belegt ist die Kette
Checkout → Webhook-Mapping → Entitlement-Auflösung → Limit-Entscheidung, also
genau die Aussage „ein bezahltes Abo schaltet höhere Limits frei". **Nicht**
belegt ist der SQL-Schreibpfad in die Tabelle `org_entitlement` — der hat
seine eigenen Integrationstests (`repositories/entitlement_repository.py`) und
liegt außerhalb dieses Zuschnitts.

## 4. Muster-Entscheidung

**Keine Muster-Entscheidung nötig** — der Test verwendet die bereits
existierenden Fake-Klassen der Suite wieder; es entsteht keine neue
Abstraktion. Ein eigener Stub-Pool ist eine Test-Hilfe, kein Produktivmuster.

## 5. Arbeitspaket

1. Kettentest unter `packages/billing/tests/` — Name benennt die Kette, nicht
   das Paket. Positivfall (nach Webhook durchgelassen) und Gegenfall (Free →
   abgewiesen mit dem Status aus `mcp_limit_service`).
2. Checkout-Endpunkt einmal über HTTP auf dem Erfolgspfad (201 + die an Mollie
   übergebenen Metadaten), Vorlage `test_mollie_endpoint.py`.
3. `scripts/smoke.sh`: Billing-Route-Check — Cloud antwortet, On-Prem 404;
   ohne Mollie-Key nicht falsch rot (prüft Existenz, nicht Erreichbarkeit).
4. `CHANGELOG.md` (Unreleased) und `.claude/context/STATE.md` als letzter
   Commit.

## 6. Verifikation

Lokal ausführbar und damit belastbar:

```bash
uv run pytest packages/billing/tests -v
uv run ruff check . && uv run ruff format --check .
uv run mypy .
bash -n scripts/smoke.sh
grep -n 'billing' scripts/smoke.sh
git diff --stat main -- packages/billing/src apps/api/src   # muss leer sein
```

Zusätzlich die Gegenprobe aus dem Issue: der Kettentest muss **fehlschlagen**,
wenn man das Webhook-Ereignis aus ihm entfernt (prüfen, nicht committen).

Nicht lokal prüfbar: `uv run pytest --cov --cov-fail-under=85` (siehe §2) —
das übernimmt die CI. Im PR wird das offengelegt statt abgehakt.
