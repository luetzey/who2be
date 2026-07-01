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
})
