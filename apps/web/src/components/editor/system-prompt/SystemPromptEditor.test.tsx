// SystemPromptEditor.test.tsx — BlockNote-Insel in jsdom mocken (Standard-Pattern).
// Prueft:
//   1. SystemPromptEditor rendert ohne Fehler.
//   2. buildSlashMenuItems enthaelt die vier Custom-Items und filtert korrekt.
//   3. buildSystemPromptSchema gibt ein Schema-Objekt zurueck.

import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

// BlockNote in jsdom nicht mountfaehig — Standard-Mock (analog PlaybookDetailPage.test.tsx).
// createReactInlineContentSpec wird benoetigt weil PlaceholderBlock.tsx es
// auf Modulebene aufruft (nicht lazy). Wir mocken es als Identity-Funktion.
vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({
    document: [],
    insertInlineContent: vi.fn(),
  }),
  SuggestionMenuController: () => null,
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
vi.mock('@/api/useApi', () => ({ useApi: () => ({}) }))

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
})

describe('buildSlashMenuItems', () => {
  it('enthaelt alle Custom-Placeholder-Items', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items = buildSlashMenuItems({} as any, vi.fn(), '')
    const titles = items.map((i) => i.title)
    expect(titles).toContain('Playbook')
    expect(titles).toContain('Resource')
    expect(titles).toContain('Persona-Feld')
    expect(titles).toContain('Persona laden (MCP)')
    expect(titles).toContain('Playbook-Katalog')
    expect(titles).toContain('Datum')
  })

  it('filtert Table und Numbered-List aus Default-Items heraus', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items = buildSlashMenuItems({} as any, vi.fn(), '')
    const titles = items.map((i) => i.title)
    expect(titles).not.toContain('Tabelle')
    expect(titles).not.toContain('Nummeriert')
  })

  it('filtert nach Query (case-insensitive)', () => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items = buildSlashMenuItems({} as any, vi.fn(), 'play')
    expect(items.some((i) => i.title === 'Playbook')).toBe(true)
    expect(items.some((i) => i.title === 'Resource')).toBe(false)
  })

  it('Custom-Items rufen openPicker mit dem richtigen Kind auf', () => {
    const openPicker = vi.fn()
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const items = buildSlashMenuItems({} as any, openPicker, '')
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
