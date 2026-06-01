import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useForm } from 'react-hook-form'

import type { ResourceBlock } from '@/api/types'
import { Form } from '@/components/ui/form'

import { PersonaModesEditor } from './PersonaModesEditor'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

// BlockNote-Insel mocken — jsdom kann ProseMirror/Mantine nicht starten. Der
// Mock spiegelt `initialBlocks` per Data-Attribut (gleiches Muster wie in
// PersonaEditorForm.test).
vi.mock('@/components/editor/BlockNoteEditor', () => ({
  BlockNoteEditor: ({ initialBlocks }: { initialBlocks: ResourceBlock[] }) => (
    <div
      data-testid="blocknote-view"
      data-initial-blocks={JSON.stringify(initialBlocks)}
    />
  ),
}))

const listPlaybooks = vi
  .fn()
  .mockResolvedValue([
    { id: 'pb-1', name: 'Onboarding-Playbook' },
    { id: 'pb-2', name: 'Eskalations-Playbook' },
  ])

vi.mock('@/api/useApi', () => ({
  useApi: () => ({ listPlaybooks }),
}))

// Harness: Wrapper mit react-hook-form-Kontext und leerer Persona.
function Harness({
  initialModes = [],
}: {
  initialModes?: PersonaEditorValues['modes']
}) {
  const form = useForm<PersonaEditorValues>({
    defaultValues: {
      name: 'Test',
      description: 'Desc',
      profileBlocks: [],
      tags: [],
      modes: initialModes,
      skills: [],
    },
  })
  return (
    <Form {...form}>
      <form>
        <PersonaModesEditor control={form.control} />
      </form>
    </Form>
  )
}

const emptyMode = (overrides: Partial<PersonaEditorValues['modes'][number]> = {}) => ({
  name: '',
  trigger: '',
  is_default: false,
  identity_add: [],
  output_style_override: [],
  anti_patterns: [],
  playbook_id: null,
  playbook_name: undefined,
  ...overrides,
})

describe('PersonaModesEditor', () => {
  it('zeigt den Leer-Zustand, wenn keine Modi vorhanden sind', () => {
    render(<Harness />)
    expect(screen.getByText(/Noch keine Modi definiert/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ersten Modus anlegen' }),
    ).toBeInTheDocument()
  })

  it('fuegt einen neuen Modus hinzu — mit drei BlockNote-Inseln + Playbook-Select', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Ersten Modus anlegen' }))

    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Trigger')).toBeInTheDocument()
    // Drei BlockNote-Inseln statt Textareas (identity_add, output_style_override,
    // anti_patterns). Der gemockte Editor traegt kein Form-Control-Binding, daher
    // pruefen wir die sichtbaren Labels + die Anzahl der Inseln.
    expect(screen.getByText('Identity-Ergänzung')).toBeInTheDocument()
    expect(screen.getByText('Output-Stil')).toBeInTheDocument()
    expect(screen.getByText('Anti-Patterns')).toBeInTheDocument()
    expect(screen.getAllByTestId('blocknote-view')).toHaveLength(3)
    // Playbook-Picker (natives Select).
    expect(screen.getByLabelText('Playbook')).toBeInTheDocument()
  })

  it('laedt Playbook-Optionen in den Select', async () => {
    render(<Harness initialModes={[emptyMode({ is_default: true })]} />)
    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Onboarding-Playbook' }),
      ).toBeInTheDocument()
    })
    expect(listPlaybooks).toHaveBeenCalled()
  })

  it('setzt playbook_id + playbook_name beim Auswaehlen', async () => {
    render(<Harness initialModes={[emptyMode({ is_default: true })]} />)
    await waitFor(() => {
      expect(
        screen.getByRole('option', { name: 'Eskalations-Playbook' }),
      ).toBeInTheDocument()
    })
    const select = screen.getByLabelText('Playbook') as HTMLSelectElement
    fireEvent.change(select, { target: { value: 'pb-2' } })
    expect(select.value).toBe('pb-2')
  })

  it('zeigt bestehende Modi mit Default-Badge', () => {
    render(
      <Harness
        initialModes={[
          emptyMode({ name: 'Coaching', trigger: 'coaching', is_default: false }),
          emptyMode({ name: 'Standard', is_default: true }),
        ]}
      />,
    )

    const nameFields = screen.getAllByLabelText('Name')
    expect(nameFields).toHaveLength(2)
    expect(screen.getByText('Default')).toBeInTheDocument()
  })

  it('erlaubt das Entfernen eines Modus', () => {
    render(<Harness initialModes={[emptyMode({ name: 'Coaching', is_default: true })]} />)

    expect(screen.getByRole('button', { name: 'Modus 1 entfernen' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Modus 1 entfernen' }))

    expect(screen.getByText(/Noch keine Modi definiert/)).toBeInTheDocument()
  })

  it('setzt Default exklusiv — nur ein Default gleichzeitig', () => {
    render(
      <Harness
        initialModes={[
          emptyMode({ name: 'Coaching', trigger: 'coaching', is_default: true }),
          emptyMode({ name: 'Analyse', trigger: 'analyse', is_default: false }),
        ]}
      />,
    )

    expect(screen.getAllByText('Default')).toHaveLength(1)
    fireEvent.click(screen.getByRole('button', { name: 'Als Default setzen' }))
    expect(screen.getAllByText('Default')).toHaveLength(1)
  })
})
