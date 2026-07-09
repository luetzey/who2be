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

afterEach(() => {
  vi.unstubAllGlobals()
  // Filter-Zustand lebt in der URL (useSearchParams) — zwischen Tests
  // zuruecksetzen, sonst leakt ?tag/?status in den naechsten Render.
  window.history.pushState({}, '', '/')
})

describe('PlaybooksPage', () => {
  it('filtert client-seitig nach Tag ueber das Tag-Select', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach', 'session'], 'how do i'),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
      expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Tag'), { target: { value: 'brain' } })

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert ueber den Status-Quick-Filter „Braucht Aufmerksamkeit"', async () => {
    renderWith([
      playbook('pb1', 'Coaching', ['coach'], null, 'active'),
      playbook('pb2', 'Brainstorming', ['brain'], null, 'review'),
    ])

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
    })

    // Chip traegt Zaehler 1 (nur die Review-Version braucht Aufmerksamkeit).
    fireEvent.click(screen.getByRole('button', { name: /Braucht Aufmerksamkeit/ }))

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })

  it('filtert per Freitext nach Name', async () => {
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
  })

  it('zeigt Trigger als einzelne Pills, kappt bei 3 sichtbaren + „+N"-Badge', async () => {
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

  it('zeigt Composite-Badge und verlinkte Sub-Playbooks (kompakte Meta-Zeile)', async () => {
    renderWith([
      playbook('pb1', 'Composite-Flow', [], null, 'active', {
        is_composite: true,
        compose_children: [
          { id: 'c1', name: 'Schritt Eins' },
          { id: 'c2', name: 'Schritt Zwei' },
        ],
      }),
      playbook('pb2', 'Atomar', [], null),
    ])

    await waitFor(() => {
      expect(screen.getByText('Composite-Flow')).toBeInTheDocument()
    })

    expect(screen.getByText('Composite')).toBeInTheDocument()
    expect(screen.getByText(/komponiert:/)).toBeInTheDocument()
    const childLink = screen.getByRole('link', { name: 'Schritt Eins' })
    expect(childLink).toHaveAttribute('href', expect.stringContaining('/playbooks/c1'))
    expect(screen.getByRole('link', { name: 'Schritt Zwei' })).toBeInTheDocument()
    // Atomare Zeile traegt weder Badge noch Sub-Playbook-Links.
    expect(screen.getAllByText('Composite')).toHaveLength(1)
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

  it('Group-by-Selector schaltet auf Typ-Gruppen um (unbekannter Typ-Key = Rohwert)', async () => {
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

    fireEvent.change(screen.getByLabelText('Gruppieren'), { target: { value: 'type' } })

    expect(screen.getByRole('heading', { name: /prompt\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /workflow\s?\(1\)/ })).toBeInTheDocument()
    // Beide Items bleiben sichtbar — Gruppierung filtert nicht.
    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })
})
