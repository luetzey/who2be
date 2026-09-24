import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright-E2E (ADR-0041, Phase 4 — duenne Spitze).
 *
 * Laeuft gegen einen bereits laufenden Stack (Compose: Web auf :5173, API auf
 * :8000). Es gibt bewusst KEINEN `webServer`-Block — der Stack wird extern
 * gestartet (CI: `docker compose up --wait`; lokal: `docker compose up -d`),
 * damit E2E echte API+DB+Auth sieht, nicht einen Vite-Dev-Mock.
 *
 *   E2E_BASE_URL=http://localhost:5173 npx playwright test
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 30_000,
  expect: { timeout: 10_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  /**
   * Vier Profile (Welle 7 / K1). `chromium` ist das bestehende, scharfe
   * Desktop-Gate; die drei uebrigen sind seit K1 im Uebergang — sie laufen in
   * einem eigenen CI-Job und blockieren bewusst noch keinen PR (das
   * Scharfstellen ist K3).
   *
   * Warum ueberall `browserName: 'chromium'` statt der Preset-Vorgabe:
   * `devices['iPhone 13']` und `devices['iPad (gen 7)']` tragen beide
   * `defaultBrowserType: 'webkit'` (nachgemessen an der installierten
   * Playwright-Version). Der CI-Schritt installiert jedoch nur einen Browser
   * (`package.json` Skript `e2e:install`: `playwright install --with-deps
   * chromium`). Ohne diesen Override waere jedes Mobile-Projekt rot, weil die
   * WebKit-Binary fehlt — ein Befund ueber die Browser-Installation, nicht
   * ueber die Anwendung. Gemessen werden soll hier Responsive-Layout, nicht
   * die Rendering-Engine; die Viewport-/Touch-/DPR-Emulation kommt vollstaendig
   * aus dem Preset und bleibt erhalten.
   */
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
    {
      name: 'mobile-iphone-13',
      use: { ...devices['iPhone 13'], browserName: 'chromium' },
    },
    {
      name: 'tablet-ipad-gen-7',
      use: { ...devices['iPad (gen 7)'], browserName: 'chromium' },
    },
    {
      /**
       * Schmalster unterstuetzter Viewport. Eigener Viewport statt Preset —
       * begruendet, nicht behauptet: es gibt sehr wohl 320-px-Presets
       * (`Galaxy S9+`, `iPhone SE`, `Nokia Lumia 520` — ausgezaehlt ueber
       * `Object.keys(devices)`), aber jedes bringt zusaetzlich einen eigenen
       * User-Agent, DPR und eine feste Hoehe mit. Getestet werden soll hier
       * die Layout-Untergrenze selbst, nicht ein bestimmtes Altgeraet. Der
       * explizite Viewport nennt genau das, was gemeint ist, und bleibt
       * stabil, wenn Playwright seine Preset-Tabelle aendert.
       *
       * 320 px ist die im Repo verbindliche Untergrenze: die
       * Responsive-Tests der Welle 3 pruefen durchgehend gegen diese Breite
       * (z. B. `apps/web/src/components/ui/hit-target.responsive.test.tsx`).
       * Basis ist das iPhone-13-Preset (Touch + isMobile), nur die
       * Viewport-Groesse wird ersetzt; 568 px Hoehe entspricht dem
       * klassischen 4-Zoll-Format.
       */
      name: 'mobile-320',
      use: {
        ...devices['iPhone 13'],
        browserName: 'chromium',
        viewport: { width: 320, height: 568 },
      },
    },
  ],
})
