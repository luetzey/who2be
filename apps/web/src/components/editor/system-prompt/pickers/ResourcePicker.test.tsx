// ResourcePicker.test.tsx — analog PlaybookPicker.test.tsx.
import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'

import { ResourcePicker } from './ResourcePicker'
import type { PlaceholderProps } from '../PlaceholderBlock'

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = { user_id: 'u1', default_workspace_id: 'ws-1', organizations: [] }

const resources = [
  {
    id: 'res1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'FAQ-Dokument',
    current_version: 1,
    content: { description: '', blocks: [] },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
  {
    id: 'res2',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Preisliste',
    current_version: 1,
    content: { description: '', blocks: [] },
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  },
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

describe('ResourcePicker', () => {
  it('laedt Resources und zeigt sie an', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(resources), { status: 200 })),
      ),
    )

    render(
      <Wrapper>
        <ResourcePicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('FAQ-Dokument')).toBeInTheDocument()
    })
    expect(screen.getByText('Preisliste')).toBeInTheDocument()
  })

  it('filtert nach Suchstring', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(resources), { status: 200 })),
      ),
    )

    render(
      <Wrapper>
        <ResourcePicker open onConfirm={vi.fn()} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByText('FAQ-Dokument')).toBeInTheDocument()
    })

    fireEvent.change(screen.getByTestId('resource-picker-search'), {
      target: { value: 'faq' },
    })

    await waitFor(() => {
      expect(screen.getByText('FAQ-Dokument')).toBeInTheDocument()
      expect(screen.queryByText('Preisliste')).not.toBeInTheDocument()
    })
  })

  it('liefert beim Konfirm ein gueltiges PlaceholderProps-Objekt', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve(new Response(JSON.stringify(resources), { status: 200 })),
      ),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <ResourcePicker open onConfirm={onConfirm} onCancel={vi.fn()} />
      </Wrapper>,
    )

    await waitFor(() => {
      expect(screen.getByTestId('resource-option-res1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('resource-option-res1'))
    fireEvent.click(screen.getByTestId('resource-picker-confirm'))

    const props = onConfirm.mock.calls[0]?.[0]
    expect(props).toMatchObject({
      kind: 'resource',
      target_id: 'res1',
      label: expect.stringContaining('FAQ-Dokument'),
    })
    // Exakte Token-JSON-Form (drei Felder, keine Extra-Felder).
    expect(Object.keys(props ?? {})).toEqual(['kind', 'target_id', 'label'])
  })

  it('Edit-Modus: vorbefuellt Resource + Section-Anker und Confirm-Label "Aktualisieren"', async () => {
    // URL-bewusster Mock: listResources → Array, getResource/res1 → mit Headings.
    const res1WithBlocks = {
      ...resources[0],
      content: {
        description: '',
        blocks: [
          {
            id: 'h1',
            type: 'heading',
            props: { level: 2 },
            content: [{ type: 'text', text: 'Einleitung', styles: {} }],
            children: [],
          },
        ],
      },
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          /\/resources\/res1$/.test(url)
            ? new Response(JSON.stringify(res1WithBlocks), { status: 200 })
            : new Response(JSON.stringify(resources), { status: 200 }),
        ),
      ),
    )

    const onConfirm = vi.fn<(props: PlaceholderProps) => void>()

    render(
      <Wrapper>
        <ResourcePicker
          open
          allowBlockAnchor
          initial={{ kind: 'resource', target_id: 'res1#h1', label: 'Resource: FAQ-Dokument › Einleitung' }}
          onConfirm={onConfirm}
          onCancel={vi.fn()}
        />
      </Wrapper>,
    )

    // Button-Label im Edit-Modus + vorbefuellter Section-Anker.
    await waitFor(() => {
      expect(screen.getByTestId('resource-picker-confirm')).toHaveTextContent('Aktualisieren')
      expect(screen.getByTestId('resource-block-option-h1')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByTestId('resource-picker-confirm'))

    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'resource',
      target_id: 'res1#h1',
      label: 'Resource: FAQ-Dokument › Einleitung',
    })
  })
})
