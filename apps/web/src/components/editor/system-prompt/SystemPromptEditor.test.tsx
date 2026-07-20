// SystemPromptEditor.test.tsx — BlockNote-Insel in jsdom mocken (Standard-Pattern).
// Prueft:
//   1. SystemPromptEditor rendert ohne Fehler.
//   2. buildSlashMenuItems enthaelt die Custom-Items und filtert korrekt.
//   3. buildSystemPromptSchema gibt ein Schema-Objekt zurueck.
//   4. Tool-Ref-Pill-Insertion via ToolPicker (Slash-Menue → Picker → Confirm).

import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from './PlaceholderBlock'

// Geteilte Spione: `insertInlineContent` wird vom `useCreateBlockNote`-Mock
// zurueckgegeben, `slashItemsRef` faengt `getItems` aus dem
// `SuggestionMenuController`-Mock ab — analog PlaybookBodyEditor.test.tsx.
const insertInlineContent = vi.fn()
const slashItemsRef: { current: ((q: string) => Promise<unknown[]>) | null } = {
  current: null,
}

// BlockNote in jsdom nicht mountfaehig — Standard-Mock (analog PlaybookDetailPage.test.tsx).
// createReactInlineContentSpec wird benoetigt weil PlaceholderBlock.tsx es
// auf Modulebene aufruft (nicht lazy). Wir mocken es als Identity-Funktion.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({
    document: [],
    insertInlineContent,
  }),
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
    { key: 'heading_2', title: 'Heading 2', onItemClick: vi.fn() },
    { key: 'heading_3', title: 'Heading 3', onItemClick: vi.fn() },
    { key: 'bullet_list', title: 'Aufzaehlung', onItemClick: vi.fn() },
    { key: 'numbered_list', title: 'Nummeriert', onItemClick: vi.fn() },
    { key: 'table', title: 'Tabelle', onItemClick: vi.fn() },
  ],
  // Mockt die Spec-Erstellung — gibt ein einfaches Objekt zurueck, das den
  // Typ-Check besteht; BlockNote baut in jsdom keine ProseMirror-Node.
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

const tools = [
  {
    id: 'tool-1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Todoist',
    alias: 'todo',
    current_version: 1,
    current_status: 'active',
    has_pending_draft: false,
    content: {
      display_name: 'Todoist',
      mcp_server_name: 'Todoist MCP',
      tool_names: ['add_task'],
      usage_notes: '',
      fallback_note: null,
      tags: [],
    },
    created_at: 't',
    updated_at: 't',
  },
]

// Stabile api-Referenz (wie der echte memoisierte useApi) — ein pro Render
// neues Objekt wuerde die `[…, api]`-Effects in den Pickern in eine
// Endlosschleife treiben (Kommentar-Pattern aus PlaybookBodyEditor.test.tsx).
const apiMock = {
  listExternalTools: () => Promise.resolve(tools),
  listPlaybooks: () => Promise.resolve([]),
  listResources: () => Promise.resolve([]),
}
vi.mock('@/api/useApi', () => ({ useApi: () => apiMock }))

import { SystemPromptEditor } from './SystemPromptEditor'
import { buildSlashMenuItems } from './slashMenu'
import { buildSystemPromptSchema } from './PlaceholderBlock'

describe('SystemPromptEditor', () => {
  it('rendert ohne Fehler', () => {
    render(<SystemPromptEditor />)
    expect(screen.getByTestId('system-prompt-editor')).toBeInTheDocument()
  })

  it('propagiert onChange nach Focus-Interact (kein Fehler)', () => {
    const onChange = vi.fn()
    const { container } = render(<SystemPromptEditor onChange={onChange} />)
    const editorDiv = container.querySelector('[data-testid="system-prompt-editor"]')
    editorDiv?.dispatchEvent(new FocusEvent('focusin', { bubbles: true }))
    // onChange wird von BlockNoteView-Mock nicht gefeuert — wir pruefen nur,
    // dass der Render fehlerfrei bleibt.
    expect(screen.getByTestId('system-prompt-editor')).toBeInTheDocument()
  })

  it('insertet eine Tool-Ref-Pill via ToolPicker (Slash-Menue → Picker → Confirm)', async () => {
    insertInlineContent.mockClear()
    render(<SystemPromptEditor />)
    expect(slashItemsRef.current).not.toBeNull()

    const items = (await slashItemsRef.current?.('')) as {
      title: string
      onItemClick: () => void
    }[]
    const toolItem = items.find((i) => i.title === 'Externes Tool')
    expect(toolItem).toBeDefined()
    toolItem?.onItemClick()

    await waitFor(() => {
      expect(screen.getByTestId('tool-option-todo')).toBeInTheDocument()
    })
    fireEvent.click(screen.getByTestId('tool-option-todo'))
    fireEvent.click(screen.getByTestId('tool-picker-confirm'))

    expect(insertInlineContent).toHaveBeenCalledTimes(1)
    const inserted = insertInlineContent.mock.calls[0][0] as [
      { type: string; props: PlaceholderProps },
      string,
    ]
    expect(inserted[0].type).toBe('placeholder')
    expect(inserted[0].props).toMatchObject({
      kind: 'tool-ref',
      target_id: 'todo',
      label: 'Tool: Todoist',
    })
  })

  it('insertet eine Gedaechtnis-Pill direkt (parameterlos, kein Picker)', async () => {
    insertInlineContent.mockClear()
    render(<SystemPromptEditor />)
    expect(slashItemsRef.current).not.toBeNull()

    const items = (await slashItemsRef.current?.('')) as {
      title: string
      onItemClick: () => void
    }[]
    const memoryItem = items.find((i) => i.title === 'Gedächtnis')
    expect(memoryItem).toBeDefined()
    memoryItem?.onItemClick()

    expect(insertInlineContent).toHaveBeenCalledTimes(1)
    const inserted = insertInlineContent.mock.calls[0][0] as [
      { type: string; props: PlaceholderProps },
      string,
    ]
    expect(inserted[0].type).toBe('placeholder')
    expect(inserted[0].props).toMatchObject({
      kind: 'memory',
      target_id: '',
      label: 'Gedächtnis-Hinweis',
    })
  })
})

