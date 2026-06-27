import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ManagedNotice } from './ManagedNotice'

describe('ManagedNotice', () => {
  it('zeigt Titel + Body fuer ein verwaltetes Aggregat', () => {
    render(<ManagedNotice />)
    expect(screen.getByTestId('managed-notice')).toBeInTheDocument()
    expect(screen.getByText('Vom System verwaltet')).toBeInTheDocument()
    expect(
      screen.getByText(/zentral vom System gepflegt und automatisch aktualisiert/i),
    ).toBeInTheDocument()
  })

  it('blendet den Duplizieren-Hinweis nur mit showDuplicateHint ein', () => {
    const { rerender } = render(<ManagedNotice />)
    expect(screen.queryByText(/Dupliziere den Agenten/i)).not.toBeInTheDocument()

    rerender(<ManagedNotice showDuplicateHint />)
    expect(screen.getByText(/Dupliziere den Agenten/i)).toBeInTheDocument()
  })
})
