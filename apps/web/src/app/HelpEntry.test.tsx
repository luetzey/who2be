import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext, type SessionValue } from '@/auth/session-context'
import { PublicHelpPage } from '@/features/help/pages/HelpPages'
import { buildHelpIndex } from '@/help/helpIndex'
import { axe } from '@/test/a11y'

import { HelpEntry } from './routes'

/*
 * Oeffentliche Hilfe ohne Login (Owner W-B, UX-Audit K5): `/help` und
 * `/help/<slug>` ohne Sitzung, nur `audience: all`, kein API-Aufruf; mit
 * Sitzung unveraendert in den Workspace.
 */

let fetchMock: ReturnType<typeof vi.fn>

beforeEach(() => {
  fetchMock = vi.fn().mockResolvedValue(new Response('{"detail":"nope"}', { status: 401 }))
  vi.stubGlobal('fetch', fetchMock)
})

afterEach(() => {
  vi.unstubAllGlobals()
})

function Probe({ name }: { name: string }) {
  const location = useLocation()
  return <div data-testid={name}>{`${location.pathname}${location.search}${location.hash}`}</div>
}

const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [
    {
      id: 'org-1',
      name: 'Acme',
      slug: 'acme',
      kind: 'company',
      workspaces: [{ id: 'ws-1', name: 'Marketing', slug: 'marketing', role: 'admin' }],
    },
  ],
}

function session(overrides: Partial<SessionValue> = {}): SessionValue {
  return {
    session: null,
    sessionLoaded: true,
    me: null,
    signIn: vi.fn(),
    signOut: vi.fn(),
    refreshMe: vi.fn(),
    ...overrides,
  }
}

