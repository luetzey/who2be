import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest'

import { notify } from '@/lib/feedback'

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

beforeAll(() => {
  // Radix-Dropdown braucht Pointer-Capture + scrollIntoView, JSDOM hat beides
  // nicht (Muster `TableDetailPage.test.tsx` / `EntityExportButton.test.tsx`).
  for (const fn of [
    'hasPointerCapture',
    'releasePointerCapture',
    'setPointerCapture',
    'scrollIntoView',
  ] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

let anchorClick: ReturnType<typeof vi.fn>
let createdAnchors: HTMLAnchorElement[]

beforeEach(() => {
  role = 'editor'
  createdAnchors = []
  anchorClick = vi.fn()
  const realCreate = document.createElement.bind(document)
  vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
    const el = realCreate(tag)
    if (tag === 'a') {
      el.click = anchorClick as () => void
      createdAnchors.push(el as HTMLAnchorElement)
    }
    return el
  })
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

// Der createElement-Spy sammelt AUCH die Anchor von `<Link>` (Zurueck-Link) —
// gesucht ist die eine mit `download`-Attribut, die `downloadFile` erzeugt.
function downloadName(): string | undefined {
  return createdAnchors.find((anchor) => anchor.download !== '')?.download
}

function openExportDropdown(): void {
  // Radix oeffnet auf pointerdown+up; in JSDOM kommen wir per Enter ans Ziel.
  fireEvent.keyDown(screen.getByTestId('export-artifact-trigger'), { key: 'Enter' })
}

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

  it('exportiert als Markdown und laedt eine Datei mit dem Titel im Dateinamen', async () => {
    stubArtifact()
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-artifact-trigger')).toBeInTheDocument()
    })
    openExportDropdown()
    fireEvent.click(await screen.findByTestId('export-artifact-markdown'))

    await waitFor(() => {
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(downloadName()).toBe('who2be-artifact-preisliste-2026.md')
    expect(notify.success).toHaveBeenCalledWith('Export heruntergeladen.')
  })

  it('exportiert als HTML unter der html-Endung', async () => {
    stubArtifact()
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-artifact-trigger')).toBeInTheDocument()
    })
    openExportDropdown()
    fireEvent.click(await screen.findByTestId('export-artifact-html'))

    await waitFor(() => {
      expect(anchorClick).toHaveBeenCalled()
    })
    expect(downloadName()).toBe('who2be-artifact-preisliste-2026.html')
  })

  it('ruft den Browser-Druckdialog beim Klick auf "Als PDF drucken"', async () => {
    stubArtifact()
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => undefined)
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-artifact-trigger')).toBeInTheDocument()
    })
    openExportDropdown()
    fireEvent.click(await screen.findByTestId('export-artifact-print'))

    expect(printSpy).toHaveBeenCalledTimes(1)
  })

  it('zeigt eine Fehlermeldung, wenn der Export fehlschlaegt', async () => {
    // `/export` muss VOR `/wa-artifacts/art-1` geprueft werden — sonst matcht
    // der Basis-Pfad zuerst (Praefix-Problem, Muster `TableDetailPage.test.tsx`).
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url: string) => {
        if (url.includes('/export')) {
          return new Response(JSON.stringify({ detail: 'Export fehlgeschlagen.' }), {
            status: 500,
            headers: { 'content-type': 'application/json' },
          })
        }
        if (url.includes('/wa-artifacts/art-1')) {
          return new Response(
            JSON.stringify({
              artifact_id: 'art-1',
              title: 'Preisliste 2026',
              rev: 2,
              markdown: MARKDOWN,
            }),
            { status: 200, headers: { 'content-type': 'application/json' } },
          )
        }
        if (url.includes('/work-areas/area-1/artifacts')) {
          return new Response(JSON.stringify([artifact()]), {
            status: 200,
            headers: { 'content-type': 'application/json' },
          })
        }
        return new Response('[]', { status: 200, headers: { 'content-type': 'application/json' } })
      }),
    )
    renderAt(<ArtifactDetailPage />, PATH, ENTRY)

    await waitFor(() => {
      expect(screen.getByTestId('export-artifact-trigger')).toBeInTheDocument()
    })
    openExportDropdown()
    fireEvent.click(await screen.findByTestId('export-artifact-markdown'))

    await waitFor(() => {
      expect(notify.error).toHaveBeenCalled()
    })
    expect(anchorClick).not.toHaveBeenCalled()
  })
})
