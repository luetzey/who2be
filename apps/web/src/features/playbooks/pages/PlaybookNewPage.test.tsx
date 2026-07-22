import type { Session } from '@supabase/supabase-js'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'

import type { Me } from '@/api/types'
import { AuthTokenProvider } from '@/auth/AuthTokenProvider'
import { SessionContext } from '@/auth/session-context'
import { PlaybookNewPage } from './PlaybookNewPage'

// BlockNote-Insel in jsdom nicht mountfaehig — siehe PlaybookDetailPage.test.tsx.
// PlaybookEditorForm importiert PlaybookBodyEditor statisch → Schema-Build beim
// Modul-Load braucht createReactInlineContentSpec/BlockNoteSchema.create.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
  SuggestionMenuController: () => null,
  getDefaultReactSlashMenuItems: () => [],
  createReactInlineContentSpec: (_config: unknown, _impl: unknown) => ({
    config: _config,
    implementation: _impl,
  }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@blocknote/core', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@blocknote/core')>()
  return {
    ...actual,
    BlockNoteSchema: {
      create: vi.fn().mockReturnValue({
        blockSchema: {},
        inlineContentSchema: {
          placeholder: { type: 'placeholder', propSchema: {}, content: 'none' },
          text: { config: 'text' },
          link: { config: 'link' },
        },
        styleSchema: {},
      }),
    },
    defaultInlineContentSpecs: { text: {}, link: {} },
  }
})
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

const session = { access_token: 'jwt' } as unknown as Session
const me: Me = {
  user_id: 'u1',
  default_workspace_id: 'ws-1',
  organizations: [],
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('PlaybookNewPage', () => {
  it('legt ein Playbook an und leitet auf die Detailseite weiter', async () => {
    const created = {
      id: 'pb7',
      workspace_id: 'ws-1',
      owner_id: 'o1',
      name: 'Brainstorming',
      current_version: 1,
      type: 'workflow',
      tags: [],
      triggers: null,
      content: {
        description: 'd',
        body: '',
        type: 'workflow',
        tags: [],
        triggers: null,
      },
      created_at: '2026-05-24T12:00:00Z',
      updated_at: '2026-05-24T12:00:00Z',
    }
    // TagInput laedt Tag-Vorschlaege via GET .../playbooks/tags — der
    // gleiche fetch-Mock muss URL-bewusst antworten, sonst kracht TagInput
    // beim Filtern auf der nicht-Array-Response.
    const fetchMock = vi.fn((url: string) => {
      if (url.includes('/playbooks/tags')) {
        return Promise.resolve(new Response(JSON.stringify([]), { status: 200 }))
      }
      return Promise.resolve(new Response(JSON.stringify(created), { status: 201 }))
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <SessionContext.Provider
        value={{ session, me, sessionLoaded: true, signIn: vi.fn(), signOut: vi.fn(), refreshMe: vi.fn() }}
      >
        <AuthTokenProvider>
          <MemoryRouter initialEntries={['/w/ws-1/playbooks/new']}>
            <Routes>
              <Route path="/w/:workspaceId/playbooks/new" element={<PlaybookNewPage />} />
              <Route
                path="/w/:workspaceId/playbooks/:id"
                element={<div>Detail von {created.id}</div>}
              />
            </Routes>
          </MemoryRouter>
        </AuthTokenProvider>
      </SessionContext.Provider>,
    )

    fireEvent.change(screen.getByLabelText('Name'), { target: { value: 'Brainstorming' } })
    // Type ist jetzt ein Select-Dropdown mit Enum statt freiem Input.
    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'workflow' } })
    fireEvent.change(screen.getByLabelText('Beschreibung'), { target: { value: 'd' } })

    fireEvent.click(screen.getByRole('button', { name: 'Anlegen' }))

    await waitFor(() => {
      expect(screen.getByText('Detail von pb7')).toBeInTheDocument()
    })

    const calls = fetchMock.mock.calls as unknown as Array<[string, RequestInit?]>
    const postCall = calls.find((call) => call[1]?.method === 'POST')
    expect(postCall).toBeDefined()
    const [url, init] = postCall!
    expect(url).toContain('/v1/workspaces/ws-1/playbooks')
    expect(init?.method).toBe('POST')
    expect(JSON.parse(init!.body as string)).toEqual({
      name: 'Brainstorming',
      content: {
        description: 'd',
        // Track B: leeres BlockNote-Dokument → "[]".
        body: '[]',
        type: 'workflow',
        tags: [],
        triggers: null,
      },
      // Content-i18n (ADR-0027): Default-Sprachauswahl wird mitgeschickt.
      locales: ['de'],
    })
  })
})
