import { expect, test } from '@playwright/test'

import { apiRequest, createUser, loginAs, seedWorkspace } from './helpers/auth'
import { decideCookieConsent } from './helpers/consent'

/**
 * Billing-Journey (Issue #453): Login -> Billing-Ansicht -> aktueller Tarif
 * inkl. Kontingenten sichtbar -> Upgrade ausgeloest -> Weiterleitung zum
 * Bezahlanbieter angestossen (abgefangen, nie ein echter Aufruf gegen Mollie).
 * Separat: ein fehlschlagender Checkout-Aufruf zeigt eine sichtbare
 * Fehlermeldung.
 *
 * **Cloud-only, eigene Datei** (Vorentscheidungen #3/#4, Issue #453): Billing
 * existiert nur in der Cloud-Edition (ADR-0029) — `features/billing` wird im
 * On-Prem-Bundle tree-geshaked, und selbst im Cloud-Bundle rendert
 * `BillingPanel` `null`, sobald `GET .../billing/entitlement` `edition`
 * ungleich `'cloud'` liefert (Backend-`WHO2BE_EDITION`). `E2E_EDITION=cloud`
 * ist das Signal, das NUR der dedizierte CI-Job `e2e-billing-cloud`
 * (`.github/workflows/ci.yml`) setzt, wenn er den Cloud-Overlay
 * (`docker-compose.cloud.yml`) hochfaehrt — ohne dieses Signal (lokaler
 * On-Prem-Lauf, der normale `e2e`-Job) wird die GESAMTE Datei sauber mit
 * Begruendung uebersprungen, statt pro Testfall.
 *
 * Selektoren: `data-testid="billing-slot"` (Wrapper, OrgSettingsPage) und
 * `data-testid="error-alert"` (ErrorAlert) existieren bereits in
 * `apps/web/src/**` und werden hier nur GELESEN — BillingPanel selbst hat
 * keine feingranularen Testids fuer einzelne Felder (kein Produktivcode-
 * Fix im Scope dieser Journey). Tarif/Kontingente werden deshalb ueber die
 * unlokalisierten, deterministischen Werte des frischen `CLOUD_FREE_ENTITLEMENT`
 * (`apps/api/src/who2be_api/licensing/entitlement.py`) geprueft: Quota
 * "0 / 1000", Rate-Limit "30/min", Feature-Code "core" (roher Code, nicht
 * uebersetzt) und die Progressbar-Rolle. Der Upgrade-Button traegt in beiden
 * unterstuetzten Locales (`de`/`en`, `features/billing/i18n.ts`) einen
 * eigenen Text — statt die Browser-Locale zu erzwingen, deckt ein Regex mit
 * beiden Varianten das ab.
 *
 * Checkout-Antwort wird IMMER per `page.route` abgefangen (Vorentscheidung
 * #2) — kein Mollie-Key im CI noetig, der echte Anbieter wird nie erreicht.
 */

const isCloudRun = process.env.E2E_EDITION === 'cloud'

test.skip(
  () => !isCloudRun,
  'Billing existiert nur in der Cloud-Edition (ADR-0029) — E2E_EDITION=cloud ' +
    'ist nicht gesetzt (On-Prem- oder lokaler Default-Lauf). Scharf nur im ' +
    'dedizierten CI-Job e2e-billing-cloud gegen den Cloud-Overlay.',
)

/** Nie aufgeloest — die Weiterleitung wird per `page.route` abgefangen, bevor
 * der Browser sie wirklich verlaesst. */
const FAKE_CHECKOUT_URL = 'https://mollie-checkout.e2e.invalid/session/e2e-test'

const UPGRADE_BUTTON_NAME = /Jetzt upgraden|Upgrade now/

/**
 * Rechnungsdaten-Vorbedingung (ADR-0061 R1): der Upgrade-Knopf ist gesperrt,
 * bis die Org Rechnungsdaten gespeichert hat. Nur Platzhalter-Daten und ohne
 * USt-IdNr., damit kein VIES-Aufruf entsteht.
 */
const PLACEHOLDER_BILLING = {
  customer_type: 'business',
  given_name: null,
  family_name: null,
  company_name: 'E2E Beispiel GmbH',
  street: 'Musterstrasse 1',
  postal_code: '12345',
  city: 'Musterstadt',
  country: 'DE',
  vat_id: null,
} as const

