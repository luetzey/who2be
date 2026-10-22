import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

const { mockConfig } = vi.hoisted(() => ({
  mockConfig: { launchContact: '', launchMessage: { de: '', en: '' } },
}))

vi.mock('@/config', () => ({ config: mockConfig }))

import i18n from '@/i18n'

import { ComingSoonPage } from './ComingSoonPage'

afterEach(async () => {
  mockConfig.launchContact = ''
  mockConfig.launchMessage = { de: '', en: '' }
  await i18n.changeLanguage('de')
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/signup']}>
      <ComingSoonPage />
    </MemoryRouter>,
  )
}

describe('ComingSoonPage', () => {
  it('rendert eine main-Landmark mit genau einer H1', () => {
    renderPage()

    expect(screen.getByRole('main')).toBeInTheDocument()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    expect(
      screen.getByRole('heading', { name: 'Wir arbeiten noch an Who2Be — bald verfügbar.' }),
    ).toBeInTheDocument()
  })

  it('verlinkt zurueck zur Anmeldung', () => {
    renderPage()

    expect(screen.getByRole('link', { name: 'Zurück zur Anmeldung' })).toHaveAttribute(
      'href',
      '/login',
    )
  })

  it('zeigt ohne WHO2BE_LAUNCH_CONTACT keinen Kontakt-Block', () => {
    renderPage()

    expect(screen.queryByText(/Fragen\?/)).not.toBeInTheDocument()
  })

  it('zeigt mit gesetztem Kontakt einen mailto-Link', () => {
    mockConfig.launchContact = 'hello@who2be.dev'

    renderPage()

    expect(screen.getByText(/Fragen\?/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'hello@who2be.dev' })).toHaveAttribute(
      'href',
      'mailto:hello@who2be.dev',
    )
  })

  // Responsive-Audit (#569): der Kontakt ist eine konfigurierte, oft lange
  // Mail-Adresse — ein ungebrochenes Token. Die Seite folgt dem §10.2-Muster
  // und traegt den Umbruch damit wie alle Auth-Karten.
  it('laesst lange Kontaktadressen umbrechen (#569)', () => {
    renderPage()

    expect(document.querySelector('main')?.className).toContain('break-words')
  })

  // Karte t_27d7c6ad: Betreiber-Freitext pro Sprache.
  it('zeigt ohne Freitext den festen Text', () => {
    renderPage()

    expect(screen.getByText(/Die Registrierung ist im Moment noch nicht offen/)).toBeInTheDocument()
  })

  it('ersetzt den festen Text durch den Freitext der aktiven Sprache', async () => {
    mockConfig.launchMessage = { de: 'Wir testen gerade allein.', en: 'Private test phase.' }

    const { unmount } = renderPage()
    expect(screen.getByText('Wir testen gerade allein.')).toBeInTheDocument()
    expect(screen.queryByText(/Die Registrierung ist im Moment/)).not.toBeInTheDocument()
    unmount()

    await i18n.changeLanguage('en')
    renderPage()
    expect(screen.getByText('Private test phase.')).toBeInTheDocument()
  })

  it('faellt auf Englisch ohne EN-Text auf den deutschen Freitext zurueck', async () => {
    mockConfig.launchMessage = { de: 'Nur DE gesetzt.', en: '' }
    await i18n.changeLanguage('en')

    renderPage()

    expect(screen.getByText('Nur DE gesetzt.')).toBeInTheDocument()
  })

  it('rendert Freitext als reinen Text — kein HTML, keine Links', () => {
    const hostile = '<a href="javascript:alert(1)">klick</a><img src=x onerror=alert(1)> [x](https://evil)'
    mockConfig.launchMessage = { de: hostile, en: '' }

    renderPage()

    expect(screen.getByText(hostile)).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
    // Einziger Link bleibt "Zurück zur Anmeldung".
    expect(screen.getAllByRole('link')).toHaveLength(1)
  })
})
