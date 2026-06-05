/// <reference types="vitest/config" />
import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// Build-Zeit-Edition-Flag (ADR-0029): steuert, ob die Billing-UI ins Bundle
// kommt. `__CLOUD_BUILD__` wird als Literal ersetzt → der On-Prem-Build (Default)
// tree-shaked `features/billing` komplett aus dem ausgelieferten JS.
const isCloudBuild = (process.env.VITE_WHO2BE_EDITION ?? 'onprem') === 'cloud'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  define: {
    __CLOUD_BUILD__: JSON.stringify(isCloudBuild),
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    // Nur Unit/Component-Tests unter src — die Playwright-E2E-Specs in `e2e/`
    // laufen im eigenen Runner und duerfen NICHT von Vitest gesammelt werden
    // (sie importieren @playwright/test). ADR-0032, Phase 4.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
    // Coverage-Ratchet (ADR-0032): v8-Provider, Thresholds als Floor in CI
    // (`npm run test:coverage`). Bewusst ohne `all: true` — gemessen wird die
    // von Tests beruehrte Surface; Schwellen liegen knapp unter der Baseline
    // und werden in dedizierten Coverage-PRs angehoben, nie gesenkt.
    coverage: {
      provider: 'v8',
      reporter: ['text-summary', 'json', 'html'],
      exclude: [
        'src/**/*.test.{ts,tsx}',
        'src/**/*.a11y.test.{ts,tsx}',
        'src/**/*.d.ts',
        'src/test/**',
        'src/main.tsx',
        'src/vite-env.d.ts',
        'src/i18n/**',
      ],
      thresholds: {
        statements: 80,
        branches: 78,
        functions: 70,
        lines: 80,
      },
    },
  },
})
