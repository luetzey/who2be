import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { DashboardActivity } from '@/api/types'

import { ActivityRow } from './ActivityRow'

const LONG_NAME =
  'Gesprächsleitfaden für schwierige Mitarbeitergespräche in der Probezeit mit Eskalationspfad'

const activity: DashboardActivity = {
  ts: '2026-09-29T10:00:00Z',
  entity_type: 'playbook',
  entity_id: 'pb-1',
  entity_name: LONG_NAME,
  event: 'submitted_for_review',
  to_version: 4,
  actor: { user_id: 'u1', display_name: 'audit-bot-vertrieb-nord' },
}

// Mobil-Spec M6 (Paket P7): Die Aktivitaetszeile ist kein Link und hat sonst
// keinen Weg zum Volltext. Vorher `truncate` — bei 320 px blieben 75 px vom
// Satz sichtbar, der Rest war fuer Touch-Nutzer unerreichbar (Hover zaehlt
// nicht). jsdom hat kein Layout, deshalb Klassen-Vertrag; die gerenderte
// Messung steht im Plan `.claude/plan/2026-10-01-1500_mobil-p7-kleinteile.md`.
describe('ActivityRow — Volltext statt Ellipse (Mobil-Spec M6)', () => {
  it('bricht den Satz um, statt ihn mit „…“ zu kuerzen', () => {
    render(<ActivityRow activity={activity} />)
    const text = screen.getByTestId('activity-text')
    expect(text).toHaveClass('wrap-anywhere')
    expect(text).not.toHaveClass('truncate')
    expect(text).toHaveTextContent(LONG_NAME)
    expect(text).toHaveTextContent('v4')
  })

  it('stellt die Zeit unter md unter den Satz und ab md daneben', () => {
    render(<ActivityRow activity={activity} />)
    const column = screen.getByTestId('activity-text').parentElement
    expect(column).toHaveClass('flex-col', 'md:flex-row')
    expect(column?.querySelector('time')).toHaveAttribute('datetime', activity.ts)
  })
})
