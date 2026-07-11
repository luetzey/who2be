import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { StatusDistribution } from '@/api/types'

import { StatusBar } from './StatusBar'

const distribution: StatusDistribution = { draft: 2, review: 1, active: 4, inactive: 0 }

describe('StatusBar', () => {
  it('rendert einen role="img"-Balken mit sprechendem Label', () => {
    render(<StatusBar label="Playbooks" distribution={distribution} />)
    const bar = screen.getByRole('img', { name: /Playbooks:/ })
    expect(bar).toBeInTheDocument()
    // Nur Werte > 0 erzeugen ein Segment (inactive = 0 → kein Segment).
    expect(bar.querySelectorAll('span[data-status]')).toHaveLength(3)
  })

  it('verlinkt die Zahlen-Ablesung auf die vorgefilterte Liste, wenn hrefFor gesetzt ist', () => {
    render(
      <MemoryRouter>
        <StatusBar
          label="Playbooks"
          distribution={distribution}
          hrefFor={(status) => `/w/ws-1/playbooks?status=${status}`}
        />
      </MemoryRouter>,
    )
    const link = screen.getByRole('link', { name: /In Review/ })
    expect(link).toHaveAttribute('href', '/w/ws-1/playbooks?status=review')
  })

  it('rendert die Ablesung ohne Links ohne hrefFor', () => {
    render(<StatusBar label="Playbooks" distribution={distribution} />)
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })

  it('zeigt einen leeren Balken bei Gesamtsumme 0', () => {
    render(<StatusBar label="Leer" distribution={{ draft: 0, review: 0, active: 0, inactive: 0 }} />)
    const bar = screen.getByRole('img', { name: /Leer:/ })
    expect(bar.querySelectorAll('span[data-status]')).toHaveLength(0)
  })
})
