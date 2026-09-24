import { render, screen } from '@testing-library/react'
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
})
