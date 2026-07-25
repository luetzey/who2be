import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { LanguageSelect } from './LanguageSelect'

function Harness() {
  const [value, setValue] = useState('de')
  return (
    <>
      <LanguageSelect value={value} onChange={setValue} />
      <output data-testid="value">{value}</output>
    </>
  )
}

describe('LanguageSelect', () => {
  it('zeigt die uebergebene Sprache vorbelegt', () => {
    render(<Harness />)
    expect(screen.getByLabelText('Sprache')).toHaveValue('de')
    expect(screen.getByTestId('value').textContent).toBe('de')
  })

  it('wechselt die Sprache ueber die Einzel-Auswahl', () => {
    render(<Harness />)
    fireEvent.change(screen.getByLabelText('Sprache'), { target: { value: 'en' } })
    expect(screen.getByTestId('value').textContent).toBe('en')
  })

  it('rendert genau die zentrale Sprachliste als Optionen', () => {
    render(<Harness />)
    const select = screen.getByLabelText('Sprache') as HTMLSelectElement
    const optionLabels = Array.from(select.options).map((option) => option.textContent)
    expect(optionLabels).toEqual(['Deutsch', 'English'])
  })
})
