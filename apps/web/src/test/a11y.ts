import { vi } from 'vitest'
import { configureAxe } from 'vitest-axe'

import { A11Y_TEST_TIMEOUT_MS } from './a11y-timeout'

/**
 * Test-Timeout fuer jede Datei, die axe ueber diesen Helfer laufen laesst (#975).
 *
 * Das Vitest-Projekt `a11y` hebt das Timeout nur fuer `*.a11y.test.tsx`. axe
 * laeuft aber auch in gewoehnlichen `*.test.tsx` (Projekt `unit`, 5-s-Default);
 * dort riss es unter Last die Grenze. Der Import dieses Helfers ist die Stelle,
 * die alle axe-Tests gemeinsam haben — deshalb wird das Timeout hier gesetzt
 * statt an jedem einzelnen `it()`.
 *
 * Wirkung: `vi.setConfig` gilt fuer die importierende Testdatei; Vitest setzt
 * die Config nach jeder Datei mit `vi.resetConfig()` zurueck. Dateien ohne axe
 * behalten also die 5 s, damit haengende Tests dort weiter schnell auffallen.
 * Innerhalb einer axe-Datei gilt das Timeout fuer alle ihre Tests — der Preis
 * der zentralen Stelle. Explizite Timeouts am `it()` haben weiter Vorrang.
 *
 * Gehalten von `a11y.test.ts` (Wert wirksam + jede axe-Datei nutzt den Helfer).
 */
vi.setConfig({ testTimeout: A11Y_TEST_TIMEOUT_MS })

/**
 * Vorkonfigurierte axe-Runner-Instanz fuer Vitest-A11y-Tests.
 *
 * `color-contrast` ist deaktiviert: axe braucht dafuer `HTMLCanvasElement.getContext`,
 * das JSDOM nicht implementiert. Contrast pruefen wir manuell beim Token-Wechsel
 * in Phase 6 (Smoke-Checkliste) — alle anderen WCAG-Rules laufen normal.
 */
export const axe = configureAxe({
  rules: {
    'color-contrast': { enabled: false },
  },
})
