import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ACKNOWLEDGED_VALUE, CONSENT_STORAGE_KEY } from '../hooks/useCookieConsent'
import { BANNER_HEIGHT_VAR, CookieConsentBanner } from './CookieConsentBanner'

function renderBanner() {
  return render(
    <MemoryRouter>
      <CookieConsentBanner />
    </MemoryRouter>,
  )
}

const region = { name: /Cookie-Hinweis/i }
const ackButton = { name: /Verstanden/i }

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })
  afterEach(() => {
    window.localStorage.clear()
  })

  it('zeigt das Banner, solange es nicht bestaetigt wurde', () => {
    renderBanner()
    expect(screen.getByRole('region', region)).toBeInTheDocument()
  })

  it('blendet sich nach „Verstanden“ aus und persistiert die Kenntnisnahme', () => {
    renderBanner()
    fireEvent.click(screen.getByRole('button', ackButton))
    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe(ACKNOWLEDGED_VALUE)
    expect(screen.queryByRole('region', region)).not.toBeInTheDocument()
  })

  // Audit A5: die App laedt kein Tracking — der Banner darf weder einen
  // Betreiber-Platzhalter zeigen noch eine Wahl vortaeuschen, die nichts
  // bewirkt.
  it('zeigt keinen Platzhalter und bietet keine Scheinwahl an', () => {
    const { container } = renderBanner()
    const banner = screen.getByRole('region', region)
    expect(container.querySelector('[data-placeholder]')).toBeNull()
    expect(banner.textContent).not.toMatch(/PLATZHALTER/)
    expect(screen.getAllByRole('button')).toHaveLength(1)
  })

  it.each([ACKNOWLEDGED_VALUE, 'accepted', 'rejected'])(
    'bleibt versteckt, wenn bereits „%s“ gespeichert ist (auch Altwerte der Zwei-Knopf-Zeit)',
    (stored) => {
      window.localStorage.setItem(CONSENT_STORAGE_KEY, stored)
      renderBanner()
      expect(screen.queryByRole('region', region)).not.toBeInTheDocument()
    },
  )

  it('zeigt sich bei unbekanntem gespeichertem Wert', () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, 'irgendwas')
    renderBanner()
    expect(screen.getByRole('region', region)).toBeInTheDocument()
  })
})

// Responsive-Audit #567 (W3, Epic #431): jsdom hat kein Layout, geprueft wird
// deshalb der Klassen-Vertrag. Die Layout-Aussage ist am gerenderten Baum
// belegt (Plandatei .claude/plan/2026-09-23-0750_567-…): `size="sm"` misst
// gerendert 36px — §11 (Floor 32px) ist damit eingehalten, AK 3 dieses Issues
// (>= 40px unterhalb `md`) nicht.
describe('CookieConsentBanner — 320px (#567)', () => {
  it('haelt den Knopf unterhalb md auf 40px Hit-Target', () => {
    renderBanner()
    const classes = screen.getByRole('button', ackButton).className.split(/\s+/)
    // h-10 = 40px unterhalb md, ab md zurueck auf die kompakte sm-Hoehe.
    expect(classes).toContain('h-10')
    expect(classes).toContain('md:h-9')
  })

  it('laesst den Knopf unterhalb sm die volle Kartenbreite nehmen', () => {
    renderBanner()
    const button = screen.getByRole('button', ackButton)
    const classes = button.className.split(/\s+/)
    expect(classes).toContain('flex-1')
    expect(classes).toContain('sm:flex-none')

    // Die Reihe selbst darf unterhalb sm schrumpfen — mit unbedingtem
    // `shrink-0` war sie auf ihre max-content-Breite genagelt.
    const row = button.parentElement as HTMLElement
    const rowClasses = row.className.split(/\s+/)
    expect(rowClasses).not.toContain('shrink-0')
    expect(rowClasses).toContain('sm:shrink-0')
  })
})

// Befund B7 (Welle 7 / K2b): das Banner reserviert den Platz, den es belegt,
// statt ihn zu ueberlagern. Es meldet dazu seine gemessene Hoehe als
// `--cookie-banner-height` an `document.documentElement`; `globals.css`
// verbraucht den Wert in `body { padding-bottom }` und
// `html { scroll-padding-bottom }`.
//
// jsdom hat weder Layout noch `ResizeObserver` — gemessen wird die Wirkung
// deshalb im E2E-Spec `apps/web/e2e/consent-overlay.spec.ts` (bei
// ungetroffener Entscheidung, auf allen vier Playwright-Profilen). Hier
// geprueft wird das, was jsdom tragen kann und was beim Refactoring am
// leichtesten stillschweigend verlorengeht: dass die Variable ueberhaupt
// gesetzt wird, solange das Banner steht — und dass sie **verschwindet**,
// sobald es das nicht mehr tut. Bliebe sie stehen, haette jede Seite fuer
// immer einen toten Rand unten.
describe('CookieConsentBanner — Platzreservierung (B7)', () => {
  class StubResizeObserver {
    constructor(private readonly callback: () => void) {}
    observe() {
      this.callback()
    }
    disconnect() {}
    unobserve() {}
  }

  const MEASURED_HEIGHT = 190

  beforeEach(() => {
    // Eigenes Clear: das `beforeEach` weiter oben gehoert zum ersten
    // `describe`-Block und gilt hier nicht — ohne das leckt der
    // 'accepted'-Wert aus dem vorherigen Test herein.
    window.localStorage.clear()
    vi.stubGlobal('ResizeObserver', StubResizeObserver)
    // jsdom gibt fuer jedes Element eine Nullbox zurueck; die Hoehe wird hier
    // vorgegeben, damit die Rechnung im Effekt ueberhaupt eine Zahl sieht.
    vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockReturnValue({
      height: MEASURED_HEIGHT,
    } as unknown as DOMRect)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
    document.documentElement.style.removeProperty(BANNER_HEIGHT_VAR)
  })

  it('meldet die gemessene Hoehe samt Wrapper-Abstand, solange das Banner steht', () => {
    renderBanner()
    // `p-4` am Wrapper = 16px oben und unten; die Karte sitzt entsprechend
    // ueber der Viewport-Unterkante.
    expect(document.documentElement.style.getPropertyValue(BANNER_HEIGHT_VAR)).toBe(
      `${MEASURED_HEIGHT + 32}px`,
    )
  })

  it('nimmt die Reservierung nach der Entscheidung zurueck', () => {
    renderBanner()
    expect(document.documentElement.style.getPropertyValue(BANNER_HEIGHT_VAR)).not.toBe('')
    fireEvent.click(screen.getByRole('button', ackButton))
    expect(document.documentElement.style.getPropertyValue(BANNER_HEIGHT_VAR)).toBe('')
  })

  it('reserviert nichts, wenn bereits eine Entscheidung vorliegt', () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, 'accepted')
    renderBanner()
    expect(document.documentElement.style.getPropertyValue(BANNER_HEIGHT_VAR)).toBe('')
  })

  it('laesst die Consent-Semantik unberuehrt: kein Storage-Schreiben beim Messen', () => {
    renderBanner()
    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBeNull()
    expect(screen.getByRole('region', region)).toBeInTheDocument()
  })
})
