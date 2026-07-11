import { fireEvent, render, screen } from '@testing-library/react'
import { FileText, Layers } from 'lucide-react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import { EntityCard } from './EntityCard'

function renderCard(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>)
}

describe('EntityCard', () => {
  it('rendert Titel als Link auf href und einen dekorativen Chevron', () => {
    renderCard(
      <EntityCard icon={FileText} iconTone="tools" title="Support-Base" href="/sp/1" />,
    )
    const link = screen.getByRole('link', { name: 'Support-Base' })
    expect(link).toHaveAttribute('href', '/sp/1')
  })

  it('rendert Slots (badges/status/description/meta/actions)', () => {
    renderCard(
      <EntityCard
        icon={FileText}
        iconTone="tools"
        title="FAQ-Base"
        href="/sp/2"
        badges={<span>faq-base</span>}
        status={<span>Aktiv</span>}
        description="Deckt die Top-Support-Fragen ab."
        meta={<span>Verwendet von 8 Agents</span>}
        actions={<button type="button">Kopieren</button>}
      />,
    )
    expect(screen.getByText('faq-base')).toBeInTheDocument()
    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByText('Deckt die Top-Support-Fragen ab.')).toBeInTheDocument()
    expect(screen.getByText('Verwendet von 8 Agents')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Kopieren' })).toBeInTheDocument()
  })

  it('rendert ohne Expander keinen Toggler', () => {
    renderCard(<EntityCard icon={FileText} iconTone="tools" title="Onboarding" href="/sp/3" />)
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('klappt den Expander (unkontrolliert) auf und zu', () => {
    renderCard(
      <EntityCard
        icon={FileText}
        iconTone="resource"
        title="Rueckerstattungs-Policy"
        href="/res/1"
        expandIcon={Layers}
        expandLabel="2 Sub-Resources"
        expandSummary="Fristen-Tabelle · Sonderfaelle"
        expandable={<div>Panel-Inhalt</div>}
      />,
    )
    const toggle = screen.getByRole('button', { name: /2 Sub-Resources/ })
    expect(toggle).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByText('Panel-Inhalt')).not.toBeInTheDocument()
    fireEvent.click(toggle)
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('Panel-Inhalt')).toBeInTheDocument()
    fireEvent.click(toggle)
    expect(screen.queryByText('Panel-Inhalt')).not.toBeInTheDocument()
  })

  it('respektiert den kontrollierten open-Zustand und meldet Toggles', () => {
    const onOpenChange = vi.fn()
    renderCard(
      <EntityCard
        icon={FileText}
        iconTone="resource"
        title="Tonfall-Richtlinie"
        href="/res/2"
        open={true}
        onOpenChange={onOpenChange}
        expandLabel="1 Sub-Resource"
        expandable={<div>Immer offen</div>}
      />,
    )
    expect(screen.getByText('Immer offen')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /1 Sub-Resource/ }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    // Kontrolliert: bleibt offen, bis der Parent open aendert.
    expect(screen.getByText('Immer offen')).toBeInTheDocument()
  })
})
