import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook, ResourceBlock } from '@/api/types'

import { PlaybookEditorForm } from './PlaybookEditorForm'
import { usePlaybookForm } from '../hooks/usePlaybookForm'

// BlockNote-Insel wird auf der Wrapper-Ebene gemockt — so koennen wir
// `initialBlocks` per Data-Attribut beobachten, ohne ProseMirror zu starten.
vi.mock('@/components/editor/BlockNoteEditor', () => ({
  BlockNoteEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
    <div
      data-testid="blocknote-view"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    />
  ),
}))

// PlaybookBodyEditor (BlockNote-Insel fuer den blocknote-Body) ebenfalls
// mocken — er importiert BlockNote direkt. Wir exponieren `initialBlocks`
// per Data-Attribut und einen Button, der onChange mit Test-Bloecken feuert.
vi.mock('./PlaybookBodyEditor', () => ({
  PlaybookBodyEditor: ({
    initialBlocks,
    onChange,
  }: {
    initialBlocks: unknown[]
    onChange?: (blocks: unknown[]) => void
  }) => (
    <div
      data-testid="playbook-body-editor"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    >
      <button
        type="button"
        data-testid="emit-blocknote-change"
        onClick={() =>
          onChange?.([
            { id: 'b1', type: 'paragraph', content: [{ type: 'text', text: 'X', styles: {} }] },
          ])
        }
      >
        emit
      </button>
    </div>
  ),
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'admin',
}))

const patchPlaybookDraft = vi.fn().mockResolvedValue({})

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    patchPlaybookDraft,
    listPlaybookTags: () => Promise.resolve(['support']),
  }),
}))

const playbook: Playbook = {
  id: 'pb-1',
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name: 'Reset-Mail',
  current_version: 1,
  type: 'workflow',
  tags: ['support'],
  triggers: 'passwort vergessen',
  content: {
    description: 'd',
    body: 'Schritt 1\n\nSchritt 2',
    type: 'workflow',
    tags: ['support'],
    triggers: 'passwort vergessen',
  },
  created_at: 't',
  updated_at: 't',
}

function Harness({
  source = playbook,
  composesChildren,
  resourceLinks,
}: {
  source?: Playbook
  composesChildren?: import('@/api/types').Playbook[]
  resourceLinks?: import('@/api/types').ResourceLink[]
} = {}) {
  const { form, initialBodyBlocks, initialBodyFormat } = usePlaybookForm(source)
  return (
    <PlaybookEditorForm
      form={form}
      formKey={`${source.id}-${source.current_version}`}
      initialBodyBlocks={initialBodyBlocks}
      initialBodyFormat={initialBodyFormat}
      composesChildren={composesChildren}
      resourceLinks={resourceLinks}
    />
  )
}

