import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { PersonaFieldPicker } from './PersonaFieldPicker'

function setup(initial?: PlaceholderProps, open = true) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <PersonaFieldPicker open={open} onConfirm={onConfirm} onCancel={onCancel} initial={initial} />,
  )
  return { onConfirm, onCancel }
}

describe('PersonaFieldPicker', () => {
  it('bestaetigt im Default-Modus mit target_id "name"', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('persona-field-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'persona-field',
      target_id: 'name',
      label: 'Persona: Name',
    })
  })

  it.each([
    ['description', 'Persona: Beschreibung'],
    ['profile', 'Persona: Profil (vollständig)'],
    ['profile-body', 'Persona: Profil-Inhalt'],
    ['modes', 'Persona: Modi'],
  ])('bestaetigt nach Auswahl von "%s" mit passendem Label', (target, label) => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId(`persona-field-option-${target}`))
    fireEvent.click(screen.getByTestId('persona-field-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'persona-field',
      target_id: target,
      label,
    })
  })

  it('belegt die Auswahl aus einer bestehenden Pill vor (Edit)', () => {
    const { onConfirm } = setup({ kind: 'persona-field', target_id: 'modes', label: 'x' })
    expect(screen.getByTestId('persona-field-option-modes')).toHaveAttribute(
      'data-state',
      'checked',
    )
    fireEvent.click(screen.getByTestId('persona-field-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'modes' }))
  })

  it('faellt bei unbekannter initial-target_id auf "name" zurueck', () => {
    const { onConfirm } = setup({ kind: 'persona-field', target_id: 'unbekannt', label: 'x' })
    fireEvent.click(screen.getByTestId('persona-field-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'name' }))
  })

  it('zeigt Edit-Beschriftungen bei vorhandener Pill', () => {
    setup({ kind: 'persona-field', target_id: 'name', label: 'x' })
    expect(screen.getByText('Persona-Feld ändern')).toBeInTheDocument()
    expect(screen.getByTestId('persona-field-picker-confirm')).toHaveTextContent('Aktualisieren')
  })

  it('zeigt Einfuegen-Beschriftungen ohne Pill', () => {
    setup()
    expect(screen.getByText('Persona-Feld einfuegen')).toBeInTheDocument()
    expect(screen.getByTestId('persona-field-picker-confirm')).toHaveTextContent('Einfuegen')
  })

  it('ruft onCancel ueber den Abbrechen-Button auf', () => {
    const { onCancel, onConfirm } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('rendert geschlossen kein Panel', () => {
    setup(undefined, false)
    expect(screen.queryByTestId('persona-field-picker-dialog')).not.toBeInTheDocument()
  })
})
