import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { InvoiceListItem } from '@/api/client'
import type { EntitlementInfo, Me } from '@/api/types'
import i18n from '@/i18n'
import { axe } from '@/test/a11y'
import { renderInRoutes } from '@/test/render'

import { BillingPanel } from './BillingPanel'

// Rechnungen im Web (ADR-0061 R3). Platzhalter-Nummern, keine echten Daten.

const cloudFree: EntitlementInfo = {
  edition: 'cloud',
  status: 'active',
  features: ['core'],
  expires_at: null,
  mcp_monthly_quota: 1000,
  mcp_rate_per_min: 30,
  token_quota: 3,
  storage_quota_bytes: 100 * 1024 * 1024,
  workspace_quota: 1,
  usage: { period: '202610', count: 0, storage_bytes: 0 },
}

function me(role: 'admin' | 'editor' | 'viewer'): Me {
  return {
    user_id: 'u1',
    default_workspace_id: 'ws-1',
    organizations: [
      {
        id: 'org-1',
        name: 'Beispiel',
        slug: 'beispiel',
        kind: 'company',
        workspaces: [{ id: 'ws-1', name: 'W', slug: 'w', role }],
      },
    ],
  }
}

const archived: InvoiceListItem = {
  id: '11111111-1111-4111-8111-111111111111',
  invoice_number: 'TEST-2026-00002',
  issued_at: '2026-10-01T09:00:00Z',
  amount_value: '11.89',
  currency: 'EUR',
  status: 'archived',
}

const issued: InvoiceListItem = {
  id: '22222222-2222-4222-8222-222222222222',
  invoice_number: 'TEST-2026-00003',
  issued_at: '2026-11-01T09:00:00Z',
  amount_value: '11.89',
  currency: 'EUR',
  status: 'issued',
}

interface FetchOptions {
  invoices?: InvoiceListItem[]
  listStatus?: number
  pdf?: () => Promise<Response>
}

function billingFetch({ invoices = [], listStatus = 200, pdf }: FetchOptions = {}) {
  return vi.fn().mockImplementation((url: string) => {
    const u = String(url)
    if (u.includes('/inbox/counts')) {
      return Promise.resolve(new Response('{"detail":"nope"}', { status: 500 }))
    }
    if (u.includes('/billing/profile')) {
      return Promise.resolve(
        new Response(JSON.stringify({ profile: null, countries: ['DE'], eu_countries: ['DE'] })),
      )
    }
    if (u.includes('/pdf')) {
      return pdf
        ? pdf()
        : Promise.resolve(new Response('%PDF-1.7', { status: 200 }))
    }
    if (u.includes('/billing/invoices')) {
      return Promise.resolve(
        listStatus === 200
          ? new Response(JSON.stringify({ invoices }))
          : new Response('{"detail":"Fehler beim Laden."}', { status: listStatus }),
      )
    }
    return Promise.resolve(new Response(JSON.stringify(cloudFree)))
  })
}

function calls(fetchMock: ReturnType<typeof vi.fn>, part: string) {
  return fetchMock.mock.calls.filter(([url]) => String(url).includes(part))
}

function renderPanel(role: 'admin' | 'editor' | 'viewer' = 'admin') {
  return renderInRoutes(<BillingPanel />, {
    path: '/w/:workspaceId/settings/billing',
    initialEntries: ['/w/ws-1/settings/billing'],
    me: me(role),
  })
}

async function invoiceCard() {
  const title = await screen.findByText('Rechnungen')
  const card = title.closest('[class*="rounded"]') as HTMLElement | null
  expect(card).not.toBeNull()
  return card!
}

beforeEach(() => {
  URL.createObjectURL = vi.fn(() => 'blob:mock')
  URL.revokeObjectURL = vi.fn()
})

afterEach(async () => {
  vi.unstubAllGlobals()
  await i18n.changeLanguage('de')
})

