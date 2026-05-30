import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useMemo } from 'react'
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

function makePersona(systemPrompt = ''): Persona {
  return {
    id: 'p-1',
    workspace_id: 'ws-1',
    owner_id: 'o-1',
    name: 'Coach',
    current_version: 1,
    content: {
      description: 'd',
      system_prompt: systemPrompt,
      traits: [],
      tags: ['coaching'],
      content: { description: '', blocks: [] },
    },
    created_at: 't',
    updated_at: 't',
  }
}

function Harness({
  legacySystemPrompt,
  persona,
}: {
  legacySystemPrompt?: string
  persona?: Persona
}) {
  // Persona-Referenz muss stabil sein — sonst feuert `usePersonaForm`s
  // form.reset-useEffect bei jedem Render und das Test rendert sich in eine
  // Endlosschleife. `useMemo` mit leerem Dependency-Array haelt die Referenz
  // genau einmal pro Mount fest.
  const usedPersona = useMemo(() => persona ?? makePersona(), [persona])
  const { form, onSubmit, saveError } = usePersonaForm(usedPersona, () => {})
  return (
    <PersonaEditorForm
      form={form}
      onSubmit={onSubmit}
      saveError={saveError}
      legacySystemPrompt={legacySystemPrompt}
    />
  )
}

describe('PersonaEditorForm', () => {
  it('rendert drei Sektionen — Identitaet, Profil, Tags (System-Prompt entfaellt)', async () => {
    render(<Harness />)
    expect(await screen.findByText('Identität')).toBeInTheDocument()
    expect(screen.getByText('Profil')).toBeInTheDocument()
    expect(screen.getByText('Tags', { selector: 'h2' })).toBeInTheDocument()
    // properties/traits-Feld entfaellt — kein „Eigenschaften"-Label mehr.
    expect(screen.queryByLabelText(/Eigenschaften/)).not.toBeInTheDocument()
    // System-Prompt-Section ist mit Track 3 weg.
    expect(screen.queryByText(/System-Prompt/)).not.toBeInTheDocument()
  })

  it('zeigt Read-Only-Hinweis fuer Bestandsdaten mit System-Prompt', () => {
    render(
      <Harness legacySystemPrompt="Sei hilfsbereit." persona={makePersona('Sei hilfsbereit.')} />,
    )
    const hint = screen.getByTestId('persona-legacy-system-prompt-hint')
    expect(hint).toBeInTheDocument()
    expect(hint).toHaveTextContent('Sei hilfsbereit.')
  })

  it('zeigt KEINEN Hinweis, wenn das Bestands-Feld leer ist', () => {
    render(<Harness legacySystemPrompt="" />)
    expect(
      screen.queryByTestId('persona-legacy-system-prompt-hint'),
    ).not.toBeInTheDocument()
  })

  it('rendert Hilfe-Tooltips statt Inline-<details>', () => {
    const { container } = render(<Harness />)
    expect(container.querySelector('details')).toBeNull()
    expect(container.querySelector('summary')).toBeNull()
    // Drei Section-Hilfen — System-Prompt-Section ist entfallen.
    expect(screen.getAllByRole('button', { name: 'Hilfe einblenden' }).length).toBe(3)
  })

  it('rendert die BlockNote-Insel im Profil-Slot', () => {
    render(<Harness />)
    // Nur noch eine BlockNote-Insel (Profil-Editor).
    expect(screen.getAllByTestId('blocknote-view').length).toBe(1)
  })

  it('submitt eine Payload mit `content.blocks` + `tags` und leerem `system_prompt`', async () => {
    updatePersona.mockClear()
    render(<Harness persona={makePersona('Sei hilfsbereit.')} />)

    fireEvent.click(screen.getByRole('button', { name: 'Neue Version speichern' }))

    await waitFor(() => {
      expect(updatePersona).toHaveBeenCalledTimes(1)
    })
    const payload = updatePersona.mock.calls[0][1]
    expect(payload).toMatchObject({
      name: 'Coach',
      content: {
        description: 'd',
        system_prompt: '',
        traits: [],
        tags: ['coaching'],
        content: { description: '', blocks: [] },
      },
    })
    expect(payload.content).not.toHaveProperty('properties')
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
