# Plan-Tiers & Mollie-Metadaten-Konvention

**Single Source of Truth** für die Cloud-Plan-Tiers (Plan
`2026-06-02-1819_followups-rls-mollie-auth-fsl.md` §3.2, Entscheidung M1/M2).
Die Code-Konstanten in `packages/billing/src/who2be_billing/plans.py` (optionales
Cloud-Paket, ADR-0029) spiegeln exakt diese Tabelle; bei Abweichung gewinnt dieses
Dokument und der Code wird nachgezogen.

> **Leitprinzip (Licensing-Standards §3.6):** Das Nutzungsrecht entscheidet die
> App über das **Entitlement** — der Zahlungsanbieter (Mollie) meldet nur
> Ereignisse und steuert den Zugriff nicht. Die freigeschalteten Feature-Codes
> und Limits liegen deshalb in der **Mollie-Subscription-/Customer-Metadata**,
> nicht in einem hartkodierten Produkt→Feature-Mapping.

## Tiers (final, 2 Stufen)

Die einzigen Groessen, die der Code tatsaechlich durchsetzt, sind Preis
(Mollie), MCP-Requests/Monat, MCP-Requests/Minute (beide `Entitlement`,
App-seitiges Rate-Limiting) und das Entity-Limit je Workspace
(`Entitlement.entity_limit()`). Das ist deshalb die verkaufsrelevante Tabelle:

| Tier | Preis          | MCP-Requests/Monat | MCP-Requests/Minute | Entity-Limit je Workspace | Features (Metadaten, s. u.) |
|------|----------------|---------------------|----------------------|----------------------------|------------------------------|
| Free | 0 € (kein Abo) | 1.000               | 30                   | 50                         | `core` |
| Pro  | 29 €/Monat     | 100.000             | 240                  | unbegrenzt                 | `core`, `composite_playbooks`, `agents`, `audit_export` |

Quellen: Preis/MCP-Requests `packages/billing/src/who2be_billing/plans.py`
(`FREE_PLAN`/`PRO_PLAN`: `price_eur`, `mcp_monthly_quota`,
`mcp_rate_per_min`); Entity-Limit `licensing/entitlement.py`
(`FREE_ENTITY_QUOTA = 50`, `Entitlement.entity_limit()`).

**Zur Features-Spalte — praezise gelesen:** Die Feature-Codes sind Metadaten
des Entitlements, kein Kaufargument. `Entitlement.entity_limit()` liest nur,
**ob ueberhaupt** ein Paid-Feature-Code vorliegt (`self.features - {Feature.CORE}`)
— diese Anwesenheit hebt das Entity-Limit von `FREE_ENTITY_QUOTA` auf
unbegrenzt. Die **einzelnen** Codes (`composite_playbooks`, `agents`,
`audit_export`) werden dagegen nirgends im Repo gegatet (keine
`has_feature()`-Pruefung greift auf sie zu; fuer `audit_export` existiert
nicht einmal ein Endpunkt) und sind deshalb **kein Leistungsversprechen** —
nur `core` selbst und das daraus abgeleitete Entity-Limit sind wirksam. Sie
tauchen weiterhin in `whoami`- und `entitlement`-Responses auf und bleiben
Teil des Datenmodells (ADR-0028 baut den On-Prem-Lizenz-Flow darauf auf) —
nur als Verkaufsversprechen zaehlen sie nicht.

- **Free** ist der Default jeder frisch registrierten Cloud-Org (ohne Mollie-Abo).
  Entspricht 1:1 `CLOUD_FREE_ENTITLEMENT` in `licensing/entitlement.py`.
- **Pro** ist eine einzelne wiederkehrende Mollie-Subscription (monatlich). Eine
  Kündigung (oder ausbleibende Zahlung → `canceled`/`suspended`) fällt die Org
  automatisch auf **Free** zurück — nie auf einen voll gesperrten Zustand, damit
  `core` erhalten bleibt.
- Pro ist bewusst ein **Superset** von Free (enthält `core`), sonst würden
  core-gated Reads für zahlende Kund:innen fehlschlagen.

## Mollie-Metadaten-Konvention

Beim Checkout schreibt die App die folgenden Schlüssel in die **Metadata** des
Mollie-Customers **und** der Subscription/Zahlung. Der Pull-Adapter
(`licensing/adapters/mollie.py`) liest sie nach dem Webhook-Ping wieder aus und
leitet daraus das Org-Entitlement ab.

| Schlüssel           | Typ    | Bedeutung                                                        |
|---------------------|--------|------------------------------------------------------------------|
| `org_id`            | UUID   | Ziel-Organisation des Entitlements (Pflicht).                    |
| `license_policy`    | String | Whitespace-/komma-separierte Liste der Feature-Codes (Pflicht).  |
| `mcp_monthly_quota` | Int    | Monats-Kontingent agent-facing MCP-Reads.                        |
| `mcp_rate_per_min`  | Int    | Per-Token-Rate-Ceiling (req/min).                                |

