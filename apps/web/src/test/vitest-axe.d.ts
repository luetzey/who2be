import '@vitest/expect'

import type { AxeMatchers } from 'vitest-axe'

// Module-Augmentation fuer Vitest 3 — `vitest-axe/extend-expect` haengt seine
// Matchers an die alte `Vi.Assertion`-Globale, die es in Vitest 3 nicht mehr
// gibt. Daher hier explizit auf `@vitest/expect#Matchers` registrieren — das
// ist der dokumentierte Erweiterungs-Punkt fuer Custom-Matcher in Vitest 3.
declare module '@vitest/expect' {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  interface Matchers<T = any> extends AxeMatchers {
    _axePhantom?: T
  }
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  interface AsymmetricMatchersContaining extends AxeMatchers {}
}
