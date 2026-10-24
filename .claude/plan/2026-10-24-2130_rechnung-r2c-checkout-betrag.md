# Rechnung R2c: Checkout-Betrag je Steuerfall + 409 ohne Rechnungsdaten

Karte t_2ab2a101. Grundlage: ADR-0061 §3, §5, §6 (W61-2 A, W61-3 A), R2a/R2b (gemergt),
Owner-Entscheidung 2026-10-24 zu W-R2c-1 A und W-R2c-2 A (Kartenkommentar des PM).

## Completion-Condition

- `start_checkout` bucht `expected_total(plan, decide_tax(...))` ab, also dieselbe Rechnung
  wie der Worker (`InvoiceService._prepare`). Steuermodus und Preisbasis kommen aus
  `WHO2BE_INVOICE_TAX_MODE` / `WHO2BE_INVOICE_PRICE_BASIS` (Default `net`).
- Steuerfälle mit Betrag im Endpunkt-Test (9,99 netto bzw. brutto):
  DE B2C 11,89 · DE B2B 11,89 · EU B2B geprüft 9,99 · EU B2B ungeprüft (VIES weiter
  stumm) 11,89 · Drittland 9,99; dazu Preisbasis brutto 9,99.
- EU B2B ungeprüft (W-R2c-1 A): VIES einmal neu prüfen (Timeout 5 s, `ViesVatChecker`),
  Ergebnis in die Rechnungsdaten schreiben; ohne Antwort 19 %.
- Ohne Rechnungsdaten: 409, ohne Mollie-Aufruf. Rot-Probe: Prüfung entfernt ⇒ Test rot.
- Ohne `WHO2BE_INVOICE_TAX_MODE` (W-R2c-2 A): 503 „Rechnungsstellung nicht konfiguriert.“,
  ohne Mollie-Aufruf (fail closed).
- Subscription wird mit dem bezahlten Erstbetrag angelegt (`payment.amount_value`), damit
  Folgezahlungen zur Rechnung passen.
- BillingPanel zeigt bei 409 eine eigene Meldung (DE mit Umlauten, EN) und verlinkt auf die
  Rechnungsdaten-Karte (R1). Fotos 1280/390 hell/dunkel mit `measure.json`.

## Dateien (8 + Changelog + dieser Plan)

1. `packages/billing/src/who2be_billing/mollie.py`: `CheckoutPricing`, Fehlerklassen,
   Betrag in `start_checkout`, Subscription mit bezahltem Erstbetrag
2. `packages/billing/src/who2be_billing/router.py`: Pricing verdrahten, 409/503 abbilden
3. `packages/billing/tests/test_mollie_endpoint.py`: Steuerfälle, 409, 503, VIES, Subscription
4. `apps/web/src/features/billing/hooks/useCheckout.ts`: HTTP-Status des Fehlers mitliefern
5. `apps/web/src/features/billing/components/BillingPanel.tsx`: 409-Meldung + Link
6. `apps/web/src/features/billing/components/BillingPanel.test.tsx`
7. `apps/web/src/features/billing/i18n.ts`
8. `apps/web/e2e/billing.spec.ts`: 409-Journey (Checkout per `page.route` gestubbt)

`test_checkout_webhook_*chain.py` bleibt unverändert: der Service ohne `pricing` verhält sich
dort wie bisher (Plan-Preis), siehe unten. Die Karte nennt die Testdatei mit „bzw.“.

## Entscheidungen

- Muster: der Preis ist ein eigenes, optionales Kollaborator-Objekt (`CheckoutPricing`) am
  `MollieBillingService`, analog zu `invoices`. `pricing=None` heißt „Installation ohne
  Rechnungsstellung“ (wie `invoices=None`) und bucht den Plan-Preis; der Router setzt es
  immer. Kompaktere Alternative (Schalter direkt als Service-Parameter) verworfen, weil
  Profil-Repo und VIES-Prüfer mitkommen müssen und die Tests ohne Rechnungsstellung sonst
  alle angepasst werden müssten (Dateibudget).
- Reihenfolge in `CheckoutPricing.amount`: erst Steuermodus (503), dann Rechnungsdaten (409),
  dann Steuerfall. Der Betrag steht fest, bevor ein Mollie-Customer angelegt wird.
- Gespeichertes Profil = vollständig (Validierung `BillingProfileInput` beim Speichern), daher
  prüft 409 nur „keine Zeile“.
- 409 trägt kein `reason`: die Übersetzung liegt im Billing-Chunk (ADR-0029), nicht in
  `common:errors`. Das Panel erkennt den Status über `useCheckout`.

## Mutationsliste (eigene Rot-Proben)

1. Profilprüfung in `CheckoutPricing.amount` entfernt ⇒ 409-Test rot.
2. VIES-Nachprüfung entfernt ⇒ Test „ungeprüft, VIES gültig“ rot.
3. Rückfall „VIES stumm ⇒ 19 %“ auf 0 % ⇒ Test „ungeprüft, VIES stumm“ rot.
4. Steuermodus-Prüfung entfernt ⇒ 503-Test rot.
5. Subscription wieder mit `plan.price_eur` ⇒ Subscription-Test rot.
6. `start_checkout` wieder mit `plan.price_eur` ⇒ Steuerfall-Tests rot.
7. Panel: 409-Zweig entfernt ⇒ Vitest rot.

## Nicht in R2c

Compose/.env, Doku (R2d); Rechnungen im Web (R3).
