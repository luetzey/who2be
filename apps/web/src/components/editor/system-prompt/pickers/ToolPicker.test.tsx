// ToolPicker.test.tsx — fetch gemockt; Picker laedt aktive Tools, filtert,
// Konfirm liefert Props mit `target_id = alias` (nicht die UUID).
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { ToolPicker } from './ToolPicker'
import type { PlaceholderProps } from '../PlaceholderBlock'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

function tool(overrides: {
  id: string
  alias: string
  name: string
  displayName: string
  status: 'draft' | 'active'
}) {
  return {
    id: overrides.id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: overrides.name,
    alias: overrides.alias,
    current_version: 1,
    current_status: overrides.status,
    has_pending_draft: false,
    content: {
      display_name: overrides.displayName,
      mcp_server_name: `${overrides.displayName} MCP`,
      tool_names: ['add_task'],
      usage_notes: '',
      fallback_note: null,
      tags: [],
    },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  }
}

const tools = [
  tool({ id: 'tool-1', alias: 'todo', name: 'Todoist', displayName: 'Todoist', status: 'active' }),
  tool({
    id: 'tool-2',
    alias: 'calendar',
    name: 'Kalender',
    displayName: 'Google Kalender',
    status: 'active',
  }),
  // Draft-Tool: darf im Picker nicht auftauchen (nur aktive Bindungen sind
  // referenzierbar — sonst Miss bis zur Promotion, siehe useToolSearch).
  tool({
    id: 'tool-3',
    alias: 'draft-tool',
    name: 'Entwurf-Tool',
    displayName: 'Entwurf-Tool',
    status: 'draft',
  }),
]

function Wrapper({ children }: { children: React.ReactNode }) {
  return (
    <SessionContext.Provider
      value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
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

describe('ToolPicker', () => {
  it('laedt nur aktive Tools und zeigt sie an', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(tools), { status: 200 }))),
    )

    render(
      <Wrapper>
        <ToolPicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('Todoist')).toBeInTheDocument()
    })
    expect(screen.getByText('Kalender')).toBeInTheDocument()
    expect(screen.queryByText('Entwurf-Tool')).not.toBeInTheDocument()
  })

  it('filtert nach Suchstring (Name, Alias, Anzeigename)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(tools), { status: 200 }))),
    )

    render(
      <Wrapper>
        <ToolPicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('Todoist')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('tool-picker-search'), {
      target: { value: 'todo' },
    })

    await waitFor(() => {
      expect(screen.getByText('Todoist')).toBeInTheDocument()
      expect(screen.queryByText('Kalender')).not.toBeInTheDocument()
    })
  })

  it('liefert beim Konfirm den Alias als target_id (nicht die UUID)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(tools), { status: 200 }))),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <ToolPicker open onConfirm={onConfirm} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('tool-option-todo')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('tool-option-todo'))
    fireEvent.click(screen.getByTestId('tool-picker-confirm'))

    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'tool-ref',
      target_id: 'todo',
      label: 'Tool: Todoist',
    })
    // Keine zusaetzlichen Felder ausser den drei vorgesehenen.
    const props = onConfirm.mock.calls[0]?.[0]
    expect(Object.keys(props ?? {})).toEqual(['kind', 'target_id', 'label'])
  })

  it('Edit-Modus: vorbefuellt das referenzierte Tool ueber den Alias + Confirm-Label "Aktualisieren"', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(tools), { status: 200 }))),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <ToolPicker
          open
          initial={{ kind: 'tool-ref', target_id: 'calendar', label: 'Tool: Google Kalender' }}
          onConfirm={onConfirm}
          onCancel={vi.fn()}
        />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('tool-picker-confirm')).toHaveTextContent('Aktualisieren')
    })

    fireEvent.click(screen.getByTestId('tool-picker-confirm'))

    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'tool-ref',
      target_id: 'calendar',
      label: 'Tool: Google Kalender',
    })
  })
})
