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
})
