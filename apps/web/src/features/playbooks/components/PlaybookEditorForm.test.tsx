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
})
