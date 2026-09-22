import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Resource, SubResource, SubResourceLinkInput } from '@/api/types'

import { SubResourcePicker } from './SubResourcePicker'

// Stabile api-Referenz (siehe PlaybookComposesPicker.test.tsx) — `api` steckt in
// den useEffect-Deps, eine frische Referenz pro Render wuerde eine
// Render-Endlosschleife ausloesen.
const listResourcesMock = vi.fn()
const stableApi = { listResources: listResourcesMock }

vi.mock('@/api/useApi', () => ({
  useApi: () => stableApi,
}))

const makeResource = (id: string, name: string): Resource => ({
  id,
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name,
  slug: id,
  current_version: 1,
  content: { description: `Beschreibung von ${name}`, blocks: [] },
  created_at: 't',
  updated_at: 't',
})

const makeSub = (id: string, name: string): SubResource => ({
  id,
  name,
  link_scope: 'resource',
  block_id: null,
  position: 0,
  fetch_call: `fetch_resource('${id}')`,
})

const rA = makeResource('r-a', 'Glossar A')
const rB = makeResource('r-b', 'Glossar B')
const currentId = 'r-current'

describe('SubResourcePicker', () => {
  it('zeigt die verfuegbaren Workspace-Resources inline', async () => {
    listResourcesMock.mockResolvedValue([rA, rB])

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    // Kein Dialog mehr — die Insel ist direkt im Tab sichtbar.
    await waitFor(() => {
      expect(screen.getByText('Glossar A')).toBeInTheDocument()
    })
    expect(screen.getByText('Glossar B')).toBeInTheDocument()
  })

  it('schliesst die aktuelle Resource aus der Liste aus', async () => {
    const current = makeResource(currentId, 'Current Self')
    listResourcesMock.mockResolvedValue([current, rA])

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Glossar A')).toBeInTheDocument()
    })
    expect(screen.queryByText('Current Self')).not.toBeInTheDocument()
  })

  it('ruft onSave sofort mit Volldokument-Links auf, wenn eine Resource hinzugefuegt wird', async () => {
    listResourcesMock.mockResolvedValue([rA, rB])
    const onSave = vi.fn()

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[]}
        saving={false}
        onSave={onSave}
      />,
    )

    await waitFor(() => {
      expect(screen.getByText('Glossar A')).toBeInTheDocument()
    })
    // Inline-Panel speichert bei jeder Aktion sofort (kein Speichern-Button).
    fireEvent.click(
      screen.getByRole('button', { name: 'Glossar A als Sub-Resource hinzufügen' }),
    )

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1)
    })
    const links = onSave.mock.calls[0][0] as SubResourceLinkInput[]
    expect(links).toEqual([
      {
        child_id: 'r-a',
        block_id: null,
        position: 0,
        link_scope: 'resource',
        embedding_mode: 'lazy',
      },
    ])
  })

  it('schaltet eine Sub-Resource auf Inline um und speichert sofort', async () => {
    listResourcesMock.mockResolvedValue([rA, rB])
    const onSave = vi.fn()

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[makeSub('r-a', 'Glossar A')]}
        saving={false}
        onSave={onSave}
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole('list', { name: 'Eingebunden' })).toBeInTheDocument()
    })

    // Standard ist 'lazy' — auf 'Inline' umstellen (speichert sofort).
    fireEvent.click(screen.getByRole('button', { name: 'Inline' }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1)
    })
    const links = onSave.mock.calls[0][0] as SubResourceLinkInput[]
    expect(links).toEqual([
      {
        child_id: 'r-a',
        block_id: null,
        position: 0,
        link_scope: 'resource',
        embedding_mode: 'inline',
      },
    ])
  })

  it('erhaelt bestehende Block-Anker beim Speichern (keine Vernichtung)', async () => {
    listResourcesMock.mockResolvedValue([rA, rB])
    const onSave = vi.fn()
    const blockAnchor: SubResource = {
      id: 'r-b',
      name: 'Glossar B',
      link_scope: 'block',
      block_id: 'heading-1',
      position: 0,
      fetch_call: "fetch_resource('r-b')",
    }

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[makeSub('r-a', 'Glossar A'), blockAnchor]}
        saving={false}
        onSave={onSave}
      />,
    )

    await waitFor(() => {
      expect(screen.getByRole('list', { name: 'Eingebunden' })).toBeInTheDocument()
    })

    // Eine Aktion (Inline-Umschalten von r-a) loest das Speichern aus.
    fireEvent.click(screen.getByRole('button', { name: 'Inline' }))

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledTimes(1)
    })
    const links = onSave.mock.calls[0][0] as SubResourceLinkInput[]
    // Volldokument-Ref (r-a) + erhaltener Block-Anker (r-b/heading-1).
    expect(links).toEqual([
      {
        child_id: 'r-a',
        block_id: null,
        position: 0,
        link_scope: 'resource',
        embedding_mode: 'inline',
      },
      { child_id: 'r-b', block_id: 'heading-1', position: 1, link_scope: 'block' },
    ])
  })
})

