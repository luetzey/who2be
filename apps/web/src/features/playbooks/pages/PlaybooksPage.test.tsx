import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PlaybooksPage } from './PlaybooksPage'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

function playbook(id: string, name: string, tags: string[], triggers: string | null) {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name,
    current_version: 1,
    type: 'workflow',
    tags,
    triggers,
    content: { description: '', body: '', type: 'workflow', tags, triggers },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  }
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybooksPage', () => {
  it('listet Playbooks und filtert client-seitig nach Tag', async () => {
    const list = [
      playbook('pb1', 'Coaching', ['coach', 'session'], 'how do i'),
      playbook('pb2', 'Brainstorming', ['brain'], null),
    ]
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

    await waitFor(() => {
      expect(screen.getByText('Coaching')).toBeInTheDocument()
      expect(screen.getByText('Brainstorming')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Tag-Filter'), { target: { value: 'brain' } })

    expect(screen.queryByText('Coaching')).not.toBeInTheDocument()
    expect(screen.getByText('Brainstorming')).toBeInTheDocument()
  })
})
