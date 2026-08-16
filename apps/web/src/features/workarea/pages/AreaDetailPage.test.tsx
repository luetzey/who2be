import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { agent, area, artifact, grant, renderAt, stubFetch } from '../test-utils'

import { AreaDetailPage } from './AreaDetailPage'

const PATH = '/w/:workspaceId/workarea/areas/:areaId'
const ENTRY = ['/w/ws-1/workarea/areas/area-1']

let role = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}))

beforeEach(() => {
  role = 'editor'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('AreaDetailPage', () => {
  it('zeigt die Inhalte eines geteilten Bereichs', async () => {
    stubFetch([
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Preisliste 2026')).toBeInTheDocument()
    })
    expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
  })

  it('bietet privaten Bereichen keinen Zugriffs-Tab an', async () => {
    // Private Areas sind serverseitig nicht grantbar (403 `area_forbidden`) —
    // ein Tab dorthin waere eine Sackgasse.
    stubFetch([
      ['/work-areas/area-1/artifacts', [artifact()]],
      ['/work-areas', [area({ scope: 'private', owner_agent_id: 'agent-1' })]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Privater Bereich')).toBeInTheDocument()
    })
    expect(screen.queryByRole('tab', { name: 'Zugriffe' })).not.toBeInTheDocument()
  })

  it('listet Freigaben mit aufgeloestem Agenten-Namen', async () => {
    stubFetch([
      ['/work-areas/area-1/grants', [grant({ level: 'write' })]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByText('Recherche-Agent')).toBeInTheDocument()
    })
    expect(screen.getByRole('combobox', { name: 'Recht' })).toHaveValue('write')
  })

  it('sperrt Freigaben fuer Viewer', async () => {
    role = 'viewer'
    stubFetch([
      ['/work-areas/area-1/grants', [grant()]],
      ['/work-areas/area-1/artifacts', []],
      ['/work-areas', [area()]],
      ['/agents', [agent()]],
    ])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Zugriffe' })).toBeInTheDocument()
    })
    fireEvent.click(screen.getByRole('tab', { name: 'Zugriffe' }))

    await waitFor(() => {
      expect(screen.getByRole('combobox', { name: 'Recht' })).toBeDisabled()
    })
    expect(screen.getByRole('button', { name: /Entfernen/ })).toBeDisabled()
  })

  it('meldet einen nicht sichtbaren Bereich als nicht gefunden', async () => {
    stubFetch([['/work-areas', []]])
    renderAt(<AreaDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(
        screen.getByText('Dieser Bereich existiert nicht oder ist für dich nicht sichtbar.'),
      ).toBeInTheDocument()
    })
  })
})
