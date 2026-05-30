import '@testing-library/jest-dom/vitest'
import { expect } from 'vitest'
import * as axeMatchers from 'vitest-axe/matchers'

// vitest-axe@0.1.0 liefert ein leeres `extend-expect.js` — daher die Matcher
// (u.a. `toHaveNoViolations`) hier explizit registrieren.
expect.extend(axeMatchers)

// JSDOM kennt weder ResizeObserver noch DOMRect — Radix-Popper-basierte Primitives
// (Tooltip, Dropdown, Dialog) bauen darauf. Wir polyfillen die Minimal-API
// genau einmal, damit `@radix-ui/react-use-size` nicht beim Mount kippt.
if (typeof globalThis.ResizeObserver === 'undefined') {
  class ResizeObserverPolyfill {
    observe(): void {}
    unobserve(): void {}
    disconnect(): void {}
  }
  globalThis.ResizeObserver = ResizeObserverPolyfill as unknown as typeof ResizeObserver
}
