import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { LanguageSelect } from './LanguageSelect'

function Harness() {
  const [value, setValue] = useState<string[]>(['de'])
  return (
    <>
      <LanguageSelect value={value} onChange={setValue} />
      <output data-testid="value">{value.join(',')}</output>
    </>
  )
}

describe('LanguageSelect', () => {
  it('toggelt eine weitere Sprache hinzu (stabile Reihenfolge)', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('English'))
    expect(screen.getByTestId('value').textContent).toBe('de,en')
  })

  it('entfernt eine abgewaehlte Sprache', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('English'))
    fireEvent.click(screen.getByLabelText('Deutsch'))
    expect(screen.getByTestId('value').textContent).toBe('en')
  })

  it('verhindert das Abwaehlen der letzten Sprache', () => {
    render(<Harness />)
    fireEvent.click(screen.getByLabelText('Deutsch'))
    expect(screen.getByTestId('value').textContent).toBe('de')
  })
})
