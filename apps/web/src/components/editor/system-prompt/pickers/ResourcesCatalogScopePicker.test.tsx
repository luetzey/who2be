import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { PlaceholderProps } from '../PlaceholderBlock'
import { ResourcesCatalogScopePicker } from './ResourcesCatalogScopePicker'

function setup(initial?: PlaceholderProps) {
  const onConfirm = vi.fn()
  const onCancel = vi.fn()
  render(
    <ResourcesCatalogScopePicker
      open
      onConfirm={onConfirm}
      onCancel={onCancel}
      initial={initial}
    />,
  )
  return { onConfirm, onCancel }
}

describe('ResourcesCatalogScopePicker', () => {
  it('bestaetigt mit target_id "all" im Default-Modus', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('resources-catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'resources-catalog', target_id: 'all' }),
    )
  })

  it('bestaetigt mit dem eingegebenen Tag als target_id', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('resources-catalog-option-tag'))
    fireEvent.change(screen.getByTestId('resources-catalog-tag-input'), {
      target: { value: 'billing' },
    })
    fireEvent.click(screen.getByTestId('resources-catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'resources-catalog', target_id: 'billing' }),
    )
  })

  it('faellt bei leerem Tag-Input auf "all" zurueck', () => {
    const { onConfirm } = setup()
    fireEvent.click(screen.getByTestId('resources-catalog-option-tag'))
    fireEvent.click(screen.getByTestId('resources-catalog-scope-picker-confirm'))
    expect(onConfirm).toHaveBeenCalledWith(
      expect.objectContaining({ target_id: 'all' }),
    )
  })

  it('belegt den Tag-Modus aus einer bestehenden Pill vor (Edit)', () => {
    setup({ kind: 'resources-catalog', target_id: 'onboarding', label: 'x' })
    const input = screen.getByTestId('resources-catalog-tag-input') as HTMLInputElement
    expect(input.value).toBe('onboarding')
  })
})
