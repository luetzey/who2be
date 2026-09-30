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

import { fireEvent, isInaccessible, render, screen } from '@testing-library/react'
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

  it('gibt der Textspalte unterhalb md die ganze Kartenbreite', () => {
    renderRow()

    // Mobil-Spec M3: vorher `basis-[calc(100%-3.75rem)]` neben der 44-px-
    // Kachel. Die Kachel sitzt unter `md` jetzt klein in der Titelzeile.
    const textColumn = screen.getByText(
      'Schritt-fuer-Schritt-Ablauf fuer den ersten Arbeitstag.',
    ).parentElement
    expect(textColumn?.className).toContain('basis-full')
    expect(textColumn?.className).toContain('md:basis-0')
  })

  it('setzt die Typ-Kachel unter md klein in die Titelzeile, ab md gross daneben', () => {
    renderRow()

    const [large, small] = screen.getAllByTestId('playbook-type-icon')
    expect(large.className).toContain('hidden')
    expect(large.className).toContain('md:flex')
    expect(large.className).toContain('size-11')
    expect(small.className).toContain('size-8')
    expect(small.className).toContain('md:hidden')
    // Die kleine Kachel steht in derselben Zeile wie der Name; der Name
    // fuellt den Rest der Zeile statt darunter zu brechen.
    const name = screen.getByRole('link', { name: /Onboarding/ })
    expect(small.parentElement).toBe(name.parentElement)
    expect(name.className).toContain('basis-[calc(100%-2.5rem)]')
    expect(name.className).toContain('md:basis-auto')
  })

  it('kuerzt die Beschreibung auf 2 Zeilen unter md, 3 ab md (M3), ohne Mehr-Knopf', () => {
    renderRow(playbook({ content: { ...playbook().content, description: 'x '.repeat(600) } }))

    const description = screen.getByText((_, el) => el?.tagName === 'P')
    expect(description.className).toContain('line-clamp-2')
    expect(description.className).toContain('md:line-clamp-3')
    // Volltext bleibt im DOM (Screenreader), der Weg dorthin ist der Name-Link.
    expect(description.textContent).toHaveLength(1200)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('laesst den Trigger neben dem Blitz stehen statt darunter (M3)', () => {
    renderRow(playbook({ triggers: 'Wenn ein Gespraech vorbereitet werden soll' }))

    const chip = screen.getByRole('listitem')
    expect(chip.className).toContain('max-w-[calc(100%-1.375rem)]')
    expect(chip.className).toContain('min-w-0')
  })

  it('blendet die Namensliste im Composite-Umschalter unter md aus (M6)', () => {
    renderRow(
      playbook({
        is_composite: true,
        compose_children: [
          { id: 'c1', name: 'Erstes Kind' },
          { id: 'c2', name: 'Zweites Kind' },
        ],
      }),
    )

    const toggle = screen.getByRole('button', { name: /2 Sub-Playbooks/ })
    const summary = screen.getByText('Erstes Kind · Zweites Kind')
    expect(toggle).toContainElement(summary)
    expect(summary.className).toContain('hidden')
    expect(summary.className).toContain('md:inline')
    expect(summary.className).toContain('min-w-24')
  })

  it('haelt shrink-0 an der Meta-Spalte und zeigt sie erst ab md', () => {
    renderRow()

    const tags = screen.getByLabelText('Tags')
    const metaColumn = tags.parentElement
    const classes = metaColumn?.className.split(/\s+/) ?? []
    // shrink-0 bleibt bewusst stehen (#573 Weiche 3).
    expect(classes).toContain('shrink-0')
    // Owner-Entscheidung W6=b: unter md faellt die Spalte ganz weg.
    expect(classes).toContain('hidden')
    expect(classes).toContain('md:flex')
    expect(classes).toContain('flex-col')
  })

  it('deckelt die Meta-Spalte ab md, damit viele Tags die Textspalte nicht verdraengen', () => {
    // t_2a3882b4: ohne Deckel wurde die `shrink-0`-Spalte mit 12 Tags 1236px
    // breit, die Textspalte fiel auf 0px (scrollWidth 1593 bei 768). Mit
    // `md:max-w-40 lg:max-w-xs` gemessen: Text 210/306/546px bei 768/1024/1280.
    renderRow(
      playbook({
        tags: Array.from({ length: 12 }, (_, i) => `tag-${i + 1}`),
      }),
    )

    const tags = screen.getByLabelText('Tags')
    const metaColumn = tags.parentElement
    const classes = metaColumn?.className.split(/\s+/) ?? []
    // `shrink-0` darf nur mit Deckel stehen.
    expect(classes).toContain('shrink-0')
    expect(classes).toContain('md:max-w-40')
    expect(classes).toContain('lg:max-w-xs')
    // Die Tags brechen im gedeckelten Block um, statt ihn zu verbreitern.
    expect(tags.className.split(/\s+/)).toContain('flex-wrap')
    expect(tags.children).toHaveLength(12)
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

// Owner-Entscheidung W6=b (t_1c5a1a34): unter `md` zeigt die Zeile nur Name,
// Status und Beschreibung. Geprueft wird der Accessibility-Tree, nicht nur die
// Klasse — ein nur visuell verstecktes Element (`sr-only`, `opacity-0`) liesse
// den Screenreader auf dem Telefon weiter zwoelf Tags vorlesen.
//
// jsdom rechnet keine Media-Queries. Das Stylesheet spielt deshalb die
// Tailwind-Kaskade je Breakpoint nach: `hidden` gilt immer, `md:flex` nur ab md
// (im gebauten CSS steht `md:flex` im @media-Block nach `hidden`).
describe('PlaybookRow — Trigger und Tags unter md (W6=b)', () => {
  const BELOW_MD = '.hidden { display: none; }'
  const FROM_MD = `${BELOW_MD} .md\\:flex { display: flex; }`

  function withCascade(css: string) {
    const style = document.createElement('style')
    style.textContent = css
    document.head.append(style)
    return () => style.remove()
  }

  const manyTags = () =>
    playbook({
      tags: Array.from({ length: 12 }, (_, i) => `tag-${i + 1}`),
      triggers: 'Wenn ein Gespraech vorbereitet werden soll',
    })

  it('nimmt Trigger-Liste und Tag-Gruppe unter md aus dem Accessibility-Tree', () => {
    const cleanup = withCascade(BELOW_MD)
    try {
      renderRow(manyTags())

      expect(screen.queryByRole('list', { name: 'Trigger-Liste' })).not.toBeInTheDocument()
      expect(screen.queryAllByRole('listitem')).toHaveLength(0)
      // Die Tag-Gruppe hat keine Rolle; `isInaccessible` ist dieselbe Pruefung,
      // mit der Testing Library Elemente aus dem Accessibility-Tree ausschliesst.
      expect(isInaccessible(screen.getByLabelText('Tags'))).toBe(true)
      expect(isInaccessible(screen.getByText('tag-1'))).toBe(true)
      // Name, Status und Beschreibung bleiben.
      expect(screen.getByRole('link', { name: /Onboarding/ })).toBeVisible()
      expect(screen.getByText(/Aktiv · v3/)).toBeVisible()
      expect(screen.getByText('Schritt-fuer-Schritt-Ablauf fuer den ersten Arbeitstag.')).toBeVisible()
    } finally {
      cleanup()
    }
  })

  it('zeigt Trigger-Liste und Tag-Gruppe ab md', () => {
    const cleanup = withCascade(FROM_MD)
    try {
      renderRow(manyTags())

      expect(screen.getByRole('list', { name: 'Trigger-Liste' })).toBeInTheDocument()
      expect(screen.getByRole('listitem')).toHaveTextContent(
        'Wenn ein Gespraech vorbereitet werden soll',
      )
      expect(isInaccessible(screen.getByLabelText('Tags'))).toBe(false)
      expect(screen.getByText('tag-1')).toBeVisible()
      expect(screen.getByText('tag-12')).toBeVisible()
    } finally {
      cleanup()
    }
  })
})
