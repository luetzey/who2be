import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { CONSENT_STORAGE_KEY } from '../hooks/useCookieConsent'
import { CookieConsentBanner } from './CookieConsentBanner'

function renderBanner() {
  return render(
    <MemoryRouter>
      <CookieConsentBanner />
    </MemoryRouter>,
  )
}

const region = { name: /Cookie-Einwilligung/i }

describe('CookieConsentBanner', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })
  afterEach(() => {
    window.localStorage.clear()
  })

  it('zeigt das Banner, solange keine Entscheidung vorliegt (Opt-in)', () => {
    renderBanner()
    expect(screen.getByRole('region', region)).toBeInTheDocument()
  })

  it('blendet sich nach „Alle akzeptieren" aus und persistiert die Zustimmung', () => {
    renderBanner()
    fireEvent.click(screen.getByRole('button', { name: /Alle akzeptieren/i }))
    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe('accepted')
    expect(screen.queryByRole('region', region)).not.toBeInTheDocument()
  })

  it('lehnt optionales Tracking via „Nur notwendige" ab', () => {
    renderBanner()
    fireEvent.click(screen.getByRole('button', { name: /Nur notwendige/i }))
    expect(window.localStorage.getItem(CONSENT_STORAGE_KEY)).toBe('rejected')
    expect(screen.queryByRole('region', region)).not.toBeInTheDocument()
  })

  it('bleibt versteckt, wenn bereits eine Entscheidung gespeichert ist', () => {
    window.localStorage.setItem(CONSENT_STORAGE_KEY, 'rejected')
    renderBanner()
    expect(screen.queryByRole('region', region)).not.toBeInTheDocument()
  })
})

// Responsive-Audit #567 (W3, Epic #431): jsdom hat kein Layout, geprueft wird
// deshalb der Klassen-Vertrag. Die Layout-Aussage ist am gerenderten Baum
// belegt (Plandatei .claude/plan/2026-09-23-0750_567-…): bei 320px Viewport
// messen die beiden `size="sm"`-Buttons 36x124px — §11 (Floor 32px) ist damit
// eingehalten, AK 3 dieses Issues (>= 40px unterhalb `md`) nicht. Die
// Button-Reihe misst dabei 256px bei 254px Innenraum.
describe('CookieConsentBanner — 320px (#567)', () => {
  function buttons() {
    return [
      screen.getByRole('button', { name: /Nur notwendige/i }),
      screen.getByRole('button', { name: /Alle akzeptieren/i }),
    ]
  }

  it('haelt beide Buttons unterhalb md auf 40px Hit-Target', () => {
    renderBanner()
    for (const button of buttons()) {
      const classes = button.className.split(/\s+/)
      // h-10 = 40px unterhalb md, ab md zurueck auf die kompakte sm-Hoehe.
      expect(classes).toContain('h-10')
      expect(classes).toContain('md:h-9')
    }
  })

  it('laesst die Buttons unterhalb sm die volle Kartenbreite teilen', () => {
    renderBanner()
    const [reject, accept] = buttons()
    for (const button of [reject, accept]) {
      const classes = button.className.split(/\s+/)
      expect(classes).toContain('flex-1')
      expect(classes).toContain('sm:flex-none')
    }

    // Die Reihe selbst darf unterhalb sm schrumpfen — mit unbedingtem
    // `shrink-0` war sie auf ihre max-content-Breite genagelt (gemessen 256px
    // bei 254px Innenraum).
    const row = reject.parentElement as HTMLElement
    const rowClasses = row.className.split(/\s+/)
    expect(rowClasses).not.toContain('shrink-0')
    expect(rowClasses).toContain('sm:shrink-0')
  })
})
