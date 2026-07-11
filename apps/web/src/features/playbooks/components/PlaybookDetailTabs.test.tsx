import { fireEvent, render, screen } from '@testing-library/react'
import { useState } from 'react'
import { describe, expect, it } from 'vitest'

import { Workflow } from 'lucide-react'

import { playbookTypeMeta } from '../lib/typeMeta'
import { PlaybookDetailTabs, type PlaybookDetailTab } from './PlaybookDetailTabs'

function Harness({ initial = 'edit' as PlaybookDetailTab }) {
  const [active, setActive] = useState<PlaybookDetailTab>(initial)
  return <PlaybookDetailTabs active={active} onChange={setActive} />
}

describe('PlaybookDetailTabs', () => {
  it('markiert den aktiven Tab (aria-selected + roving tabindex)', () => {
    render(<Harness />)
    const edit = screen.getByRole('tab', { name: 'Bearbeiten' })
    const relations = screen.getByRole('tab', { name: 'Beziehungen' })
    expect(edit).toHaveAttribute('aria-selected', 'true')
    expect(edit).toHaveAttribute('tabindex', '0')
    expect(relations).toHaveAttribute('aria-selected', 'false')
    expect(relations).toHaveAttribute('tabindex', '-1')

    fireEvent.click(relations)
    expect(relations).toHaveAttribute('aria-selected', 'true')
  })

  it('navigiert per Pfeiltasten zyklisch durch die Tabs', () => {
    render(<Harness />)
    const edit = screen.getByRole('tab', { name: 'Bearbeiten' })

    fireEvent.keyDown(edit, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: 'Beziehungen' })).toHaveAttribute(
      'aria-selected',
      'true',
    )

    // ArrowLeft vom ersten Tab wrappt ans Ende.
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Beziehungen' }), {
      key: 'ArrowLeft',
    })
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Bearbeiten' }), {
      key: 'ArrowLeft',
    })
    expect(screen.getByRole('tab', { name: 'Versionen' })).toHaveAttribute(
      'aria-selected',
      'true',
    )

    // Andere Tasten aendern nichts.
    fireEvent.keyDown(screen.getByRole('tab', { name: 'Versionen' }), { key: 'Enter' })
    expect(screen.getByRole('tab', { name: 'Versionen' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })
})

describe('playbookTypeMeta', () => {
  it('liefert die Typ-Zuordnung und faellt bei Unbekanntem auf die Snippet-Tint zurueck', () => {
    expect(playbookTypeMeta('workflow').icon).toBe(Workflow)
    expect(playbookTypeMeta('workflow').tint).toContain('pill-catalog')
    expect(playbookTypeMeta('unbekannt').tint).toContain('pill-tools')
    expect(playbookTypeMeta(undefined).tint).toContain('pill-tools')
  })
})
