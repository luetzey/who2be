import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

// Responsive-Vertrag der Tab-Leiste (Mobil-Spec M7, Owner-Weiche W1=a).
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag. Die
// Layout-Aussage ist am gebauten Stylesheet in Chromium gemessen und steht
// in `e2e/scroll-guard.spec.ts` („M7“) als dauerhafte Pruefung:
//
// - vorher: horizontaler Scroll-Container ohne Hinweis auf verdeckte Tabs.
//   Agent-Detail 461 px Tabs in 288 px Leiste (320 px Viewport), „Werkzeuge
//   & Rechte“ und „Verbindung“ ausserhalb; Resource-Detail 540 von 288 px,
//   „Verwendung“ und „Versionen“ ausserhalb (auch bei 390 und 430 px).
// - nachher: die Leiste bricht um, alle Tabs liegen im Viewport, die Leiste
//   hat keine eigene Scrollweite mehr.
//
// Der fruehere Einwand gegen den Umbruch (die `border-b` ist keine
// durchgehende Unterkante unter der oberen Zeile) ist durch die Owner-
// Entscheidung W1=a abgewogen: sichtbare Tabs vor durchgehender Linie.
function renderAgentTabs(className?: string) {
  render(
    <Tabs defaultValue="config">
      <TabsList aria-label="Detailansicht" className={className}>
        <TabsTrigger value="config">Konfiguration</TabsTrigger>
        <TabsTrigger value="tools">Werkzeuge &amp; Rechte</TabsTrigger>
        <TabsTrigger value="connection">Verbindung</TabsTrigger>
      </TabsList>
      <TabsContent value="config">Konfig-Panel</TabsContent>
    </Tabs>,
  )
}

describe('TabsList — Responsive (Mobil-Spec M7, W1=a)', () => {
  it('bricht um, statt Tabs in einem Scroll-Container zu verstecken', () => {
    renderAgentTabs()
    const list = screen.getByRole('tablist')
    expect(list).toHaveClass('flex-wrap')
    expect(list.className).not.toMatch(/overflow-(x-)?(auto|scroll)/)
  })

  it('jeder Trigger ist ein 44-px-Ziel und bricht selbst nicht um', () => {
    renderAgentTabs()
    for (const tab of screen.getAllByRole('tab')) {
      expect(tab).toHaveClass('h-11')
      expect(tab).toHaveClass('whitespace-nowrap')
    }
  })

  // Die Aufrufstellen brauchen kein eigenes `flex-wrap` mehr (die lokale
  // Klasse im Persona-Detail ist entfallen); `className` ergaenzt den
  // Default, statt ihn zu ersetzen.
  it('reicht className weiter, ohne den Umbruch zu verlieren', () => {
    renderAgentTabs('mt-4')
    const list = screen.getByRole('tablist')
    expect(list).toHaveClass('mt-4')
    expect(list).toHaveClass('flex-wrap')
  })
})
