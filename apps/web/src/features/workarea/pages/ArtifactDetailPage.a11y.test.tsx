import { fireEvent, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'

import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { artifact, stubFetch } from '../test-utils'

import { ArtifactDetailPage } from './ArtifactDetailPage'

beforeAll(() => {
  // Radix-Dropdown braucht Pointer-Capture, JSDOM hat das nicht (Muster
  // `TableDetailPage.test.tsx`).
  for (const fn of ['hasPointerCapture', 'releasePointerCapture', 'setPointerCapture'] as const) {
    Object.defineProperty(window.HTMLElement.prototype, fn, {
      value: () => (fn === 'hasPointerCapture' ? false : undefined),
      configurable: true,
    })
  }
})

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('ArtifactDetailPage (a11y)', () => {
  it('hat keine axe-Violations im AppLayout', async () => {
    stubFetch([
      [
        '/wa-artifacts/art-1',
        {
          artifact_id: 'art-1',
          title: 'Preisliste 2026',
          rev: 2,
          markdown: '# Preisliste [#aaaaaaaa]\n\nDer Preis stieg um 8 %. [#bbbbbbbb]',
        },
      ],
      ['/work-areas/area-1/artifacts', [artifact()]],
    ])

    const { container } = renderInRoutes(<ArtifactDetailPage />, {
      path: '/w/:workspaceId/workarea/areas/:areaId/artifacts/:artifactId',
      initialEntries: ['/w/ws-1/workarea/areas/area-1/artifacts/art-1'],
    })

    await waitFor(() => {
      expect(screen.getByText('# Preisliste')).toBeInTheDocument()
    })

    expect(await axe(container)).toHaveNoViolations()
  })

  it('hat keine axe-Violations mit geoeffnetem Export-Menue', async () => {
    stubFetch([
      [
        '/wa-artifacts/art-1',
        {
          artifact_id: 'art-1',
          title: 'Preisliste 2026',
          rev: 2,
          markdown: '# Preisliste [#aaaaaaaa]\n\nDer Preis stieg um 8 %. [#bbbbbbbb]',
        },
      ],
      ['/work-areas/area-1/artifacts', [artifact()]],
    ])

    renderInRoutes(<ArtifactDetailPage />, {
      path: '/w/:workspaceId/workarea/areas/:areaId/artifacts/:artifactId',
      initialEntries: ['/w/ws-1/workarea/areas/area-1/artifacts/art-1'],
    })

    await waitFor(() => {
      expect(screen.getByTestId('export-artifact-trigger')).toBeInTheDocument()
    })
    // Radix oeffnet auf pointerdown+up; in JSDOM kommen wir per Enter ans Ziel.
    fireEvent.keyDown(screen.getByTestId('export-artifact-trigger'), { key: 'Enter' })
    await screen.findByTestId('export-artifact-markdown')

    // Radix rendert den Menue-Inhalt per Portal direkt unter <body>, ausserhalb
    // des von `render()` zurueckgegebenen Containers — deshalb hier gegen
    // `document.body` pruefen, sonst bleibt das offene Menue vom Scan
    // unbemerkt. Der Popper-Wrapper (position: fixed) landet dabei selbst
    // als Geschwister-Element von `<main>` unter `<body>` und loest einen
    // bekannten False-Positive der `region`-Regel aus (der Menue-Inhalt
    // selbst traegt bereits `role="menu"`, ist also kein "unverortetes"
    // Seiten-Content) — nur fuer diesen Check deaktiviert, nicht global
    // (Muster `color-contrast` in `src/test/a11y.ts`).
    expect(await axe(document.body, { rules: { region: { enabled: false } } })).toHaveNoViolations()
  })
})
