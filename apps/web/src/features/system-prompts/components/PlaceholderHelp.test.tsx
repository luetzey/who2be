import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlaceholderHelp } from './PlaceholderHelp'

describe('PlaceholderHelp', () => {
  it('listet die sieben verfuegbaren Placeholders auf', () => {
    render(<PlaceholderHelp />)
    expect(screen.getByText('{{ persona.name }}')).toBeInTheDocument()
    expect(screen.getByText('{{ persona.description }}')).toBeInTheDocument()
    expect(screen.getByText('{{ persona.profile }}')).toBeInTheDocument()
    expect(screen.getByText('{{ persona.tags }}')).toBeInTheDocument()
    expect(screen.getByText('{{ playbooks }}')).toBeInTheDocument()
    expect(screen.getByText('{{ triggers }}')).toBeInTheDocument()
    expect(screen.getByText('{{ resources }}')).toBeInTheDocument()
  })

  it('zeigt KEINEN persona.system_prompt-Eintrag (deprecated)', () => {
    render(<PlaceholderHelp />)
    expect(
      screen.queryByText('{{ persona.system_prompt }}'),
    ).not.toBeInTheDocument()
  })
})
