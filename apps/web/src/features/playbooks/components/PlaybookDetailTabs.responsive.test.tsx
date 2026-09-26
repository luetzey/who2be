// Responsive-Vertrag der Tab-Leiste (#573, Haelfte B).
//
// Diese Assertions pruefen KLASSEN, kein Layout — jsdom rechnet kein Layout.
// Die Layout-Aussage dahinter ist am gebauten Stylesheet in Chromium
// gemessen und in `.claude/plan/2026-09-23-1845_573-w3-playbooks-haelfte-b-
// responsive.md` belegt: vorher liefen die drei Tabs bei 320px auf 403,8px
// und erzeugten 84px horizontalen Body-Scroll, nachher 0px.

import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { PlaybookDetailTabs } from './PlaybookDetailTabs'

describe('PlaybookDetailTabs — Responsive', () => {
  it('laesst die Tab-Leiste umbrechen, statt sie ueberlaufen zu lassen', () => {
    render(<PlaybookDetailTabs active="edit" onChange={() => {}} />)

    const tablist = screen.getByRole('tablist')
    expect(tablist.className).toContain('flex-wrap')
  })
})
