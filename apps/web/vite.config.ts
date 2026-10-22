import path from 'node:path'

import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { configDefaults } from 'vitest/config'

import { A11Y_TEST_TIMEOUT_MS } from './src/test/a11y-timeout.ts'

// Eigenes Timeout fuer axe-Tests, NICHT global: alle Tests ohne axe behalten
// den 5-s-Default von Vitest, damit haengende Tests weiter schnell auffallen.
// Wert und Messung stehen in `src/test/a11y-timeout.ts` (eine Quelle).
// Zwei Wege fuehren zu demselben Wert:
//  - Projekt `a11y` (`*.a11y.test.tsx`) per `testTimeout` unten
//    (Karte t_ef93f8e3, Befund aus Review von PR #814);
//  - jede andere Testdatei, die den Helfer `@/test/a11y` importiert, per
//    `vi.setConfig` im Helfer selbst (#975: 43 axe-Tests in gewoehnlichen
//    `*.test.tsx` liefen mit 5 s und haben main rot gemacht).
// Gehalten von `src/test/a11y.test.ts`.
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
  // Source-Maps fuer das Fehler-Tracking (Stabilitaet A3): `hidden` erzeugt
  // die .map-Dateien, ohne im JS auf sie zu verweisen. Ausgeliefert werden sie
  // nie: das Dockerfile loescht sie und bricht ab, falls im Image noch eine
  // liegt. Der Upload zum Tracker folgt in einem eigenen Infra-Schritt.
  build: {
    sourcemap: 'hidden',
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
    // Schutz gegen Node >= 25 (oder einen falschen `node` im PATH): dort ist
    // Node-eigenes Web Storage aktiv, und Vitest 4 filtert jsdoms
    // `window.localStorage` weg (vitest#8757). Auf dem gepinnten Node 22 ohne
    // Wirkung. Gilt nur fuer die Test-Worker, nicht fuer Build oder Dev-Server.
    // Details: CONTRIBUTING.md, Definition of Done. Karte t_61bd62ed.
    execArgv: ['--no-experimental-webstorage'],
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
