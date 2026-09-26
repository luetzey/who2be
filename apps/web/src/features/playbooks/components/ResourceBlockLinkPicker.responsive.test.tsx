import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Resource, ResourceBlock } from '@/api/types'

import { ResourceBlockLinkPicker } from './ResourceBlockLinkPicker'

// Responsive-Vertrag #573 (Haelfte A). Die Zahl 40 px stammt aus AK 5 dieses
// Issues, NICHT aus der Norm: `docs/frontend/design-language.md` §11 ist die
// einzige Quelle des Hit-Target-Floors und setzt ihn auf >= 32 px. Die hier
// gemessenen 24 px der Embed-Modus-Buttons unterschreiten diesen Norm-Floor.
//
// jsdom hat kein Layout, deshalb ist das hier ein Klassen-Vertrag; die
// Layout-Aussage selbst ist in
// .claude/plan/2026-09-23-1700_573-w3-playbooks-haelfte-a-responsive.md
// gegen das gebaute Stylesheet in Chromium belegt.

// Bewusst pessimistische Fixture: lange Resource-Namen sind der Regelfall.
const resource: Resource = {
  id: 'r-1',
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name: 'Vertriebshandbuch-Enterprise-Gesamtausgabe-2026',
  slug: 'vertriebshandbuch',
  current_version: 1,
  content: { description: '', blocks: [] },
  created_at: 't',
  updated_at: 't',
}

const heading: ResourceBlock = {
  id: 'h-1',
  type: 'heading',
  props: { level: 1 },
  content: [{ type: 'text', text: 'Preisverhandlung', styles: {} }],
}

const mockedApi = {
  listResources: vi.fn().mockResolvedValue([resource]),
  getResource: vi
    .fn()
    .mockResolvedValue({ ...resource, content: { description: '', blocks: [heading] } }),
}

vi.mock('@/api/useApi', () => ({
  useApi: () => mockedApi,
}))

describe('ResourceBlockLinkPicker — Responsive (#573)', () => {
  it('laesst den Resource-Namen in der Auswahlliste umbrechen', async () => {
    render(<ResourceBlockLinkPicker existing={[]} saving={false} onSave={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Bloecke verknuepfen' }))

    // Gemessen: der Button erbt das `whitespace-nowrap` der Button-Basis und
    // schneidet den Namen ab — 344 px Inhalt in 238 px sichtbar, und zwar bei
    // 320, 375 UND 768 px. Deshalb ohne `md:`-Rueckfall.
    const entry = await screen.findByRole('button', { name: resource.name })
    expect(entry).toHaveClass('whitespace-normal')
    expect(entry).toHaveClass('break-words')
    expect(entry).toHaveClass('h-auto')
    expect(entry).toHaveClass('min-h-10')
  })

  it('haelt die Embed-Modus-Buttons auf dem 40-px-Hit-Target aus AK 5', async () => {
    render(<ResourceBlockLinkPicker existing={[]} saving={false} onSave={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: 'Bloecke verknuepfen' }))
    fireEvent.click(await screen.findByRole('button', { name: resource.name }))
    fireEvent.click(
      await screen.findByRole('checkbox', { name: 'Gesamtes Dokument verknuepfen' }),
    )

    // Gemessen je 24 px hoch (`h-6`) — unter dem Norm-Floor aus §11 und unter
    // AK 5. Ab `md` bleibt die Verdichtung der Segmentleiste erhalten.
    for (const name of ['Link (lazy)', 'Fest einbetten']) {
      const button = await screen.findByRole('button', { name })
      expect(button).toHaveClass('h-10')
      expect(button).toHaveClass('md:h-6')
    }
  })
})
