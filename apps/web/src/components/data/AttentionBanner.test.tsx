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

  it('rendert die destructive-Variante', () => {
    const { container } = render(
      <AttentionBanner icon={TriangleAlert} title="Entwurf unvollstaendig" variant="destructive" />,
    )
    expect((container.firstElementChild as HTMLElement).className).toContain('bg-destructive/10')
  })
})