describe('Rechnungen im Billing-Bereich (R3)', () => {
  it('listet Nummer, Datum, Betrag und Status, Download nur bei archiviertem PDF', async () => {
    vi.stubGlobal('fetch', billingFetch({ invoices: [issued, archived] }))
    renderPanel()

    const list = await screen.findByRole('list', { name: 'Rechnungen der Organisation' })
    const items = within(list).getAllByRole('listitem')
    expect(items).toHaveLength(2)
    // Reihenfolge der API bleibt erhalten (Server sortiert, neueste zuerst).
    expect(items[0]).toHaveTextContent('TEST-2026-00003')
    expect(items[0]).toHaveTextContent('PDF wird vorbereitet')
    expect(within(items[0]).queryByRole('button')).not.toBeInTheDocument()

    expect(items[1]).toHaveTextContent('TEST-2026-00002')
    expect(items[1]).toHaveTextContent('1.10.2026')
    expect(items[1]).toHaveTextContent(/11,89\s€/)
    expect(items[1]).toHaveTextContent('PDF verfügbar')
    const button = within(items[1]).getByRole('button', {
      name: 'Rechnung TEST-2026-00002 als PDF herunterladen',
    })
    // 40px-Hit-Target wie der Upgrade-Knopf.
    expect(button.className.split(/\s+/)).toContain('h-10')
    expect(within(items[1]).getByText('1.10.2026').tagName).toBe('TIME')
  })

  it('zeigt den Leerzustand ohne Rechnungen', async () => {
    vi.stubGlobal('fetch', billingFetch({ invoices: [] }))
    renderPanel()

    expect(await screen.findByText('Noch keine Rechnungen')).toBeInTheDocument()
    expect(
      screen.getByText('Nach jeder Zahlung erscheint die Rechnung hier zum Herunterladen.'),
    ).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: 'Rechnungen der Organisation' })).toBeNull()
  })

  it('zeigt einen Ladefehler der Liste als Meldung', async () => {
    vi.stubGlobal('fetch', billingFetch({ listStatus: 500 }))
    renderPanel()

    const card = await invoiceCard()
    await waitFor(() => {
      expect(within(card).getByRole('alert')).toHaveTextContent('(500)')
    })
  })

  it.each(['editor', 'viewer'] as const)(
    'fragt fuer %s keine Rechnungen ab und zeigt keine Karte',
    async (role) => {
      const fetchMock = billingFetch({ invoices: [archived] })
      vi.stubGlobal('fetch', fetchMock)
      renderPanel(role)

      await screen.findByText('Plan & Nutzung')
      expect(screen.queryByText('Rechnungen')).not.toBeInTheDocument()
      expect(calls(fetchMock, '/billing/invoices')).toHaveLength(0)
    },
  )

  it('laedt das PDF ueber die API und speichert es unter der Rechnungsnummer', async () => {
    const fetchMock = billingFetch({ invoices: [archived] })
    vi.stubGlobal('fetch', fetchMock)
    const clicked: string[] = []
    const click = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(function (this: HTMLAnchorElement) {
        clicked.push(this.download)
      })
    renderPanel()

    fireEvent.click(
      await screen.findByRole('button', { name: 'Rechnung TEST-2026-00002 als PDF herunterladen' }),
    )
    await waitFor(() => expect(clicked).toEqual(['TEST-2026-00002.pdf']))
    const pdfCalls = calls(fetchMock, '/pdf')
    expect(pdfCalls).toHaveLength(1)
    expect(String(pdfCalls[0][0])).toContain(
      `/workspaces/ws-1/billing/invoices/${archived.id}/pdf`,
    )
    // Der Bearer-Token geht mit, sonst gaebe der Server 401.
    expect((pdfCalls[0][1] as RequestInit).headers).toHaveProperty('Authorization')
    click.mockRestore()
  })

  it('sperrt waehrend eines Downloads jeden weiteren Abruf (kein Doppel-Klick)', async () => {
    let release: (r: Response) => void = () => {}
    const fetchMock = billingFetch({
      invoices: [archived, { ...archived, id: '33333333-3333-4333-8333-333333333333', invoice_number: 'TEST-2026-00001' }],
      pdf: () =>
        new Promise<Response>((resolve) => {
          release = resolve
        }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    renderPanel()

    const first = await screen.findByRole('button', {
      name: 'Rechnung TEST-2026-00002 als PDF herunterladen',
    })
    fireEvent.click(first)
    fireEvent.click(first)
    await waitFor(() => expect(first).toBeDisabled())
    expect(first).toHaveTextContent('Lädt…')
    expect(
      screen.getByRole('button', { name: 'Rechnung TEST-2026-00001 als PDF herunterladen' }),
    ).toBeDisabled()
    expect(calls(fetchMock, '/pdf')).toHaveLength(1)

    release(new Response('%PDF-1.7', { status: 200 }))
    await waitFor(() => expect(first).not.toBeDisabled())
    expect(calls(fetchMock, '/pdf')).toHaveLength(1)
    click.mockRestore()
  })

  it('meldet einen fehlgeschlagenen Download und gibt den Knopf wieder frei', async () => {
    vi.stubGlobal(
      'fetch',
      billingFetch({
        invoices: [archived],
        pdf: () => Promise.resolve(new Response('{"detail":"Rechnung nicht gefunden."}', { status: 404 })),
      }),
    )
    renderPanel()

    const button = await screen.findByRole('button', {
      name: 'Rechnung TEST-2026-00002 als PDF herunterladen',
    })
    fireEvent.click(button)
    expect(await screen.findByText('Das PDF konnte nicht geladen werden.')).toBeInTheDocument()
    expect(button).not.toBeDisabled()
  })

  it('zeigt die Karte auf Englisch', async () => {
    await i18n.changeLanguage('en')
    vi.stubGlobal('fetch', billingFetch({ invoices: [issued, archived] }))
    renderPanel()

    expect(await screen.findByText('Invoices')).toBeInTheDocument()
    expect(screen.getByText('PDF in preparation')).toBeInTheDocument()
    expect(screen.getByText('PDF available')).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Download invoice TEST-2026-00002 as PDF' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('list', { name: 'Invoices of the organization' })).toHaveTextContent(
      /€11\.89/,
    )
  })

  it('zeigt den Leerzustand auf Englisch', async () => {
    await i18n.changeLanguage('en')
    vi.stubGlobal('fetch', billingFetch({ invoices: [] }))
    renderPanel()

    expect(await screen.findByText('No invoices yet')).toBeInTheDocument()
  })

  it('hat in Liste und Leerzustand keine axe-Verstoesse', async () => {
    vi.stubGlobal('fetch', billingFetch({ invoices: [issued, archived] }))
    const { unmount } = renderPanel()
    await screen.findByRole('list', { name: 'Rechnungen der Organisation' })
    expect(await axe(document.body)).toHaveNoViolations()
    unmount()

    vi.stubGlobal('fetch', billingFetch({ invoices: [] }))
    renderPanel()
    await screen.findByText('Noch keine Rechnungen')
    expect(await axe(document.body)).toHaveNoViolations()
  })
})
