# Rechnung R3: Rechnungen im Web (Liste + PDF-Download)

Kanban-Karte t_ed914245, Paket R3 aus ADR-0061 (Rechnung Mollie). Basis: origin/main
2660d2c3 (R2a–R2c gemergt; R2d #1087 betrifft nur Deploy/Doku).

## Ziel (Completion-Condition)

Im Billing-Bereich der Org-Einstellungen sehen Admins die Rechnungen ihrer
Organisation (Nummer, Datum, Betrag, Status) und laden archivierte PDFs aus dem
eigenen Archiv. Erfüllt, wenn:

- `GET /v1/workspaces/{ws}/billing/invoices` liefert nur Rechnungen der Org des
  Workspace, nur für Admins (403 sonst), 404 On-Prem.
- `GET /v1/workspaces/{ws}/billing/invoices/{invoice_id}/pdf` liefert das PDF;
  fremde, unbekannte oder noch nicht archivierte Rechnung → 404; Nicht-UUID → 422.
- Leerzustand, Lade- und Fehlerzustand im Web, DE/EN, axe ohne Befund.
- Fotos 1280/390 × hell/dunkel + measure.json.

## Vorentschiedene Weichen (mit Beleg)

1. **Rolle = admin.** Wie Checkout und Rechnungsdaten (`router.py`,
   `require_role(ctx, WorkspaceRole.admin)`); es gibt keine eigene Billing-Rolle.
2. **Org aus dem Workspace, nie aus der URL.** `resolve_org_id` wie beim Profil;
   jede Abfrage filtert explizit `org_id = $org` (die RLS-Policy von
   `billing_invoice` ist ohne `app.current_org` permissiv, darauf verlassen wir
   uns nicht).
3. **Gelistet werden nur `issued` und `archived`.** Nur sie haben eine
   Rechnungsnummer (`billing_invoice_issued_check`). `pending`/`failed` sind
   Betreiber-Zustände ohne Beleg.
4. **Status in der UI:** `archived` → „PDF verfügbar“ mit Download, `issued` →
   „PDF wird vorbereitet“ ohne Knopf. Eine Quelle: das Feld `status` der API.
5. **PDF nur aus dem eigenen Archiv**, nie live von Mollie; vor der Auslieferung
   wird der SHA-256 gegen `pdf_sha256` geprüft (ADR-0061 §7 Unveränderbarkeit).
   Abweichung oder fehlendes Blob → 500 mit Log, nichts ausgeliefert. Ohne
   BlobStore → 503.
6. **Keine Migration.** Index `billing_invoice_org_idx (org_id, created_at DESC)`
   existiert; SELECT-Grant für `who2be_app` existiert (billing_0111).
7. **Keine Pagination, kein Filter:** monatliche Rechnungen, Obergrenze 240
   Zeilen (20 Jahre); ListFilterBar laut PM nur „falls nötig“ → nicht nötig.
8. **Steuer-Schalter unberührt:** R3 zeigt nur, was R2 ausgestellt hat; der
   Betrag ist `amount_value` (bezahlter Betrag) – keine Neuberechnung.

## Dateien (≤ 8, Changelog-Fragment und dieser Plan zählen nicht)

1. `packages/billing/src/who2be_billing/invoice.py` – Lesemethoden je Org
2. `packages/billing/src/who2be_billing/router.py` – zwei Endpunkte
3. `packages/billing/tests/test_invoice_endpoint.py` – neu
4. `apps/web/src/api/client.ts` – Typen + zwei Methoden
5. `apps/web/src/features/billing/components/InvoiceList.tsx` – neu (Hook + Karte)
6. `apps/web/src/features/billing/components/InvoiceList.test.tsx` – neu
7. `apps/web/src/features/billing/i18n.ts` – DE/EN
8. `apps/web/src/features/billing/components/BillingPanel.tsx` – Karte einhängen

## Schritte

1. Backend Repo + Router, Endpunkt-Tests (Fakes) + Integrationstest Repo.
2. Web: Client, Karte, i18n, Einhängen, Vitest + axe.
3. DoD aus CONTRIBUTING.md, Mutationsliste, Fotos, PR.

## Stand

- [ ] 1 Backend
- [ ] 2 Web
- [ ] 3 DoD / Fotos / PR
