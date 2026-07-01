import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { StatusBadge } from './StatusBadge'

describe('StatusBadge', () => {
  it('rendert nichts ohne Status', () => {
    const { container } = render(<StatusBadge status={undefined} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('zeigt das lokalisierte Status-Label', () => {
    render(<StatusBadge status="review" />)
    expect(screen.getByText('In Review')).toBeInTheDocument()
  })

  it('zeigt den „Entwurf offen"-Marker bei pendingDraft', () => {
    render(<StatusBadge status="active" pendingDraft />)
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByTestId('status-badge-pending-draft')).toBeInTheDocument()
  })

  it('zeigt keinen Marker ohne pendingDraft', () => {
    render(<StatusBadge status="active" />)
    expect(screen.queryByTestId('status-badge-pending-draft')).not.toBeInTheDocument()
  })
})
