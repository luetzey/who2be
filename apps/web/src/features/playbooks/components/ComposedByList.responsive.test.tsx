// Responsive-Vertrag der Composite-Rueckverweise (#573, Haelfte B).
//
// Klassenvertrag, kein Layout — jsdom rechnet kein Layout. Gemessen am
// gebauten Stylesheet in Chromium (Plan-Datei): ein Composite-Name ohne
// Trennstelle mass bei 320px 397,7px gegen 288px Spalte und erzeugte 94px
// horizontalen Body-Scroll; mit `break-words` 282,5px und 0px Scroll.

import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import type { PlaybookRef } from '@/api/types'

import { ComposedByList } from './ComposedByList'

vi.mock('@/auth/useWorkspacePath', () => ({
  useWorkspacePath: () => (path: string) => `/w/ws-1${path}`,
}))

describe('ComposedByList — Responsive', () => {
  it('bricht lange Composite-Namen ohne Trennstelle um', () => {
    const parents: PlaybookRef[] = [
      { id: 'parent-1', name: 'Kundenonboardinggesamtprozessvertriebsuebergabecomposite' },
    ]

    render(
      <MemoryRouter>
        <ComposedByList parents={parents} />
      </MemoryRouter>,
    )

    const link = screen.getByRole('link', {
      name: 'Kundenonboardinggesamtprozessvertriebsuebergabecomposite',
    })
    const item = link.closest('li')
    expect(item).not.toBeNull()
    expect(item?.className).toContain('break-words')
  })
})
