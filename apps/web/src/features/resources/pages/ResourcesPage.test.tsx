import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { renderInRoutes } from '@/test/render'
import { ResourcesPage } from './ResourcesPage'

function resource(id: string, name: string, tags: string[] = []) {
  return {
    id,
    workspace_id: 'ws-1',
    owner_id: 'o1',
    name,
    slug: id,
    current_version: 1,
    current_status: 'active',
    has_pending_draft: false,
    content: { description: '', blocks: [], tags },
    created_at: '2026-05-24T11:00:00Z',
    updated_at: '2026-05-24T11:00:00Z',
  }
}

function renderWith(list: unknown[], initialEntries: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue(new Response(JSON.stringify(list), { status: 200 })),
  )
  return renderInRoutes(<ResourcesPage />, {
    path: '/w/:workspaceId/resources',
    initialEntries,
  })
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ResourcesPage', () => {
  it('gruppiert via ?group=tag mit Sektions-Headern je Tag, Mehrfach-Tags in jeder Gruppe', async () => {
    renderWith(
      [
        resource('r1', 'Datenschutz-FAQ', ['recht', 'faq']),
        resource('r2', 'Onboarding-Guide', ['faq']),
        resource('r3', 'Notizen', []),
      ],
      ['/w/ws-1/resources?group=tag'],
    )

    await waitFor(() => {
      expect(screen.getAllByText('Datenschutz-FAQ').length).toBeGreaterThan(0)
    })

    expect(screen.getByRole('heading', { name: /faq\s?\(2\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /recht\s?\(1\)/ })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: /Ohne Tag\s?\(1\)/ })).toBeInTheDocument()
    // r1 traegt zwei Tags und erscheint dadurch in zwei Tag-Gruppen.
    expect(screen.getAllByText('Datenschutz-FAQ')).toHaveLength(2)
  })

  it('Group-by-Selector schaltet von Tag-Gruppen zurueck auf die flache Liste', async () => {
    renderWith(
      [resource('r1', 'Datenschutz-FAQ', ['faq']), resource('r2', 'Onboarding-Guide', ['faq'])],
      ['/w/ws-1/resources?group=tag'],
    )

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /faq\s?\(2\)/ })).toBeInTheDocument()
    })

    fireEvent.change(screen.getByLabelText('Gruppieren'), { target: { value: '' } })

    expect(screen.queryByRole('heading', { name: /faq\s?\(2\)/ })).not.toBeInTheDocument()
    expect(screen.getByText('Datenschutz-FAQ')).toBeInTheDocument()
    expect(screen.getByText('Onboarding-Guide')).toBeInTheDocument()
  })
})
