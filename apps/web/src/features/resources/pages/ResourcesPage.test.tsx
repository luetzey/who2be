import { fireEvent, screen, waitFor, within } from '@testing-library/react'
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

// Responsive-Audit #564 (W3, Epic #431): jsdom hat kein Layout, geprueft wird
// deshalb der Klassen-Vertrag. Die Layout-Aussage selbst ist am gerenderten
// Baum belegt (Plandatei .claude/plan/2026-09-23-0130_564-…): der Slug-Badge
// misst dort bei 320px Viewport 554px und ist der einzige Ueberlaeufer der
// Liste. Muster: components/ui/dialog.test.tsx / features/tools (#562).
describe('ResourcesPage — Umbruch bei 320px (#564)', () => {
  const LONG_SLUG = 'kundenonboarding_wissensbasis_vertriebsteam_langbezeichner_q4'
  const LONG_TAG = 'produktivitaets-automatisierung-langer-tag-fuer-messung'

  function renderWithLongIdentifiers() {
    const entry = resource('r1', 'Onboarding', [LONG_TAG])
    return renderWith([{ ...entry, slug: LONG_SLUG }], ['/w/ws-1/resources'])
  }

  it('laesst den umbruchfeindlichen Slug mitten im Wort brechen', async () => {
    renderWithLongIdentifiers()

    const classes = (await screen.findByText(LONG_SLUG)).className.split(/\s+/)
    expect(classes).toContain('break-all')
    expect(classes).toContain('max-w-full')
  })

  it('laesst lange Tags an Wortgrenzen brechen', async () => {
    renderWithLongIdentifiers()

    // `findByText` allein traefe auch die <option> der Tag-Facette in der
    // ListFilterBar — gesucht ist der Badge in der Karte.
    await screen.findByText(LONG_SLUG)
    const badge = screen
      .getAllByText(LONG_TAG)
      .find((el) => el.tagName !== 'OPTION')
    const classes = (badge as HTMLElement).className.split(/\s+/)
    expect(classes).toContain('break-words')
    expect(classes).toContain('max-w-full')
  })
})

// Audit A13-Rest (Folge zu #777): Listen-Karten zeigen unter `md` drei Tags
// und „+n“; der Knopf klappt im Fluss auf (W3=a), ab `md` stehen alle Tags
// da. jsdom hat kein Layout — geprueft wird die Verdrahtung mit TagList.
describe('ResourcesPage — Tags „+n“ in der Listen-Karte (A13)', () => {
  it('zeigt drei Tags und „+2“, Klick klappt in der Karte auf', async () => {
    renderWith([resource('r1', 'Onboarding', ['t1', 't2', 't3', 't4', 't5'])], [
      '/w/ws-1/resources',
    ])

    // renderInRoutes bringt die AppLayout-Navigation mit (eigene <li>) —
    // die Karte ist das <article> um den Titel-Link.
    const link = await screen.findByRole('link', { name: 'Onboarding' })
    const card = within(link.closest('article') as HTMLElement)
    const more = card.getByRole('button', { name: '2 weitere anzeigen' })
    const rest = card.getByTestId('tag-list-rest')
    expect(more).toHaveTextContent('+2')
    expect(rest).toHaveClass('hidden', 'md:contents')
    expect(rest).toHaveTextContent('t4t5')
    expect(rest).not.toHaveTextContent('t1')

    fireEvent.click(more)
    expect(more).toHaveAttribute('aria-expanded', 'true')
    expect(rest).not.toHaveClass('hidden')
    // Kein Seitenwechsel: die Karte steht noch da.
    expect(card.getByRole('link', { name: 'Onboarding' })).toBeInTheDocument()
  })
})
