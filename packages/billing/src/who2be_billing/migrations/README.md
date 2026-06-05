# Billing-eigene Migrationen (Cloud-only)

Hier liegen Migrationen für **billing-spezifische** Tabellen (z. B. ein künftiger
Webhook-Dedupe-Ledger). Sie laufen **ausschließlich in der Cloud-Edition**: der
Migrations-Runner (`who2be_api.core.migrations`) entdeckt dieses Verzeichnis nur,
wenn das optionale `who2be-billing`-Paket installiert ist (dynamische Discovery,
kein statischer Import). Im On-Prem-Artefakt ist das Paket nicht vorhanden →
diese Migrationen gelangen nie in den On-Prem-Migrationspfad (ADR-0029).

## Konventionen

- Dateiname-Präfix `billing_<NNNN>_<slug>.sql`, damit die Namen global eindeutig
  sind und **nach** den Kern-Migrationen sortiert/angewendet werden (gemeinsames
  `schema_migrations`-Ledger).
- Idempotent schreiben (`CREATE TABLE IF NOT EXISTS`, guarded `ADD CONSTRAINT`).

## Abgrenzung

Die Org-SSoT `org_entitlement` ist **keine** Billing-Tabelle — sie wird vom Kern
**gelesen** (Cloud- und On-Prem-Read-Adapter) und lebt daher im Kern-Migrationspfad
(`apps/api/.../migrations/`). Hierher gehören nur Tabellen, die **ausschließlich**
der Billing-Schreibdienst braucht. (`processed_webhook_event` aus Migration 0039
stammt aus der Zeit vor diesem Schnitt und bleibt im Kernpfad; neue billing-only
Tabellen kommen hierher.)