describe('PlaybookEditorForm', () => {
  it('rendert den Typ als Select mit sechs Optionen', async () => {
    render(<Harness />)
    const select = (await screen.findByLabelText('Typ')) as HTMLSelectElement
    expect(select.tagName).toBe('SELECT')
    const optionValues = Array.from(select.options).map((option) => option.value)
    expect(optionValues).toEqual([
      'prompt',
      'instructions',
      'snippet',
      'workflow',
      'checklist',
      'faq',
    ])
  })

  it('zeigt einen Per-Option-Hint, der sich beim Wechsel aktualisiert', () => {
    render(<Harness />)
    expect(
      screen.getByText(/Mehrstufiger Prozess mit Verzweigungen/),
    ).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'faq' } })

    expect(
      screen.getByText(/Frage-Antwort-Sammlung/),
    ).toBeInTheDocument()
  })

  it('rendert die BlockNote-Insel im Inhalt-Slot', () => {
    render(<Harness />)
    expect(screen.getByTestId('blocknote-view')).toBeInTheDocument()
  })

  it('auto-saved eine Payload mit `tags: string[]` und neuem Typ aus dem Select', async () => {
    patchPlaybookDraft.mockClear()
    render(<Harness />)

    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'checklist' } })
    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalledTimes(1)
      },
      { timeout: 3000 },
    )
    const payload = patchPlaybookDraft.mock.calls[0][1]
    expect(payload).toMatchObject({
      name: 'Reset-Mail',
      content: {
        type: 'checklist',
        tags: ['support'],
        triggers: 'passwort vergessen',
        description: 'd',
      },
    })
    expect(Array.isArray(payload.content.tags)).toBe(true)
  }, 10_000)

  it('zeigt Hilfe-Tooltips fuer jede Section', () => {
    render(<Harness />)
    // Zwei Sections (Identität, Inhalt) → zwei Info-Buttons.
    expect(screen.getAllByRole('button', { name: 'Hilfe einblenden' }).length).toBe(2)
  })

  it('rendert bestehende Trigger als Pills (kein Komma-Input mehr)', () => {
    render(<Harness />)
    // Bestehender Trigger aus dem Mock-Playbook taucht als Badge-Pill auf
    // (mit Entfernen-Button via TagInput).
    expect(
      screen.getByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    ).toBeInTheDocument()
    // Es gibt KEIN klassisches <input type="text"> mit dem alten Placeholder.
    expect(
      screen.queryByPlaceholderText(/passwort vergessen.*reset link/),
    ).not.toBeInTheDocument()
  })

  it('legt einen neuen Trigger als Pill an und sendet ihn via Auto-Save als Komma-String', async () => {
    patchPlaybookDraft.mockClear()
    render(<Harness />)

    const triggerLabel = screen.getByText('Trigger', { selector: 'label' })
    const triggerLabelId = triggerLabel.getAttribute('id') ?? triggerLabel.id
    const triggerInput = screen
      .getAllByRole('combobox')
      .find((element) => element.getAttribute('aria-labelledby') === triggerLabelId)
    if (triggerInput === undefined) {
      throw new Error('Trigger-Combobox nicht gefunden')
    }
    fireEvent.change(triggerInput, { target: { value: 'reset link' } })
    fireEvent.keyDown(triggerInput, { key: 'Enter' })

    expect(
      await screen.findByRole('button', { name: 'Tag reset link entfernen' }),
    ).toBeInTheDocument()

    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const lastCall =
      patchPlaybookDraft.mock.calls[patchPlaybookDraft.mock.calls.length - 1]
    expect(lastCall[1].content.triggers).toBe('passwort vergessen, reset link')
  }, 10_000)

  it('rehydratisiert die BlockNote-Insel, wenn `formKey` wechselt', async () => {
    const v1: Playbook = {
      ...playbook,
      current_version: 1,
      content: { ...playbook.content, body: 'alpha-body' },
    }
    const v2: Playbook = {
      ...playbook,
      current_version: 2,
      content: { ...playbook.content, body: 'beta-body' },
    }

    const { rerender } = render(<Harness source={v1} />)
    await waitFor(() => {
      const editor = screen.getByTestId('blocknote-view')
      expect(editor.getAttribute('data-initial-blocks')).toContain('alpha-body')
    })

    rerender(<Harness source={v2} />)
    await waitFor(() => {
      const editor = screen.getByTestId('blocknote-view')
      expect(editor.getAttribute('data-initial-blocks')).toContain('beta-body')
    })
  })

  it('entfernt einen Trigger per Klick auf das X und propagiert ihn via Auto-Save', async () => {
    patchPlaybookDraft.mockClear()
    render(<Harness />)

    fireEvent.click(
      screen.getByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    )

    expect(
      screen.queryByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    ).not.toBeInTheDocument()

    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const lastCall =
      patchPlaybookDraft.mock.calls[patchPlaybookDraft.mock.calls.length - 1]
    expect(lastCall[1].content.triggers).toBeNull()
  }, 10_000)

  it('rendert bei body_format=plain den ResourceEditor + Migrate-Button, nicht den BlockNote-Body', () => {
    render(<Harness />)
    expect(screen.getByTestId('blocknote-view')).toBeInTheDocument()
    expect(screen.queryByTestId('playbook-body-editor')).not.toBeInTheDocument()
    expect(screen.getByTestId('migrate-to-blocknote-btn')).toBeInTheDocument()
  })

  it('Regression: rendert beim allerersten Render schon den PlaybookBodyEditor, wenn das Playbook body_format=blocknote ist (sonst landen Placeholder-Pills im default-schema-ResourceEditor)', () => {
    // form.reset im usePlaybookForm-Effect laeuft erst NACH dem ersten Render,
    // d. h. form.watch('body_format') ist initial der Form-Default 'plain'.
    // Wuerde die Branch-Entscheidung daran haengen, mountete der ResourceEditor
    // (Default-BlockNote-Schema) mit Placeholder-Pills im initialContent und
    // wirft live "node type placeholder not found in schema".
    const bnPlaybook: Playbook = {
      ...playbook,
      content: {
        ...playbook.content,
        body: JSON.stringify([
          {
            id: 'b0',
            type: 'paragraph',
            content: [{ type: 'placeholder', props: { kind: 'resource', target_id: 'r-1', label: 'R' } }],
          },
        ]),
        body_format: 'blocknote',
      },
    }
    render(<Harness source={bnPlaybook} />)
    // Erster Render bereits korrekt — kein doppeltes Mount mit ResourceEditor.
    expect(screen.queryByTestId('blocknote-view')).not.toBeInTheDocument()
    expect(screen.getByTestId('playbook-body-editor')).toBeInTheDocument()
  })

  it('serialisiert bei body_format=blocknote den Body als JSON.stringify(blocks)', async () => {
    patchPlaybookDraft.mockClear()
    const bnPlaybook: Playbook = {
      ...playbook,
      content: {
        ...playbook.content,
        body: JSON.stringify([
          { id: 'b0', type: 'paragraph', content: [{ type: 'text', text: 'Y', styles: {} }] },
        ]),
        body_format: 'blocknote',
      },
    }
    render(<Harness source={bnPlaybook} />)

    // BlockNote-Body wird gerendert, ResourceEditor nicht.
    expect(await screen.findByTestId('playbook-body-editor')).toBeInTheDocument()
    expect(screen.queryByTestId('blocknote-view')).not.toBeInTheDocument()

    // onChange feuern → Auto-Save mit JSON-serialisiertem Body + body_format.
    fireEvent.click(screen.getByTestId('emit-blocknote-change'))
    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const payload = patchPlaybookDraft.mock.calls.at(-1)?.[1]
    expect(payload.content.body_format).toBe('blocknote')
    const parsed = JSON.parse(payload.content.body)
    expect(Array.isArray(parsed)).toBe(true)
    expect(parsed[0]).toMatchObject({ id: 'b1', type: 'paragraph' })
  }, 10_000)

  it('Migrate-Button schaltet auf blocknote um und hebt Relationen als Pills in den Body', async () => {
    patchPlaybookDraft.mockClear()
    const child: import('@/api/types').Playbook = {
      ...playbook,
      id: 'pb-child',
      name: 'Sub-Playbook',
    }
    const links: import('@/api/types').ResourceLink[] = [
      {
        resource_id: 'res-1',
        resource_name: 'FAQ',
        block_id: 'blk-1',
        position: 0,
        available: true,
        section_preview: 'Reset',
        preview: null,
        link_scope: 'block',
      },
    ]
    render(<Harness composesChildren={[child]} resourceLinks={links} />)

    fireEvent.click(screen.getByTestId('migrate-to-blocknote-btn'))

    // Nach Migration: BlockNote-Body sichtbar, initialBlocks enthalten Pills.
    const editor = await screen.findByTestId('playbook-body-editor')
    const initial = editor.getAttribute('data-initial-blocks') ?? ''
    expect(initial).toContain('"kind":"playbook"')
    expect(initial).toContain('pb-child')
    expect(initial).toContain('"kind":"resource"')
    expect(initial).toContain('res-1#blk-1')

    // Auto-Save serialisiert den migrierten Body als blocknote.
    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const payload = patchPlaybookDraft.mock.calls.at(-1)?.[1]
    expect(payload.content.body_format).toBe('blocknote')
    expect(payload.content.body).toContain('pb-child')
    expect(payload.content.body).toContain('res-1#blk-1')
  }, 10_000)
})
