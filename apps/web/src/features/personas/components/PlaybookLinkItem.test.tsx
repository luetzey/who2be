import { fireEvent, render, screen } from '@testing-library/react'
import { Plus, X } from 'lucide-react'
import { describe, expect, it, vi } from 'vitest'

import { PlaybookLinkItem } from './PlaybookLinkItem'

function renderItem(props?: Partial<Parameters<typeof PlaybookLinkItem>[0]>) {
  const onAction = vi.fn()
  render(
    <ul>
      <PlaybookLinkItem
        name="Coaching"
        actionLabel="Verknüpfen"
        actionIcon={Plus}
        onAction={onAction}
        {...props}
      />
    </ul>,
  )
  return { onAction }
}

describe('PlaybookLinkItem', () => {
  it('rendert Name und Aktions-Schaltflaeche', () => {
    renderItem()

    expect(screen.getByText('Coaching')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Verknüpfen' })).toBeInTheDocument()
  })

  it('triggert onAction beim Klick auf die Schaltflaeche', () => {
    const { onAction } = renderItem()

    fireEvent.click(screen.getByRole('button', { name: 'Verknüpfen' }))

    expect(onAction).toHaveBeenCalledTimes(1)
  })

  it('rendert den optionalen Status-Slot und eine „Entfernen"-Aktion', () => {
    renderItem({
      status: <span>Aktiv</span>,
      actionLabel: 'Entfernen',
      actionIcon: X,
    })

    expect(screen.getByText('Aktiv')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Entfernen' })).toBeInTheDocument()
  })

  it('deaktiviert die Schaltflaeche bei disabled', () => {
    const { onAction } = renderItem({ disabled: true })

    const button = screen.getByRole('button', { name: 'Verknüpfen' })
    expect(button).toBeDisabled()
    fireEvent.click(button)
    expect(onAction).not.toHaveBeenCalled()
  })

  it('zeigt den Referenz-Badge mit Hinweis, wenn referenced gesetzt ist', () => {
    renderItem({
      referenced: true,
      referencedLabel: 'Im Text referenziert',
      referencedHint: 'Nur ein Hinweis.',
    })

    const badge = screen.getByText('Im Text referenziert')
    expect(badge).toBeInTheDocument()
    // Hinweis liegt als natives title-Tooltip am Badge (rein informativ).
    expect(badge).toHaveAttribute('title', 'Nur ein Hinweis.')
    // Die Aktion bleibt uneingeschraenkt nutzbar (kein Lock).
    expect(screen.getByRole('button', { name: 'Verknüpfen' })).toBeEnabled()
  })

  it('zeigt keinen Referenz-Badge, wenn referenced nicht gesetzt ist', () => {
    renderItem({ referencedLabel: 'Im Text referenziert' })

    expect(screen.queryByText('Im Text referenziert')).not.toBeInTheDocument()
  })

  // Responsive-Audit #571 (Haelfte B): AK 3 des Audits nennt diese Zeile
  // ausdruecklich und setzt die Schwelle dieses Pakets auf 40 px unterhalb
  // `md`. Gemessen lag die Aktion bei 36 px (`size="sm"`) — nach der Norm
  // (§11) zulaessig, aber unter dem Akzeptanzkriterium. `h-10 md:h-9` hebt den
  // Phone-Fall und laesst die Verdichtung ab `md` unangetastet; `cn()` loest
  // das `h-9` der Variante ueber tailwind-merge auf.
  it('hebt die Aktion unterhalb `md` auf das Hit-Target aus AK 3', () => {
    renderItem()

    const button = screen.getByRole('button', { name: 'Verknüpfen' })
    expect(button.className).toContain('h-10')
    expect(button.className).toContain('md:h-9')
    expect(button.className).not.toMatch(/(^|\s)h-9(\s|$)/)
  })
})
