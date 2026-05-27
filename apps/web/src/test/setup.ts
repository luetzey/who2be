import '@testing-library/jest-dom/vitest'
import { expect } from 'vitest'
import * as axeMatchers from 'vitest-axe/matchers'

// vitest-axe@0.1.0 liefert ein leeres `extend-expect.js` — daher die Matcher
// (u.a. `toHaveNoViolations`) hier explizit registrieren.
expect.extend(axeMatchers)
