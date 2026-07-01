import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { StatusDistribution } from '@/api/types'

import { StatusDonut } from './StatusDonut'

const distribution: StatusDistribution = { draft: 2, review: 1, active: 4, inactive: 0 }

describe('StatusDonut', () => {
  it('rendert Segmente und die Gesamtsumme', () => {
    render(<StatusDonut label="Playbooks" distribution={distribution} />)
    // Zentrum zeigt die Summe (2+1+4+0 = 7).
    expect(screen.getByText('7')).toBeInTheDocument()
    // Segmente nur fuer Werte > 0 (inactive = 0 → kein Ring-Segment).
    const segments = document.querySelectorAll('circle[data-status]')
    expect(segments).toHaveLength(3)
  })

  it('verlinkt die Legende auf die vorgefilterte Liste, wenn hrefFor gesetzt ist', () => {
    render(
      <MemoryRouter>
        <StatusDonut
          label="Playbooks"
          distribution={distribution}
          hrefFor={(status) => `/w/ws-1/playbooks?status=${status}`}
        />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /In Review/ })
    expect(link).toHaveAttribute('href', '/w/ws-1/playbooks?status=review')
  })

  it('rendert die Legende ohne Links ohne hrefFor', () => {
    render(<StatusDonut label="Playbooks" distribution={distribution} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('zeigt einen leeren Ring bei Gesamtsumme 0', () => {
    render(
      <StatusDonut
        label="Leer"
        distribution={{ draft: 0, review: 0, active: 0, inactive: 0 }}
      />,
    )
    const legend = screen.getByText('Leer').closest('div')
    expect(legend).not.toBeNull()
    expect(within(legend as HTMLElement).getByText('0')).toBeInTheDocument()
    expect(document.querySelectorAll('circle[data-status]')).toHaveLength(0)
  })
})
