# #536 — Speicher-Quota je Org (Free 100 MB, Pro 10 GB)

Branch: `wt/i536-storage-quota` · Karte: `t_b41bfe0d` · Issue: #536
Owner-Entscheidung: **Option A — Free 100 MB, Pro 10 GB.**

## Ziel (Completion-Condition, messbar)

Ein Ingest über der für den Tarif geltenden Byte-Grenze antwortet `402`
mit `reason="storage_quota_exceeded"` und der Grenze in `params`; Bestand
bleibt les- und herunterladbar; On-Prem/OSS ist unbegrenzt;
`docs/licensing/plans.md` nennt dieselben Zahlen wie `plans.py`; die
Tabellen-Store-Lücke (ADR-0049) steht ausdrücklich in der Doku. Grün =
DoD-Kommandos + OpenAPI-Drift-Check Exit 0.

## Ist-Zustand (nachgemessen auf dem Worktree)

- `Entitlement` (`licensing/entitlement.py`) kennt `mcp_monthly_quota`,
  `mcp_rate_per_min`, `grace_until` — kein Speicherfeld.
- Zwilling: `services/entity_quota_service.py` (Cloud-Wache, Org-Auflösung,
  Zählung, 402 + `params`), Tests `tests/test_entity_quota_service.py`.
- Zählgrundlage: `wa_blob.size_bytes bigint NOT NULL` (Migration 0075),
  RLS auf `app.current_tenant`.
- Persistenz: `org_entitlement` (0030) + `entitlement_history` (0045)
  tragen je eine Spalte pro Entitlement-Feld; `PgEntitlementRepository`
  liest/schreibt sie explizit.
- Ingest-Routen: `routers/wa_ingest.py` (2 POST-Routen).

## Entscheidungen (Abweichungen begründet)

1. **Migration nötig.** Ein neues `Entitlement`-Feld ohne Spalte wäre nach
   dem ersten Webhook-Upsert verloren (`_row_to_entitlement` liest Spalten).
   Deshalb `0084_org_entitlement_storage_quota.sql`: Spalte auf
   `org_entitlement` **und** `entitlement_history` (das Journal spiegelt die
   SSoT-Felder), beide `IF NOT EXISTS`, `CHECK (… IS NULL OR … >= 0)` wie
   bei den MCP-Spalten.
2. **Zähl-Granularität = Workspace**, wortgleich zur Begründung des
   Zwillings: das Gate läuft im `tenant_scope` des Requests, RLS zeigt nur
   den aktuellen Workspace; für den Free-Tier (Personal-Org, ein Workspace)
   deckungsgleich mit „pro Org".
3. **Vorab-Check statt Nachkalkulation.** Die Dependency kennt den Body
   nicht; sie prüft `summe >= limit` (Muster `entity_quota_service`). Der
   Überschuss je Ingest ist damit auf `WHO2BE_INGEST_MAX_BYTES` begrenzt —
   ausdrücklich im Service-Docstring festgehalten, nicht stillschweigend.
4. **Tabellen-Store (ADR-0049) zählt nicht mit** — in `plans.md` *und* im
   Service-Docstring als bekannte Grenze.

## Arbeitsschritte

1. `Entitlement.storage_quota_bytes` + Konstanten
   `FREE_STORAGE_QUOTA_BYTES = 100 MB`, `PRO_STORAGE_QUOTA_BYTES = 10 GB`;
   `CLOUD_FREE_ENTITLEMENT` bekommt den Free-Wert, `OSS_ENTITLEMENT` `None`.
2. Migration 0084 + `PgEntitlementRepository` (fetch/upsert/history) +
   `licensing/license.py` (On-Prem-Lizenz-Payload) + `core/license_cli.py`.
3. `plans.py`: `Plan.storage_quota_bytes`, `META_STORAGE_QUOTA_BYTES`,
   Werte in `FREE_PLAN`/`PRO_PLAN`, Metadata-Ausgabe.
   `webhook.py`: `_parse_int_meta(metadata, "storage_quota_bytes")`.
   `billing/router.py` (`override`): Wert aus dem Plan.
4. `services/storage_quota_service.py` + Dependency an beiden Ingest-Routen.
5. Read-Pfad (`routers/entitlement.py`): `storage_quota_bytes` +
   `usage.storage_bytes`; `apps/web/src/api/types.ts` + `BillingPanel`
   (Verbrauch/Grenze) + i18n de/en.
6. Doku: `docs/licensing/plans.md` (Spalte, Metadaten-Key, ADR-0049-Lücke),
   `CHANGELOG.md` (Unreleased/Added).
7. Tests: `test_storage_quota_service.py` (onprem no-op, unbegrenzt ohne
   Zähl-Roundtrip, unter Limit frei, am Limit 402 + reason + params),
   Read-Pfad-Beleg (kein Storage-Gate an Read-/Export-Routen, Gate an beiden
   Ingest-Routen), Ergänzungen in `test_licensing_entitlement.py`,
   `packages/billing/tests/test_plans.py`, Webhook-Metadaten.
8. Verifikation: DoD-Block Python + Web, `scripts/export_openapi.py` +
   `git diff --exit-code docs/reference/openapi.json`.

## Bekannte Grenzen (im PR zu nennen)

- Das Entitlement trägt die Metadaten des **Kaufzeitpunkts**
  (`webhook.py:448`): eine später angehobene Zahl wirkt erst beim nächsten
  Checkout. Heute folgenlos (keine Kunden).
- Bestandszeilen in `org_entitlement` tragen nach der Migration `NULL` =
  unbegrenzt — identisch zur Semantik der MCP-Spalten und AK-konform
  („`None` = unbegrenzt").
- Datei-Kollision mit #538 (`entitlement.py`, `plans.py`, `plans.md`):
  diese Karte läuft zuerst.
