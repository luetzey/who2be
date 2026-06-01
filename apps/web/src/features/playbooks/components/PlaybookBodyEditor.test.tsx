// PlaybookBodyEditor.test.tsx — BlockNote-Insel in jsdom mocken (Standard-Pattern,
// analog SystemPromptEditor.test.tsx). Prueft:
//   1. Editor rendert ohne Fehler.
//   2. Nur Playbook/Resource-Slash-Items (kein Persona-Feld/Datum/MCP-Tools).
//   3. Pill-Insert via Picker ruft insertInlineContent mit korrekten Props.

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from '@/components/editor/system-prompt/PlaceholderBlock'

const insertInlineContent = vi.fn()
const slashItemsRef: { current: ((q: string) => Promise<unknown[]>) | null } = {
  current: null,
}

vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({
    document: [],
    insertInlineContent,
  }),
  // SuggestionMenuController faengt getItems ab, damit der Test die
  // Slash-Items pruefen kann, ohne ProseMirror zu starten.
  SuggestionMenuController: ({
    getItems,
  }: {
    getItems: (q: string) => Promise<unknown[]>
  }) => {
    slashItemsRef.current = getItems
    return null
  },
  getDefaultReactSlashMenuItems: () => [
    { key: 'paragraph', title: 'Absatz', onItemClick: vi.fn() },
    { key: 'heading_1', title: 'Heading 1', onItemClick: vi.fn() },
    { key: 'bullet_list', title: 'Aufzaehlung', onItemClick: vi.fn() },
  ],
  createReactInlineContentSpec: (_config: unknown, _impl: unknown) => ({
    config: _config,
    implementation: _impl,
  }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="blocknote-view">{children}</div>
  ),
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

const resources = [
  {
    id: 'res-1',
    workspace_id: 'ws-1',
    owner_id: 'o-1',
    name: 'FAQ-Dokument',
    current_version: 1,
    content: { description: '', blocks: [] },
    created_at: 't',
    updated_at: 't',
  },
]

// Stabile api-Referenz (wie der echte memoisierte useApi) — ein pro Render
// neues Objekt wuerde die `[…, api]`-Effects in den Pickern in eine
// Endlosschleife treiben.
const apiMock = {
  listResources: () => Promise.resolve(resources),
  listPlaybooks: () => Promise.resolve([]),
  getResource: (id: string) =>
    Promise.resolve({
      ...resources[0],
      id,
      content: {
        description: '',
        blocks: [
          {
            id: 'blk-1',
            type: 'heading',
            props: { level: 1 },
            content: [{ type: 'text', text: 'Abschnitt A', styles: {} }],
          },
        ],
      },
    }),
}

vi.mock('@/api/useApi', () => ({
  useApi: () => apiMock,
}))

import { PlaybookBodyEditor } from './PlaybookBodyEditor'

describe('PlaybookBodyEditor', () => {
  it('rendert ohne Fehler', () => {
    render(<PlaybookBodyEditor />)
    expect(screen.getByTestId('playbook-body-editor')).toBeInTheDocument()
  })

  it('bietet im Slash-Menue nur Playbook + Resource (kein Persona-Feld/Datum/MCP)', async () => {
    render(<PlaybookBodyEditor />)
    expect(slashItemsRef.current).not.toBeNull()
    const items = (await slashItemsRef.current?.('')) as { title: string }[]
    const titles = items.map((i) => i.title)
    expect(titles).toContain('Playbook')
    expect(titles).toContain('Resource')
    expect(titles).not.toContain('Persona-Feld')
    expect(titles).not.toContain('Datum')
    expect(titles).not.toContain('MCP-Tools')
  })

  it('insertet eine Resource-Pill via Picker (ganze Resource)', async () => {
    insertInlineContent.mockClear()
    render(<PlaybookBodyEditor />)

    // Resource-Picker via Slash-Item oeffnen.
    const items = (await slashItemsRef.current?.('')) as {
      title: string
      onItemClick: () => void
    }[]
    const resourceItem = items.find((i) => i.title === 'Resource')
    resourceItem?.onItemClick()

    await waitFor(() => {
      expect(screen.getByTestId('resource-option-res-1')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('resource-option-res-1'))
    fireEvent.click(screen.getByTestId('resource-picker-confirm'))

    expect(insertInlineContent).toHaveBeenCalledTimes(1)
    const inserted = insertInlineContent.mock.calls[0][0] as [
      { type: string; props: PlaceholderProps },
      string,
    ]
    expect(inserted[0].type).toBe('placeholder')
    expect(inserted[0].props).toMatchObject({
      kind: 'resource',
      target_id: 'res-1',
      label: 'Resource: FAQ-Dokument',
    })
  })

  it('insertet eine Resource-Pill mit #block_id, wenn ein Heading gewaehlt ist', async () => {
    insertInlineContent.mockClear()
    render(<PlaybookBodyEditor />)

    const items = (await slashItemsRef.current?.('')) as {
      title: string
      onItemClick: () => void
    }[]
    items.find((i) => i.title === 'Resource')?.onItemClick()

    await waitFor(() => {
      expect(screen.getByTestId('resource-option-res-1')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('resource-option-res-1'))

    // Heading-Block-Auswahl erscheint nach dem Laden der Resource.
    await waitFor(() => {
      expect(screen.getByTestId('resource-block-option-blk-1')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('resource-block-option-blk-1'))
    fireEvent.click(screen.getByTestId('resource-picker-confirm'))

    const inserted = insertInlineContent.mock.calls[0][0] as [
      { props: PlaceholderProps },
      string,
    ]
    expect(inserted[0].props.target_id).toBe('res-1#blk-1')
    expect(inserted[0].props.label).toContain('Abschnitt A')
  })
})
