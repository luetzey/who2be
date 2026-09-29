import { render, screen } from '@testing-library/react'
import { Clock, TriangleAlert } from 'lucide-react'
import { describe, expect, it } from 'vitest'

import { AttentionBanner } from './AttentionBanner'

describe('AttentionBanner', () => {
  it('rendert Titel, Beschreibung und Actions', () => {
    render(
      <AttentionBanner
        icon={Clock}
        title="Version 3 liegt zur Review"
        description="Von Max Berger eingereicht."
        actions={<button type="button">Aktivieren</button>}
      />,
    )
    expect(screen.getByText('Version 3 liegt zur Review')).toBeInTheDocument()
    expect(screen.getByText('Von Max Berger eingereicht.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Aktivieren' })).toBeInTheDocument()
  })

  it('nutzt die brand-Flaeche als Default', () => {
    const { container } = render(<AttentionBanner icon={Clock} title="Hinweis" />)
    expect((container.firstElementChild as HTMLElement).className).toContain('bg-brand/10')
  })

  // Audit A4: `text-muted-foreground` auf `bg-brand/10` mass 4,31:1 bei 12 px
  // (hell). Die Beschreibung laeuft deshalb auf `text-foreground/80`; die
  // gemessenen Werte stehen im PR. jsdom kann Kontrast nicht messen, der Test
  // haelt die Token-Wahl fest.
  it('setzt die Beschreibung kontraststark statt in muted-foreground', () => {
    render(<AttentionBanner icon={Clock} title="Hinweis" description="Beschreibung" />)
    const description = screen.getByText('Beschreibung')
    expect(description).toHaveClass('text-foreground/80')
    expect(description).not.toHaveClass('text-muted-foreground')
  })

  // Lange Direktlink-Beschriftungen (Entitaetsnamen) duerfen auf 390 px nicht
  // aus dem Banner laufen: der Action-Slot ist schrumpffaehig und begrenzt.
  it('begrenzt den Action-Slot auf die Bannerbreite', () => {
    render(
      <AttentionBanner
        icon={Clock}
        title="Hinweis"
        actions={<a href="/x">Sehr langer Link</a>}
      />,
    )
    const slot = screen.getByRole('link', { name: 'Sehr langer Link' }).parentElement!
    expect(slot).toHaveClass('min-w-0', 'max-w-full')
  })

  it('rendert die destructive-Variante', () => {
    const { container } = render(
      <AttentionBanner icon={TriangleAlert} title="Entwurf unvollstaendig" variant="destructive" />,
    )
    expect((container.firstElementChild as HTMLElement).className).toContain('bg-destructive/10')
  })
})