// Editor-Stub fuer buildSlashMenuItems: Der Parameter ist dort bewusst als
// `unknown` getypt (s. slashMenu.ts) und wird nur an das gemockte
// getDefaultReactSlashMenuItems durchgereicht — ein leeres Objekt genuegt,
// kein `as any` noetig (CODE-3).
const editorStub: unknown = {}

describe('buildSlashMenuItems', () => {
  it('enthaelt alle Custom-Placeholder-Items', () => {
    const items = buildSlashMenuItems(editorStub, vi.fn(), '')
    const titles = items.map((i) => i.title)
    expect(titles).toContain('Playbook')
    expect(titles).toContain('Resource')
    expect(titles).toContain('Persona-Feld')
    expect(titles).toContain('Persona laden (MCP)')
    expect(titles).toContain('Playbook-Katalog')
    expect(titles).toContain('Datum')
    expect(titles).toContain('Externes Tool')
    expect(titles).toContain('Gedächtnis')
  })

  it('filtert Table und Numbered-List aus Default-Items heraus', () => {
    const items = buildSlashMenuItems(editorStub, vi.fn(), '')
    const titles = items.map((i) => i.title)
    expect(titles).not.toContain('Tabelle')
    expect(titles).not.toContain('Nummeriert')
  })

  it('filtert nach Query (case-insensitive)', () => {
    const items = buildSlashMenuItems(editorStub, vi.fn(), 'play')
    expect(items.some((i) => i.title === 'Playbook')).toBe(true)
    expect(items.some((i) => i.title === 'Resource')).toBe(false)
  })

  it('Custom-Items rufen openPicker mit dem richtigen Kind auf', () => {
    const openPicker = vi.fn()
    const items = buildSlashMenuItems(editorStub, openPicker, '')
    const playbookItem = items.find((i) => i.title === 'Playbook')
    playbookItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('playbook')

    const dateItem = items.find((i) => i.title === 'Datum')
    dateItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('date')

    const personaRefItem = items.find((i) => i.title === 'Persona laden (MCP)')
    personaRefItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('persona-ref')

    const catalogItem = items.find((i) => i.title === 'Playbook-Katalog')
    catalogItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('playbooks-catalog')

    const resourceCatalogItem = items.find((i) => i.title === 'Resource-Katalog')
    resourceCatalogItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('resources-catalog')

    const toolRefItem = items.find((i) => i.title === 'Externes Tool')
    toolRefItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('tool-ref')

    const memoryItem = items.find((i) => i.title === 'Gedächtnis')
    memoryItem?.onItemClick()
    expect(openPicker).toHaveBeenCalledWith('memory')
  })

  it('allowedKinds filtert die Custom-Items (Persona-Pill-Satz)', () => {
    const allowed = new Set([
      'playbook',
      'resource',
      'playbooks-catalog',
      'resources-catalog',
    ] as const)
    const items = buildSlashMenuItems(editorStub, vi.fn(), '', allowed)
    const titles = items.map((i) => i.title)
    expect(titles).toContain('Resource-Katalog')
    expect(titles).toContain('Playbook-Katalog')
    // Nicht erlaubte Kinds fehlen.
    expect(titles).not.toContain('Persona-Feld')
    expect(titles).not.toContain('Datum')
    expect(titles).not.toContain('MCP-Tools')
    expect(titles).not.toContain('Externes Tool')
    expect(titles).not.toContain('Gedächtnis')
  })
})

describe('buildSystemPromptSchema', () => {
  it('gibt ein Objekt mit inlineContentSchema zurueck (Smoke)', () => {
    const schema = buildSystemPromptSchema()
    expect(schema).toBeDefined()
    expect(schema.inlineContentSchema).toBeDefined()
  })

  it('inlineContentSchema enthaelt den placeholder-Typ', () => {
    const schema = buildSystemPromptSchema()
    expect(schema.inlineContentSchema).toHaveProperty('placeholder')
  })
})
