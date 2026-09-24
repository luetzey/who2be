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

  // §4.4 Checklistenpunkt 3: feste Breiten auf Container-Ebene brauchen eine
  // responsive Abfederung. Das Label ist die Achsenbeschriftung des Balkens und
  // bleibt stehen (#563 Weiche 1) — nur seine Breite federt ab.
  it('federt die Label-Breite responsiv ab, statt sie fest auf w-24 zu binden', () => {
    render(<StatusBar label="Playbooks" distribution={distribution} />)
    const labelNode = screen.getByText('Playbooks')
    expect(labelNode).toHaveClass('w-20', 'truncate', 'md:w-24')
    // Kein nacktes `w-24` mehr: auf 320px bliebe dem Balken sonst nach Label,
    // zwei gap-4 und der Zahlen-Ablesung kaum Platz.
    expect(labelNode.className).not.toMatch(/(^|\s)w-24(\s|$)/)
  })

  it('zeigt einen leeren Balken bei Gesamtsumme 0', () => {
    render(<StatusBar label="Leer" distribution={{ draft: 0, review: 0, active: 0, inactive: 0 }} />)
    const bar = screen.getByRole('img', { name: /Leer:/ })
    expect(bar.querySelectorAll('span[data-status]')).toHaveLength(0)
  })
})
