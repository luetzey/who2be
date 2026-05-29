import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import type { Resource, ResourceBlock } from '@/api/types'

import { ResourceBlockLinkPicker } from './ResourceBlockLinkPicker'

const resource: Resource = {
  id: 'r-1',
  workspace_id: 'ws-1',
  owner_id: 'o-1',
  name: 'Runbook',
  current_version: 1,
  content: { description: '', blocks: [] },
  created_at: 't',
  updated_at: 't',
}

const headingOne: ResourceBlock = {
  id: 'h-1',
  type: 'heading',
  props: { level: 1 },
  content: [{ type: 'text', text: 'Reset-Flow', styles: {} }],
}
const paragraphInsideOne: ResourceBlock = {
  id: 'p-1',
  type: 'paragraph',
  content: [
    { type: 'text', text: 'Schritt 1 — Kunde begruessen, Identitaet pruefen.', styles: {} },
  ],
}
const headingTwo: ResourceBlock = {
  id: 'h-2',
  type: 'heading',
  props: { level: 1 },
  content: [{ type: 'text', text: 'Eskalation', styles: {} }],
}

const blocks: ResourceBlock[] = [headingOne, paragraphInsideOne, headingTwo]

function fakeApi() {
  return {
    listResources: vi.fn().mockResolvedValue([resource]),
    getResource: vi.fn().mockResolvedValue({ ...resource, content: { description: '', blocks } }),
  }
}

vi.mock('@/api/useApi', () => {
  return {
    useApi: () => mockedApi,
  }
})

let mockedApi: ReturnType<typeof fakeApi>

describe('ResourceBlockLinkPicker', () => {
  it('zeigt nur Heading-Bloecke und rendert Section-Preview', async () => {
    mockedApi = fakeApi()
    render(
      <ResourceBlockLinkPicker existing={[]} saving={false} onSave={() => {}} />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Bloecke verknuepfen' }))

    fireEvent.click(await screen.findByRole('button', { name: 'Runbook' }))

    await waitFor(() => {
      expect(screen.getByText('Reset-Flow')).toBeInTheDocument()
    })
    expect(screen.getByText('Eskalation')).toBeInTheDocument()
    // Section-Preview unter dem Heading.
    expect(
      screen.getByText('Schritt 1 — Kunde begruessen, Identitaet pruefen.'),
    ).toBeInTheDocument()
    // Paragraph-Bloecke werden NICHT als waehlbar gerendert.
    expect(
      screen.queryByRole('checkbox', { name: /Schritt 1/ }),
    ).not.toBeInTheDocument()
  })

  it('kennzeichnet eine leere Section als (leere Section)', async () => {
    mockedApi = {
      listResources: vi.fn().mockResolvedValue([resource]),
      getResource: vi.fn().mockResolvedValue({
        ...resource,
        content: { description: '', blocks: [headingTwo] },
      }),
    }
    render(
      <ResourceBlockLinkPicker existing={[]} saving={false} onSave={() => {}} />,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Bloecke verknuepfen' }))
    fireEvent.click(await screen.findByRole('button', { name: 'Runbook' }))
    await waitFor(() => {
      expect(screen.getByText('Eskalation')).toBeInTheDocument()
    })
    expect(screen.getByText('(leere Section)')).toBeInTheDocument()
  })
})
