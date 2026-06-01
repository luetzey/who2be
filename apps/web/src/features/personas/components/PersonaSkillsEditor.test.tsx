import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { useForm } from 'react-hook-form'

import { axe } from '@/test/a11y'
import { Form } from '@/components/ui/form'

import { PersonaSkillsEditor } from './PersonaSkillsEditor'
import type { PersonaEditorValues } from '../hooks/usePersonaForm'

function Harness({
  initialSkills = [],
}: {
  initialSkills?: PersonaEditorValues['skills']
}) {
  const form = useForm<PersonaEditorValues>({
    defaultValues: {
      name: 'Test',
      description: 'Desc',
      profileBlocks: [],
      tags: [],
      modes: [],
      skills: initialSkills,
    },
  })
  return (
    <Form {...form}>
      <form>
        <PersonaSkillsEditor control={form.control} />
      </form>
    </Form>
  )
}

describe('PersonaSkillsEditor', () => {
  it('zeigt den Leer-Zustand, wenn keine Skills vorhanden sind', () => {
    render(<Harness />)
    expect(screen.getByText(/Noch keine Skills referenziert/)).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Ersten Skill hinzufügen' }),
    ).toBeInTheDocument()
  })

  it('fuegt einen Skill mit Name + Notiz hinzu', () => {
    render(<Harness />)
    fireEvent.click(screen.getByRole('button', { name: 'Ersten Skill hinzufügen' }))
    expect(screen.getByLabelText('Name')).toBeInTheDocument()
    expect(screen.getByLabelText('Notiz')).toBeInTheDocument()
    expect(screen.getByTestId('persona-skill-row')).toBeInTheDocument()
  })

  it('rendert bestehende Skills', () => {
    render(
      <Harness
        initialSkills={[
          { name: 'Aktives Zuhören', note: 'paraphrasiert' },
          { name: 'Deeskalation', note: 'ruhig bleiben' },
        ]}
      />,
    )
    expect(screen.getAllByTestId('persona-skill-row')).toHaveLength(2)
    expect(screen.getAllByLabelText('Name')).toHaveLength(2)
  })

  it('erlaubt das Entfernen eines Skills', () => {
    render(<Harness initialSkills={[{ name: 'X', note: 'y' }]} />)
    fireEvent.click(screen.getByRole('button', { name: 'Skill 1 entfernen' }))
    expect(screen.getByText(/Noch keine Skills referenziert/)).toBeInTheDocument()
  })

  it('hat keine axe-Violations mit einem Skill', async () => {
    const { container } = render(
      <Harness initialSkills={[{ name: 'Aktives Zuhören', note: 'paraphrasiert' }]} />,
    )
    expect(await axe(container)).toHaveNoViolations()
  })
})
