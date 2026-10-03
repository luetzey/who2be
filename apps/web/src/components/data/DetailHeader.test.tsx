import { fireEvent, render, screen } from '@testing-library/react'
import { FileText } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { DetailHeader } from './DetailHeader'

function renderHeader(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('DetailHeader', () => {
  it('rendert H1, Badges, Beschreibung und Actions', () => {
    renderHeader(
      <DetailHeader
        icon={FileText}
        iconTone="tools"
        title="Support-Base"
        badges={<span>support-base</span>}
        description="Grund-Prompt fuer Support-Gespraeche."
        actions={<button type="button">Duplizieren</button>}
      />,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Support-Base' })).toBeInTheDocument()
    expect(screen.getByText('support-base')).toBeInTheDocument()
    expect(screen.getByText('Grund-Prompt fuer Support-Gespraeche.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Duplizieren' })).toBeInTheDocument()
  })

  it('bricht einen langen Titel ohne Trennstellen in der H1 um', () => {
    // 320px: ein Bezeichner ohne Trennstelle liefe sonst ueber den Rand.
    // Zwei Klassen tragen den Umbruch, beide sind noetig:
    // - `break-words` (overflow-wrap: break-word) erlaubt den Bruch im Wort,
    // - `min-w-0` hebt das `min-width: auto` des Flex-Items auf; ohne das
    //   blaeht sich die H1 auf die ungebrochene Wortbreite auf, bevor der
    //   Umbruch greift (bei 320px gemessen: 365,8px statt 206px).
    // Das `min-w-0` der Elternkette liegt eine Ebene ueber dem Flex-Container
    // und schuetzt die H1 nicht.
    renderHeader(
      <DetailHeader
        icon={FileText}
        iconTone="tools"
        title="supercalifragilisticexpialidocious-mcp-server-produktion"
      />,
    )
    expect(screen.getByRole('heading', { level: 1 })).toHaveClass('break-words', 'min-w-0')
  })

  it('rendert den Zurueck-Link nur mit backHref', () => {
    const { rerender } = renderHeader(
      <DetailHeader icon={FileText} iconTone="tools" title="Ohne Back" />,
    )
    expect(screen.queryByRole('link')).not.toBeInTheDocument()

    rerender(
      <MemoryRouter>
        <DetailHeader
          icon={FileText}
          iconTone="tools"
          title="Mit Back"
          backHref="/system-prompts"
          backLabel="System-Prompts"
        />
      </MemoryRouter>,
    )
    expect(screen.getByRole('link', { name: 'System-Prompts' })).toHaveAttribute(
      'href',
      '/system-prompts',
    )
  })

  // Audit A13 / #624: jsdom rendert kein CSS — die Zusicherung liegt deshalb
  // auf den Klassen, die die Sichtbarkeit tragen (Phone: `hidden`, ab md:
  // `md:flex`), plus dem ARIA-Vertrag des Knopfs. Die echte Sichtbarkeit je
  // Viewport belegt `e2e/status-actions-viewport.spec.ts`.
  it('klappt mit collapseActionsBelowMd die Aktionen hinter „Mehr" ein', () => {
    renderHeader(
      <DetailHeader
        icon={FileText}
        iconTone="tools"
        title="Persona"
        collapseActionsBelowMd
        actions={<button type="button">Duplizieren</button>}
      />,
    )
    const more = screen.getByRole('button', { name: 'Mehr' })
    expect(more).toHaveClass('md:hidden')
    expect(more).toHaveAttribute('aria-expanded', 'false')
    // Ab md Basis auto zurueck — sonst quetschen die offenen Aktionen den
    // Titel auf Tablet-Breite zusammen (CI-Befund tablet-ipad-gen-7).
    const titleBlock = screen.getByRole('heading', { level: 1 }).closest('header > div')
    expect(titleBlock).toHaveClass('flex-1', 'md:flex-initial')

    const slot = document.getElementById(more.getAttribute('aria-controls') ?? '')
    expect(slot).not.toBeNull()
    expect(slot).toContainElement(screen.getByRole('button', { name: 'Duplizieren' }))
    expect(slot).toHaveClass('hidden', 'md:flex')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(slot).toHaveClass('flex', 'md:flex')
    expect(slot).not.toHaveClass('hidden')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'false')
    expect(slot).toHaveClass('hidden')
  })

  it('laesst die Aktionen ohne Opt-in offen und rendert keinen „Mehr"-Knopf', () => {
    renderHeader(
      <DetailHeader
        icon={FileText}
        iconTone="tools"
        title="Agent"
        actions={<button type="button">Copy</button>}
      />,
    )
    expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument()
    const copy = screen.getByRole('button', { name: 'Copy' })
    expect(copy.parentElement).toHaveClass('flex')
    expect(copy.parentElement).not.toHaveClass('hidden')
  })

  it('rendert ohne Aktionen auch mit Opt-in keinen „Mehr"-Knopf', () => {
    renderHeader(
      <DetailHeader icon={FileText} iconTone="tools" title="Leer" collapseActionsBelowMd />,
    )
    expect(screen.queryByRole('button', { name: 'Mehr' })).not.toBeInTheDocument()
  })

  // Audit A8 (PM-Entscheidung A): die Chip-Reihenfolge legt der Header fest,
  // nicht die Seite. Die Zusicherung liest die Reihenfolge der Geschwister in
  // der Titelzeile — egal in welcher Reihenfolge die Props uebergeben werden.
  it('rendert die Meta-Chips in der festen Reihenfolge Status · Version · Sprache · Slug · Tags', () => {
    renderHeader(
      <DetailHeader
        icon={FileText}
        iconTone="tools"
        title="Support-Base"
        tags={<span data-testid="slot-tags">billing</span>}
        slug="support-base"
        locale="de"
        version={3}
        status={<span data-testid="slot-status">Aktiv</span>}
        badges={<span data-testid="slot-extra">extra</span>}
      />,
    )
    const heading = screen.getByRole('heading', { level: 1 })
    const row = heading.parentElement
    expect(row).not.toBeNull()
    const order = Array.from(row?.children ?? []).map(
      (el) => el.getAttribute('data-testid') ?? el.textContent,
    )
    expect(order).toEqual([
      'Support-Base',
      'slot-status',
      'detail-header-version',
      'DE',
      'detail-header-slug',
      'slot-tags',
      'slot-extra',
    ])
    expect(screen.getByTestId('detail-header-version')).toHaveTextContent('v3')
    // #564/#566: der Slug braucht Umbruch + Cap, sonst 497 px bei 320 px.
    expect(screen.getByTestId('detail-header-slug')).toHaveClass(
      'max-w-full',
      'font-mono',
      'break-all',
    )
  })

  it('laesst leere Meta-Slots weg', () => {
    renderHeader(
      <DetailHeader icon={FileText} iconTone="tools" title="Agent" slug="" locale="" />,
    )
    const row = screen.getByRole('heading', { level: 1 }).parentElement
    expect(row?.children).toHaveLength(1)
    expect(screen.queryByTestId('detail-header-version')).not.toBeInTheDocument()
    expect(screen.queryByTestId('detail-header-slug')).not.toBeInTheDocument()
  })
})
