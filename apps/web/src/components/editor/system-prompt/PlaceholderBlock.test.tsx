// PlaceholderBlock.test.tsx — Pill-Render fuer alle vier Placeholder-Kinds.
// BlockNote-Insel ist in jsdom nicht mountfaehig — wir rendern die Pill-
// Komponente direkt als React-Element, da createReactInlineContentSpec ein
// normales React-FC als `render` akzeptiert.

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { KIND_META_TEST_EXPORT, PlaceholderPill } from './PlaceholderBlock.test-utils'

// Wir exportieren zu Testzwecken die Pill-Render-Funktion separat, damit wir
// sie ohne vollen BlockNote-Kontext rendern koennen. Siehe PlaceholderBlock.test-utils.tsx.
describe('PlaceholderPill', () => {
  it('rendert Playbook-Pill mit BookOpen-Klasse und Label', () => {
    render(<PlaceholderPill kind="playbook" label="Playbook: Reset-Mail" target_id="abc" />)
    const pill = screen.getByTestId('placeholder-pill-playbook')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveTextContent('Playbook: Reset-Mail')
  })

  it('rendert Resource-Pill', () => {
    render(<PlaceholderPill kind="resource" label="Resource: FAQ-Doc" target_id="def" />)
    const pill = screen.getByTestId('placeholder-pill-resource')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveTextContent('Resource: FAQ-Doc')
  })

  it('rendert Persona-Feld-Pill', () => {
    render(<PlaceholderPill kind="persona-field" label="Persona: Name" target_id="name" />)
    const pill = screen.getByTestId('placeholder-pill-persona-field')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveTextContent('Persona: Name')
  })

  it('rendert Datum-Pill', () => {
    render(<PlaceholderPill kind="date" label="Datum (lesbar)" target_id="human" />)
    const pill = screen.getByTestId('placeholder-pill-date')
    expect(pill).toBeInTheDocument()
    expect(pill).toHaveTextContent('Datum (lesbar)')
  })

  it('faellt auf labelPrefix zurueck wenn label leer ist', () => {
    render(<PlaceholderPill kind="date" label="" target_id="" />)
    const pill = screen.getByTestId('placeholder-pill-date')
    expect(pill).toHaveTextContent('Datum')
  })

  it('alle vier Kinds haben unterschiedliche pill-Klassen (distinct color)', () => {
    const kinds = ['playbook', 'resource', 'persona-field', 'date'] as const
    const pillClasses = kinds.map((k) => KIND_META_TEST_EXPORT[k].pillClass)
    const unique = new Set(pillClasses)
    expect(unique.size).toBe(4)
  })
})