// Responsive-Audit #564 (W3, Epic #431): jsdom hat kein Layout, geprueft wird
// deshalb der Klassen-Vertrag. Die Layout-Aussage ist am gerenderten Baum
// belegt (Plandatei .claude/plan/2026-09-23-0130_564-…): bei 320px Viewport
// misst die Anker-Pill 463px, die Zeilen-Aktionen 19x32px und die
// Segment-Gruppe 54px bei 86px Inhalt — alle drei unter dem 40px-Floor aus
// design-language.md §11 bzw. ueberlaufend.
describe('SubResourcePicker — 320px (#564)', () => {
  const LONG = 'kundenonboarding_wissensbasis_vertriebsteam_langbezeichner_q4'

  it('laesst die Block-Anker-Pill mitten im Wort brechen', async () => {
    listResourcesMock.mockResolvedValue([])
    const anchor: SubResource = {
      id: 'r-b',
      name: 'Anker-Resource',
      link_scope: 'block',
      block_id: LONG,
      position: 0,
      fetch_call: "fetch_resource('r-b')",
    }

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[anchor]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    const pill = await screen.findByText(`Im Text (Block ${LONG})`)
    const classes = pill.className.split(/\s+/)
    expect(classes).toContain('break-all')
    expect(classes).toContain('max-w-full')
  })

  it('haelt die Zeilen-Aktionen unterhalb md auf 40px Hit-Target', async () => {
    listResourcesMock.mockResolvedValue([rA])

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[makeSub('r-a', 'Glossar A')]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    const remove = await screen.findByRole('button', { name: 'Glossar A entfernen' })
    const removeClasses = remove.className.split(/\s+/)
    // size-10 = 40px unterhalb md, ab md zurueck auf die kompakten 32px.
    expect(removeClasses).toContain('size-10')
    expect(removeClasses).toContain('md:size-8')

    const lazy = screen.getByRole('button', { name: 'Lazy' })
    const lazyClasses = lazy.className.split(/\s+/)
    expect(lazyClasses).toContain('h-10')
    expect(lazyClasses).toContain('md:h-8')
  })

  it('bricht die Resource-Link-Zeile um, statt die Textspalte zu zerdruecken', async () => {
    listResourcesMock.mockResolvedValue([rA])

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[makeSub('r-a', 'Glossar A')]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    const row = (await screen.findByRole('button', { name: 'Glossar A entfernen' })).closest('li')
    expect(row?.className.split(/\s+/)).toContain('flex-wrap')

    // Die Segment-Gruppe bleibt eine visuelle Einheit (Weiche 3 des Issues):
    // kein Umbruch INNERHALB der Gruppe, sie wandert als Ganzes.
    const group = screen.getByRole('group', { name: 'Einbettungs-Modus für Glossar A' })
    expect(group.className.split(/\s+/)).toContain('shrink-0')
  })
})
