import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Tabs, TabsContent, TabsList, TabsTrigger } from './tabs'

// Responsive-Vertrag (Primitive-Fund 1 aus dem Audit #570 Haelfte A).
//
// `TabsList` rendert eine Zeile aus `whitespace-nowrap`-Triggern ohne
// Umbruch und — vor dieser Aenderung — ohne Scroll-Moeglichkeit. Gemessen
// gegen das gebaute Stylesheet summieren die drei Trigger des
// `AgentEditorForm` 461 px; der Container klemmt bei 320 px Viewport auf
// 288 px ab. Der dritte Tab lag damit 173 px ausserhalb der Innenkante und
// war per Hit-Test NICHT erreichbar — ein Bedienelement ohne jeden Weg
// dorthin, nicht nur ein knapper Ueberlauf.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1700_primitives-tabslist-entitycard-hit-target.md
// gerendert belegt (320 px: dritter Tab unerreichbar -> erreichbar,
// horizontaler Scroll 173 px; 768/1024 px unveraendert kein Scroll).
//
// `overflow-x-auto` und nicht `flex-wrap`: eine umbrechende Tab-Leiste
// verliert die durchgehende `border-b`-Kante und setzt den aktiven
// 2px-Unterstrich in die obere Zeile (gemessen 141 px Leistenhoehe statt 45).
// Horizontales Scrollen ist das etablierte Tab-Muster, und
// docs/frontend/design-language.md §4.4 Punkt 1 nimmt bewusst gescrollte
// Container vom 320px-Kriterium ausdruecklich aus.
describe('TabsList — Responsive (Primitive-Fund #570/A)', () => {
  it('scrollt horizontal, statt Trigger unerreichbar abzuschneiden', () => {
    render(
      <Tabs defaultValue="config">
        <TabsList aria-label="Detail-Tabs">
          <TabsTrigger value="config">Konfiguration</TabsTrigger>
          <TabsTrigger value="tools">Werkzeuge &amp; Rechte</TabsTrigger>
          <TabsTrigger value="connection">Verbindung</TabsTrigger>
        </TabsList>
        <TabsContent value="config">Konfig-Panel</TabsContent>
      </Tabs>,
    )
    expect(screen.getByRole('tablist')).toHaveClass('overflow-x-auto')
  })

  // Der aktive Unterstrich sitzt mit `-bottom-px` bewusst 1 px ausserhalb der
  // Trigger-Box, damit er die `border-b` der Leiste ueberdeckt statt darueber
  // zu schweben. `overflow-x: auto` zieht `overflow-y` rechnerisch auf `auto`
  // nach — dieser eine Pixel wird dadurch zu echtem vertikalem Scroll-Inhalt:
  // gemessen scrollHeight 45 > clientHeight 44, und der Container liess sich
  // tatsaechlich um 1 px vertikal scrollen (Trackpad-/Touch-Falle auf einer
  // Leiste, die gar nicht vertikal scrollen soll).
  //
  // `pb-px` gibt dem Unterstrich diesen Pixel als Polsterung INNERHALB der
  // Box, statt ihn zu Overflow werden zu lassen: gemessen scrollHeight 44 =
  // clientHeight 44, vertikal nicht mehr scrollbar, horizontaler Scroll und
  // die Optik des Unterstrichs unveraendert.
  it('erzeugt keinen vertikalen Overflow durch den aktiven Unterstrich', () => {
    render(
      <Tabs defaultValue="config">
        <TabsList aria-label="Detail-Tabs">
          <TabsTrigger value="config">Konfiguration</TabsTrigger>
          <TabsTrigger value="tools">Werkzeuge &amp; Rechte</TabsTrigger>
        </TabsList>
        <TabsContent value="config">Konfig-Panel</TabsContent>
      </Tabs>,
    )
    expect(screen.getByRole('tablist')).toHaveClass('pb-px')
  })

  it('bricht die Leiste nicht um — die Unterstrich-Kante bleibt eine Zeile', () => {
    render(
      <Tabs defaultValue="config">
        <TabsList aria-label="Detail-Tabs">
          <TabsTrigger value="config">Konfiguration</TabsTrigger>
          <TabsTrigger value="tools">Werkzeuge &amp; Rechte</TabsTrigger>
        </TabsList>
        <TabsContent value="config">Konfig-Panel</TabsContent>
      </Tabs>,
    )
    expect(screen.getByRole('tablist')).not.toHaveClass('flex-wrap')
  })

  // Die Aufrufstellen sollen die Scroll-Eigenschaft nicht versehentlich
  // zuruecknehmen koennen: `className` wird weiterhin durchgereicht und
  // gewinnt per tailwind-merge, aber der Default traegt sie.
  it('reicht className weiter, ohne den Default zu verlieren', () => {
    render(
      <Tabs defaultValue="config">
        <TabsList aria-label="Detail-Tabs" className="mt-4">
          <TabsTrigger value="config">Konfiguration</TabsTrigger>
        </TabsList>
        <TabsContent value="config">Konfig-Panel</TabsContent>
      </Tabs>,
    )
    const list = screen.getByRole('tablist')
    expect(list).toHaveClass('mt-4')
    expect(list).toHaveClass('overflow-x-auto')
  })
})
