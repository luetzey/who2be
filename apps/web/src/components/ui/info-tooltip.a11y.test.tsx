import { fireEvent, render, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { axe } from '@/test/a11y'

import { InfoTooltip } from './info-tooltip'

describe('InfoTooltip (a11y)', () => {
  it('hat keine axe-Violations im geschlossenen Zustand', async () => {
    const { container } = render(
      <InfoTooltip>Hilfe-Inhalt</InfoTooltip>,
    )
    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })

  it('haelt korrekte ARIA, wenn der Tooltip offen ist', async () => {
    const { container, getByRole, findByRole } = render(
      <InfoTooltip>Erklaer-Text</InfoTooltip>,
    )
    fireEvent.focus(getByRole('button', { name: 'Hilfe einblenden' }))

    await findByRole('tooltip')
    await waitFor(() => {
      // Trigger zeigt im offenen Zustand den `aria-describedby`-Link zum Content.
      expect(getByRole('button', { name: 'Hilfe einblenden' })).toHaveAttribute(
        'aria-describedby',
      )
    })

    const results = await axe(container)
    expect(results).toHaveNoViolations()
  })
})