Beispiel-Metadata für **Pro**:

```json
{
  "org_id": "11111111-1111-1111-1111-111111111111",
  "license_policy": "agents audit_export composite_playbooks core",
  "mcp_monthly_quota": "100000",
  "mcp_rate_per_min": "240"
}
```

`license_policy` akzeptiert sowohl Komma- als auch Whitespace-Trenner; unbekannte
Codes werden ignoriert (Forward-Compatibility). Fehlen `mcp_monthly_quota`/
`mcp_rate_per_min`, gilt das jeweilige Limit als unbegrenzt (`None`).

Zusätzlich schreibt der Checkout einen **operativen** Schlüssel `plan_code`
(z. B. `"pro"`) in die Metadata. Er ist *nicht* Teil der entitlement-ableitenden
Konvention oben, sondern erlaubt dem Webhook, beim Anlegen der wiederkehrenden
Subscription Preis und Intervall des gebuchten Tiers wiederzufinden.

## Pull-Modell (Mollie-spezifisch, Entscheidung M2)

Mollie sendet **keine** signierten Webhook-Bodies, sondern nur einen Ping mit der
Zahlungs-`id` (form-encoded `id=`). Die Sicherheit entsteht durch das
**Pull-after-Ping**: die App holt das Objekt aktiv über die Mollie-API
(`MOLLIE_API_KEY`) — ein gefälschter Ping mit fremder/erfundener `id` liefert
entweder einen 404 oder ein Objekt ohne unsere `org_id`-Metadata und wird
verworfen. Optional härtet `MOLLIE_WEBHOOK_SECRET` den Endpunkt zusätzlich über
einen Pfad-/Query-Token (`?token=…`, konstant-zeitlich verglichen).

Ablauf:

1. **Checkout** (`POST /v1/workspaces/{ws}/billing/checkout`, admin): Mollie-Customer
   anlegen + erste Zahlung (`sequenceType=first`) mit Plan-Metadata erzeugen →
   Hosted-Checkout-URL zurückgeben.
2. **Erste Zahlung bezahlt** (Webhook-Ping): App fetcht die Zahlung; bei `paid` +
   gültigem Mandat + Plan-Metadata wird die eigentliche **Subscription** angelegt
   und das Org-Entitlement auf den gebuchten Tier gesetzt (`source="mollie"`,
   `external_ref=<subscription_id>`).
3. **Folgezahlungen / Statuswechsel** (Webhook-Ping): App fetcht die zugehörige
   Subscription → `active` ⇒ Tier bleibt; `canceled`/`suspended`/`completed` ⇒
   Org fällt auf **Free** zurück.

## Entitlement-Schreibquellen (ADR-0028)

`org_entitlement` ist die einzige **gelesene** SSoT; sie wird nur von klar
benannten Quellen **geschrieben** (per CHECK auf diese vier begrenzt), nie von der
ausgelieferten Read-App:

| `source` | Edition | Wer schreibt | Pflichtfelder |
|---|---|---|---|
| `mollie` | Cloud | Billing-Paket (Mollie-Pull) | `external_ref` |
| `cloud` | Cloud | Billing-Paket (generischer HMAC-Webhook) | `external_ref` |
| `manual_override` | Cloud | Admin-Endpoint `POST …/billing/override` | `expires_at`, `created_by`, `reason` |
| `signed_license` | On-Prem | **kein Tabellen-Write** — Adapter resolved live aus dem K_pub-verifizierten Token | — |

- **On-Prem:** Entitlement nur über den K_pub-Verifikationspfad
  (`WHO2BE_LICENSE_KEY`, env-validiert via `who2be-license verify`). Kein
  Tabellen-Writer im On-Prem-Build (das rohe `who2be-set-entitlement` wurde
  entfernt).
- **`manual_override`:** kontrollierter, **befristeter** + auditierter
  Ausnahmepfad (Support/Kulanz/Webhook-Hänger) — gleiche Tabelle, gleiches Lesen,
  Ablauf über `is_active()`/`expires_at`. Nur in der Cloud-Edition (Billing-Paket).
- **Build-Isolation:** Das Mollie-/Billing-Modul (`who2be-billing`) ist im
  On-Prem-Artefakt physisch nicht vorhanden (ADR-0029).

## Out of Scope (späterer Iterationsschritt)

Dunning/Retry-Strategie, Idempotency-Key-Dedupe der Webhooks und mehr als zwei
Tiers — siehe Plan §5.
