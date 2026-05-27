import { configureAxe } from 'vitest-axe'

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
