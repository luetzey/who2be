import { expect, test } from '@playwright/test'

/**
 * Befund B7 (Welle 7 / K2b), Anwendungsseite.
 *
 * Diese Datei ruft **bewusst kein** `decideCookieConsent` auf — anders als jede
 * andere Spec im Verzeichnis. Genau das ist ihr Zweck: sie prueft den Zustand,
 * den ein echter Erstbesucher sieht (keine Entscheidung im `localStorage`,
 * Banner steht), und stellt sicher, dass die primaere Formularaktion darunter
 * trotzdem erreichbar bleibt.
 *
 * Wer hier `decideCookieConsent` ergaenzt, macht den Test gruen und wertlos: er
 * pruefte dann den Helfer aus K2 statt des Fixes. Der Helfer ist fuer die
 * fachlichen Journeys richtig — hier waere er die Messung, die sich selbst
 * abschafft.
 *
 * **Warum `/reset-password` und nicht `/login`:** gemessen, nicht geraten. Auf
 * `mobile-320` misst die Login-Seite 662px Inhalt bei 568px Viewport — sie ist
 * scrollbar, der Button laesst sich unter dem Banner hervorscrollen, und der
 * Klick gelingt auch ohne Fix. `/reset-password` misst dort 568px bei 568px
 * Viewport: **kein** Scrollweg, der Button liegt fest unter dem Banner. Genau
 * dort reproduziert sich der CI-Befund woertlich (Lauf 35928126972):
 *
 *   <p class="text-sm text-muted-foreground">…</p> from
 *   <div class="pointer-events-none fixed inset-x-0 bottom-0 z-50 flex justify-center p-4">…</div>
 *   subtree intercepts pointer events
 *
 * `/signup` waere ebenfalls ungeeignet: der Submit-Button ist dort bis zum
 * geloesten Captcha `disabled` — ein Timeout waere nicht dem Banner zuzurechnen.
 */

const CONSENT_STORAGE_KEY = 'who2be:cookie-consent'
const ROUTE = '/reset-password'

test.beforeEach(async ({ page }) => {
  // Gegenprobe zum Default der uebrigen Specs: sicherstellen, dass wirklich
  // keine Entscheidung vorliegt — sonst waere der Test still gruen, ohne je
  // ein Banner gesehen zu haben.
  await page.addInitScript((key: string) => {
    window.localStorage.removeItem(key)
  }, CONSENT_STORAGE_KEY)
})

test('Submit-Button ist bei ungetroffener Consent-Entscheidung klickbar', async ({ page }) => {
  await page.goto(ROUTE)

  const banner = page.getByRole('region', { name: /cookie/i })
  await expect(banner).toBeVisible()

  const submit = page.locator('form button[type="submit"]').first()
  await expect(submit).toBeVisible()
  await expect(submit).toBeEnabled()

  // Der Kern: ein echter Klick, ohne `force`, ohne das Banner wegzuraeumen.
  // Playwright prueft dabei das Hit-Target — liegt das Banner darueber, laeuft
  // der Aufruf in den Timeout statt still danebenzuklicken. Kurzes Timeout:
  // wir warten nicht 30s auf ein Ergebnis, das nach 8s feststeht.
  await submit.click({ timeout: 8_000 })

  // Der Klick hat das Formular erreicht, nicht das Banner: die Entscheidung
  // steht weiterhin aus, das Banner ist unveraendert da.
  await expect(banner).toBeVisible()
  const stored = await page.evaluate(
    (key: string) => window.localStorage.getItem(key),
    CONSENT_STORAGE_KEY,
  )
  expect(stored).toBeNull()
})

test('Das Banner ueberdeckt die primaere Aktion nicht', async ({ page }) => {
  await page.goto(ROUTE)

  const banner = page.getByRole('region', { name: /cookie/i })
  await expect(banner).toBeVisible()

  const submit = page.locator('form button[type="submit"]').first()
  await submit.scrollIntoViewIfNeeded()

  // Gemessen, nicht behauptet: nach dem Scrollen liegt die Unterkante des
  // Buttons oberhalb der Oberkante des Banners. Vor dem Fix war diese Zahl
  // negativ — der Button lag im Banner.
  const [buttonBox, bannerBox] = await Promise.all([submit.boundingBox(), banner.boundingBox()])
  expect(buttonBox).not.toBeNull()
  expect(bannerBox).not.toBeNull()
  const gap = bannerBox!.y - (buttonBox!.y + buttonBox!.height)
  expect(
    gap,
    `Submit-Unterkante ${buttonBox!.y + buttonBox!.height}px, Banner-Oberkante ${bannerBox!.y}px`,
  ).toBeGreaterThanOrEqual(0)
})
