import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { CatalogScopePicker } from './CatalogScopePicker'

function setup(initial?: PlaceholderProps, open = true) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <CatalogScopePicker open={open} onConfirm={onConfirm} onCancel={onCancel} initial={initial} />,
  )
  return { onConfirm, onCancel }
}

describe('CatalogScopePicker', () => {
  it('bestaetigt im Default-Modus mit target_id "all"', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'playbooks-catalog',
      target_id: 'all',
      label: 'Playbook-Katalog (alle)',
    })
  })

  it('bestaetigt nach Auswahl von "triggered" mit passendem Label', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('catalog-scope-option-triggered'))
    fireEvent.click(screen.getByTestId('catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith({
      kind: 'playbooks-catalog',
      target_id: 'triggered',
      label: 'Playbook-Katalog (getriggert)',
    })
  })

  it('wechselt von "triggered" zurueck zu "all"', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('catalog-scope-option-triggered'))
    fireEvent.click(screen.getByTestId('catalog-scope-option-all'))
    fireEvent.click(screen.getByTestId('catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'all' }))
  })

  it('belegt den Scope aus einer bestehenden Pill vor (Edit)', () => {
    const { onConfirm } = setup({
      kind: 'playbooks-catalog',
      target_id: 'triggered',
      label: 'x',
    })
    expect(screen.getByTestId('catalog-scope-option-triggered')).toHaveAttribute(
      'data-state',
      'checked',
    )
    fireEvent.click(screen.getByTestId('catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'triggered' }))
  })

  it('faellt bei unbekannter initial-target_id auf "all" zurueck', () => {
    const { onConfirm } = setup({ kind: 'playbooks-catalog', target_id: 'unbekannt', label: 'x' })
    fireEvent.click(screen.getByTestId('catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(expect.objectContaining({ target_id: 'all' }))
  })

  it('zeigt Edit-Beschriftungen bei vorhandener Pill', () => {
    setup({ kind: 'playbooks-catalog', target_id: 'all', label: 'x' })
    expect(screen.getByText('Playbook-Katalog ändern')).toBeInTheDocument()
    expect(screen.getByTestId('catalog-scope-picker-confirm')).toHaveTextContent('Aktualisieren')
  })

  it('zeigt Einfuegen-Beschriftungen ohne Pill', () => {
    setup()
    expect(screen.getByText('Playbook-Katalog einfuegen')).toBeInTheDocument()
    expect(screen.getByTestId('catalog-scope-picker-confirm')).toHaveTextContent('Einfuegen')
  })

  it('ruft onCancel ueber den Abbrechen-Button auf', () => {
    const { onCancel, onConfirm } = setup()
    fireEvent.click(screen.getByRole('button', { name: 'Abbrechen' }))
    expect(onCancel).toHaveBeenCalledTimes(1)
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('rendert geschlossen kein Panel', () => {
    setup(undefined, false)
    expect(screen.queryByTestId('catalog-scope-picker-dialog')).not.toBeInTheDocument()
  })
})
