import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import { TagInput } from './tag-input'

function Harness({
  initial = [],
  loadSuggestions,
}: {
  initial?: string[]
  loadSuggestions?: () => Promise<string[]>
}) {
  const [value, setValue] = useState<string[]>(initial)
  return (
    <TagInput
      value={value}
      onChange={setValue}
      loadSuggestions={loadSuggestions}
      placeholder="Tag eingeben"
    />
  )
}

describe('TagInput', () => {
  it('zeigt API-Vorschlaege beim Fokus und uebernimmt einen Treffer', async () => {
    const loadSuggestions = vi.fn().mockResolvedValue(['support', 'reset'])
    render(<Harness loadSuggestions={loadSuggestions} />)

    const input = screen.getByRole('combobox')
    fireEvent.focus(input)

    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'support' })).toBeInTheDocument()
    })

    fireEvent.mouseDown(screen.getByRole('option', { name: 'support' }))

    await waitFor(() => {
      expect(screen.getByText('support')).toBeInTheDocument()
    })
    expect(screen.getByRole('button', { name: 'Tag support entfernen' })).toBeInTheDocument()
  })

  it('erstellt einen neuen Tag manuell via Enter', () => {
    render(<Harness loadSuggestions={() => Promise.resolve([])} />)

    const input = screen.getByRole('combobox')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'custom-tag' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(screen.getByText('custom-tag')).toBeInTheDocument()
  })

  it('bietet "Neu erstellen" an, wenn der Query nicht in der Vorschlagsliste ist', async () => {
    const loadSuggestions = vi.fn().mockResolvedValue(['support'])
    render(<Harness loadSuggestions={loadSuggestions} />)

    const input = screen.getByRole('combobox')
    fireEvent.focus(input)
    await waitFor(() => {
      expect(screen.getByRole('option', { name: 'support' })).toBeInTheDocument()
    })

    fireEvent.change(input, { target: { value: 'neu' } })

    expect(screen.getByText(/Neu erstellen/)).toBeInTheDocument()
  })

  it('entfernt den letzten Tag mit Backspace im leeren Feld', () => {
    render(<Harness initial={['a', 'b']} />)
    const input = screen.getByRole('combobox')
    fireEvent.keyDown(input, { key: 'Backspace' })

    expect(screen.queryByText('b')).not.toBeInTheDocument()
    expect(screen.getByText('a')).toBeInTheDocument()
  })

  it('faengt Loader-Fehler still ab und bleibt manuell befuellbar', async () => {
    const loadSuggestions = vi.fn().mockRejectedValue(new Error('404'))
    render(<Harness loadSuggestions={loadSuggestions} />)

    const input = screen.getByRole('combobox')
    fireEvent.focus(input)
    fireEvent.change(input, { target: { value: 'manuell' } })
    fireEvent.keyDown(input, { key: 'Enter' })

    expect(screen.getByText('manuell')).toBeInTheDocument()
  })
})
