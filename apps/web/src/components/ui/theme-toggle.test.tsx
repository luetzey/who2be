import { fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '@/app/ThemeProvider'
import i18n, { DEFAULT_LOCALE } from '@/i18n'

import { ThemeToggle } from './theme-toggle'

function installMatchMedia(initial: boolean) {
  Object.defineProperty(window, 'matchMedia', {
    configurable: true,
    writable: true,
    value: vi.fn().mockImplementation(() => ({
      matches: initial,
      media: '(prefers-color-scheme: dark)',
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  })
}

describe('ThemeToggle', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
  })

  it('renders an accessible trigger button with screen-reader label', () => {
    installMatchMedia(false)
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    const trigger = screen.getByRole('button', { name: /theme umstellen/i })
    expect(trigger).toHaveAttribute('aria-haspopup', 'menu')
    expect(trigger).toHaveTextContent('Theme umstellen')
  })

  it('reflects the resolved theme in the trigger icon (dark)', () => {
    installMatchMedia(true)
    window.localStorage.setItem('who2be:theme', 'dark')
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    const trigger = screen.getByRole('button', { name: /theme umstellen/i })
    // lucide-react renders the icon name into the rendered SVG `class`-Attr
    // (`lucide-moon`, `lucide-sun`, `lucide-monitor`). Wir pruefen darueber
    // ohne auf data-theme zu warten (das ist in den ThemeProvider-Tests
    // abgedeckt).
    const svg = trigger.querySelector('svg')
    expect(svg?.getAttribute('class') ?? '').toMatch(/moon/i)
  })

  it('reflects the resolved theme in the trigger icon (light)', () => {
    installMatchMedia(false)
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    )

    const trigger = screen.getByRole('button', { name: /theme umstellen/i })
    const svg = trigger.querySelector('svg')
    expect(svg?.getAttribute('class') ?? '').toMatch(/sun/i)
  })

  // Audit A9: Trigger-Label und Menue-Eintraege folgen der UI-Sprache.
  describe('in der englischen Oberflaeche', () => {
    beforeEach(async () => {
      await i18n.changeLanguage('en')
    })
    afterEach(async () => {
      await i18n.changeLanguage(DEFAULT_LOCALE)
    })

    it('beschriftet Trigger und Optionen englisch', async () => {
      installMatchMedia(false)
      render(
        <ThemeProvider>
          <ThemeToggle />
        </ThemeProvider>,
      )

      const trigger = screen.getByRole('button', { name: 'Change theme' })
      expect(trigger).toHaveTextContent('Change theme')
      fireEvent.keyDown(trigger, { key: 'Enter' })

      const items = await screen.findAllByRole('menuitemradio')
      expect(items.map((item) => item.textContent)).toEqual(['Light', 'Dark', 'System'])
    })
  })
})
