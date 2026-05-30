import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Persona } from '@/api/types'

import { PersonaEditorForm } from './PersonaEditorForm'
import { usePersonaForm } from '../hooks/usePersonaForm'

// BlockNote-Insel + Theme-Context muessen gemockt sein — siehe ADR-0022.
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

// Workspace-Rolle als `admin` voreinstellen, damit der Save-Button aktiv ist.
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'admin',
}))

const updatePersona = vi.fn().mockResolvedValue({})
const listPersonaTags = vi.fn().mockResolvedValue([])
// Playbook-Tags duerfen vom Persona-Form nicht mehr geladen werden — die
// Domaenen sind getrennt. Mock vorhanden, aber Aufrufe = Regression.
const listPlaybookTags = vi.fn().mockResolvedValue(['playbook-only'])

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    updatePersona,
    listPersonaTags,
    listPlaybookTags,
  }),
}))

const persona: Persona = {
  id: 'p-1',
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name: 'Coach',
  current_version: 1,
  content: {
    description: 'd',
    system_prompt: 'Sei hilfsbereit.',
    traits: [],
    tags: ['coaching'],
    content: { description: '', blocks: [] },
  },
  created_at: 't',
  updated_at: 't',
}

function Harness() {
  const { form, onSubmit, saveError } = usePersonaForm(persona, () => {})
  return <PersonaEditorForm form={form} onSubmit={onSubmit} saveError={saveError} />
}

describe('PersonaEditorForm', () => {
  it('rendert die vier Sektionen — Identitaet, Profil, System-Prompt, Tags', async () => {
    render(<Harness />)
    expect(await screen.findByText('Identität')).toBeInTheDocument()
    expect(screen.getByText('Profil')).toBeInTheDocument()
    expect(screen.getAllByText('System-Prompt').length).toBeGreaterThan(0)
    expect(screen.getByText('Tags', { selector: 'h2' })).toBeInTheDocument()
    // properties/traits-Feld entfaellt — kein „Eigenschaften"-Label mehr.
    expect(screen.queryByLabelText(/Eigenschaften/)).not.toBeInTheDocument()
  })

  it('rendert die BlockNote-Insel im Profil-Slot', () => {
    render(<Harness />)
    // Profil-Editor + System-Prompt-Editor — beide BlockNote.
    expect(screen.getAllByTestId('blocknote-view').length).toBeGreaterThan(0)
  })

  it('submitt eine Payload mit `content.blocks` + `tags` und ohne `properties`', async () => {
    updatePersona.mockClear()
    render(<Harness />)

    // System-Prompt laeuft seit Track 2 ueber den BlockNote-Editor (Slash-Menu
    // verfuegbar). Der Editor ist im Test gemockt — also kein DOM-Event noetig;
    // der Wert kommt aus `persona.content.system_prompt` via `form.reset`.
    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(updatePersona).toHaveBeenCalledTimes(1)
    })
    const payload = updatePersona.mock.calls[0][1]
    expect(payload).toMatchObject({
      name: 'Coach',
      content: {
        description: 'd',
        system_prompt: 'Sei hilfsbereit.',
        traits: [],
        tags: ['coaching'],
        content: { description: '', blocks: [] },
      },
    })
    // properties existiert nicht (nur traits, das wir bewusst leer mitsenden).
    expect(payload.content).not.toHaveProperty('properties')
  })

  it('rendert zwei BlockNote-Inseln — Profil + System-Prompt (gleicher Wrapper)', () => {
    render(<Harness />)
    // Profil-Editor + System-Prompt-Editor teilen sich denselben Wrapper —
    // entsprechend zweimal `blocknote-view` im DOM.
    expect(screen.getAllByTestId('blocknote-view').length).toBe(2)
  })

  it('laedt Tag-Vorschlaege aus `listPersonaTags`, nicht aus `listPlaybookTags`', async () => {
    listPersonaTags.mockClear()
    listPlaybookTags.mockClear()
    listPersonaTags.mockResolvedValueOnce(['empathie', 'leadership'])
    render(<Harness />)

    // Beim Fokus auf das Tag-Input erscheint der gefilterte Vorschlag.
    const tagInput = screen.getByRole('combobox')
    fireEvent.focus(tagInput)
    fireEvent.change(tagInput, { target: { value: 'lead' } })

    expect(await screen.findByRole('option', { name: 'leadership' })).toBeInTheDocument()
    expect(listPersonaTags).toHaveBeenCalled()
    expect(listPlaybookTags).not.toHaveBeenCalled()
  })
})
