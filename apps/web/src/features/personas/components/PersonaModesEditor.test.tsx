import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { useForm } from 'react-hook-form'

import { Form } from '@/components/ui/form'

import { PersonaModesEditor } from './PersonaModesEditor'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

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

describe('PersonaModesEditor', () => {
  it('zeigt den Leer-Zustand, wenn keine Modi vorhanden sind', () => {
    render(<Harness />)
    expect(screen.getByText(/Noch keine Modi definiert/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ersten Modus anlegen' }),
    ).toBeInTheDocument()
  })

  it('fuegt einen neuen Modus hinzu', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Ersten Modus anlegen' }))

    // Nach dem Anlegen muss ein Name-Feld sichtbar sein.
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Trigger')).toBeInTheDocument()
    expect(screen.getByLabelText('Identity-Ergänzung')).toBeInTheDocument()
    expect(screen.getByLabelText('Output-Stil')).toBeInTheDocument()
  })

  it('zeigt bestehende Modi mit Default-Badge', () => {
    render(
      <Harness
        initialModes={[
          {
            name: 'Coaching',
            trigger: 'coaching',
            is_default: false,
            identity_add: '',
            output_style_override: '',
          },
          {
            name: 'Standard',
            trigger: '',
            is_default: true,
            identity_add: 'Sei sachlich',
            output_style_override: '',
          },
        ]}
      />,
    )

    // Beide Modi sichtbar.
    const nameFields = screen.getAllByLabelText('Name')
    expect(nameFields).toHaveLength(2)

    // Default-Badge nur beim Standard-Modus.
    expect(screen.getByText('Default')).toBeInTheDocument()
  })

  it('erlaubt das Entfernen eines Modus', () => {
    render(
      <Harness
        initialModes={[
          {
            name: 'Coaching',
            trigger: null,
            is_default: true,
            identity_add: '',
            output_style_override: '',
          },
        ]}
      />,
    )

    expect(screen.getByRole('button', { name: 'Modus 1 entfernen' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Modus 1 entfernen' }))

    // Nach dem Entfernen ist der Leer-Zustand wieder sichtbar.
    expect(screen.getByText(/Noch keine Modi definiert/)).toBeInTheDocument()
  })

  it('setzt Default exklusiv — nur ein Default gleichzeitig', () => {
    render(
      <Harness
        initialModes={[
          {
            name: 'Coaching',
            trigger: 'coaching',
            is_default: true,
            identity_add: '',
            output_style_override: '',
          },
          {
            name: 'Analyse',
            trigger: 'analyse',
            is_default: false,
            identity_add: '',
            output_style_override: '',
          },
        ]}
      />,
    )

    // Nur ein Default-Badge zu Beginn.
    expect(screen.getAllByText('Default')).toHaveLength(1)

    // Analyse als Default setzen.
    fireEvent.click(screen.getByRole('button', { name: 'Als Default setzen' }))

    // Immer noch genau ein Default-Badge (Exklusivitaet).
    expect(screen.getAllByText('Default')).toHaveLength(1)
  })
})
