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
