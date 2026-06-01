import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, expect } from 'vitest'
import * as axeMatchers from 'vitest-axe/matchers'

// vitest-axe@0.1.0 liefert ein leeres `extend-expect.js` — daher die Matcher
// (u.a. `toHaveNoViolations`) hier explizit registrieren.
expect.extend(axeMatchers)

// Explizites Unmount nach jedem Test. Ohne das bleiben Radix-Portal-Knoten
// (Dialog/Tooltip/Dropdown) im document.body haengen — offene Handles, die
// den vitest-Worker-Prozess am sauberen Exit hindern (Hang statt Exit, der
// in CI als Timeout-Failure auflaeuft). `globals: true` allein registriert
// das Auto-Cleanup hier nicht zuverlaessig, daher manuell.
afterEach(() => {
  cleanup()
})

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
