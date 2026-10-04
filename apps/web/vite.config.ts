import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

// Eigenes Timeout fuer die axe-Tests (`*.a11y.test.tsx`), NICHT global.
// axe ueber eine ganze Seite in jsdom ist CPU-gebunden: ruhig 1–3 s, unter
// fremder Last (Load-Avg ~10, parallele pytest/podman-Laeufe anderer Worktrees)
// gemessen bis ~7 s — ueber dem 5-s-Default von Vitest. 15 s = ~2x Puffer.
// Alle anderen Tests behalten den Default (5000 ms), damit haengende Tests
// weiter schnell auffallen. Karte t_ef93f8e3, Befund aus Review von PR #814.
const A11Y_TEST_TIMEOUT_MS = 15_000
const A11Y_TEST_GLOB = 'src/**/*.a11y.test.tsx'

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
    // Zwei Projekte, die sich die Wurzel-Config teilen (`extends: true`) und
    // sich nur im Timeout unterscheiden. Coverage, Reporter und CLI-Filter
    // (`--testNamePattern a11y`) wirken weiter ueber beide Projekte.
    // `include` steht bewusst NUR in den Projekten: `extends: true` haengt
    // Arrays aneinander, ein Wurzel-`include` landete sonst auch im
    // a11y-Projekt und jeder Unit-Test liefe doppelt.
    projects: [
      {
        extends: true,
        test: {
          name: 'unit',
          // Nur Unit/Component-Tests unter src — die Playwright-E2E-Specs in
          // `e2e/` laufen im eigenen Runner und duerfen NICHT von Vitest
          // gesammelt werden (sie importieren @playwright/test). ADR-0041, Phase 4.
          include: ['src/**/*.{test,spec}.{ts,tsx}'],
          exclude: [...configDefaults.exclude, A11Y_TEST_GLOB],
        },
      },
      {
        extends: true,
        test: {
          name: 'a11y',
          include: [A11Y_TEST_GLOB],
          testTimeout: A11Y_TEST_TIMEOUT_MS,
        },
      },
    ],
    // Coverage-Ratchet (ADR-0041): v8-Provider, Thresholds als Floor in CI
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
      // Gemessen (deterministisch, gleiche Suite): ~81.6 / 80.9 / 76.8.
      // Floors knapp darunter; Anhebung nur in dedizierten Coverage-PRs.
      thresholds: {
        statements: 80,
        branches: 79,
        functions: 75,
        lines: 80,
      },
    },
  },
})
