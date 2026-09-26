import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import { LegalArticle, LegalSection } from './LegalArticle'

function renderArticle() {
  return render(
    <MemoryRouter>
      <LegalArticle title="Allgemeine Geschaeftsbedingungen (AGB)">
        <LegalSection heading="1. Geltungsbereich">
          <p>Inhalt</p>
        </LegalSection>
      </LegalArticle>
    </MemoryRouter>,
  )
}

// Responsive-Audit #567 (W3, Epic #431): jsdom hat kein Layout, geprueft wird
// deshalb der Klassen-Vertrag. Die Layout-Aussage ist am gerenderten Baum
// belegt (Plandatei .claude/plan/2026-09-23-0750_567-…): bei 320px Viewport
// misst der Titeltext der AGB-Seite 337px gegen 288px Lesespalte (49px
// Ueberlauf) und erzeugt horizontalen Body-Scroll; mit `text-2xl` sind es
// gemessen 288px = Spaltenbreite.
describe('LegalArticle — 320px (#567)', () => {
  it('stuft den Seitentitel unterhalb sm ab, statt aus der Lesespalte zu laufen', () => {
    renderArticle()
    const classes = screen
      .getByRole('heading', { level: 1, name: /Geschaeftsbedingungen/ })
      .className.split(/\s+/)

    // Mobile-first: die praefixlose Klasse ist der Phone-Fall, `sm:` stellt
    // den bisherigen Desktop-Zustand wieder her.
    expect(classes).toContain('text-2xl')
    expect(classes).toContain('sm:text-3xl')
    expect(classes).not.toContain('text-3xl')
  })

  it('laesst langen Fliesstext am gemeinsamen Prose-Traeger umbrechen', () => {
    renderArticle()
    const article = screen
      .getByRole('heading', { level: 1, name: /Geschaeftsbedingungen/ })
      .closest('article') as HTMLElement

    // Weiche 2 des Issues: `break-words` einmal am gemeinsamen Traeger, nicht
    // je Seite — es deckt die vier Rechtstexte und die Placeholder-Chips in
    // einem Zug ab. `break-all` ist dort ausdruecklich verworfen.
    const classes = article.className.split(/\s+/)
    expect(classes).toContain('break-words')
    expect(classes).not.toContain('break-all')
  })
})