function renderEntry(path: string, value: SessionValue) {
  return render(
    <SessionContext.Provider value={value}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/help/*" element={<HelpEntry />} />
            <Route path="/login" element={<Probe name="login" />} />
            <Route path="/w/:workspaceId/help/*" element={<Probe name="workspace" />} />
          </Routes>
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

describe('HelpEntry ohne Sitzung', () => {
  it('Consent-Link „Was passiert hier?“: zeigt die Seite direkt, samt Anker, ohne API-Aufruf', async () => {
    // Exakt das Ziel des Consent-Links (OAuthConsentPage, CONNECT_HELP_PATH).
    const { container } = renderEntry('/help/connect-claude#schritte', session())
    expect(await screen.findByRole('heading', { level: 1, name: 'Mit Claude verbinden' })).toBeInTheDocument()
    expect(container.querySelector('h2#schritte')).not.toBeNull()
    expect(screen.queryByTestId('login')).toBeNull()
    // Kopf mit „Anmelden“: Ruecksprung auf genau diese Stelle.
    expect(screen.getByRole('link', { name: 'Anmelden' })).toHaveAttribute(
      'href',
      `/login?next=${encodeURIComponent('/help/connect-claude#schritte')}`,
    )
    // Interne Links bleiben oeffentlich (`/help/…`), nicht `/w/<id>/…`.
    for (const link of screen.getAllByRole('link')) {
      expect(link.getAttribute('href') ?? '').not.toMatch(/^\/w\//)
    }
    expect(fetchMock).not.toHaveBeenCalled()
    expect(await axe(container)).toHaveNoViolations()
  })

  it('Startseite: Nachschlagen ohne Tutorials, Neuigkeiten und Fortschritt', async () => {
    renderEntry('/help', session())
    expect(await screen.findByRole('heading', { level: 1, name: 'Hilfe' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 2, name: 'Nachschlagen' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 2, name: 'Tutorials' })).toBeNull()
    expect(screen.queryByRole('region', { name: 'Was ist neu' })).toBeNull()
    expect(screen.queryByRole('progressbar')).toBeNull()
    expect(screen.queryByRole('link', { name: 'Problem melden' })).toBeNull()
    expect(screen.getByRole('link', { name: 'Mit Claude verbinden' })).toHaveAttribute(
      'href',
      '/help/connect-claude',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it.each([
    ['/help/tutorials/getting-started#verbinden'],
    ['/help/neu'],
    ['/help/placeholders'],
  ])('%s braucht ein Konto: Login mit Anker in next', (path) => {
    renderEntry(path, session())
    expect(screen.getByTestId('login').textContent).toBe(`/login?next=${encodeURIComponent(path)}`)
  })

  it('wartet den Session-Bootstrap ab', () => {
    renderEntry('/help/connect-claude', session({ sessionLoaded: false }))
    expect(screen.getByText('Wird geladen…')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Anmelden' })).toBeNull()
  })
})

describe('HelpEntry mit Sitzung', () => {
  it('leitet wie bisher in den Default-Workspace, Anker inklusive', () => {
    renderEntry(
      '/help/connect-claude#schritte',
      session({ session: { access_token: 'tok' } as unknown as Session, me }),
    )
    expect(screen.getByTestId('workspace').textContent).toBe('/w/ws-1/help/connect-claude#schritte')
    expect(screen.queryByRole('link', { name: 'Anmelden' })).toBeNull()
  })
})

// Eigene Testdaten: eine Seite fuer alle, eine nur fuer admin.
const pageMd = (lang: string, title: string, audience: string, order: number, body: string) =>
  [
    '---',
    `title: ${title} ${lang}`,
    'description: Beschreibung.',
    'section: konto-und-team',
    `order: ${order}`,
    'updated: 2026-10-23',
    `audience: ${audience}`,
    '---',
    '',
    body,
    '',
    '## Abschnitt [#abschnitt]',
    '',
    'Mehr.',
  ].join('\n')

const index = buildHelpIndex({
  './konto-und-team/team.de.md': pageMd('de', 'Team', 'all', 1, 'Für alle lesbar.'),
  './konto-und-team/team.en.md': pageMd('en', 'Team', 'all', 1, 'Readable for everyone.'),
  './konto-und-team/admin-only.de.md': pageMd('de', 'Abrechnung', 'admin', 2, 'Geheimwort Zahlungsdaten.'),
  './konto-und-team/admin-only.en.md': pageMd('en', 'Billing', 'admin', 2, 'Secret word payment data.'),
})

function renderPublic(slug: string, value: SessionValue = session()) {
  return render(
    <SessionContext.Provider value={value}>
      <AuthTokenProvider>
        <MemoryRouter initialEntries={[`/help/${slug}`]}>
          <PublicHelpPage slug={slug} index={index} />
        </MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

describe('PublicHelpPage: nur audience all', () => {
  it('Testdaten sind gültig', () => {
    expect(index.errors).toEqual([])
  })

  it('zeigt eine Seite für alle mit Inhalt', () => {
    renderPublic('team')
    expect(screen.getByRole('heading', { level: 1, name: 'Team de' })).toBeInTheDocument()
    expect(screen.getByText('Für alle lesbar.')).toBeInTheDocument()
  })

  it('liefert eine Admin-Seite als „nicht gefunden“, auch wenn me admin sagt', () => {
    // Auch mit einem (veralteten) Admin-`me` im Kontext: oeffentlich heisst nur `all`.
    renderPublic('admin-only', session({ me }))
    expect(screen.getByText('Diese Hilfe-Seite gibt es nicht.')).toBeInTheDocument()
    expect(screen.queryByText(/Geheimwort/)).toBeNull()
    expect(screen.queryByRole('heading', { level: 1, name: 'Abrechnung de' })).toBeNull()
  })

  it('führt die Admin-Seite weder in der Übersicht noch in der Navigation', () => {
    renderPublic('team', session({ me }))
    expect(screen.getAllByRole('link', { name: 'Team de' }).length).toBeGreaterThan(0)
    expect(screen.queryByRole('link', { name: 'Abrechnung de' })).toBeNull()
  })

  it('findet die Admin-Seite in der Suche nicht', () => {
    renderPublic('', session({ me }))
    expect(screen.queryByRole('link', { name: 'Abrechnung de' })).toBeNull()
    fireEvent.change(screen.getByLabelText('Hilfe durchsuchen'), { target: { value: 'geheimwort' } })
    expect(screen.getByRole('status')).toHaveTextContent('Nichts gefunden.')
    fireEvent.change(screen.getByLabelText('Hilfe durchsuchen'), { target: { value: 'lesbar' } })
    expect(screen.getByRole('link', { name: 'Team de' })).toHaveAttribute('href', '/help/team')
  })
})