test('Billing: aktueller Tarif sichtbar, Upgrade stoesst abgefangene Weiterleitung an', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)

  // Checkout-Aufruf UND das (fiktive) Redirect-Ziel abfangen: der echte
  // Bezahlanbieter wird zu keinem Zeitpunkt kontaktiert.
  await page.route('**/billing/checkout', (route) =>
    route.fulfill({
      status: 201,
      contentType: 'application/json',
      body: JSON.stringify({ checkout_url: FAKE_CHECKOUT_URL }),
    }),
  )
  await page.route(FAKE_CHECKOUT_URL, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<!doctype html><title>E2E Mollie-Stub</title>',
    }),
  )

  await page.goto(`/w/${workspaceId}/settings/org`)
  const billingSlot = page.getByTestId('billing-slot')
  await expect(billingSlot).toBeVisible()

  // AC 1: aktueller Tarif + Kontingente sichtbar. Frische Org -> Backend
  // liefert CLOUD_FREE_ENTITLEMENT (Free-Tier, 1000 MCP-Reads/Monat, 30/min,
  // Feature "core") — Zahlen und der rohe Feature-Code sind nicht lokalisiert.
  await expect(billingSlot.getByText('0 / 1000')).toBeVisible()
  await expect(billingSlot.getByText('30/min')).toBeVisible()
  await expect(billingSlot.getByText('core', { exact: true })).toBeVisible()
  // Die Quota-Leiste per Rolle + Semantik pruefen, NICHT per Sichtbarkeit:
  // bei einer frischen Org steht die Nutzung auf 0, der Balken hat damit
  // Breite 0 — und ein Element ohne Bounding-Box gilt Playwright als
  // unsichtbar. `toBeVisible()` waere hier also eine Assertion ueber die
  // Pixelbreite des Fuellstands, nicht ueber das, was gemeint ist: dass das
  // Kontingent ueberhaupt ausgewiesen wird. Genau das pruefen die Attribute.
  //
  // Der Slot zeigt seit Issue #536 ZWEI Balken (MCP-Kontingent und Speicher),
  // beide mit `role="progressbar"` — ein Locator allein auf die Rolle waere
  // mehrdeutig. Adressiert wird deshalb ueber die stabile Testid.
  const quotaBar = billingSlot.getByTestId('mcp-quota-bar')
  await expect(quotaBar).toBeAttached()
  await expect(quotaBar).toHaveAttribute('aria-valuemax', '1000')
  await expect(quotaBar).toHaveAttribute('aria-valuenow', '0')

  // Speicher-Quota (Issue #536): frische Free-Org -> 100 MiB Grenze, 0 belegt.
  const storageBar = billingSlot.getByTestId('storage-bar')
  await expect(storageBar).toBeAttached()
  await expect(storageBar).toHaveAttribute('aria-valuemax', String(104857600))
  await expect(storageBar).toHaveAttribute('aria-valuenow', '0')

  // R1: ohne Rechnungsdaten ist Upgrade gesperrt. Die Daten werden hier ueber
  // das echte Formular gegen den echten Endpunkt gespeichert, danach ist der
  // Knopf frei.
  const upgrade = billingSlot.getByRole('button', { name: UPGRADE_BUTTON_NAME })
  await expect(upgrade).toBeDisabled()
  const form = billingSlot.getByRole('form', { name: /Rechnungsdaten|Billing details/ })
  await form.getByLabel(/^(Firmenname|Company name)$/).fill(PLACEHOLDER_BILLING.company_name)
  await form.getByLabel(/^(Straße und Hausnummer|Street and number)$/).fill(PLACEHOLDER_BILLING.street)
  await form.getByLabel(/^(PLZ|Postal code)$/).fill(PLACEHOLDER_BILLING.postal_code)
  await form.getByLabel(/^(Ort|City)$/).fill(PLACEHOLDER_BILLING.city)
  await form.getByLabel(/^(Land|Country)$/).selectOption(PLACEHOLDER_BILLING.country)
  await form.getByRole('button', { name: /Rechnungsdaten speichern|Save billing details/ }).click()
  await expect(billingSlot.getByTestId('billing-details-summary')).toBeVisible()

  // AC 2: Upgrade ausloesen.
  await expect(upgrade).toBeEnabled()
  await upgrade.click()

  // Weiterleitung zum Bezahlanbieter ist angestossen (`window.location.href`
  // in `useCheckout`), aber abgefangen: die Navigation landet auf dem lokalen
  // Stub, nie beim echten Mollie.
  await page.waitForURL(FAKE_CHECKOUT_URL)
  expect(page.url()).toBe(FAKE_CHECKOUT_URL)
})

test('Billing: fehlgeschlagener Checkout-Aufruf zeigt eine sichtbare Fehlermeldung', async ({
  page,
  request,
}) => {
  const user = await createUser(request)
  await loginAs(page, user)
  await decideCookieConsent(page)
  const { workspaceId } = await seedWorkspace(request, user)
  // R1-Vorbedingung direkt per API (das Formular deckt der Test oben ab).
  await apiRequest(request, user.session.access_token, `/v1/workspaces/${workspaceId}/billing/profile`, {
    method: 'PUT',
    data: PLACEHOLDER_BILLING,
  })

  // AC 5: der Checkout-Aufruf schlaegt fehl (Backend 500) -> sichtbarer Fehler.
  await page.route('**/billing/checkout', (route) =>
    route.fulfill({
      status: 500,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'E2E-Stub: Checkout absichtlich fehlgeschlagen.' }),
    }),
  )

  await page.goto(`/w/${workspaceId}/settings/org`)
  const billingSlot = page.getByTestId('billing-slot')
  await billingSlot.getByRole('button', { name: UPGRADE_BUTTON_NAME }).click()

  await expect(page.getByTestId('error-alert')).toBeVisible()
})
