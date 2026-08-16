import { screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { artifact, renderAt, stubFetch } from '../test-utils'

import { ArtifactDetailPage } from './ArtifactDetailPage'

const PATH = '/w/:workspaceId/workarea/areas/:areaId/artifacts/:artifactId'
const ENTRY = ['/w/ws-1/workarea/areas/area-1/artifacts/art-1']

let role = 'editor'
vi.mock('@/auth/useCurrentWorkspaceRole', () => ({
  useCurrentWorkspaceRole: () => role,
}))

vi.mock('@/lib/feedback', () => ({
  notify: { success: vi.fn(), error: vi.fn() },
}))

const MARKDOWN = ['# Preisliste [#aaaaaaaa]', '', 'Der Preis stieg um 8 %. [#bbbbbbbb]'].join('\n')

function stubArtifact(): void {
  stubFetch([
    ['/wa-artifacts/art-1', { artifact_id: 'art-1', title: 'Preisliste 2026', rev: 2, markdown: MARKDOWN }],
    ['/work-areas/area-1/artifacts', [artifact()]],
  ])
}

beforeEach(() => {
  role = 'editor'
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ArtifactDetailPage', () => {
  it('rendert die Bloecke ohne die Anker-Annotation im Text', async () => {
    stubArtifact()
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('# Preisliste')).toBeInTheDocument()
    })
    expect(screen.getByText('Der Preis stieg um 8 %.')).toBeInTheDocument()
    // Die Annotation gehoert in den Anker-Button, nicht in den Text.
    expect(screen.queryByText(/\[#aaaaaaaa\]/)).not.toBeInTheDocument()
  })

  it('gibt jedem Block einen adressierbaren Anker', async () => {
    stubArtifact()
    const { container } = renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(container.querySelector('#block-aaaaaaaa')).not.toBeNull()
    })
    expect(container.querySelector('#block-bbbbbbbb')).not.toBeNull()
    expect(screen.getAllByRole('button', { name: 'Anker kopieren' })).toHaveLength(2)
  })

  it('hebt den ueber das URL-Fragment angesprungenen Block hervor', async () => {
    stubArtifact()
    const { container } = renderAt(<ArtifactDetailPage />, PATH, [
      '/w/ws-1/workarea/areas/area-1/artifacts/art-1#bbbbbbbb',
    ])

    await waitFor(() => {
      expect(container.querySelector('#block-bbbbbbbb')).not.toBeNull()
    })
    // Ring UND Flaeche — die Markierung haengt nicht allein an der Farbe.
    expect(container.querySelector('#block-bbbbbbbb')?.className).toContain('ring-2')
    expect(container.querySelector('#block-aaaaaaaa')?.className).not.toContain('ring-2')
  })

  it('sperrt das Loeschen fuer Viewer', async () => {
    role = 'viewer'
    stubArtifact()
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Löschen/ })).toBeDisabled()
    })
  })

  it('zeigt einen Hinweis statt einer leeren Flaeche bei Artifacts ohne Text', async () => {
    stubFetch([
      ['/wa-artifacts/art-1', { artifact_id: 'art-1', title: 'Leer', rev: 1, markdown: '' }],
      ['/work-areas/area-1/artifacts', [artifact({ title: 'Leer' })]],
    ])
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByText('Dieses Element hat keinen Textinhalt.')).toBeInTheDocument()
    })
  })
})
