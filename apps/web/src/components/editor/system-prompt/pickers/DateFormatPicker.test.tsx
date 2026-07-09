import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { DateFormatPicker } from './DateFormatPicker'

function setup(initial?: PlaceholderProps, open = true) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(<DateFormatPicker open={open} onConfirm={onConfirm} onCancel={onCancel} initial={initial} />)
  return { onConfirm, onCancel }
}

describe('DateFormatPicker', () => {
  it('bestaetigt im Default-Modus mit target_id "human"', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('date-format-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'date',
      target_id: 'human',
      label: 'Datum (lesbar)',
    })
  })

  it('bestaetigt nach Auswahl von ISO mit target_id ""', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('date-format-option-iso'))
    fireEvent.click(screen.getByTestId('date-format-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'date',
      target_id: '',
      label: 'Datum (ISO-8601)',
    })
  })

  it('wechselt von ISO zurueck zu "human"', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('date-format-option-iso'))
    fireEvent.click(screen.getByTestId('date-format-option-human'))
    fireEvent.click(screen.getByTestId('date-format-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ target_id: 'human' }),
    )
  })

  it('belegt ISO aus einer bestehenden Pill vor (Edit, target_id "")', () => {
    const { onConfirm } = setup({ kind: 'date', target_id: '', label: 'x' })
    expect(screen.getByTestId('date-format-option-iso')).toHaveAttribute('data-state', 'checked')
    fireEvent.click(screen.getByTestId('date-format-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: '' }))
  })

  it('belegt "human" aus einer bestehenden Pill vor (Edit)', () => {
    setup({ kind: 'date', target_id: 'human', label: 'x' })
    expect(screen.getByTestId('date-format-option-human')).toHaveAttribute('data-state', 'checked')
  })

  it('faellt bei unbekannter initial-target_id auf "human" zurueck', () => {
    const { onConfirm } = setup({ kind: 'date', target_id: 'unbekannt', label: 'x' })
    fireEvent.click(screen.getByTestId('date-format-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'human' }))
  })

  it('zeigt Edit-Beschriftungen bei vorhandener Pill', () => {
    setup({ kind: 'date', target_id: 'human', label: 'x' })
    expect(screen.getByText('Datum ändern')).toBeInTheDocument()
    expect(screen.getByTestId('date-format-picker-confirm')).toHaveTextContent('Aktualisieren')
  })

  it('zeigt Einfuegen-Beschriftungen ohne Pill', () => {
    setup()
    expect(screen.getByText('Datum einfuegen')).toBeInTheDocument()
    expect(screen.getByTestId('date-format-picker-confirm')).toHaveTextContent('Einfuegen')
  })

  it('ruft onCancel ueber den Abbrechen-Button auf', () => {
    const { onCancel, onConfirm } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('rendert geschlossen kein Panel', () => {
    setup(undefined, false)
    expect(screen.queryByTestId('date-format-picker-dialog')).not.toBeInTheDocument()
  })
})
