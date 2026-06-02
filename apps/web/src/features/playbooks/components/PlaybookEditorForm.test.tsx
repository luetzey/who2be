import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'

import { PlaybookEditorForm } from './PlaybookEditorForm'
import { usePlaybookForm } from '../hooks/usePlaybookForm'

// PlaybookBodyEditor (BlockNote-Insel fuer den Body) mocken — er importiert
// BlockNote direkt. Wir exponieren `initialBlocks` per Data-Attribut und einen
// Button, der onChange mit Test-Bloecken feuert.
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

// Track B: `body` ist immer ein stringifiziertes BlockNote-Dokument.
function blocknoteBody(text: string): string {
  return JSON.stringify([
    { id: 'b0', type: 'paragraph', content: [{ type: 'text', text, styles: {} }] },
  ])
}

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
    body: blocknoteBody('Schritt 1'),
    type: 'workflow',
    tags: ['support'],
    triggers: 'passwort vergessen',
  },
  created_at: 't',
  updated_at: 't',
}

function Harness({ source = playbook }: { source?: Playbook } = {}) {
  const { form, initialBodyBlocks } = usePlaybookForm(source)
  return (
    <PlaybookEditorForm
      form={form}
      formKey={`${source.id}-${source.current_version}`}
      initialBodyBlocks={initialBodyBlocks}
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
    expect(screen.getByText(/Mehrstufiger Prozess mit Verzweigungen/)).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'faq' } })
    expect(screen.getByText(/Frage-Antwort-Sammlung/)).toBeInTheDocument()
  })

  it('rendert immer den BlockNote-Body-Editor (Track B: Nur-BlockNote)', () => {
    render(<Harness />)
    expect(screen.getByTestId('playbook-body-editor')).toBeInTheDocument()
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
    // Track B: kein body_format mehr im Payload.
    expect('body_format' in payload.content).toBe(false)
    expect(Array.isArray(payload.content.tags)).toBe(true)
  }, 10_000)

  it('zeigt Hilfe-Tooltips fuer jede Section', () => {
    render(<Harness />)
    expect(screen.getAllByRole('button', { name: 'Hilfe einblenden' }).length).toBe(2)
  })

  it('rendert bestehende Trigger als Pills (kein Komma-Input mehr)', () => {
    render(<Harness />)
    expect(
      screen.getByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    ).toBeInTheDocument()
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
    const lastCall = patchPlaybookDraft.mock.calls[patchPlaybookDraft.mock.calls.length - 1]
    expect(lastCall[1].content.triggers).toBe('passwort vergessen, reset link')
  }, 10_000)

  it('rehydratisiert die BlockNote-Insel, wenn `formKey` wechselt', async () => {
    const v1: Playbook = {
      ...playbook,
      current_version: 1,
      content: { ...playbook.content, body: blocknoteBody('alpha-body') },
    }
    const v2: Playbook = {
      ...playbook,
      current_version: 2,
      content: { ...playbook.content, body: blocknoteBody('beta-body') },
    }

    const { rerender } = render(<Harness source={v1} />)
    await waitFor(() => {
      const editor = screen.getByTestId('playbook-body-editor')
      expect(editor.getAttribute('data-initial-blocks')).toContain('alpha-body')
    })

    rerender(<Harness source={v2} />)
    await waitFor(() => {
      const editor = screen.getByTestId('playbook-body-editor')
      expect(editor.getAttribute('data-initial-blocks')).toContain('beta-body')
    })
  })

  it('entfernt einen Trigger per Klick auf das X und propagiert ihn via Auto-Save', async () => {
    patchPlaybookDraft.mockClear()
    render(<Harness />)

    fireEvent.click(screen.getByRole('button', { name: 'Tag passwort vergessen entfernen' }))

    expect(
      screen.queryByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    ).not.toBeInTheDocument()

    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const lastCall = patchPlaybookDraft.mock.calls[patchPlaybookDraft.mock.calls.length - 1]
    expect(lastCall[1].content.triggers).toBeNull()
  }, 10_000)

  it('serialisiert den Body als JSON.stringify(blocks) ohne body_format', async () => {
    patchPlaybookDraft.mockClear()
    render(<Harness source={{ ...playbook, content: { ...playbook.content, body: blocknoteBody('Y') } }} />)

    expect(await screen.findByTestId('playbook-body-editor')).toBeInTheDocument()

    fireEvent.click(screen.getByTestId('emit-blocknote-change'))
    await waitFor(
      () => {
        expect(patchPlaybookDraft).toHaveBeenCalled()
      },
      { timeout: 3000 },
    )
    const payload = patchPlaybookDraft.mock.calls.at(-1)?.[1]
    expect('body_format' in payload.content).toBe(false)
    const parsed = JSON.parse(payload.content.body)
    expect(Array.isArray(parsed)).toBe(true)
    expect(parsed[0]).toMatchObject({ id: 'b1', type: 'paragraph' })
  }, 10_000)
})
