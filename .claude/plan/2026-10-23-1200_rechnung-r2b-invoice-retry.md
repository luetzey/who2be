# Rechnung R2b: Worker `invoice-retry` + VIES-Nachpruefung (72 h)

Karte t_820a9196. Grundlage: ADR-0061 §3, §4, §6 (W61-3 A, 72 h), ADR-0057 (Registry),
PM-Kommentar zu R2a N1 (Webhook nur vormerken, Ausstellen in den Worker).

## Completion-Condition

- Routine `invoice-retry` (`@every 5m`) in `worker/routines.py`, in `_EXPECTED`. On-Prem bzw.
  ohne `who2be_billing`: No-Op mit Zaehler, kein statischer Import (ADR-0029).
- Webhook merkt nur noch vor; Ausstellen und Archivieren macht ausschliesslich der Worker.
- Timeout nach POST: der naechste Lauf sucht zuerst ueber die List-API
  (`paymentDetails[].sourceReference == payment_id`), findet ⇒ uebernimmt ID/Nummer, kein POST.
  Rot-Probe: Suche neutralisiert ⇒ zweiter POST ⇒ Test rot.
- Backoff je Zeile (5 min · 2^(n-1), hoechstens 6 h) ueber `attempts` + `updated_at`;
  nach 8 technischen Fehlern `pending` ⇒ `failed` + ERROR-Log (Betreiber-Hinweis).
  `issued` (Archiv fehlt) wird nie `failed`: die Rechnung existiert, Archiv bleibt Pflicht.
- Zurueckgehaltene Zeilen (`hold:*`) zaehlen keinen Versuch, Nachpruefung stuendlich.
- VIES-Nachpruefung bei `hold:vat_id_unchecked`: Ergebnis in `billing_profile`, dann Ausstellen
  nach Ergebnis. Ab 72 h nach Vormerken ohne Ergebnis: B (19 % wie ungueltig) + WARN-Log.
- Tests mit gefaelschter Uhr (72-h-Grenze, Backoff), DoD aus CONTRIBUTING gruen.

## Dateien (7 + Changelog + dieser Plan)

1. `apps/api/src/who2be_api/worker/routines.py`
2. `apps/api/tests/test_worker_routines.py`
3. `packages/billing/src/who2be_billing/invoice.py`
4. `packages/billing/tests/test_invoice.py`
5. `packages/billing/src/who2be_billing/billing_profile.py` (VIES-Ergebnis zurueckschreiben, Repo auf Connection)
6. `packages/billing/src/who2be_billing/mollie.py` (N1: kein `issue` mehr im Webhook)
7. `packages/billing/tests/test_mollie_adapter.py`

## Entscheidungen (belegt, keine Weiche)

- Keine Migration: Backoff aus `attempts` (zaehlt jetzt technische Fehler statt POST-Starts)
  und `updated_at` (Trigger setzt es bei jedem Fehlerschreiben). Faelligkeit als reine Funktion.
- List-API hat keinen Filter (Referenz `list-sales-invoices`: nur `from`, `limit`): Seiten zu 250,
  hoechstens 4; `_links.next` nur an api.mollie.com. Seitenlimit erreicht ohne Treffer ⇒ unklar,
  kein POST (lieber spaeter als doppelt).
- Gefundene Rechnung: Satz, `vatMode` und Memo werden aus der Mollie-Rechnung uebernommen,
  nicht neu berechnet (sie ist die Wahrheit dessen, was ausgestellt wurde).
- Uebergang: bis R2d die Variablen am `worker` durchreicht, bleiben Zeilen `pending`
  (fail closed, Mollie stellt nachtraeglich aus, ADR-0061 §3).

## Nicht in R2b

Compose/.env, RUNBOOK-Routinenliste, ADR-0061-Nachtrag zum Webhook-Schnitt (R2d);
Checkout-Betrag/409 (R2c).
