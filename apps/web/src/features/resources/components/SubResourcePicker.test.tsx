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
  it('oeffnet den Dialog und zeigt Workspace-Resources', async () => {
    listResourcesMock.mockResolvedValue([rA, rB])

    render(
      <SubResourcePicker
        currentResourceId={currentId}
        existing={[]}
        saving={false}
        onSave={vi.fn()}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Resources bearbeiten' }))

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

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Resources bearbeiten' }))

    await waitFor(() => {
      expect(screen.getByText('Glossar A')).toBeInTheDocument()
    })
    expect(screen.queryByText('Current Self')).not.toBeInTheDocument()
  })

  it('ruft onSave mit Volldokument-Links auf', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Resources bearbeiten' }))

    await waitFor(() => {
      expect(screen.getByText('Glossar A')).toBeInTheDocument()
    })
    fireEvent.click(
      screen.getByRole('checkbox', { name: 'Glossar A als Sub-Resource hinzufügen' }),
    )

    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))

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

  it('schaltet eine Sub-Resource auf "Fest einbetten" (inline) um', async () => {
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

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Resources bearbeiten' }))

    await waitFor(() => {
      expect(
        screen.getByRole('list', { name: 'Ausgewaehlte Sub-Resources' }),
      ).toBeInTheDocument()
    })

    // Standard ist 'lazy' — auf 'Fest einbetten' umstellen.
    fireEvent.click(screen.getByRole('button', { name: 'Fest einbetten' }))
    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))

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

    fireEvent.click(screen.getByRole('button', { name: 'Sub-Resources bearbeiten' }))

    await waitFor(() => {
      expect(
        screen.getByRole('list', { name: 'Ausgewaehlte Sub-Resources' }),
      ).toBeInTheDocument()
    })

    fireEvent.click(screen.getByRole('button', { name: /Speichern/ }))

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
        embedding_mode: 'lazy',
      },
      { child_id: 'r-b', block_id: 'heading-1', position: 1, link_scope: 'block' },
    ])
  })
})
