// PlaybookPicker.test.tsx — fetch gemockt; Picker laedt Liste, filtert, Konfirm liefert Props.
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { PlaybookPicker } from './PlaybookPicker'
import type { PlaceholderProps } from '../PlaceholderBlock'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

const playbooks = [
  {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Reset-Mail Playbook',
    current_version: 1,
    type: 'workflow',
    tags: [],
    triggers: null,
    content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'pb2',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Onboarding Flow',
    current_version: 1,
    type: 'workflow',
    tags: [],
    triggers: null,
    content: { description: '', body: '', type: 'workflow', tags: [], triggers: null },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <SessionContext.Provider
      value={{ session, me, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
    >
      <AuthTokenProvider>
        <MemoryRouter initialEntries={['/w/ws-1']}>{children}</MemoryRouter>
      </AuthTokenProvider>
    </SessionContext.Provider>
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybookPicker', () => {
  it('laedt Playbooks und zeigt sie an', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(playbooks), { status: 200 })),
      ),
    )

    render(
      <Wrapper>
        <PlaybookPicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('Reset-Mail Playbook')).toBeInTheDocument()
    })
    expect(screen.getByText('Onboarding Flow')).toBeInTheDocument()
  })

  it('filtert nach Suchstring', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(playbooks), { status: 200 })),
      ),
    )

    render(
      <Wrapper>
        <PlaybookPicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('Reset-Mail Playbook')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('playbook-picker-search'), {
      target: { value: 'reset' },
    })

    await waitFor(() => {
      expect(screen.getByText('Reset-Mail Playbook')).toBeInTheDocument()
      expect(screen.queryByText('Onboarding Flow')).not.toBeInTheDocument()
    })
  })

  it('liefert beim Konfirm ein gueltiges PlaceholderProps-Objekt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(playbooks), { status: 200 })),
      ),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <PlaybookPicker open onConfirm={onConfirm} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('playbook-option-pb1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('playbook-option-pb1'))
    fireEvent.click(screen.getByTestId('playbook-picker-confirm'))

    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'playbook',
      target_id: 'pb1',
      label: 'Playbook: Reset-Mail Playbook',
    })
  })

  it('Props-Objekt matcht Backend-Schema exakt (kind, target_id, label)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(playbooks), { status: 200 })),
      ),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <PlaybookPicker open onConfirm={onConfirm} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('playbook-option-pb2')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('playbook-option-pb2'))
    fireEvent.click(screen.getByTestId('playbook-picker-confirm'))

    const props = onConfirm.mock.calls[0]?.[0]
    // Verifiziert die exakte Token-JSON-Form laut Backend-Vertrag.
    expect(props).toMatchObject({
      kind: 'playbook',
      target_id: 'pb2',
      label: expect.stringContaining('Onboarding Flow'),
    })
    // Keine zusaetzlichen Felder ausser den drei vorgesehenen.
    expect(Object.keys(props ?? {})).toEqual(['kind', 'target_id', 'label'])
  })
})
