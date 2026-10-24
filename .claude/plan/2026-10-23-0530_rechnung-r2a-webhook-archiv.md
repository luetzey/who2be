# Rechnung R2a: Rechnung im Webhook-Pfad + PDF-Archiv

Karte t_36c180ed. Grundlage: ADR-0061 §3, §4, §5, §7; PM-Entscheidung 2026-10-23 (Teilung R2a–R2d).

## Completion-Condition

- Bezahlter Erst- oder Folgezahlungs-Webhook legt genau eine `billing_invoice`-Zeile je
  payment_id an (`UNIQUE (payment_id)`), POSTet hoechstens einmal `/v2/sales-invoices`.
- Fehler (422, Timeout, Netz, PDF, BlobStore) lassen die Zeile `pending`/`issued`, der
  Webhook antwortet 200, das Entitlement bleibt geschrieben.
- Rot-Probe: ohne UNIQUE wird der Doppel-Webhook-Integrationstest rot.
- DoD aus CONTRIBUTING (ruff, format, mypy, pytest mit DB + Coverage).

## Dateien (7 + Changelog-Fragment)

1. `packages/billing/src/who2be_billing/migrations/billing_0111_billing_invoice.sql` (0111 frei: 0109 R1, 0110 account_state)
2. `packages/billing/src/who2be_billing/invoice.py`
3. `packages/billing/src/who2be_billing/mollie.py` (nur Hook + `paid_at`)
4. `packages/billing/src/who2be_billing/router.py` (nur Verdrahtung)
5. `apps/api/src/who2be_api/core/config.py` (zwei Schalter)
6. `packages/billing/tests/test_invoice.py`
7. `packages/billing/tests/test_mollie_adapter.py`

## Entscheidungen (belegt, keine Weiche)

- Zweite Sperre neben UNIQUE: `post_started_at` wird atomar vor dem POST gesetzt. Nur bei
  sicher nicht angelegter Rechnung (4xx, Verbindungsaufbau gescheitert) wird sie
  zurueckgesetzt; bei Timeout/5xx bleibt sie stehen, R2b sucht dann ueber die List-API.
- Kein FK auf `organization` (Aufbewahrung ueberlebt den Org-Purge, ADR-0061 §9).
- Trigger statt Spalten-Grants: PDF-Key, Hash, Mollie-ID, Nummer einmal gesetzt
  unveraenderlich, Status nur vorwaerts, kein DELETE-Grant.
- Empfaenger-E-Mail aus dem Mollie-Customer (beim Checkout mit Admin-Mail angelegt);
  fehlt sie, haelt die Rechnung zurueck. Kein `emailDetails`: Who2Be verschickt nichts.
- pdfLink wird nur an `https://api.mollie.com` mit Key abgerufen; Rechnungsnummer und
  -ID werden vor Key- bzw. URL-Bau per Muster geprueft.
- Zeilenbetrag = Planpreis (W61-2 A); Zahlbetrag je Steuerfall kommt mit R2c.

## Nicht in R2a

Worker-Retry/VIES (R2b), Checkout-Betrag/409/e2e (R2c), Compose/.env/Doku (R2d).
