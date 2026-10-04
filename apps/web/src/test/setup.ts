import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach, beforeEach, expect } from 'vitest'
import * as axeMatchers from 'vitest-axe/matchers'

/**
 * Wartezeit von `findBy*`/`waitFor` zentral auf 3 s statt 1 s (Testing-Library-Default).
 *
 * Unter lokaler Fremdlast (parallele Worktrees, Load 10–15) brauchen
 * jsdom-Render und Mock-Antwort zusammen mehr als 1000 ms. Vier Einzelfaelle
 * (#814, #817, #818, ResourceDetailPage S11) rissen genau diese Grenze, die
 * Assertion selbst war nie falsch; die CI war nicht betroffen.
 *
 * Der Wert wirkt nur auf Warte-Schritte: ein gruener Test wird nicht
 * langsamer, ein roter wartet hoechstens 2 s laenger. 3 s passen in das
 * 5-s-Testtimeout des Projekts `unit`. Gezielt gesetzte `{ timeout: … }`
 * einzelner Tests haben Vorrang und bleiben. Gehalten von `setup.test.ts`.
 */
configure({ asyncUtilTimeout: 3000 })

// i18n-Singleton initialisieren und auf Deutsch fixieren. Der Sprachdetektor
// wuerde in JSDOM sonst `navigator.language` (en-US) ziehen und die UI auf
// Englisch schalten — die bestehenden Tests assertieren deutsche Strings.
import i18n from '@/i18n'

beforeEach(() => {
  if (i18n.language !== 'de') {
    void i18n.changeLanguage('de')
  }
})

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
  resetFocusBookkeeping()
})

/**
 * Fokus-Buchhaltung nach `cleanup()` zuruecksetzen — Pflicht ab jsdom 30.
 *
 * jsdom 30 hat die "focus fixup rule" umgestellt: wird das fokussierte Element
 * aus dem DOM entfernt (genau das tut `cleanup()`), zeigt `_lastFocusedElement`
 * nicht mehr auf `null`, sondern auf das *Document*
 * (`node_modules/jsdom/lib/jsdom/living/nodes/Node-impl.js`, `_removingSteps()`:
 * „Represent the viewport with the Document so that activeElement resolves to
 * the body (or document element) while hasFocus() remains true.") — in jsdom 29
 * setzte `_detach()` dort noch `null`.
 *
 * Folge: `document.activeElement` liest sich zwar weiter als `<body>`, intern
 * gilt aber „es ist etwas fokussiert". Der naechste `focus()`-Aufruf nimmt
 * deshalb den `previous`-Zweig in `HTMLOrSVGElement-impl.js#focus()` und feuert
 * ein `blur` — mit Target-Adjustment auf das `window`, weil das Document ein
 * `_defaultView` hat. Radix' Menu-Root schliesst auf genau dieses
 * `window`-`blur` (`@radix-ui/react-menu`, `handleBlur`), womit sich jedes
 * Dropdown ab dem ZWEITEN Test einer Datei sofort nach dem Oeffnen wieder
 * schloss. Das traf 13 Tests (Export-Menues, WorkspaceSwitcher, Dropdown-Cap).
 *
 * Der Reset fokussiert ein Wegwerf-Element und blurrt es explizit: `blur()`
 * setzt `_lastFocusedElement` auf `null` und stellt damit den Zustand
 * „nichts fokussiert" wieder her, den jsdom 29 implizit hinterliess.
 */
function resetFocusBookkeeping(): void {
  const probe = document.createElement('span')
  probe.tabIndex = -1
  document.body.appendChild(probe)
  probe.focus()
  probe.blur()
  probe.remove()
}

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
