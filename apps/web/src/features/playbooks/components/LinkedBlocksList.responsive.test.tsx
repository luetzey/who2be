// Responsive-Vertrag der verknuepften Bloecke (#573, Haelfte B).
//
// Klassenvertrag, kein Layout — jsdom rechnet kein Layout. Gemessen am
// gebauten Stylesheet in Chromium (Plan-Datei): bei 320px belegte die
// `shrink-0`-Aktionsspalte 144,1px, dem Resource-Namen blieben 105,9px und er
// lief 78px aus seiner Box; nach dem Umbruch 262px und kein Ueberlauf.

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import type { ResourceLink } from '@/api/types'

import { LinkedBlocksList } from './LinkedBlocksList'

const longLink: ResourceLink = {
  resource_id: 'c0ffee12-3456-7890-abcd-ef0123456789',
  resource_name: 'Compliance-Handbuch-Kapitel-Datenschutzgrundverordnung',
  block_id: 'abschnitt-4-2-auftragsverarbeitung',
  position: 0,
  available: true,
  available_in: 'active',
  preview: null,
  section_preview: 'c0ffee12-3456-7890-abcd-ef0123456789#abschnitt-4-2-auftragsverarbeitung',
}

describe('LinkedBlocksList — Responsive', () => {
  it('laesst den Listeneintrag umbrechen und gibt der Textspalte eine eigene Zeile', () => {
    render(<LinkedBlocksList links={[longLink]} onRemove={() => {}} />)

    const item = screen.getByText(longLink.resource_name).closest('li')
    expect(item).not.toBeNull()
    expect(item?.className).toContain('flex-wrap')

    const textColumn = screen.getByText(longLink.resource_name).parentElement
    expect(textColumn?.className).toContain('basis-full')
    expect(textColumn?.className).toContain('md:basis-0')
  })

  it('bricht lange Resource-Namen um, statt sie ueberlaufen zu lassen', () => {
    render(<LinkedBlocksList links={[longLink]} onRemove={() => {}} />)

    expect(screen.getByText(longLink.resource_name).className).toContain('break-words')
  })

  it('hebt die Entfernen-Aktion unterhalb md auf die von Issue #573 AK 5 geforderten 40px', () => {
    render(<LinkedBlocksList links={[longLink]} onRemove={() => {}} />)

    // `size="sm"` liefert h-9 (36px) — ueber dem Floor aus
    // docs/frontend/design-language.md §11 und dort als Zeilen-Aktion
    // zulaessig, aber unter der Zahl, die Issue #573 AK 5 verlangt.
    // `h-10` loest das h-9 per tailwind-merge unterhalb md ab.
    const button = screen.getByRole('button', { name: 'Entfernen' })
    expect(button.className).toContain('h-10')
    expect(button.className).toContain('md:h-9')
  })
})
