import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Playbook } from '@/api/types'

import { PlaybookEditorForm } from './PlaybookEditorForm'
import { usePlaybookForm } from '../hooks/usePlaybookForm'

vi.mock('@blocknote/react', () => ({
  useCreateBlockNote: () => ({ document: [] }),
}))
vi.mock('@blocknote/mantine', () => ({
  BlockNoteView: () => <div data-testid="blocknote-view" />,
}))
vi.mock('@/app/theme-context', () => ({ useTheme: () => ({ resolved: 'light' }) }))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'admin',
}))

const updatePlaybook = vi.fn().mockResolvedValue({})

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    updatePlaybook,
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

function Harness() {
  const { form, onSubmit, saveError } = usePlaybookForm(playbook, () => {})
  return <PlaybookEditorForm form={form} onSubmit={onSubmit} saveError={saveError} />
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

  it('submitt eine Payload mit `tags: string[]` und neuem Typ aus dem Select', async () => {
    updatePlaybook.mockClear()
    render(<Harness />)

    fireEvent.change(screen.getByLabelText('Typ'), { target: { value: 'checklist' } })
    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(updatePlaybook).toHaveBeenCalledTimes(1)
    })
    const payload = updatePlaybook.mock.calls[0][1]
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
  })

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

  it('legt einen neuen Trigger als Pill an und schickt ihn beim Submit als Komma-String', async () => {
    updatePlaybook.mockClear()
    render(<Harness />)

    // Trigger-Input ueber sein Label finden (aria-labelledby haelt das Combobox-Element).
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

    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(updatePlaybook).toHaveBeenCalledTimes(1)
    })
    const payload = updatePlaybook.mock.calls[0][1]
    expect(payload.content.triggers).toBe('passwort vergessen, reset link')
  })

  it('entfernt einen Trigger per Klick auf das X', async () => {
    updatePlaybook.mockClear()
    render(<Harness />)

    fireEvent.click(
      screen.getByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    )

    expect(
      screen.queryByRole('button', { name: 'Tag passwort vergessen entfernen' }),
    ).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(updatePlaybook).toHaveBeenCalledTimes(1)
    })
    expect(updatePlaybook.mock.calls[0][1].content.triggers).toBeNull()
  })
})
