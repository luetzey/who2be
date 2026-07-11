import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me, VersionStatus } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PlaybooksPage } from './PlaybooksPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function playbook(
  id: string,
  name: string,
  tags: string[],
  triggers: string | null,
  status: VersionStatus = 'active',
  overrides: Record<string, unknown> = {},
) {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name,
    current_version: 1,
    current_status: status,
    type: 'workflow',
    tags,
    triggers,
    content: { description: '', body: '', type: 'workflow', tags, triggers },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
    ...overrides,
  }
}

function renderWith(list: unknown[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify(list), { status: 200 })),
  )
  render(
    <SessionContext.Provider value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}>
      <AuthTokenProvider>
        <BrowserRouter>
          <PlaybooksPage />
        </BrowserRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>,
  )
}

// Erweiterte Facetten (Tag/Typ/Agent/Gruppieren) leben hinter dem
// „Filter"-Button in einem Popover — fuer Tests erst oeffnen.
function openFacetPopover() {
  fireEvent.click(screen.getByRole('button', { name: /^Filter/ }))
}

afterEach(() => {
  vi.unstubAllGlobals()
  // Filter-Zustand lebt in der URL (useSearchParams) — zwischen Tests
  // zuruecksetzen, sonst leakt ?tag/?status in den naechsten Render.
  window.history.pushState({}, '', '/')
})

describe('PlaybooksPage', () => {
  it('filtert client-seitig nach Tag ueber das Tag-Select im Filter-Popover', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach', 'session'], 'how do i'),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
      expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    })

    openFacetPopover()
    fireEvent.change(screen.getByLabelText('Tag'), { target: { value: 'brain' } })

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert ueber das Status-Segment „Braucht Aufmerksamkeit"', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null, 'active'),
      playbook('pb2', 'Brainstorming', ['brain'], null, 'review'),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Segment traegt Zaehler 1 (nur die Review-Version braucht Aufmerksamkeit).
    fireEvent.click(screen.getByRole('button', { name: /Braucht Aufmerksamkeit/ }))

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert per Freitext nach Name und laesst sich per X leeren', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'coach' } })

    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.queryByText('Brainstorming')).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Suche leeren' }))
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert per Freitext auch ueber Trigger', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], 'eskalation starten'),
      playbook('pb2', 'Brainstorming', [], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'eskal' } })

    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.queryByText('Brainstorming')).not.toBeInTheDocument()
  })

  it('zeigt Trigger als einzelne Pills, kappt bei 3 sichtbaren + „+N"', async () => {
    renderWith([playbook('pb1', 'Coaching', [], 'alpha, beta; gamma, delta, epsilon')])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Split an ',' UND ';' (WP-D1) — die ersten drei als Pills sichtbar.
    expect(screen.getByText('alpha')).toBeInTheDocument()
    expect(screen.getByText('beta')).toBeInTheDocument()
    expect(screen.getByText('gamma')).toBeInTheDocument()
    expect(screen.queryByText('delta')).not.toBeInTheDocument()
    expect(screen.queryByText('epsilon')).not.toBeInTheDocument()
    expect(screen.getByLabelText('2 weitere Trigger')).toHaveTextContent('+2')
  })

  it('zeigt sanften Status samt Version und „Entwurf offen"-Marker', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], null, 'active', {
        current_version: 3,
        has_pending_draft: true,
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    expect(screen.getByText(/Aktiv · v3/)).toBeInTheDocument()
    expect(screen.getByText('Entwurf offen')).toBeInTheDocument()
  })

  it('zeigt den Composite-Footer und klappt Sub-Playbooks als Links auf', async () => {
    renderWith([
      playbook('pb1', 'Composite-Flow', [], null, 'active', {
        is_composite: true,
        compose_children: [
          { id: 'c1', name: 'Schritt Eins' },
          { id: 'c2', name: 'Schritt Zwei' },
        ],
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Composite-Flow')).toBeInTheDocument()
    })

    // Zugeklappt: Zusammenfassung mit Zaehler + Kind-Namen, keine Links.
    const toggle = screen.getByRole('button', { name: /2 Sub-Playbooks/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('link', { name: /Schritt Zwei/ })).not.toBeInTheDocument()

    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    const childLink = screen.getByRole('link', { name: /Schritt Zwei/ })
    expect(childLink).toHaveAttribute('href', expect.stringContaining('/playbooks/c2'))
    expect(screen.getByRole('link', { name: /Schritt Eins/ })).toBeInTheDocument()
  })

  it('zeigt den „Teil von"-Marker auf Kind-Zeilen (Rueckrichtung aus compose_children)', async () => {
    renderWith([
      playbook('pb1', 'Eskalation Level 2', [], null, 'active', {
        is_composite: true,
        compose_children: [{ id: 'pb2', name: 'Kunde begruessen' }],
      }),
      playbook('pb2', 'Kunde begruessen', [], null),
    ])

    // Der Kind-Name erscheint doppelt (eigene Zeile + Footer-Vorschau des
    // Composites) — direkt auf den Marker-Link warten.
    const marker = await screen.findByRole('link', {
      name: /Teil von Eskalation Level 2/,
    })
    expect(marker).toHaveAttribute('href', expect.stringContaining('/playbooks/pb1'))
  })

  it('gruppiert via ?group=composite mit Sektions-Headern und Zaehlern', async () => {
    window.history.pushState({}, '', '/?group=composite')
    renderWith([
      playbook('pb1', 'Composite-Flow', [], null, 'active', { is_composite: true }),
      playbook('pb2', 'Atomar A', [], null),
      playbook('pb3', 'Atomar B', [], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Composite-Flow')).toBeInTheDocument()
    })

    expect(screen.getByRole('heading', { name: /Composite\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Standalone\s?\(2\)/ })).toBeInTheDocument()
  })

  it('Group-by-Selector im Popover schaltet auf Typ-Gruppen um', async () => {
    renderWith([
      playbook('pb1', 'Coaching', [], null),
      playbook('pb2', 'Brainstorming', [], null, 'active', {
        type: 'prompt',
        content: { description: '', body: '', type: 'prompt', tags: [], triggers: null },
      }),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })
    expect(screen.queryByRole('heading', { name: /workflow/ })).not.toBeInTheDocument()

    openFacetPopover()
    fireEvent.change(screen.getByLabelText('Gruppieren'), { target: { value: 'type' } })

    expect(screen.getByRole('heading', { name: /prompt\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /workflow\s?\(1\)/ })).toBeInTheDocument()
    // Beide Items bleiben sichtbar — Gruppierung filtert nicht.
    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('zeigt Header-Count-Pill und Onboarding-Hero bei leerem Workspace', async () => {
    renderWith([])

    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Lege dein erstes Playbook an' }),
      ).toBeInTheDocument()
    })
    // Kein Count-Pill, keine Toolbar im Onboarding-Zustand — dafuer spiegelt
    // der Hero den Header-CTA (zwei „Neues Playbook"-Links).
    expect(screen.queryByLabelText('Suche')).not.toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: /Neues Playbook/ })).toHaveLength(2)
  })

  it('zeigt den gefilterten Leerzustand mit Suchbegriff und Reset', async () => {
    renderWith([playbook('pb1', 'Coaching', [], null)])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })
    expect(screen.getByLabelText('1 Playbook')).toHaveTextContent('1')

    fireEvent.change(screen.getByLabelText('Suche'), { target: { value: 'nix' } })

    expect(
      screen.getByRole('heading', { name: /Keine Treffer für „nix“/ }),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Filter zurücksetzen/ }))
    expect(screen.getByText('Coaching')).toBeInTheDocument()
  })
})
