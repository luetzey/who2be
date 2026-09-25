// Responsive-Vertrag der Playbook-Listenzeile (#573, Haelfte B).
//
// Klassenvertrag, kein Layout — jsdom rechnet kein Layout. Gemessen am
// gebauten Stylesheet in Chromium (Plan-Datei): bei 320px belegte die
// `shrink-0`-Meta-Spalte mit zwei Tags 193,3px, wodurch die `min-w-0`-
// Textspalte auf 0px gerechnet wurde und Name, Beschreibung und Kind-Links
// 102px aus ihrer Box liefen. Nach dem Umbruch misst die Textspalte 194px.
//
// Weiche 3 des Issues gibt die Loesungsrichtung vor: Umbruch der Zeile
// unterhalb `md`, NICHT Streichen von `shrink-0` — die Klasse schuetzt die
// Badges vor dem Zerquetschen und bleibt deshalb stehen.

import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import type { Playbook } from '@/api/types'

import { PlaybookRow } from './PlaybookRow'

function playbook(overrides: Partial<Playbook> = {}): Playbook {
  return {
    id: 'pb1',
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name: 'Onboarding-Checkliste fuer neue Teammitglieder',
    current_version: 3,
    current_status: 'active',
    type: 'workflow',
    tags: ['produktivitaet', 'onboarding'],
    triggers: null,
    content: {
      description: 'Schritt-fuer-Schritt-Ablauf fuer den ersten Arbeitstag.',
      body: '',
      type: 'workflow',
      tags: [],
      triggers: null,
    },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
    ...overrides,
  } as Playbook
}

function renderRow(pb: Playbook = playbook()) {
  return render(
    <MemoryRouter>
      <PlaybookRow playbook={pb} wsPath={(path) => `/w/ws-1${path}`} />
    </MemoryRouter>,
  )
}

describe('PlaybookRow — Responsive', () => {
  it('bricht die Zeile unterhalb md um und bleibt ab md einzeilig', () => {
    renderRow()

    const row = screen.getByTestId('playbook-row')
    expect(row.className).toContain('flex-wrap')
    expect(row.className).toContain('md:flex-nowrap')
  })

  it('gibt der Textspalte unterhalb md eine eigene Zeile', () => {
    renderRow()

    const textColumn = screen.getByText(
      'Schritt-fuer-Schritt-Ablauf fuer den ersten Arbeitstag.',
    ).parentElement
    expect(textColumn?.className).toContain('basis-[calc(100%-3.75rem)]')
    expect(textColumn?.className).toContain('md:basis-0')
  })

  it('haelt shrink-0 an der Meta-Spalte und legt sie unterhalb md quer', () => {
    renderRow()

    const tags = screen.getByLabelText('Tags')
    const metaColumn = tags.parentElement
    // shrink-0 bleibt bewusst stehen (#573 Weiche 3).
    expect(metaColumn?.className).toContain('shrink-0')
    expect(metaColumn?.className).toContain('w-full')
    expect(metaColumn?.className).toContain('md:w-auto')
    expect(metaColumn?.className).toContain('md:flex-col')
  })

  it('hebt Composite-Umschalter und Kind-Link unterhalb md auf die von Issue #573 AK 5 geforderten 40px', () => {
    renderRow(
      playbook({
        is_composite: true,
        compose_children: [{ id: 'c1', name: 'Recherche-Playbook mit sehr langem Namen' }],
      }),
    )

    // Gemessen vorher: Umschalter 32px, Kind-Link 38px — beide ueber dem
    // Floor aus docs/frontend/design-language.md §11, beide unter der Zahl
    // aus Issue #573 AK 5. `min-h-10` hebt sie unterhalb md an, ab md faellt
    // die Zeile auf die alte Dichte zurueck.
    const toggle = screen.getByRole('button', { name: /1 Sub-Playbook/ })
    expect(toggle.className).toContain('min-h-10')
    expect(toggle.className).toContain('md:min-h-0')

    fireEvent.click(toggle)
    const childLink = screen.getByRole('link', {
      name: /Recherche-Playbook mit sehr langem Namen/,
    })
    expect(childLink.className).toContain('min-h-10')
    expect(childLink.className).toContain('md:min-h-0')
  })
})
