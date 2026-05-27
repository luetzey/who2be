import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { PlaybookLinkItem } from './PlaybookLinkItem'

function renderItem(props?: Partial<Parameters<typeof PlaybookLinkItem>[0]>) {
  const onToggle = vi.fn()
  render(
    <ul>
      <PlaybookLinkItem
        id="pb1"
        name="Coaching"
        checked={false}
        onToggle={onToggle}
        {...props}
      />
    </ul>,
  )
  return { onToggle }
}

describe('PlaybookLinkItem', () => {
  it('rendert Label und Checkbox mit korrektem htmlFor/id', () => {
    renderItem()

    const checkbox = screen.getByLabelText('Coaching') as HTMLInputElement
    expect(checkbox).toBeInTheDocument()
    expect(checkbox.id).toBe('playbook-link-pb1')
    expect(checkbox.checked).toBe(false)
  })

  it('triggert onToggle beim Klick auf das Label', () => {
    const { onToggle } = renderItem()

    fireEvent.click(screen.getByLabelText('Coaching'))

    expect(onToggle).toHaveBeenCalledTimes(1)
  })

  it('zeigt den checked-Zustand an', () => {
    renderItem({ checked: true })

    const checkbox = screen.getByLabelText('Coaching') as HTMLInputElement
    expect(checkbox.checked).toBe(true)
  })
})
