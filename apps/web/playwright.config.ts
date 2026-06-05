import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright-E2E (ADR-0032, Phase 4 — duenne Spitze).
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
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
