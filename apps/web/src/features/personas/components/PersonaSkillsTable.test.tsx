import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { SkillRef } from '@/api/types'

import { PersonaSkillsTable } from './PersonaSkillsTable'

describe('PersonaSkillsTable', () => {
  it('rendert Skills als Tabelle mit Name + Hinweis', () => {
    const skills: SkillRef[] = [
      { name: 'Aktives Zuhören', note: 'paraphrasiert vor jeder Antwort' },
      { name: 'Refactoring', note: '' },
    ]
    render(<PersonaSkillsTable skills={skills} />)

    expect(screen.getByTestId('persona-skills-table')).toBeInTheDocument()
    expect(screen.getByText('Aktives Zuhören')).toBeInTheDocument()
    expect(screen.getByText('paraphrasiert vor jeder Antwort')).toBeInTheDocument()
    expect(screen.getByText('Refactoring')).toBeInTheDocument()
    // Leere Notiz → Em-Dash-Platzhalter.
    expect(screen.getByText('—')).toBeInTheDocument()
  })

  it('rendert nichts, wenn keine (benannten) Skills vorhanden sind', () => {
    const { container } = render(
      <PersonaSkillsTable skills={[{ name: '  ', note: 'x' }]} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('rendert nichts bei leerer Liste', () => {
    const { container } = render(<PersonaSkillsTable skills={[]} />)
    expect(container).toBeEmptyDOMElement()
  })
})
