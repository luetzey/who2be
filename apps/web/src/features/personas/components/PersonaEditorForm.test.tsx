import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Persona, ResourceBlock } from '@/api/types'

import { PersonaEditorForm } from './PersonaEditorForm'
import { usePersonaForm } from '../hooks/usePersonaForm'

// BlockNote-Insel wird auf der Wrapper-Ebene gemockt — so koennen wir
// `initialBlocks` per Data-Attribut beobachten, ohne ProseMirror zu starten.
// Existierende Tests pruefen `data-testid="blocknote-view"`; der Mock erfuellt
// beide Rollen.
vi.mock('@/components/editor/BlockNoteEditor', () => ({
  BlockNoteEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
    <div
      data-testid="blocknote-view"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    />
  ),
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

// Workspace-Rolle als `admin` voreinstellen, damit der Save-Button aktiv ist.
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => 'admin',
}))

const patchPersonaDraft = vi.fn().mockResolvedValue({})
const listPersonaTags = vi.fn().mockResolvedValue([])
// Playbook-Tags duerfen vom Persona-Form nicht mehr geladen werden — die
// Domaenen sind getrennt. Mock vorhanden, aber Aufrufe = Regression.
const listPlaybookTags = vi.fn().mockResolvedValue(['playbook-only'])

vi.mock('@/api/useApi', () => ({
  useApi: () => ({
    patchPersonaDraft,
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
    // Bestandsdaten mit gefuelltem System-Prompt — Track 3 zeigt dafuer
    // die Read-Only-Hinweis-Box. Wir setzen den Wert hier, weil viele
    // Tests beide Zustaende (mit + ohne Wert) brauchen.
    system_prompt: 'Sei hilfsbereit.',
    traits: [],
    tags: ['coaching'],
    content: { description: '', blocks: [] },
  },
  created_at: 't',
  updated_at: 't',
}

function Harness({
  source = persona,
  legacySystemPrompt = source.content.system_prompt,
}: {
  source?: Persona
  legacySystemPrompt?: string
} = {}) {
  const { form } = usePersonaForm(source)
  return (
    <PersonaEditorForm
      form={form}
      formKey={`${source.id}-${source.current_version}`}
      initialProfileBlocks={source.content.content?.blocks ?? []}
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
    // Mit Track 3 ist die System-Prompt-Section weg — der Form-Section-Titel
    // existiert nicht mehr (die Read-Only-Hinweis-Box verwendet andere Texte).
    expect(
      screen.queryByText('System-Prompt', { selector: 'h2' }),
    ).not.toBeInTheDocument()
  })

  it('zeigt Read-Only-Hinweis fuer Bestandsdaten mit System-Prompt', () => {
    render(<Harness />)
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

  it('rendert die BlockNote-Insel im Profil-Slot (eine Insel)', () => {
    render(<Harness />)
    // Nur noch eine BlockNote-Insel (Profil-Editor) — System-Prompt-Editor
    // ist mit Track 3 entfallen.
    expect(screen.getAllByTestId('blocknote-view').length).toBe(1)
  })

  it('rendert keinen Save-Button mehr — Auto-Save uebernimmt', () => {
    render(<Harness />)
    expect(
      screen.queryByRole('button', { name: 'Neue Version speichern' }),
    ).not.toBeInTheDocument()
  })

  it(
    'triggert per Auto-Save einen PATCH-Draft mit `system_prompt: ""`',
    async () => {
      patchPersonaDraft.mockClear()
      render(<Harness />)
      const nameInput = screen.getByLabelText('Name')
      fireEvent.change(nameInput, { target: { value: 'Coach v2' } })
      await waitFor(
        () => {
          expect(patchPersonaDraft).toHaveBeenCalledTimes(1)
        },
        { timeout: 3000 },
      )
      const payload = patchPersonaDraft.mock.calls[0][1]
      expect(payload).toMatchObject({
        name: 'Coach v2',
        content: {
          description: 'd',
          // Track 3: System-Prompt wandert ins Template. Wir schicken den
          // Default '' mit, damit Backend-Pydantic ihn nicht ablehnt.
          system_prompt: '',
          traits: [],
          tags: ['coaching'],
          content: { description: '', blocks: [] },
        },
      })
      expect(payload.content).not.toHaveProperty('properties')
    },
    10_000,
  )

  it('rehydratisiert die Profil-Insel, wenn `formKey` wechselt', async () => {
    const paragraph = (text: string, id: string): ResourceBlock => ({
      id,
      type: 'paragraph',
      content: [{ type: 'text', text, styles: {} }],
    })
    const v1: Persona = {
      ...persona,
      current_version: 1,
      content: {
        ...persona.content,
        content: { description: '', blocks: [paragraph('alpha-block', 'b-1')] },
      },
    }
    const v2: Persona = {
      ...persona,
      current_version: 2,
      content: {
        ...persona.content,
        content: { description: '', blocks: [paragraph('beta-block', 'b-2')] },
      },
    }

    const { rerender } = render(<Harness source={v1} />)
    await waitFor(() => {
      const [profile] = screen.getAllByTestId('blocknote-view')
      expect(profile.getAttribute('data-initial-blocks')).toContain('alpha-block')
    })

    rerender(<Harness source={v2} />)
    await waitFor(() => {
      const [profile] = screen.getAllByTestId('blocknote-view')
      expect(profile.getAttribute('data-initial-blocks')).toContain('beta-block')
    })
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
