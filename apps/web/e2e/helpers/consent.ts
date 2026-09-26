import type { Page } from '@playwright/test'

/**
 * Cookie-Consent vorab entscheiden — sonst liegt das Banner ueber den
 * primaeren Buttons und der Klick laeuft in den Timeout.
 *
 * Das Banner (`apps/web/src/features/legal/components/CookieConsentBanner.tsx`)
 * rendert, solange unter diesem Key keine Entscheidung im `localStorage`
 * steht, und es traegt `pointer-events-auto` — es faengt den Klick also
 * tatsaechlich ab, statt nur darueber zu liegen.
 *
 * Auf Desktop-Viewports fiel das lange nicht auf: die Ziele der bestehenden
 * Journeys lagen ausserhalb des Banners. Auf den Mobile-Profilen (Welle 7 /
 * K1) tut es das nicht mehr — dort liefen die drei Jobs des Laufs 35928126972
 * in `Test timeout of 30000ms exceeded`, weil der Submit-Button unter dem
 * Banner lag. Deshalb gilt der Helfer jetzt fuer **jeden** Test mit
 * `page`-Fixture, nicht nur fuer Billing.
 *
 * **Reihenfolge:** `addInitScript` wirkt ab der naechsten Navigation, nicht
 * rueckwirkend. Der Aufruf muss also vor dem ersten `page.goto` stehen —
 * neben `loginAs` (das nach demselben Muster arbeitet) ist er dabei in beiden
 * Reihenfolgen richtig, solange beide vor der ersten Navigation kommen:
 * mehrere Init-Skripte werden gesammelt und alle vor dem Seiten-Skript
 * ausgefuehrt. Nach einem `page.goto` aufgerufen, greift er erst bei der
 * uebernaechsten Seite — und das Banner steht genau einmal im Weg.
 *
 * `rejected` statt `accepted`: der Test braucht keine Analytics, und die
 * datensparsame Variante ist der ehrlichere Ausgangszustand.
 *
 * **Dies ersetzt keinen Fix.** Dass ein Banner auf einem 320-px-Geraet den
 * primaeren Button unerreichbar macht, ist ein Anwendungsdefekt; der wird
 * getrennt behandelt (Befund B7). Der Helfer haelt nur die Journeys frei von
 * einem globalen Overlay, von dem sie fachlich nichts wissen.
 *
 * Key als Literal, nicht importiert — dieselbe Konvention wie
 * `SESSION_STORAGE_KEY` in `helpers/auth.ts` (E2E laeuft ausserhalb des
 * Vite-Bundles). Quelle: `CONSENT_STORAGE_KEY` in
 * `apps/web/src/features/legal/hooks/useCookieConsent.ts`.
 */
const CONSENT_STORAGE_KEY = 'who2be:cookie-consent'

export async function decideCookieConsent(page: Page): Promise<void> {
  await page.addInitScript(
    (key: string) => {
      window.localStorage.setItem(key, 'rejected')
    },
    CONSENT_STORAGE_KEY,
  )
}
