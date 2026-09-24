import { render, screen } from '@testing-library/react'
import { Bot } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { EntityCard } from './EntityCard'

// Responsive-Vertrag (Primitive-Fund 2 aus dem Audit #570 Haelfte A).
//
// PR #606 hat den description-Absatz und die `DetailHeader`-H1 mit
// `break-words` versehen, den Titel-Link derselben Komponente aber
// ausgelassen. Ein snake_case-Agentenname misst gemessen 282,5 px und lief bei
// 320 px 116,5 px ueber die 166 px breite Textspalte. Trifft jede Listenseite.
//
// jsdom hat kein Layout; das hier ist ein Klassen-Vertrag. Die Layout-Aussage
// ist in .claude/plan/2026-09-23-1700_primitives-tabslist-entitycard-hit-target.md
// gerendert belegt (Chromium gegen das gebaute Stylesheet, 320/375/768/1024 px).

function renderCard(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

const SNAKE = 'kundenservice_eskalation_stufe_zwei_bot'

describe('EntityCard — Responsive (Primitive-Fund #570/A)', () => {
  // `break-words` (= `overflow-wrap: break-word`) waere hier wirkungslos, und
  // zwar aus zwei unabhaengigen Gruenden — beide gemessen:
  //
  // 1. Der Titel-Link ist ein Flex-Item der `flex flex-wrap`-Titelzeile und
  //    hat damit `min-width: auto`. `break-word` senkt die min-content-Breite
  //    eines Elements NICHT; das Item bleibt 282,5 px breit. Gemessen: mit
  //    `break-words` allein blieb der Ueberlauf exakt bei +116,5 px, also
  //    unveraendert gegenueber dem Ist-Zustand.
  // 2. Selbst mit `min-w-0` greift `break-word` bei reinem snake_case nur,
  //    weil das Wort als Ganzes nicht passt — bei einem Titel aus mehreren
  //    Woertern, von denen eines zu lang ist, bliebe der Rest ungebrochen.
  //
  // `wrap-anywhere` (= `overflow-wrap: anywhere`) senkt die min-content-Breite
  // mit und braucht deshalb kein zusaetzliches `min-w-0` an dieser Stelle.
  // Gegen `break-all` entschieden, weil `break-all` bedingungslos mitten im
  // Wort bricht: gemessen zerlegte es "Kundenservice Eskalation Stufe Zwei" in
  // Zeilen von 165,8 / 82,5 px (mitten im Wort), waehrend `wrap-anywhere`
  // dieselbe Zeile an den Leerzeichen bei 100,4 / 143,9 px umbricht. Bei einem
  // Titel ohne Trennstelle sind beide identisch (165,8 / 116,7 px) — der
  // Unterschied trifft nur gewoehnliche Titel, und die sind der Regelfall.
  it('erlaubt dem Titel-Link den Umbruch innerhalb eines Bezeichners', () => {
    renderCard(<EntityCard icon={Bot} iconTone="persona" title={SNAKE} href="/agents/1" />)
    expect(screen.getByRole('link', { name: SNAKE })).toHaveClass('wrap-anywhere')
  })

  // Die Umbruch-Erlaubnis allein reicht nicht: traegt die Karte
  // Zeilen-Actions (AgentsPage: favorite-toggle + "Einrichten"), kollabiert
  // die `min-w-0 flex-1`-Textspalte bei 320 px gemessen auf 0 px Breite. Der
  // Titel bricht dann nach JEDEM Zeichen um und die Karte waechst von 762 auf
  // 1522 px Hoehe — eine schlimmere Regression als der Ausgangsdefekt.
  //
  // `min-w-32` (8rem) gibt der Spalte eine Untergrenze. Ohne `flex-wrap` am
  // Karten-Body wuerde diese Untergrenze die Actions gemessen 105 px ueber
  // den Rand schieben (body 425 px in 320 px); mit `flex-wrap` rutschen sie
  // bei Bedarf in die naechste Zeile. Beide Klassen sind gemessen noetig:
  // `flex-wrap` allein liess 375 px bei 44,7 px Spaltenbreite stehen,
  // `min-w-32` allein erzeugte den Body-Ueberlauf.
  it('haelt die Textspalte breit genug, statt sie kollabieren zu lassen', () => {
    const { container } = renderCard(
      <EntityCard
        icon={Bot}
        iconTone="persona"
        title={SNAKE}
        href="/agents/1"
        description="Automatische Eskalation zweiter Stufe."
        actions={<button type="button">Einrichten</button>}
      />,
    )
    const textColumn = screen.getByRole('link', { name: SNAKE }).closest('div')?.parentElement
    expect(textColumn).toHaveClass('min-w-32')

    const article = container.querySelector('article')
    expect(article).toHaveClass('flex-wrap')
  })

  // Ab `md` gibt es den Defekt nicht: die Spalte misst dort gemessen 437,7 px
  // und der Titel passt mit 282,5 px hinein. Die Mindestbreite bleibt
  // trotzdem gefahrlos stehen — sie ist eine Unter-, keine Festbreite, und
  // `flex-1` gewinnt darueber. Desktop-Gegenprobe: Karte unveraendert 84 px
  // hoch bei 768 und 1024 px, Titel einzeilig.
  it('laesst den Desktop-Zustand unveraendert (Titel einzeilig, flex-1 gewinnt)', () => {
    renderCard(<EntityCard icon={Bot} iconTone="persona" title={SNAKE} href="/agents/1" />)
    const textColumn = screen.getByRole('link', { name: SNAKE }).closest('div')?.parentElement
    expect(textColumn).toHaveClass('flex-1')
  })
})
